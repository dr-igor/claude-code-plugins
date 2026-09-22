#!/usr/bin/env python3

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import tokenize
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal, NamedTuple

BUDGET_NAME = "expository-content-budget.json"
BANNER = "READ-THIS-FIRST"
EXCLUDE = "EXCLUDE"
RESERVED_KEYS = frozenset({BANNER, EXCLUDE})
BANNER_TEXT = (
    "A per-file ceiling on comment blocks, block comments and docstrings. Claude Code "
    "cannot edit this file and nothing it runs will raise a number here; only you can. "
    "If a hook is refusing an edit, the fix is to remove the prose - express it in the "
    "code, in a decision record, or in the commit message - unless you judge the comment "
    "has earned its place, in which case raise its number here by hand. Files you never "
    "want counted go in EXCLUDE as gitignore-style patterns - vendor/, src/generated/**, "
    "*.pb.go - and their entries disappear from this file."
)
MAX_SCANNED_BYTES = 2_000_000

Kind = Literal["line", "trailing", "block", "docstring"]


class Span(NamedTuple):
    first_line: int
    last_line: int
    kind: Kind


def counts_for_tree(root: Path, excludes: Iterable[str]) -> dict[str, int]:
    rules = exclude_rules(excludes)
    included = (name for name in working_tree_files(root) if not is_excluded(name, rules))
    counted = ((name, count_in(root, name)) for name in included)
    return {name: count for name, count in counted if count}


def working_tree_files(root: Path) -> list[str]:
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return sorted({line for line in listing.stdout.splitlines() if line})


class ExcludeRule(NamedTuple):
    pattern: re.Pattern[str]
    is_directory_only: bool


GLOB_TOKEN = re.compile(r"\*\*/|\*\*|[*?]|\[[^]]*\]|[^*?\[]+|.")
GLOB_REPLACEMENTS = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*", "?": "[^/]"}
CATCH_ALL_PROBES = ("a", "a/b/c")


def exclude_rules(patterns: Iterable[str]) -> tuple[ExcludeRule, ...]:
    compiled = (exclude_rule(pattern) for pattern in patterns)
    return tuple(rule for rule in compiled if rule is not None)


def exclude_rule(raw: str) -> ExcludeRule | None:
    cleaned = raw.strip().removeprefix("./")
    body = cleaned.strip("/")
    if not body:
        return None
    prefix = "" if cleaned.startswith("/") or "/" in body else "(?:.*/)?"
    source = prefix + "".join(glob_piece(token) for token in GLOB_TOKEN.findall(body))
    try:
        pattern = re.compile(source)
    except re.error:
        return None
    if all(pattern.fullmatch(probe) for probe in CATCH_ALL_PROBES):
        return None
    return ExcludeRule(pattern, cleaned.endswith("/"))


def glob_piece(token: str) -> str:
    if token in GLOB_REPLACEMENTS:
        return GLOB_REPLACEMENTS[token]
    if len(token) > 2 and token.startswith("[") and token.endswith("]"):
        return character_class(token[1:-1])
    return re.escape(token)


def character_class(body: str) -> str:
    escaped = body.replace("\\", "\\\\")
    return f"[^{escaped[1:]}]" if escaped[0] in "!^" else f"[{escaped}]"


def ancestor_paths(name: str) -> tuple[str, ...]:
    parts = name.split("/")[:-1]
    return tuple("/".join(parts[: depth + 1]) for depth in range(len(parts)))


def is_excluded(name: str, rules: tuple[ExcludeRule, ...]) -> bool:
    if not rules:
        return False
    directories = ancestor_paths(name)
    candidates = (*directories, name)
    return any(
        rule.pattern.fullmatch(candidate)
        for rule in rules
        for candidate in (directories if rule.is_directory_only else candidates)
    )


def count_in(root: Path, relative: str) -> int | None:
    dialect = dialect_of(relative)
    if dialect is None:
        return None
    absolute = root / relative
    try:
        if absolute.stat().st_size > MAX_SCANNED_BYTES:
            return None
        source = absolute.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return len(blocks(prose_spans(source, dialect)))


