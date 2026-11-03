# Browsers under the Claude Code sandbox (macOS)

Applies when a sandboxed Bash command starts Chromium or Chrome on macOS, whatever drives it: Playwright (library, Test, `playwright-cli`), Vitest browser mode, Puppeteer, WebdriverIO, or the binary itself. Package manager and bundler don't matter. Verified 2026-10-31: Claude Code 2.1.316 (sandbox-runtime 0.0.81), Playwright 1.64.1, Chrome Headless Shell 156. Firefox and WebKit untested.

## Check first whether this still applies

Run a Chromium binary sandboxed, with no workaround flags: `<chromium> --headless --dump-dom "data:text/html,<p>ok</p>"` (Playwright's builds live under `~/Library/Caches/ms-playwright/`). If it prints `<p>ok</p>`, the sandbox now permits Chromium and nothing below is needed.

## Symptoms

| Output | Cause | Fix |
| --- | --- | --- |
| `bootstrap_check_in org.chromium…MachPortRendezvousServer.<pid>: Permission denied (1100)` | Multi-process Chromium registers a Mach service for its child processes. The sandbox profile never allows registration (`mach-register`), and no setting adds it: `sandbox.network.allowMachLookup` only adds lookups. | Option A or B |
| `Failed to create a ProcessSingleton for your profile directory`, Crashpad `Operation not permitted` | The tool launched the installed Chrome with the user's real profile | Launch a Playwright-managed Chromium with a temporary or in-memory profile, then A or B |
| `Target page, context or browser has been closed` with `--single-process` | Single-process Chromium crashes when pages open concurrently | One page at a time |
| `listen EPERM: operation not permitted …/<name>.sock` | Unix sockets are blocked by default | Put that socket's directory in `sandbox.network.allowUnixSockets` |

## Option A: single-process Chromium, everything sandboxed

`--single-process` keeps Chromium from registering the Mach service, so it runs inside the sandbox with no setting changes.

- Gate it on the sandbox so runs outside it stay normal: sandboxed commands carry `SANDBOX_RUNTIME=1` (set by sandbox-runtime, undocumented by Claude Code; re-check if absent). Read it in the runner config from `process.env`, or through the config system's env loader if that filters variables by prefix.
- Add `--single-process` to the runner's Chromium launch args, and open one page at a time:

| Runner | Launch args | One page at a time |
| --- | --- | --- |
| Vitest browser mode, Playwright provider | provider `launchOptions.args` | `test.fileParallelism: false` (verified necessary) |
| Playwright Test | `use.launchOptions.args` | each worker has its own browser; whether `workers: 1` is needed is untested |
| Playwright library | `chromium.launch({ args })` | don't create pages concurrently |
| Puppeteer | `puppeteer.launch({ args })` | untested |
| Other runners | their Chromium args setting (WebdriverIO: `goog:chromeOptions.args`) | untested |

- Runners that serve pages on localhost need `sandbox.network.allowLocalBinding: true` (it was on in every verified run).
- Costs: an unsupported Chromium mode; serial pages; system-font text renders with different weight and wrapping than normal Chromium (web-font layout measured identical). Suits unattended test runs, not screenshots meant to show real rendering.

## Option B: browser server outside the sandbox, clients inside

Only the browser runs unsandboxed. The runner, bundler, test code and CLI clients stay sandboxed and connect over localhost. Normal multi-process Chromium, parallel pages, true rendering.

1. **Server.** Playwright's hidden command `playwright launch-server --browser chromium --config <file.json>` passes the JSON to `browserType.launchServer()` and prints `ws://127.0.0.1:<port>/<random>`. In the JSON set `"host": "127.0.0.1"` and `"chromiumSandbox": true` (Playwright defaults it to `false`); leave `wsPath` unset so it stays random. Run it from the project's own Playwright through the project's package manager (`npx`, `pnpm exec`, `yarn`, `bunx`).
2. **Versions.** A client's Playwright major.minor must equal the server's. Tools that bundle their own `playwright-core`, like `playwright-cli`, need a server started from that bundled copy (`node <bundled playwright-core>/cli.js launch-server …`, with `executablePath` set to an installed Chromium).
3. **Permissions, per project and intentional.** Ask the user to approve two entries in `.claude/settings.local.json`: the exact server command in `sandbox.excludedCommands`, and the same command as a `Bash(…)` rule in `permissions.allow`. Start it as a background task with no output redirect; a redirect keeps an excluded command sandboxed. If the first start prompts right after the settings edit, retry once: edits reach the session after a delay.
4. **Endpoint handoff.** Put the printed endpoint in an environment variable in an ignored local file, and have the config connect only when it is set:

| Client | Connect setting |
| --- | --- |
| Vitest Playwright provider | `connectOptions: { wsEndpoint }` |
| Playwright Test | `use.connectOptions: { wsEndpoint }` |
| Playwright library | `chromium.connect(wsEndpoint)` |
| `playwright-cli` | `browser.remoteEndpoint` plus `browser.isolated: true` |

   Remove the variable when the server stops: a stale endpoint fails to connect instead of falling back. The endpoint changes on every start.
5. **Puppeteer** has no Playwright server. `puppeteer.connect({ browserWSEndpoint })` needs a CDP endpoint from Chrome started with `--remote-debugging-port`, which has no secret path. Untested and weaker.

- Costs: the server is a way out of the sandbox. Whatever knows the endpoint drives an unsandboxed browser that can open `file://` paths the sandbox denies and reach the network outside the proxy; Playwright's docs say knowing the path gives control of the OS user. With `allowLocalBinding` on, every sandboxed command can reach localhost. Stop the server when done.

## Choosing

Default to A: nothing leaves the sandbox. Use B when rendering fidelity matters (screenshots for review, system fonts, multi-process behavior) and the user agrees to the per-project permission entries.

## Settings that don't help

- `allowMachLookup`: lookups only; the failing operation is registration.
- `allowAllUnixSockets`: opens every Unix socket, including Claude Code's messaging socket. Use `allowUnixSockets` with the one directory.
- Excluding the test runner command: runs all project code unsandboxed, and any redirect in the call keeps it sandboxed anyway.
