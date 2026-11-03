# away-mode

Denies every Bash permission prompt, so an autonomous session never stalls on a dialog nobody is watching. Instead of waiting, Claude receives a standing message telling it to try simpler tool usages, and, when a denial blocks a task, to report it in a section titled **Blocking Permission Rejections** with what it was trying to do, why, and the minimal sandbox setting (preferred) or Allow rule that would unblock it.

It is always on. There are no modes, no commands, and no per-session state: enabling the plugin is the switch.

## What it does and doesn't block

The hook runs on `PermissionRequest` with the matcher `Bash`. `PermissionRequest` fires _only_ when a permission dialog is about to be shown, so anything that never prompts is untouched: sandboxed commands that auto-allow, the built-in read-only commands (`ls`, `cat`, `git status`, …), and anything matching your `permissions.allow` rules all keep working normally. Only Bash calls that would have blocked on you get denied.

Every other tool prompts exactly as it would without this plugin, including `Edit`, `Write`, `WebFetch`, MCP tools, `ExitPlanMode` and `AskUserQuestion`.

Claude is not stopped, just denied: `interrupt` is left unset, so it continues the task and can retry with something simpler.

## Denial log

Every denied call is appended as one JSON line to `~/.claude/away-mode/denials.jsonl`. Each record holds the timestamp, `session_id`, `cwd`, `tool_name`, `tool_input`, and `permission_suggestions` — the "always allow" options the dialog would have offered you. Those suggestions are deliberately _not_ sent to Claude; they are logged for you to review alongside the session's **Blocking Permission Rejections** report:

```bash
tail -n 20 ~/.claude/away-mode/denials.jsonl | jq .
```

The path is user-global rather than project-local on purpose, so nothing drops an untracked file into every repo you work in. Override it with `AWAY_MODE_LOG`.

A failure to write the log never affects the decision, and an unreadable or malformed hook event is still denied.

## Tests

```bash
plugins/away-mode/tests/harness.py
```

No framework: it drives the hook as a subprocess over the real stdin/stdout contract and checks the hook registration in `hooks.json`. Exits non-zero if any check fails.
