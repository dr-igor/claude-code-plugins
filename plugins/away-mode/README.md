# away-mode

Auto-denies permission prompts so a session doesn't stall on a dialog while you're away from the keyboard. Instead of waiting, Claude gets a standing message telling it to keep working with whatever is already auto-allowed and to propose a narrow allow rule you can review later.

**Leave the plugin enabled.** The switch is no longer the plugin's enable flag — that flag is read when the plugin registry loads, so changing it does nothing to a session that is already running, which is exactly when you need it. The hook script, by contrast, is spawned fresh for every single permission event, so it re-reads its state every time. **A mode change takes effect on the very next prompt, mid-turn.**

```
/away          leaving — deny prompts until I say otherwise
/here          back — prompts wait for me again
/here 30m      back for half an hour, then fall back to /auto
/auto          let presence decide
```

State is per session. Two sessions in the same repo can be in different modes, and nothing you do in one affects the other.

## The three modes

| Mode | Behavior | Expires |
| --- | --- | --- |
| `away` | Denies every prompt. | Never. It is sticky on purpose. |
| `here` | Prompts wait for you, exactly as without this plugin. | Optionally, into `auto`. |
| `auto` | Denies only on positive evidence that you are absent. | Never. |

**A session you never touch is in `auto`.** There is nothing to arm and nothing to remember to turn off; walking away is the switch.

`away` does not expire because you set it when you stand up, and a timer that cleared it would re-introduce the stall it exists to prevent. `here` is the one that takes a duration, and it falls back to `auto` rather than `away` — so the timer is a re-check, not a hard flip. If you are still at the keyboard when `/here 30m` runs out, nothing changes.

`/here` and `/auto` also re-bind the session to whichever application is frontmost when you run them, which is how a session started from a script or another window gets corrected.

The three commands set `disable-model-invocation: true`. Without it Claude could invoke `/here` itself, and the one thing away mode exists to prevent — work proceeding without you — would become something it could unlock the moment it got denied.

### How the commands work

Each command is a skill whose body is never meant to be read. A `UserPromptExpansion` hook matches on `command_name`, takes the mode from the command's last segment and the duration from `command_args`, writes the state file, and returns `{"decision": "block"}` with the new state as the `reason`. Blocking the expansion means the skill body never reaches Claude, so flipping a mode costs no model turn and no tokens — you just see the confirmation line.

The body only ever renders when the hook failed to run, so it says exactly that. If you see Claude talking about away-mode instead of a one-line confirmation, the hook is not firing.

Note that `UserPromptExpansion` receives `command_name`, `command_args`, `command_source`, `expansion_type`, and `prompt` — where `prompt` is the text you typed, such as `/here 30m`. It never receives the rendered skill body, which is why the mode is read from the command name rather than parsed out of the markdown.

Invocations are appended to `~/.claude/away-mode/commands.jsonl` (override `AWAY_MODE_COMMAND_LOG`), which doubles as an audit trail of mode changes and as the first place to look if a command appears to do nothing.

## Presence detection

`auto` asks two questions, both macOS-only, neither needing an Accessibility grant:

- **Is the screen locked?** Read from `IOConsoleUsers` in the I/O registry (`ioreg -l -w 0 -d 1`, about 25ms). Locked, that line carries `"CGSSessionScreenIsLocked"=Yes`; unlocked, the key is absent entirely. Note that `kCGSSessionOnConsoleKey` stays `Yes` either way, so it is not a lock signal. Both forms are captured verbatim in the test harness, sampled across a real lock cycle.
- **Is the session's application frontmost?** `lsappinfo front` gives the frontmost process, and `lsappinfo info -only bundleID` resolves its bundle identifier, which is compared against the one recorded for the session.

Either answering "absent" denies. **A detector that cannot answer never denies** — an unknown resolves to letting the prompt through, so a broken detector costs you a dialog rather than silently blocking every tool call. Denial in `auto` always requires positive evidence.

Two limits worth knowing. Focus is **application-level**, not window-level: two VS Code windows both read as frontmost, because per-window focus needs `osascript` and an Accessibility grant. And keyboard idle is deliberately not consulted — sitting still while reading is not being away.

## What it does and doesn't block

The hook runs on `PermissionRequest`, which fires _only_ when a permission dialog is about to be shown. Anything that never prompts is untouched: file reads, greps, the built-in read-only Bash commands (`ls`, `cat`, `git status`, …), and anything matching your `permissions.allow` rules all keep working normally. Only the calls that would have blocked on you get denied.

Claude is not stopped, just denied — it continues the task and can retry with something simpler.

Two tools are deliberately exempt — the hook's matcher (`^(?!(ExitPlanMode|AskUserQuestion)$).*`) skips both, so they still show their dialog and wait for you:

