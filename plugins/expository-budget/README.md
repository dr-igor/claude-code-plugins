# expository-budget

A per-file ceiling on comments, block comments and docstrings, enforced on every edit. The
ceiling only ever falls: removing prose lowers it, and nothing Claude Code can do raises it.

The problem it solves is not carelessness. Reasoning is freshest at the moment the code is
written and a comment is the lowest-friction place to put it; a comment reads as *free*
because it changes no behaviour, so nothing pushes back; and relocating prose from a deleted
site into a new docstring feels like progress when it is the same sentence at a new address.
None of that is fixed by intending to do better, so this makes it a check.

Adapted from the comment budget built for the `visABle` repository, where a refactor
commissioned to remove 2,236 comment blocks added 223 comment lines in its first three stages.

## The budget file

`.claude/expository-content-budget.json` in the project, one entry per file:

```json
{
  "READ-THIS-FIRST": "A per-file ceiling on comment blocks, block comments and docstrings...",
  "src/parser.py": 4,
  "src/render.ts": 1
}
```

It lives in `.claude/` so it is yours to edit. Claude Code cannot touch it: a `PreToolUse`
hook denies `Edit`, `Write`, `MultiEdit` and `NotebookEdit` against it, and denies any `Bash`
command that so much as names it. **Raising a number is a hand edit by a person.** That is the
whole design — the only path from "I want to keep this comment" to a green check runs through
you.

A file with no entry has a ceiling of zero, so a newly created file arrives with no budget to
spend and may carry no comments or docstrings at all.

## The three hooks

**`SessionStart` records the budget.** It scans the working tree — everything git tracks plus
everything untracked and not ignored — and writes what each file currently holds. On the first
run every file is recorded as-is, so an existing codebase starts green.

On later sessions it re-records from the tree on `startup`, `resume` and `clear`, absorbing
whatever changed while no session was running. That amnesty is deliberate: between sessions
only a person edits the tree, and a check that refuses to acknowledge your own comments is a
check you would turn off. On `compact` it **only lowers** — auto-compaction happens mid-task
without anyone asking for it, and it is the one session boundary Claude can cause on its own,
so absorbing there would let a long session launder every comment it had just added.

**`PostToolUse` enforces it.** After every edit *and every shell command* it rescans the whole
worktree — not just the file named in the tool call, so nothing added by a `sed`, a heredoc or a
generator slips past. Any file over its ceiling and the tool call is blocked, naming each file,
what it holds and what it is allowed; the hook fires again on the next call, and the next, until
the tree is green. Every file under its ceiling has that ceiling lowered to match, on the spot.

A full scan costs about 0.12s on a small repository and 0.45s on one of 159 files and 2,151
blocks, which is the price of the guarantee.

The refusal tells Claude to remove prose *it* added and, for a file it has not touched this
session, to stop and report rather than delete someone else's comment. After an absorbing
`SessionStart` the tree begins at exactly zero overruns, so anything over budget appeared while
the session was running.

**`PreToolUse` guards the budget file**, as above.

## What counts

The unit is the **block**, not the line: a run of adjacent whole-line comments counts once, a
docstring counts once however many lines it spans, and a trailing comment always counts on its
own because it belongs to its line rather than to the run.

Python docstrings count as expository content. In practice they carry the same prose the `#`
blocks do, and a budget that skipped them would miss most of the writing in a Python codebase.

What is *not* prose does not count: a first-line shebang, and machine-read directives —
`//go:build`, `// +build`, `# noqa`, `# type: ignore`, `# pragma:`, `# fmt: on|off`,
`# pylint:`/`# ruff:`/`# mypy:`/`# isort:`, `# shellcheck`, `# -*- coding:`, `// eslint-*`,
`// prettier-*`, `// @ts-*`, `// biome-*`, `//nolint`, and istanbul/c8 pragmas. These are
program input rather than commentary, and counting them would mean a new file could not carry
its own shebang or build tag while its ceiling was zero.

Scanned: Python, Rust, the C-style family (C, C++, C#, Java, Kotlin, Scala, Go, Swift, Dart,
PHP, JS/TS and JSX/TSX, Svelte, Vue, CSS/SCSS/LESS, GLSL, protobuf), shell (and `justfile`,
`Makefile`, `Dockerfile`), YAML, TOML, Ruby/Perl/R/Julia/Elixir/Terraform, and SQL/Lua/Haskell/
Elm. Markdown, JSON and lockfiles are not: they are either prose already or have no comment
syntax. Files over 2 MB are skipped as generated or vendored.

## Accuracy

The scanners are lexical rather than parsers, so they are exact for Python — `tokenize` and
`ast` do the work — and heuristic elsewhere. Every known soft edge fails by *missing* a comment
rather than by inventing one, which keeps the budget from accusing anyone falsely:

- **C-style.** Telling a regex literal from a division uses the usual preceding-token rule. A
  comment inside a template literal's `${...}` reads as string content.
- **Rust** reads `'` as an ordinary character rather than a quote, because lifetimes are far
  more common there than `'"'` char literals. Every other C-style language reads it as a quote,
  which is right for their char literals.
- **Marker dialects** (`#`, `--`) track quote state within a line only; TOML triple-quoted
  strings and YAML block scalars are skipped wholesale. A stray apostrophe in an unquoted YAML
  value can hide a later `#` on that line.

## Failure behaviour

Every hook fails open: a filesystem, JSON or git failure exits silently and the tool call
proceeds. A hook bug must never wedge a session. If the project is not a git worktree, the
plugin does nothing.

A failed `git ls-files` raises rather than reporting an empty tree, so a broken git can never
cause the budget to be rewritten as empty — the recorded ceilings survive.

## Tests

```bash
plugins/expository-budget/tests/harness.py [other-repo-to-benchmark]
```

Builds a scratch repository under `$TMPDIR` and drives the three hook scripts as subprocesses
over their real stdin/stdout contract: the baseline, a refusal that repeats, the ratchet, a
zero-budget new file, a file written by a shell command, compaction declining to absorb,
`startup` absorbing, the guard, and each failure path. A guard whose calibration only exercises
its pure functions has not been calibrated — the workflow is where these go wrong.

## Seeing where you stand

```bash
python3 ~/.claude/plugins/.../expository-budget/scripts/expository_scan.py
```

Run from the repository root, it prints every file's count against its ceiling, marks the ones
over budget, and totals them. It only reads.
