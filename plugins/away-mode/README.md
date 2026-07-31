# away-mode

Auto-denies every permission prompt so a session doesn't stall on a dialog while you're away from
the keyboard. Instead of waiting, Claude gets a standing message telling it to keep working with
whatever is already auto-allowed and to propose a narrow allow rule you can review later.

**Off by default.** Enabling and disabling the plugin *is* the switch — Claude Code hot-reloads
plugin enable/disable, so both take effect immediately in a running session:

```
/plugin enable  away-mode@cc-plugins-igorlabworks   # leaving
/plugin disable away-mode@cc-plugins-igorlabworks   # back
```

It stays on until you explicitly disable it (the setting persists in `.claude/settings.local.json`).

## What it does and doesn't block

The hook runs on `PermissionRequest`, which fires *only* when a permission dialog is about to be
shown. Anything that never prompts is untouched: file reads, greps, the built-in read-only Bash
commands (`ls`, `cat`, `git status`, …), and anything matching your `permissions.allow` rules all
keep working normally. Only the calls that would have blocked on you get denied.

Claude is not stopped, just denied — it continues the task and can retry with something simpler.

Two tools are deliberately exempt — the hook's matcher (`^(?!(ExitPlanMode|AskUserQuestion)$).*`)
skips both, so they still show their dialog and wait for you:

- `ExitPlanMode` — auto-denying it would either throw away a finished plan or push Claude to start
  implementing without approval. A plan sitting there when you get back is the better outcome.
- `AskUserQuestion` — a question is exactly the case where the standing "keep going without me"
  message is the wrong answer. (In practice this exemption is belt-and-braces: `PermissionRequest`
  does not appear to fire for `AskUserQuestion` in the first place, so the matcher is documenting
  intent more than changing behavior.)

Both exemptions mean a session *can* stall while you're away. That is the trade: away mode keeps
Claude moving through tool permissions, not through decisions that are genuinely yours.

One other edge: `PermissionRequest` never fires for `EndConversation`.

## Denial log

Every blocked call is appended as one JSON line to `~/.claude/away-mode/denials.jsonl` (override
with `AWAY_MODE_LOG`). Each record holds the timestamp, `session_id`, `cwd`, `tool_name`,
`tool_input`, and `permission_suggestions` — the "always allow" options the dialog would have
offered you. Those suggestions are deliberately *not* sent to Claude; they're logged for you to
review when you get back:

```bash
tail -n 20 ~/.claude/away-mode/denials.jsonl | jq .
```

The log is user-global rather than project-local on purpose, so it doesn't drop an untracked file
into every repo you work in.

## Failure behavior

The hook fails open: any unexpected error exits 0 and the prompt appears as it normally would. A
hook bug should never silently deny work. A failure to write the log never affects the decision.