def prose_spans(source: str, dialect: str) -> list[Span]:
    lines = source.splitlines()
    metadata_lines = script_metadata_lines(source) if dialect == PYTHON else frozenset()
    return [
        span
        for span in spans_for(source, dialect)
        if not machine_span(span, lines, metadata_lines)
    ]


def machine_span(span: Span, lines: list[str], metadata_lines: frozenset[int]) -> bool:
    if span.kind == "docstring":
        return False
    if span.first_line == span.last_line and span.first_line in metadata_lines:
        return True
    opening = lines[span.first_line - 1] if span.first_line <= len(lines) else ""
    if not shebang(opening) and not MACHINE_DIRECTIVE.search(opening):
        return False
    return all(
        directive_continuation(lines[number - 1])
        for number in range(span.first_line + 1, min(span.last_line, len(lines)) + 1)
    )


SHEBANG = re.compile(r"#!\s*/\S+(?:\s+\S+){0,8}")


def shebang(line: str) -> bool:
    return SHEBANG.fullmatch(line.strip()) is not None


class DirectiveFamily(NamedTuple):
    name: str
    body: str


DIRECTIVE_FAMILIES = (
    DirectiveFamily("build_constraints", r"go:|\+build"),
    DirectiveFamily(
        "linters",
        r"nolint|lint:|noqa|pylint:|ruff:|mypy:|pyright:|isort:|shellcheck|nosec"
        r"|yamllint\s+disable|tflint-ignore:",
    ),
    DirectiveFamily("suppressions", r"type:\s*ignore|pragma:"),
    DirectiveFamily(
        "formatters", r"prettier|fmt:\s*(?:on|off|skip)|yapf:\s*(?:disable|enable)"
    ),
    DirectiveFamily("sorters", r"keep-sorted\s+(?:start|end)"),
    DirectiveFamily("javascript_tooling", r"eslint|biome|@ts-|istanbul|c8\s+ignore"),
    DirectiveFamily(
        "typescript_references", r"/\s*<(?:reference|amd-module|amd-dependency)\b"
    ),
    DirectiveFamily("source_maps", r"#\s*sourceMappingURL=\S"),
    DirectiveFamily("spellers", r"cspell:|codespell:"),
    DirectiveFamily("editors", r"noinspection\s+\w"),
    DirectiveFamily("licences", r"SPDX-[A-Za-z-]+:"),
    DirectiveFamily("encodings", r"coding[:=]"),
    DirectiveFamily("container_parsers", r"(?:syntax|escape)=\S"),
    DirectiveFamily("notebook_cells", r"%%\s*$"),
)

MACHINE_DIRECTIVE = re.compile(
    r"(?:#|//|--|/\*)\s*(?:"
    + "|".join(family.body for family in DIRECTIVE_FAMILIES)
    + r")",
    re.IGNORECASE,
)

DIRECTIVE_CONTINUATION = re.compile(r"\*?\s*\S*?,?\s*(?:\*/)?")


def directive_continuation(line: str) -> bool:
    return DIRECTIVE_CONTINUATION.fullmatch(line.strip()) is not None


SCRIPT_METADATA_MARKER = "# ///"
SCRIPT_METADATA_OPEN = "# /// script"
SCRIPT_METADATA_MAX_LINES = 50
SCRIPT_METADATA_KEYS = frozenset({"requires-python", "dependencies", "tool"})


def script_metadata_lines(source: str) -> frozenset[int]:
    if SCRIPT_METADATA_MARKER not in source:
        return frozenset()
    lines = source.splitlines()
    region = script_metadata_region(lines)
    if region is None:
        return frozenset()
    opener, closer = region
    body = script_metadata_body(lines[opener : closer - 1])
    if body is None or not script_metadata_toml(body):
        return frozenset()
    return frozenset(range(opener, closer + 1))


def script_metadata_region(lines: list[str]) -> tuple[int, int] | None:
    prelude = comment_prelude_length(lines)
    opener = next(
        (
            number
            for number in range(1, prelude + 1)
            if lines[number - 1].strip() == SCRIPT_METADATA_OPEN
        ),
        None,
    )
    if opener is None:
        return None
    last_allowed = min(opener + SCRIPT_METADATA_MAX_LINES, len(lines))
    closer = next(
        (
            number
            for number in range(opener + 1, last_allowed + 1)
            if lines[number - 1].strip() == SCRIPT_METADATA_MARKER
        ),
        None,
    )
    return None if closer is None else (opener, closer)


