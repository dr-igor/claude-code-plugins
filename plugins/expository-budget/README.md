# expository-budget

A per-file ceiling on comments, block comments and docstrings, enforced on every edit. The ceiling only ever falls: removing prose lowers it, and nothing Claude Code can do raises it.

## The budget file

`.claude/expository-content-budget.json` in the project, one entry per file:

```json
{
  "READ-THIS-FIRST": "A per-file ceiling on comment blocks, block comments and docstrings...",
  "EXCLUDE": ["vendor/", "src/generated/**", "*.pb.go"],
  "src/parser.py": 4,
  "src/render.ts": 1
}
```

It lives in `.claude/` so it is yours to edit. Claude Code cannot touch it: a `PreToolUse` hook denies `Edit`, `Write`, `MultiEdit` and `NotebookEdit` against it, and denies any `Bash` command that so much as names it. **Raising a number is a hand edit by a person.** That is the whole design — the only path from "I want to keep this comment" to a green check runs through you.

A file with no entry has a ceiling of zero, so a newly created file arrives with no budget to spend and may carry no expository comments or docstrings at all.

### Excluding files

`EXCLUDE` is a list of gitignore-style patterns for paths the budget should not account for at all — vendored code, generated code, a legacy corner you have decided not to fight. It is a hand edit like every other change to this file.

Four rules cover:

- A pattern with no `/` matches that **basename anywhere** — `conftest.py`, `*.pb.go`.
- A pattern containing `/` matches the **repo-root-relative path** — `src/generated/**`, `docs/legacy/old.py`. `**` crosses directories; a single `*` or `?` does not.
- A trailing `/` means **directory only**, so `vendor/` excludes the tree but not a file named `vendor`.
- A bare directory name excludes its whole subtree.

A leading `/` anchors to the repository root; a leading `./` is ignored.

What you will see: an excluded file's entry **disappears from this file** on the next write, and the file stops being scanned. Delete the pattern and the next `startup`, `resume` or `clear` re-absorbs it at whatever it then holds. There is no dormant bookkeeping — an exclusion is a deletion, and un-excluding is an amnesty like any other. Between the two, a file you un-exclude mid-session is over budget until the next absorbing `SessionStart`, which is the same rule that governs everything else here.

Not supported, so nobody wastes an afternoon on it: negation (`!keep.py`), brace expansion, and patterns that would match the entire repository — `**`, `*` and their spellings are **ignored rather than obeyed**, because one of them would silently switch the plugin off.

Exclusion happens before a file is ever opened, so an excluded tree is never read from disk. Excluding a large `vendor/` also removes it from the scan cost quoted below.

## The three hooks

**`SessionStart` records the budget.** It scans the working tree — everything git tracks plus everything untracked and not ignored — and writes what each file currently holds. On the first run every file is recorded as-is, so an existing codebase starts green.

On later sessions it re-records from the tree on `startup`, `resume` and `clear`, absorbing whatever changed while no session was running. That amnesty is deliberate: between sessions only a person edits the tree, and a check that refuses to acknowledge your own comments is a check you would turn off. On `compact` it **only lowers** — auto-compaction happens mid-task without anyone asking for it, and it is the one session boundary Claude can cause on its own, so absorbing there would let a long session launder every comment it had just added.

**`PostToolUse` enforces it.** After every edit _and every shell command_ it rescans the whole worktree — not just the file named in the tool call, so nothing added by a `sed`, a heredoc or a generator slips past. Any file over its ceiling and the tool call is blocked, naming each file, what it holds and what it is allowed; the hook fires again on the next call, and the next, until the tree is green. Every file under its ceiling has that ceiling lowered to match, on the spot.

A full scan costs about 0.12s on a small repository and 0.45s on one of 159 files and 2,151 blocks, which is the price of the guarantee.

The refusal tells Claude to remove prose _it_ added and, for a file it has not touched this session, to stop and report rather than delete someone else's comment. After an absorbing `SessionStart` the tree begins at exactly zero overruns, so anything over budget appeared while the session was running.

**`PreToolUse` guards the budget file**, as above.

## What counts

The unit is the **block**, not the line: a run of adjacent whole-line comments counts once, a docstring counts once however many lines it spans, and a trailing comment always counts on its own because it belongs to its line rather than to the run.

Python docstrings count as expository content. In practice they carry the same prose the `#` blocks do, and a budget that skipped them would miss most of the writing in a Python codebase.

What is _not_ prose does not count. These are program input rather than commentary, and counting them would mean a new file could not carry its own shebang, build tag or dependency metadata while its ceiling was zero. Four rules cover them, each narrow enough that no sentence fits through it:

