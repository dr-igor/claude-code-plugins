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
BANNER_TEXT = (
    "A per-file ceiling on comment blocks, block comments and docstrings. Claude Code "
    "cannot edit this file and nothing it runs will raise a number here; only you can. "
    "If a hook is refusing an edit, the fix is to remove the prose - express it in the "
    "code, in a decision record, or in the commit message - unless you judge the comment "
    "has earned its place, in which case raise its number here by hand."
)
MAX_SCANNED_BYTES = 2_000_000

Kind = Literal["line", "trailing", "block", "docstring"]


class Span(NamedTuple):
    first_line: int
    last_line: int
    kind: Kind


def counts_for_tree(root: Path) -> dict[str, int]:
    counted = ((name, count_in(root, name)) for name in working_tree_files(root))
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
    return [
        span for span in spans_for(source, dialect) if not machine_directive(span, lines)
    ]


MACHINE_DIRECTIVE = re.compile(
    r"(?:#|//|--|/\*)\s*(?:go:|nolint|lint:|\+build|eslint|prettier|@ts-|biome|istanbul"
    r"|noqa|type:\s*ignore|pragma:|fmt:\s*(?:on|off)|pylint:|ruff:|mypy:|isort:"
    r"|shellcheck|coding[:=])",
    re.IGNORECASE,
)


def machine_directive(span: Span, lines: list[str]) -> bool:
    if span.first_line != span.last_line or span.first_line > len(lines):
        return False
    line = lines[span.first_line - 1]
    if span.first_line == 1 and line.startswith("#!"):
        return True
    return MACHINE_DIRECTIVE.search(line) is not None


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


def load_budget(path: Path) -> dict[str, int] | None:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(spec, dict):
        return None
    return {
        name: int(allowed)
        for name, allowed in spec.items()
        if name != BANNER and isinstance(allowed, (int, float))
    }


def write_budget(path: Path, ceilings: dict[str, int]) -> None:
    spec = {BANNER: BANNER_TEXT, **{name: ceilings[name] for name in sorted(ceilings)}}
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
    counts = counts_for_tree(root)
    ceilings = load_budget(root / ".claude" / BUDGET_NAME) or {}
    for name, count in sorted(counts.items(), key=lambda item: -item[1]):
        allowed = ceilings.get(name, 0)
        mark = "OVER" if count > allowed else "    "
        print(f"{mark} {count:5} / {allowed:<5} {name}")
    over = overruns(counts, ceilings)
    print(f"{sum(counts.values())} blocks in {len(counts)} files, {len(over)} over budget")


if __name__ == "__main__":
    main()
