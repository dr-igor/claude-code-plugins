# playwright-cli under the Claude Code sandbox (macOS)

Supplements the `playwright-cli` skill, which `playwright-cli install --skills` regenerates from the CLI's own template, so this guidance lives here instead of in the skill. The general Chromium guidance is in [sandbox-interop.md](sandbox-interop.md).

Verified 2026-10-31 with `@playwright/cli` 0.1.13 and Claude Code 2.1.316; the code paths below were re-checked in `@playwright/cli` 0.1.25 (`playwright-core` 1.66.0-alpha-2026-11-18) on 2026-11-18.

## Failures out of the box

`open` fails inside the sandbox in up to three ways:

| Output | Cause | Fix |
| --- | --- | --- |
| `Failed to create a ProcessSingleton`, Crashpad `Operation not permitted` | It launched the installed Chrome with the user's real profile | A config that uses a Playwright-managed Chromium and `isolated: true` |
| `bootstrap_check_in … MachPortRendezvousServer … Permission denied (1100)` | Multi-process Chromium registers a Mach service, which the sandbox never allows | Single-process config, or an external browser server |
| `listen EPERM: operation not permitted <TMPDIR>/pw-<hash>/…sock` | The daemon's Unix socket is blocked | Ask the user to add `<TMPDIR>/pw-<hash>` (from the error) to `sandbox.network.allowUnixSockets` in `.claude/settings.local.json`. The hash is of the OS username, so the same directory serves every workspace |

## Two configs that work

Pass one with `--config=<file>` or save it as `.playwright/cli.config.json`, the default location.

Single-process, everything sandboxed:

```json
{ "browser": { "browserName": "chromium", "isolated": true,
  "launchOptions": { "headless": true, "args": ["--single-process"],
    "executablePath": "<a Chromium or headless shell under ~/Library/Caches/ms-playwright/>" } } }
```

Single-process Chromium crashes when pages open concurrently, so use one tab at a time. Text in system fonts renders differently from normal Chromium; for screenshots that must look real, use an external server:

```json
{ "browser": { "browserName": "chromium", "isolated": true, "remoteEndpoint": "ws://127.0.0.1:<port>/<path>" } }
```

- Without `isolated: true`, `remoteEndpoint` fails with `unable to connect to a browser that does not have any contexts`.
- Client and server Playwright versions must match, so the server must come from the `playwright-core` that `playwright-cli` bundles: `node <npm global root>/@playwright/cli/node_modules/playwright-core/cli.js launch-server --browser chromium --config <server.json>`, with `{ "headless": true, "chromiumSandbox": true, "host": "127.0.0.1", "executablePath": "…" }`. It prints the endpoint. When the CLI runs as `npx playwright cli` from a project's own Playwright, start the server from that same Playwright instead.
- The server has to run outside the sandbox. Ask the user for an exact `sandbox.excludedCommands` entry plus a matching `Bash(…)` allow rule, start it as a background task with no output redirect, and stop it when done: anything holding the endpoint drives an unsandboxed browser.

## Local pages

`playwright-cli` refuses `file:` URLs, so serve local pages over `http://127.0.0.1:<port>` instead; the sandboxed side needs `sandbox.network.allowLocalBinding: true`.