- **Interpreter lines**, matched by shape rather than by position: an absolute interpreter path and at most eight arguments, anchored to the whole line. An indented `#!/usr/bin/env bash` opening a `justfile` recipe is free; `#!this is emphatic prose about ordering` is not.
- **Machine-read directives** — build constraints (`//go:build`, `// +build`), linters (`//nolint`, `# noqa`, `# pylint:`/`# ruff:`/`# mypy:`/`# pyright:`/`# isort:`, `# nosec`, `# shellcheck`, `# yamllint disable`, `# tflint-ignore:`), suppressions (`# type: ignore`, `# pragma:`), formatters (`// prettier-*`, `# fmt: on|off|skip`, `# yapf: disable|enable`), sorters (`# keep-sorted start|end`), JS/TS tooling (`// eslint-*`, `// biome-*`, `// @ts-*`, istanbul and `/* c8 ignore */`), `/// <reference`, `//# sourceMappingURL=`, spellers (`# cspell:`, `# codespell:`), `# noinspection`, `SPDX-*:` licence tags, `# -*- coding:`, a Dockerfile `# syntax=`, and a bare `# %%` cell marker. A `# %%` carrying a title is prose and counts.
- **A directive continued over several lines**, while every line after the first is a single bare token — optionally led by `*`, optionally trailed by a comma or `*/`. `/* eslint-disable` / `no-console,` / `no-undef */` costs nothing; the same opener followed by a sentence costs a block.
- **A PEP 723 inline-script header** in a Python file — the `# /// script` region `uv` reads as dependency metadata, which without this would consume the entire budget of a new script.

The metadata region is the one exemption that spans lines, so five conditions bound it: the delimiters must read exactly `# /// script` and `# ///`, the opener must sit in the file's comment prelude, only the first occurrence counts, no body line may be `# #`, and the body must parse as TOML whose keys fall within `requires-python`, `dependencies` and `tool`. Anything else — including a `# description = """..."""` — is rejected and counts as ordinary prose. Exemption is decided before adjacent comments merge, so a comment on the line after `# ///` becomes its own block and is charged rather than being absorbed into the free region.

A Python docstring is never exempt. It is prose by definition, so a directive appearing inside one — `"""# type: ignore"""` — does not buy it out.

Scanned: Python, Rust, the C-style family (C, C++, C#, Java, Kotlin, Scala, Go, Swift, Dart, PHP, JS/TS and JSX/TSX, Svelte, Vue, CSS/SCSS/LESS, GLSL, protobuf), shell (and `justfile`, `Makefile`, `Dockerfile`), YAML, TOML, Ruby/Perl/R/Julia/Elixir/Terraform, and SQL/Lua/Haskell/ Elm. Markdown, JSON and lockfiles are not: they are either prose already or have no comment syntax. Files over 2 MB are skipped as generated or vendored.

## Accuracy

The scanners are lexical rather than parsers, so they are exact for Python — `tokenize` and `ast` do the work — and heuristic elsewhere. Every known soft edge fails by _missing_ a comment rather than by inventing one, which keeps the budget from accusing anyone falsely:

- **C-style.** Telling a regex literal from a division uses the usual preceding-token rule. A comment inside a template literal's `${...}` reads as string content.
- **Rust** reads `'` as an ordinary character rather than a quote, because lifetimes are far more common there than `'"'` char literals. Every other C-style language reads it as a quote, which is right for their char literals.
- **Marker dialects** (`#`, `--`) track quote state within a line only; TOML triple-quoted strings and YAML block scalars are skipped wholesale. A stray apostrophe in an unquoted YAML value can hide a later `#` on that line.
- **Exemptions fail towards counting.** Every rule above is structural rather than a keyword search — a shape, a bare token, a validated TOML region — so a malformed or ambiguous case is charged rather than waved through. The cost of that choice is an occasional real directive counted as prose, which you can raise by hand; the cost of the other choice would be a hole prose could be pushed through.

## Failure behaviour

Every hook fails open: a filesystem, JSON or git failure exits silently and the tool call proceeds. A hook bug must never wedge a session. If the project is not a git worktree, the plugin does nothing.

A failed `git ls-files` raises rather than reporting an empty tree, so a broken git can never cause the budget to be rewritten as empty — the recorded ceilings survive.

A malformed `EXCLUDE` — anything that is not a list of strings, a pattern that will not compile, a pattern that would match everything — is ignored and **never invalidates the ceilings**. The recorded numbers survive intact, nothing is excluded, and the bad value is replaced on the next write. But a JSON syntax error anywhere in the file makes the whole file unreadable, and an unreadable budget is rebuilt from the tree as it stands, which absorbs every comment currently in it and empties `EXCLUDE`. Exclusions mean more hand edits, so it is worth checking the file still parses after one.

Validating a PEP 723 header needs `tomllib`, which arrived in Python 3.11. It is imported inside the validator rather than at module scope, so on 3.10 the import simply fails and the header counts as prose — the same direction as every other soft edge, and no parse failure reaches the hook.

## Tests

```bash
plugins/expository-budget/tests/harness.py [other-repo-to-benchmark]
```

Builds a scratch repository under `$TMPDIR` and drives the three hook scripts as subprocesses over their real stdin/stdout contract: the baseline, the exemption rules against both genuine directives and prose dressed as one, a refusal that repeats, the ratchet, a zero-budget new file, a file written by a shell command, compaction declining to absorb, `startup` absorbing, the exclusion matcher against a table of patterns, a hand-added exclude list surviving a ratchet write, a malformed one leaving the ceilings intact, the guard, and each failure path. A guard whose calibration only exercises its pure functions has not been calibrated — the workflow is where these go wrong.

## Seeing where you stand

```bash
python3 ~/.claude/plugins/.../expository-budget/scripts/expository_scan.py
```

Run from the repository root, it prints every file's count against its ceiling, marks the ones over budget, and totals them. It only reads.