def comment_prelude_length(lines: list[str]) -> int:
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return number - 1
    return len(lines)


def script_metadata_body(lines: list[str]) -> str | None:
    stripped = [line.strip() for line in lines]
    if any(
        line != "#" and (not line.startswith("# ") or line.startswith("# #"))
        for line in stripped
    ):
        return None
    return "\n".join(line[2:] for line in stripped)


def script_metadata_toml(body: str) -> bool:
    try:
        import tomllib

        return set(tomllib.loads(body)) <= SCRIPT_METADATA_KEYS
    except (ImportError, ValueError):
        return False


CSTYLE, RUST, PYTHON = "cstyle", "rust", "python"

DIALECTS: dict[str, str] = {
    ".py": PYTHON,
    ".pyi": PYTHON,
    ".rs": RUST,
    ".ts": CSTYLE,
    ".tsx": CSTYLE,
    ".mts": CSTYLE,
    ".cts": CSTYLE,
    ".js": CSTYLE,
    ".jsx": CSTYLE,
    ".mjs": CSTYLE,
    ".cjs": CSTYLE,
    ".svelte": CSTYLE,
    ".vue": CSTYLE,
    ".c": CSTYLE,
    ".h": CSTYLE,
    ".cc": CSTYLE,
    ".hh": CSTYLE,
    ".cpp": CSTYLE,
    ".hpp": CSTYLE,
    ".cxx": CSTYLE,
    ".hxx": CSTYLE,
    ".m": CSTYLE,
    ".mm": CSTYLE,
    ".cs": CSTYLE,
    ".java": CSTYLE,
    ".kt": CSTYLE,
    ".kts": CSTYLE,
    ".scala": CSTYLE,
    ".go": CSTYLE,
    ".swift": CSTYLE,
    ".dart": CSTYLE,
    ".php": CSTYLE,
    ".groovy": CSTYLE,
    ".gradle": CSTYLE,
    ".proto": CSTYLE,
    ".css": CSTYLE,
    ".scss": CSTYLE,
    ".less": CSTYLE,
    ".glsl": CSTYLE,
    ".vert": CSTYLE,
    ".frag": CSTYLE,
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".fish": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".rb": "ruby",
    ".pl": "ruby",
    ".pm": "ruby",
    ".r": "ruby",
    ".R": "ruby",
    ".jl": "ruby",
    ".ex": "ruby",
    ".exs": "ruby",
    ".tf": "ruby",
    ".tfvars": "ruby",
    ".sql": "sql",
    ".lua": "sql",
    ".hs": "sql",
    ".elm": "sql",
    "justfile": "shell",
    "Justfile": "shell",
    "Makefile": "shell",
    "makefile": "shell",
    "GNUmakefile": "shell",
    "Dockerfile": "shell",
    "Containerfile": "shell",
}


def dialect_of(relative: str) -> str | None:
    path = Path(relative)
    return DIALECTS.get(path.name) or DIALECTS.get(path.suffix)


def spans_for(source: str, dialect: str) -> list[Span]:
    if dialect == PYTHON:
        return python_spans(source)
    if dialect in (CSTYLE, RUST):
        return _CStyleScanner(source, single_quotes_open_strings=dialect == CSTYLE).run()
    return marker_spans(source, dialect)


def python_spans(source: str) -> list[Span]:
    return list(_python_comment_spans(source)) + list(_python_docstring_spans(source))


def _python_comment_spans(source: str) -> Iterator[Span]:
    lines = source.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        row, column = token.start
        head = lines[row - 1][:column] if row <= len(lines) else ""
        yield Span(row, token.end[0], "line" if not head.strip() else "trailing")


_DOCSTRING_HOLDERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _python_docstring_spans(source: str) -> Iterator[Span]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_HOLDERS) or ast.get_docstring(node) is None:
            continue
        opener = node.body[0]
        yield Span(opener.lineno, opener.end_lineno or opener.lineno, "docstring")


