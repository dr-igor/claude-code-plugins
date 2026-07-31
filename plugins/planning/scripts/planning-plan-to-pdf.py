#!/usr/bin/env python3
"""PreToolUse(ExitPlanMode) hook: render the plan Markdown to PDF.

The plan file goes through ``pandoc`` with ``pandoc-plantuml`` as a filter, so every
```plantuml fenced block becomes a rendered diagram. A failure the plan's author can
fix — a PlantUML syntax error, or a document the PDF engine rejects — exits 2 with the
diagnostics on stderr, which blocks ExitPlanMode and hands the errors back to the agent.
A failure the author cannot fix — a missing pandoc, filter, PlantUML or PDF engine —
exits 0 with a systemMessage naming the install command, because blocking there would
trap the session in a retry loop it can never escape.

Also runnable standalone for testing::

    planning-plan-to-pdf.py <plan.md> [-o <out.pdf>]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

PREFIX = "cc-plugins-igorlabworks/planning"

DISABLE_ENV = "PLANNING_PDF_DISABLE"
OUTPUT_DIR_ENV = "PLANNING_PDF_OUTPUT_DIR"
PANDOC_ENV = "PLANNING_PANDOC_BIN"
FILTER_ENV = "PLANNING_PLANTUML_FILTER"
ENGINE_ENV = "PLANNING_PDF_ENGINE"
PLANTUML_ENV = "PLANTUML_BIN"

PDF_ENGINE_CANDIDATES = ("typst", "xelatex", "lualatex", "pdflatex", "weasyprint", "wkhtmltopdf")
LATEX_ENGINES = frozenset({"xelatex", "lualatex", "pdflatex", "tectonic", "latexmk"})

# -failfast2 is load-bearing: without it PlantUML draws the syntax error into the image
# and exits 0, so a broken diagram would sail through into the PDF unnoticed.
PLANTUML_FLAGS = ("-failfast2", "-Sdpi=200")


class ToolchainMissing(Exception):
    def __init__(self, tool: str, install_hint: str) -> None:
        super().__init__(f"{tool} not found ({install_hint})")


class RenderFailed(Exception):
    def __init__(self, report: str) -> None:
        super().__init__(report)
        self.report = report


@dataclass(frozen=True)
class Toolchain:
    pandoc: str
    plantuml_filter: str
    plantuml_command: str
    pdf_engine: str


def main() -> None:
    if os.environ.get(DISABLE_ENV):
        return
    if len(sys.argv) > 1:
        render_from_cli(sys.argv[1:])
        return
    render_from_hook()


def render_from_hook() -> None:
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input") or {}
        cwd = payload.get("cwd") or os.getcwd()
        with temporary_workspace() as workspace:
            source = resolve_source(tool_input, cwd=cwd, workspace=workspace)
            if source is None:
                return
            destination = resolve_destination(source, cwd=cwd, workspace=workspace)
            render(source, destination, workspace=workspace)
            print(json.dumps({"systemMessage": f"{PREFIX}: plan PDF written to {destination}"}))
    except ToolchainMissing as missing:
        print(json.dumps({"systemMessage": f"{PREFIX}: plan PDF skipped, {missing}"}))
    except RenderFailed as failure:
        sys.stderr.write(failure.report)
        sys.exit(2)
    except Exception:
        return


def render_from_cli(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(description="Render a plan Markdown file to PDF.")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    arguments = parser.parse_args(argv)

    source = arguments.source.expanduser().resolve()
    destination = (arguments.output or source.with_suffix(".pdf")).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temporary_workspace() as workspace:
            render(source, destination, workspace=workspace)
    except ToolchainMissing as missing:
        sys.stderr.write(f"{PREFIX}: plan PDF skipped, {missing}\n")
        return
    except RenderFailed as failure:
        sys.stderr.write(failure.report)
        sys.exit(2)
    print(destination)


@contextmanager
def temporary_workspace() -> Iterator[Path]:
    workspace = Path(tempfile.mkdtemp(prefix="planning-plan-pdf-"))
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def resolve_source(tool_input: dict, *, cwd: str, workspace: Path) -> Path | None:
    plan_file = tool_input.get("planFilePath")
    if plan_file:
        candidate = Path(plan_file)
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        if candidate.is_file():
            return candidate.resolve()

    plan_text = tool_input.get("plan")
    if not plan_text:
        return None
    fallback = workspace / "plan.md"
    fallback.write_text(plan_text, encoding="utf-8")
    return fallback


def resolve_destination(source: Path, *, cwd: str, workspace: Path) -> Path:
    override = os.environ.get(OUTPUT_DIR_ENV)
    if override:
        directory = Path(override).expanduser()
    elif workspace in source.parents:
        directory = Path(cwd) / ".claude" / "plans-local"
    else:
        directory = source.parent
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{source.stem}.pdf"


def render(source: Path, destination: Path, *, workspace: Path) -> None:
    toolchain = resolve_toolchain()
    result = run_pandoc(toolchain, source, destination, workspace=workspace)
    if result.returncode != 0 and "failfast" in result.stderr:
        result = run_pandoc(toolchain, source, destination, workspace=workspace, plantuml_flags=())
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        raise RenderFailed(build_report(source, result.stderr))


def resolve_toolchain() -> Toolchain:
    return Toolchain(
        pandoc=require(PANDOC_ENV, "pandoc", "brew install pandoc"),
        plantuml_filter=require(
            FILTER_ENV, "pandoc-plantuml", "uv tool install pandoc-plantuml-filter"
        ),
        plantuml_command=resolve_plantuml(),
        pdf_engine=resolve_pdf_engine(),
    )


def require(env_name: str, executable: str, install_hint: str) -> str:
    override = os.environ.get(env_name)
    located = locate(override) if override else shutil.which(executable)
    if not located:
        raise ToolchainMissing(override or executable, install_hint)
    return located


def locate(name: str) -> str | None:
    candidate = Path(name).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return shutil.which(name)


def resolve_plantuml() -> str:
    configured = os.environ.get(PLANTUML_ENV, "").strip()
    if not configured:
        return require("", "plantuml", "brew install plantuml")
    if not locate(configured.split()[0]):
        raise ToolchainMissing(configured.split()[0], f"named by {PLANTUML_ENV}")
    return configured


def resolve_pdf_engine() -> str:
    override = os.environ.get(ENGINE_ENV)
    if override:
        if not locate(override):
            raise ToolchainMissing(override, f"named by {ENGINE_ENV}")
        return override
    for candidate in PDF_ENGINE_CANDIDATES:
        if shutil.which(candidate):
            return candidate
    raise ToolchainMissing("a PDF engine", "brew install typst")


def run_pandoc(
    toolchain: Toolchain,
    source: Path,
    destination: Path,
    *,
    workspace: Path,
    plantuml_flags: Sequence[str] = PLANTUML_FLAGS,
) -> subprocess.CompletedProcess[str]:
    command = [
        toolchain.pandoc,
        str(source),
        "-o",
        str(destination),
        "--filter",
        toolchain.plantuml_filter,
        "--pdf-engine",
        toolchain.pdf_engine,
        "--toc",
        "--number-sections",
        "--resource-path",
        os.pathsep.join([str(workspace), str(source.parent)]),
    ]
    if Path(toolchain.pdf_engine).name in LATEX_ENGINES:
        command += ["-V", "geometry:margin=1in"]

    # The filter writes its images to plantuml-images/ relative to the process cwd, so
    # pandoc runs inside the workspace and the whole directory is discarded afterwards.
    environment = {
        **os.environ,
        PLANTUML_ENV: " ".join([toolchain.plantuml_command, *plantuml_flags]),
    }
    return subprocess.run(
        command, cwd=workspace, env=environment, capture_output=True, text=True, check=False
    )


def build_report(source: Path, stderr: str) -> str:
    return (
        f"{PREFIX}: could not render {source} to PDF.\n\n"
        "Fix the plan file, then call ExitPlanMode again. If the error below comes from "
        "PlantUML it is a syntax error inside one of the ```plantuml fenced blocks, and "
        "PlantUML names the offending line. If the same diagram fails twice, simplify or "
        f"remove it rather than retrying. Set {DISABLE_ENV}=1 to skip PDF rendering "
        "entirely.\n\n"
        f"{stderr.strip()}\n"
    )


if __name__ == "__main__":
    main()
