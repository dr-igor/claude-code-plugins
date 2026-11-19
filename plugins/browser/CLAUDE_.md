# 🌐 Browsers under the Claude Code Sandbox

## Additional contexts

- [browser-sandbox-interop](contexts/sandbox-interop.md) Describes why Chromium-based tools fail under the Claude Code sandbox on macOS, and the two verified setups that work. **Read** this file before configuring or running a browser from a sandboxed session (Playwright, Vitest browser mode, Puppeteer, WebdriverIO, `playwright-cli`, Chrome itself), whatever the package manager or bundler.
- [playwright-cli-sandbox](contexts/playwright-cli.md) Supplements the `playwright-cli` skill with the configs, socket permission and browser-server setup that make `playwright-cli open` work in the sandbox. **Read** this file before running `playwright-cli` from a sandboxed session; the skill itself is regenerated from the CLI and does not carry it.