_SLASH_OPENS_REGEX_AFTER = frozenset("(,=:[!&|?{};+-*%~^<>")
_SLASH_OPENS_REGEX_AFTER_KEYWORD = frozenset(
    {
        "return", "typeof", "instanceof", "in", "of", "case", "do",
        "else", "yield", "await", "delete", "void", "new", "throw",
    }
)
_TRAILING_WORD = re.compile(r"[A-Za-z_$][\w$]*$")


class _CStyleScanner:
    def __init__(self, source: str, *, single_quotes_open_strings: bool) -> None:
        self.source = source
        self.quotes = "\"'`" if single_quotes_open_strings else '"`'
        self.pos = 0
        self.line = 1
        self.spans: list[Span] = []
        self.last_code_char = ""

    def run(self) -> list[Span]:
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == "\n":
                self.line += 1
                self.pos += 1
            elif char in self.quotes:
                self._skip_string(char)
            elif char == "/":
                self._at_slash()
            else:
                if not char.isspace():
                    self.last_code_char = char
                self.pos += 1
        return self.spans

    def _at_slash(self) -> None:
        following = self.source[self.pos + 1 : self.pos + 2]
        if following == "/":
            self._take_line_comment()
        elif following == "*":
            self._take_block_comment()
        elif self._regex_follows():
            self._skip_regex()
        else:
            self.last_code_char = "/"
            self.pos += 1

    def _take_line_comment(self) -> None:
        kind: Kind = "line" if self._nothing_before_on_line() else "trailing"
        self.spans.append(Span(self.line, self.line, kind))
        end = self.source.find("\n", self.pos)
        self.pos = len(self.source) if end == -1 else end

    def _take_block_comment(self) -> None:
        kind: Kind = "block" if self._nothing_before_on_line() else "trailing"
        closing = self.source.find("*/", self.pos + 2)
        end = len(self.source) if closing == -1 else closing + 2
        spanned = self.source.count("\n", self.pos, end)
        self.spans.append(Span(self.line, self.line + spanned, kind))
        self.line += spanned
        self.pos = end

    def _skip_string(self, quote: str) -> None:
        self.pos += 1
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == "\\":
                self.line += self.source.count("\n", self.pos, self.pos + 2)
                self.pos += 2
                continue
            if char == quote:
                self.pos += 1
                break
            if char == "\n":
                self.line += 1
                if not _spans_newlines(quote):
                    self.pos += 1
                    break
            self.pos += 1
        self.last_code_char = quote

    def _skip_regex(self) -> None:
        self.pos += 1
        in_character_class = False
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "\n":
                break
            if char == "[":
                in_character_class = True
            elif char == "]":
                in_character_class = False
            elif char == "/" and not in_character_class:
                self.pos += 1
                break
            self.pos += 1
        self.last_code_char = "/"

    def _regex_follows(self) -> bool:
        if not self.last_code_char or self.last_code_char in _SLASH_OPENS_REGEX_AFTER:
            return True
        word = _TRAILING_WORD.search(self.source[: self.pos].rstrip())
        return word is not None and word.group() in _SLASH_OPENS_REGEX_AFTER_KEYWORD

    def _nothing_before_on_line(self) -> bool:
        start = self.source.rfind("\n", 0, self.pos) + 1
        return not self.source[start : self.pos].strip()


def _spans_newlines(quote: str) -> bool:
    return quote == "`"


MARKERS = {"shell": "#", "yaml": "#", "toml": "#", "ruby": "#", "sql": "--"}
MARKER_NEEDS_LEADING_SPACE = frozenset({"shell", "yaml"})
_BLOCK_SCALAR = re.compile(r"[|>][+-]?\d*\s*$")