- `ExitPlanMode` — auto-denying it would either throw away a finished plan or push Claude to start implementing without approval. A plan sitting there when you get back is the better outcome.
- `AskUserQuestion` — a question is exactly the case where the standing "keep going without me" message is the wrong answer. (In practice this exemption is belt-and-braces: `PermissionRequest` does not appear to fire for `AskUserQuestion` in the first place, so the matcher is documenting intent more than changing behavior.)

Both exemptions mean a session _can_ stall while you're away. That is the trade: away mode keeps Claude moving through tool permissions, not through decisions that are genuinely yours.

One other edge: `PermissionRequest` never fires for `EndConversation`.

## Status line

`statusline/statusline.py` renders a badge for the current session, and it is **always** visible — there is no state in which the cell goes blank, because a silent status line and a broken one look identical:

**There are only two statuses, `HERE` and `AWAY`**, and they report what will actually happen to the next permission prompt — not which mode you selected. `auto` is a policy, not a status: a session in `auto` reads `AWAY` while you are away and `HERE` while you are at the keyboard.

| Badge | Meaning |
| --- | --- |
| `[HERE]` | The next prompt will wait for you. Dim. |
| `[HERE 28m]` | Same, with the time left on a timed `/here` before presence takes over again. |
| `[AWAY]` | The next prompt will be denied. Bold yellow, because this is the one to notice. |
| `[AWAY x12]` | Denying, with 12 denials so far this session. Capped at 99. |

To resolve `auto`, the status line shells out to `away_mode_state.py <session_id>`, which prints `present`, `absent`, or `unknown` — the same detectors the deny hook uses, so the badge cannot disagree with the decision. It only spawns that process when the mode is actually `auto`; a pinned `here` or `away` is answered from the state file alone. Override the path with `AWAY_MODE_STATE_SCRIPT` if the plugin does not sit beside `statusline/` in this repo; if the script cannot be found or times out, presence reads `unknown`, which resolves to `HERE` — matching the hook's fail-open behavior.

This is worth the subprocess. A status line that showed the selected mode would have said `AUTO` whether or not the host binding was correct, and a session bound to the wrong application denies every prompt while you sit in front of it. The badge now shows that.

The default mode is duplicated as `AWAY_MODE_DEFAULT` in `statusline.py`, because the status line is a standalone script and cannot import the plugin. If the default ever changes in `away_mode_state.py`, change it there too.

The cell reads the state file and nothing else — it deliberately does not run the detectors. At a five-second refresh that would be two subprocesses per tick, and the answer would be close to useless anyway: if you can read the status line, your window is frontmost.

## State and logs

Per-session state lives at `~/.claude/away-mode/sessions/<session_id>.json`, written atomically (temp file plus rename, so a reader never sees a half-written file) and removed when the session ends. Files from sessions that crashed are pruned after 7 days. A session id that isn't plain `[A-Za-z0-9_-]` is refused outright rather than turned into a path.

Every blocked call is appended as one JSON line to `~/.claude/away-mode/denials.jsonl`. Each record holds the timestamp, `session_id`, `cwd`, `tool_name`, `tool_input`, and `permission_suggestions` — the "always allow" options the dialog would have offered you. Those suggestions are deliberately _not_ sent to Claude; they're logged for you to review when you get back:

```bash
tail -n 20 ~/.claude/away-mode/denials.jsonl | jq .
```

Both paths are user-global rather than project-local on purpose, so nothing drops an untracked file into every repo you work in. They also need to be reachable from `statusline.py`, which is a standalone script and never sees `${CLAUDE_PLUGIN_DATA}`.

## Environment overrides

- `AWAY_MODE_SESSIONS` — session state directory (default: `~/.claude/away-mode/sessions`)
- `AWAY_MODE_LOG` — denial log file (default: `~/.claude/away-mode/denials.jsonl`)
- `AWAY_MODE_COMMAND_LOG` — mode-change log (default: `~/.claude/away-mode/commands.jsonl`)
- `AWAY_MODE_STATE_SCRIPT` — path the status line uses to resolve presence (default: the plugin's `scripts/away_mode_state.py`, relative to `statusline/`)
- `AWAY_MODE_HOST_BUNDLE_ID` — pin the application the focus detector compares against, instead of the one recorded for the session
- `AWAY_MODE_SESSION_TTL_DAYS` — how long a stale session file survives (default: `7`)

## Failure behavior

The hook fails open: any unexpected error exits 0 and the prompt appears as it normally would. A hook bug should never silently deny work. That matters more now than it did when the plugin was a plain on/off switch, because `auto` is a mode that can decide to deny on its own — so an unknown from either detector resolves to letting the prompt through, and an unreadable, corrupt or missing state file resolves to the default mode rather than to denial.

A failure to write the state file or the denial log never affects the decision.

## Tests

```bash
plugins/away-mode/tests/harness.py
```

No framework: it drives each hook as a subprocess over the real stdin/stdout contract, with stub `ioreg` and `lsappinfo` on `PATH` so the detectors can be put into every state including failure. Exits non-zero if any check fails.
