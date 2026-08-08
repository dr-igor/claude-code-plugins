#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from expository_scan import (
    BUDGET_NAME,
    counts_for_tree,
    load_budget,
    overruns,
    repo_root,
    write_budget,
)

ABSORBING_SOURCES = frozenset({"startup", "resume", "clear"})


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    try:
        report(event)
    except (OSError, ValueError, subprocess.SubprocessError):
        return


def report(event: dict[str, object]) -> None:
    project = project_dir(event)
    root = repo_root(project)
    if root is None:
        return
    budget_path = project / ".claude" / BUDGET_NAME
    counts = counts_for_tree(root)
    recorded = load_budget(budget_path)
    ceilings = next_ceilings(counts, recorded, source=str(event.get("source") or ""))
    if ceilings != recorded:
        write_budget(budget_path, ceilings)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": briefing(counts, ceilings, budget_path),
                }
            }
        )
    )


def project_dir(event: dict[str, object]) -> Path:
    override = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(override) if override else Path(str(event.get("cwd") or Path.cwd()))


def next_ceilings(
    counts: dict[str, int], recorded: dict[str, int] | None, *, source: str
) -> dict[str, int]:
    if recorded is None or source in ABSORBING_SOURCES:
        return counts
    return {
        name: min(allowed, counts[name])
        for name, allowed in recorded.items()
        if name in counts
    }


def briefing(
    counts: dict[str, int], ceilings: dict[str, int], budget_path: Path
) -> str:
    over = overruns(counts, ceilings)
    lines = [
        (
            f"Expository-content budget active: {sum(ceilings.values())} comment, "
            f"block-comment and docstring blocks are budgeted across {len(ceilings)} "
            f"files."
        ),
        (
            "Every code file has a ceiling. A file with no entry has a ceiling of zero, "
            "so a file you create may carry no comments and no docstrings at all."
        ),
        (
            "When a comment is refused, express it in the code, in a decision record, or "
            "in the commit message instead. If you genuinely feel that a comment is "
            "needed, include this the recommended comment in your response to the user."
        ),
    ]
    if over:
        listed = ", ".join(
            f"{name} ({count}/{ceilings.get(name, 0)})" for name, count in over.items()
        )
        lines.append(f"Already over budget, edited outside this session: {listed}.")
    return " ".join(lines)


if __name__ == "__main__":
    main()