def marker_spans(source: str, dialect: str) -> list[Span]:
    marker = MARKERS[dialect]
    lines = source.splitlines()
    spans: list[Span] = []
    number = 1
    while number <= len(lines):
        line = lines[number - 1]
        multiline_string_end = _multiline_string_end(lines, number, dialect)
        if multiline_string_end is not None:
            number = multiline_string_end + 1
            continue
        column = _marker_column(
            line, marker, needs_space=dialect in MARKER_NEEDS_LEADING_SPACE
        )
        if column is not None:
            kind: Kind = "line" if not line[:column].strip() else "trailing"
            spans.append(Span(number, number, kind))
        number += 1
    return spans


def _multiline_string_end(lines: list[str], number: int, dialect: str) -> int | None:
    if dialect == "yaml":
        return _block_scalar_end(lines, number)
    if dialect == "toml":
        return _triple_quote_end(lines, number)
    return None


def _block_scalar_end(lines: list[str], number: int) -> int | None:
    line = lines[number - 1]
    if not line.strip() or not _BLOCK_SCALAR.search(line.split(" #")[0]):
        return None
    indent = len(line) - len(line.lstrip())
    last = number
    for probe in range(number + 1, len(lines) + 1):
        candidate = lines[probe - 1]
        if candidate.strip() and (len(candidate) - len(candidate.lstrip())) <= indent:
            break
        last = probe
    return last


def _triple_quote_end(lines: list[str], number: int) -> int | None:
    line = lines[number - 1]
    for quote in ('"""', "'''"):
        if line.count(quote) % 2 == 0:
            continue
        for probe in range(number + 1, len(lines) + 1):
            if quote in lines[probe - 1]:
                return probe
        return len(lines)
    return None


def _marker_column(line: str, marker: str, *, needs_space: bool) -> int | None:
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif line.startswith(marker, index) and (
            not needs_space or index == 0 or line[index - 1].isspace()
        ):
            return index
        index += 1
    return None


def blocks(spans: Iterable[Span]) -> list[Span]:
    merged: list[Span] = []
    for span in sorted(spans):
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.kind == "line"
            and span.kind == "line"
            and span.first_line == previous.last_line + 1
        ):
            merged[-1] = Span(previous.first_line, span.last_line, "line")
        else:
            merged.append(span)
    return merged


def repo_root(start: Path) -> Path | None:
    try:
        found = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(found.stdout.strip()) if found.stdout.strip() else None


class Budget(NamedTuple):
    ceilings: dict[str, int]
    excludes: tuple[str, ...]


def load_budget(path: Path) -> Budget | None:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(spec, dict):
        return None
    return Budget(ceilings_in(spec), excludes_in(spec))


def ceilings_in(spec: dict[str, object]) -> dict[str, int]:
    return {
        name: int(allowed)
        for name, allowed in spec.items()
        if name not in RESERVED_KEYS and isinstance(allowed, (int, float))
    }


def excludes_in(spec: dict[str, object]) -> tuple[str, ...]:
    listed = spec.get(EXCLUDE)
    if not isinstance(listed, list):
        return ()
    return tuple(entry for entry in listed if isinstance(entry, str))


def excludes_of(budget: Budget | None) -> tuple[str, ...]:
    return budget.excludes if budget is not None else ()


def write_budget(path: Path, budget: Budget) -> None:
    spec = {
        BANNER: BANNER_TEXT,
        EXCLUDE: list(budget.excludes),
        **{name: budget.ceilings[name] for name in sorted(budget.ceilings)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


def overruns(counts: dict[str, int], ceilings: dict[str, int]) -> dict[str, int]:
    return {
        name: count
        for name, count in sorted(counts.items())
        if count > ceilings.get(name, 0)
    }


def main() -> None:
    root = repo_root(Path.cwd())
    if root is None:
        print("not a git worktree")
        return
    recorded = load_budget(root / ".claude" / BUDGET_NAME)
    counts = counts_for_tree(root, excludes_of(recorded))
    ceilings = recorded.ceilings if recorded is not None else {}
    for name, count in sorted(counts.items(), key=lambda item: -item[1]):
        allowed = ceilings.get(name, 0)
        mark = "OVER" if count > allowed else "    "
        print(f"{mark} {count:5} / {allowed:<5} {name}")
    over = overruns(counts, ceilings)
    print(f"{sum(counts.values())} blocks in {len(counts)} files, {len(over)} over budget")


if __name__ == "__main__":
    main()
