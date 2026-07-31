# quality-inspector

Wires [`belphegor inspect`](../../../quality-inspector) into Claude Code's Pre/PostToolUse hooks:
around a burst of edits it runs your quality commands, diffs against a pre-edit baseline, and
reports only the **newly-introduced** findings back to Claude.

- **Config**: `./quality-inspector.yaml` at the project root (override with `QUALITY_INSPECTOR_CONFIG`).
  Copy [`quality-inspector.example.yaml`](quality-inspector.example.yaml) to start.
- **Executable**: `belphegor` on `PATH` (override with `BELPHEGOR_BIN`). Install via
  `pipx install belphegor`. A missing config or executable is reported once at session start; edits
  are never blocked.
- **Live state**: the [status line](../../statusline/) renders a cell for this session's daemon —
  whether it is up, priming, settling, checking, and how many findings the last burst introduced.
  Findings themselves still arrive on the `PostToolUse` hook; the cell just makes the daemon visible
  between bursts. It also asks the daemon for its live dashboard and prints the URL, so the full
  picture is one click away.

## Command recipes

Copy the blocks you need under `commands:` in your `quality-inspector.yaml`. **Run only the checks a
project actually uses** — every command runs on each edit burst.

How belphegor consumes a command dictates the exact shape of each recipe:

1. **stdout only.** belphegor parses a command's **stdout**; stderr is discarded. A tool that writes
   findings to stderr (e.g. `black`) needs `2>&1`.
2. **Exit codes are ignored.** A linter exiting non-zero because it found issues is fine — findings
   come purely from stdout content.
3. **Findings are diffed by exact line match, with no normalization.** A record carrying a **volatile
   line/column number (or timestamp)** re-appears as "new" the instant an edit shifts it, so every
   recipe strips positions in the `run` string. That stripping is the whole reason these commands
   look the way they do — keep it when you adapt them.
4. **Commands run in belphegor's daemon cwd** (the session's cwd), not re-`cd`'d to the repo.
   Config-discovering tools (tsconfig, eslintrc) work if you start Claude at the repo root; otherwise
   prefix `cd <repo> && `.

`reconcile: append` (per-line set-difference) with the default newline delimiter is right for all of
these: each finding is one stable line, and "new" = a line present now but absent from the baseline.

> `eslint` and `vitest` below pipe through **`jq`** — install it if you use them. `pytest` and
> `vitest` run the whole suite on every burst; raise `command_timeout` and/or scope them
> (`pytest --lf`, `vitest run --changed`).

### black

```yaml
# --check reports "would reformat <path>" (file-level, already position-free).
# 2>&1 because some black versions write it to stderr.
black:
  run: black --check . 2>&1 | grep '^would reformat'
  reconcile: append
```

### prettier

```yaml
# -l/--list-different prints ONLY differing filenames to stdout (no positions).
prettier:
  run: prettier --list-different .
  reconcile: append
```

### eslint

```yaml
# Default output embeds volatile line:col; the json reporter + jq keeps rule + message only.
# (needs jq; identical messages on different lines collapse to one record.)
eslint:
  run: eslint -f json . | jq -r '.[].messages[] | "[\(.ruleId)] \(.message)"'
  reconcile: append
```

### typescript (tsc)

```yaml
# --pretty false gives `file(line,col): error TSxxxx: msg`; sed drops (line,col),
# leaving `file: error TSxxxx: msg`. Needs a tsconfig in the daemon cwd (or add -p <path>).
typescript:
  run: tsc --noEmit --pretty false | sed -E 's/\([0-9]+,[0-9]+\)//'
  reconcile: append
```

### svelte-check

```yaml
# machine rows are `{timestamp} SEVERITY "file" line:col "message"`.
# grep keeps only ERROR/WARNING rows; sed strips the per-run timestamp AND the line:col.
svelte-check:
  run: svelte-check --output machine 2>&1 | grep -E ' (ERROR|WARNING) ' | sed -E 's/^[0-9]+ //; s/ [0-9]+:[0-9]+ / /'
  reconcile: append
```

### pytest

```yaml
# -rf prints `FAILED path::test - reason`; --tb=no drops tracebacks; sed trims the
# (possibly volatile) reason, leaving the stable node id. Heavy: runs the suite each burst.
pytest:
  run: pytest -q -rf --tb=no 2>&1 | grep '^FAILED' | sed -E 's/ - .*$//'
  reconcile: append
```

### vitest

```yaml
# json reporter + jq emits the full name of each failed test (position-free).
# (needs jq; heavy — consider `vitest run --changed` to limit scope.)
vitest:
  run: vitest run --reporter=json 2>/dev/null | jq -r '.testResults[].assertionResults[] | select(.status=="failed") | .fullName'
  reconcile: append
```
