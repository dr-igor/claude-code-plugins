# Permission decision attribution in the mod API (Claude Code 2.1.329)

Sources: `plugin-authoring` skill types (`types/claude-code.d.ts`, build 2.1.329) and
`reference.md`, read 2026-11-20; `claude plugin validate` and `claude plugin test` output for
`plugins/prompt-why`. Complements `sandbox-network-prompt.md`.

## Where a verdict comes from

- `tool.check` fires after the `tool.call` and `PreToolUse` hooks and before the mode settles an
  ask. `await next(e)` is the verdict from beneath this hook: core's (rules, mode, the tool's own
  check, PreToolUse's folded decision) as amended by plugins beneath. Nothing runs.
- `ToolCheckResult` fields, as the engine sets them:
  - `decision`: `allow` | `ask` | `deny`.
  - `reason`: from core, the rule or check that decided; from a hook, its own text.
  - `rule`: the settings rule as written (`Bash(git push:*)`). No source is given.
  - `hook`: the classic event name that decided (`PreToolUse`). It does not name the hook.
  - `setting`: the option key whose check asked (`permissions.blockReadsOutsideWorkingDirectories`).
  - `plugin`: pinned by the engine, the plugin whose `tool.check` hook made the ask (beneath only).
  - `ceiling`: the organization's most permissive verdict for the call.
- `e.approver` is absent where nobody can be asked (an ask then becomes a deny), as for a
  background subagent and for every `$.tool.call` in a test.
- `tool.judge` fires only in auto mode, before the classifier; `next(e)` is its verdict, `ask`
  meaning no verdict (outage, conversation too long).
- Settings hooks fold into one answer, last write wins (`ClassicResult` doc). No API reports
  which hook answered, so the plugin lists candidates: settings `hooks[event]` per source and each
  enabled plugin's `hooks/hooks.json`, filtered by matcher.
- `classic.PermissionRequest` carries `tool_name`, `tool_input` and `permission_mode` but no
  `tool_use_id`. Its chain is [managed hooks, hooks modules, other settings hooks], so a module's
  `await next(e)` includes every non-managed settings hook's `decision`.

## What a mod may do

- `$.ui.notice(tool_use_id, text)` stores one line for an open call; core removes it when the call
  resolves; a call that is not open is refused. Only the question-card dialog draws it (see below).
- `$.ui.toast(text, { timeoutMs })` shows while a permission dialog is open; `$.ui.status` is hidden
  while one is up.
- `$.settings.read({ source })` reads `user` | `project` | `local` | `flag` | `policy`. The
  `plugin` layer appears only in `settings.read` event layers, not as a readable source.
- `$` may not be passed, bound or returned: `claude plugin validate` refuses any `$` that is not
  spelled `$.noun.event(...)` at the call site. `read($, atom)` and `update($, atom, fn)` are
  accepted, as are closures that call `$.noun.event(...)` (used here to build a `Host` client).
- In tests (`claude plugin test`), calls on `$` are answered by the test's `on` hooks with
  `{ value }` or `{ deny }`; `$.tool.call` raises `tool.check` and then `classic.PermissionRequest`.
  With no approver, an ask resolves as a deny and the tool's own `tool.call` hook is never reached,
  so a test holds a call open by sleeping on `mock.clock` in its `PermissionRequest` hook.
  `mock.clock(on)` registers the `clock.*` hooks itself; a second `on('clock.every')` fails the load.

## Assumptions, by evidence

| Assumption | Evidence |
| --- | --- |
| `tool.check` result fields as above | verified: types |
| A hook ask's exact hook cannot be named | verified: types (fold) |
| `$.ui.notice` lines are drawn only in the question-card dialog, not in the standard Bash/Read permission dialogs | verified 2026-11-20, live and in the 2.1.330 binary. Live: no plugin line in any standard dialog; "Rule Bash(uname:*) from project local settings says to ask." is core's own text. Binary: `setNotice` keeps `{plugin, text}` by `tool_use_id` while the call is open (refusing with "no call with that tool_use_id is open" otherwise, logged as `$.ui.notice dropped`), and one component reads that store, rendered once, inside the card component whose props are `payload, asked, answer, wouldTakeAnswer`. Timing plays no part |
| A plugin toast shows while a permission dialog is open; a plugin status entry does not | observed live 2026-11-20 (the status line is hidden while the dialog is up) |
| A `$.ui.log` transcript row written at `tool.check` lands beside the call that asked | observed live 2026-11-20, for a batch of two Reads and a Bash call |
| A `ui.render` hook on `ToolUse` (matcher `{ component: 'ToolUse' }`, no `plugin` key) hears core's tool rows and can draw a colored `Text` under `await next(e)`; the line sits below the row's result summary | observed live 2026-11-24: amber (`warning`) lines under two prompted Reads of `/etc/hosts` and `/etc/shells` |
| A `tool.call` hook's `context` reaches the model after the call's result, also on an errored result | observed live 2026-11-24: the note arrived as "tool.call hook additional context" after `tr "a=b" "x" /dev/null` exited 1, carrying Claude Code's full reason |
| A call the user rejects at the dialog carries no `tool.call` `context` | observed live 2026-11-24: rejecting `tr "a=b" "x" /dev/null` gave the model only core's "The user doesn't want to proceed with this tool use" text, no note; the rejection likely reaches `tool.call` hooks as `{ deny }`, which takes no `context` |
| A `tool.check` hook that turns an ask into `{ decision: 'deny', reason }` ends the call with no dialog, and `tool.call` hooks still see an errored result that carries `context` | observed live 2026-11-24: `tr "a=b" "x" /dev/null` refused; the model read "Permission to use Bash denied by plugins prompt-why, cc-plugin-privacy: <reason>" and the prompt-why note after it. The engine's attribution named a second plugin that has a `tool.check` hook but did not decide |
| The `ToolGroup` hook's lines appear under a folded group's summary | unverified live: the two prompted Reads above were drawn as separate rows, not folded; covered by `claude plugin test` only |
| `PermissionRequest`'s `tool_input` equals `tool.check`'s `input` (correlation key) | inferred; a mismatch shows up as an "unseen" entry with a re-queried verdict |
| `installed_plugins.json` `installPath` holds the hooks that run | inferred; a folder marketplace may run from its folder instead |
| Sandbox network prompts reach no event | verified earlier: `sandbox-network-prompt.md` |

## Not covered

Hooks declared in a plugin manifest's `hooks` field, `--plugin-dir` plugins, skill frontmatter
hooks, and hooks modules' own `classic.PreToolUse` hooks appear in no candidate list.
