# Claude Code Plugin Marketplace

Personal marketplace for Claude Code plugins that inject language-specific coding guidelines into your development sessions.

> DISCLAIMER: This is all maintained for my own personal benefit. I am sharing it in case others find some aspect of it useful, but it is not intended to be directly consumable by anyone else.
>
> The project does not accept contributions; if you want something changed for personal use, you are more than welcome to fork it and modify to your own needs.

## Overview

This marketplace provides plugins that automatically inject best practices and coding guidelines whenever you work on projects in specific languages. Each plugin uses two complementary hooks:

- A `SessionStart` hook that adds a lightweight pointer (`CLAUDE_.md`) listing the available context files.
- A `PreToolUse` hook that **deterministically** injects the full guideline files the moment you edit a matching file (e.g. a `.py` edit pulls in the Python conventions). This is pure rule evaluation — no LLM decides relevance — and each context is injected at most once per compaction window, verified by scanning the conversation transcript. This ensures less sophisticated models still receive the right context without bloating it with rules they don't need.

## Prerequisites

- **Python 3**: All plugins require Python 3 to be installed and available in your PATH.
- **Claude Code**: These plugins are designed for use with Claude Code.

## Available Plugins

### Core Context (`core-context`)

Injects global, language-agnostic coding-rule files from `~/.claude/additional-context/` based on what you are doing:

- **On editing any recognized code file**: `code-fundamentals.md` and `narrative-code-flow.md`; plus `software-engineering.md` when a project marker (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, …) is found in the file's ancestor directories.
- **On running a shell command**: `terminal-tool-usage.md`; plus `linting.md` when the command invokes a known linter/formatter (`ruff`, `eslint`, `prettier`, `mypy`, `cargo clippy`, `shellcheck`, `terraform fmt`, …).

**Best for**: applying your personal global coding rules across every language. Requires the corresponding files to exist under `~/.claude/additional-context/`.

### Python (`python`)

Injects Python coding conventions and advanced software engineering patterns:

**Conventions:**

- Strict typing with type hints and generic types
- Modern Python idioms (`pathlib`, f-strings, dataclasses, `Protocol`s)
- Dependency management with `uv` and `pyproject.toml`
- Pythonic error handling ("ask forgiveness, not permission")
- Declarative vs imperative code patterns
- Full-object assertions in pytest

**Engineering:**

- Behavioral testing over structural testing
- Type discrimination at ingestion with error wrapping
- Encapsulating external resources in client protocols

**Best for**: Python 3.10+ projects

### TypeScript (`typescript`)

Injects TypeScript coding conventions and advanced software engineering patterns:

**Conventions:**

- Required use of TypeScript (no untyped JavaScript)
- Strict typing (no `any`, use `unknown` when necessary)
- Declarative vs imperative code patterns
- Proper resource cleanup with try/finally

**Engineering:**

- Behavioral testing over structural testing
- Type discrimination at ingestion with error wrapping
- Type guards and discriminated unions

**Best for**: TypeScript/JavaScript projects

### Rust (`rust`)

Injects Rust coding conventions and advanced software engineering patterns:

**Conventions:**

- Declarative vs imperative code patterns (iterator chains)
- RAII patterns with Drop trait for resource cleanup
- Custom RAII guards for transactions and resources

**Engineering:**

- Type discrimination at ingestion using `serde` tagged enums
- Pattern matching for type-specific logic

**Best for**: Rust projects and CLI tools

### Go (`golang`)

Injects Go conventions following Effective Go principles:

- Code style and formatting (`gofmt`, naming conventions, acronym consistency)
- Package organization (single responsibility, avoiding util packages)
- Error handling (wrapping with context, error chains, sentinel errors)
- Interfaces and types (define where consumed, accept interfaces/return structs)
- Concurrency patterns (goroutines, channels, context propagation)
- Context best practices (first parameter, never store in structs)

**Best for**: Go projects and services

### GitHub Actions (`gha`)

Injects GitHub Actions workflow conventions:

- Security: avoid direct context variable substitution in scripts (use environment variables)
- Reusability: search for existing reputable actions before reimplementing common functionality

**Best for**: Repositories with `.github/workflows/` CI/CD pipelines

### Fish (`fish`)

Injects Fish shell scripting conventions focused on bash/zsh compatibility issues:

- **Critical:** No heredoc support (`<< EOF ... EOF`) - use multi-line strings with pipes instead
- Variable assignment and usage (`set`, `set -l`, `set -x`, `set -Ux`)
- Fish paths as lists (not colon-separated strings)
- Command substitution syntax (`set value (command)`)
- Redirection patterns (`&>` for stdout and stderr)
- Conditional expressions (`test`/`[`, no `[[`, close with `end` not `fi`)

**Best for**: Fish shell script development and configuration

### Terraform/OpenTofu (`tf`)

Injects Terraform/OpenTofu infrastructure-as-code conventions:

- Tool preference: prefer OpenTofu for new projects, use existing tool for existing projects
- Version management: bounded version constraints (`>= 1.10, < 1.16`)
- Provider configuration: pessimistic version pinning (`~>`), no hardcoded credentials
- Module structure: standard file layout (`main.tf`, `variables.tf`, `outputs.tf`, etc.)
- Naming conventions: `snake_case`, descriptive names, `enable_`/`is_` boolean prefixes
- Variables and outputs: always include `type` and `description`, use validation blocks
- Data sources over hardcoding: look up existing infrastructure
- State management: remote backends with locking, separate state per environment
- Security: no secrets in code/state, `sensitive = true` for sensitive values
- Testing: built-in `terraform test`/`tofu test` framework with behavioral assertions
- Expressions: `for_each` over `count`, use `locals` for repeated expressions

**Best for**: Terraform/OpenTofu infrastructure-as-code projects (versions 1.10+)

### Browser (`browser`)

Injects `sandbox-interop.md`, guidance for running Chromium-based tools (Playwright, Vitest browser mode, Puppeteer, `playwright-cli`) under the Claude Code sandbox on macOS:

- Why multi-process Chromium dies in the sandbox, and which settings don't help
- Option A: single-process Chromium with everything sandboxed
- Option B: a browser server outside the sandbox with sandboxed clients, and its per-project permission setup
- Injected when editing a browser-runner config, before browser commands, and when a tool result or failure shows a known sandbox signature

**Best for**: Projects that run browser tests or browser automation from sandboxed sessions

## Installation

### 1. Add this marketplace to Claude Code

```bash
/plugin marketplace add /Users/igor/Documents/dev/cc-plugins
```

### 2. Install plugins you need

Install one or more plugins:

```bash
/plugin install core-context@cc-plugins
/plugin install python@cc-plugins
/plugin install typescript@cc-plugins
/plugin install rust@cc-plugins
/plugin install golang@cc-plugins
/plugin install gha@cc-plugins
/plugin install fish@cc-plugins
/plugin install tf@cc-plugins
```

### 3. Enable plugins in your projects

Navigate to a project directory and enable the relevant plugin:

```bash
cd ~/my-python-project
/plugin enable python
```

Or enable globally if you want guidelines available in all sessions:

```bash
/plugin enable python --global
```

## How It Works

Each plugin contains:

- A `SessionStart` hook that runs when you start a session and injects the plugin's `CLAUDE_.md` pointer.
- A `PreToolUse` hook (`scripts/<name>-context-inject.py`) that fires on `Edit`/`Write`/`NotebookEdit` (and `Bash` for `core-context`). It reads the plugin's `contexts/rules.json`, matches the edited file's extension / path / project markers (or the command, for Bash rules), and injects the matching context file(s).
- `contexts/rules.json` — a declarative mapping of trigger conditions to context files. The injector script's **content** is byte-identical across all plugins (it derives everything from `${CLAUDE_PLUGIN_ROOT}`); only its **filename** differs per plugin — Claude Code deduplicates hook commands per event by command name, so each copy must be uniquely named (the same reason the `<name>-session-start.py` scripts are). Only `rules.json` varies in substance.

**Deduplication**: before injecting, the injector script streams the conversation transcript and skips any context already loaded since the last compaction boundary. It recognizes prior injections (by the `Contents of <path>:` sentinel) as well as cases where the model already read the file itself — via the `Read` tool (relative paths resolved against the transcript entry's own `cwd`) or a Bash pager command (`cat`/`head`/`tail`/`less`/`more`/`bat`) naming the file. Any hook failure exits cleanly without blocking the tool call.

When you edit a matching file in a project with an enabled plugin, Claude automatically receives the relevant coding guidelines without any manual intervention.

## Usage Tips

- **Enable project-specific plugins**: Use `/plugin enable <name>` in each project directory to only inject relevant guidelines
- **Check active plugins**: Use `/plugin list` to see which plugins are enabled
- **Verify hook execution**: Enable verbose mode (Ctrl+O) to see the `SessionStart` hook output
- **Update plugins**: Use `/plugin update <name>@cc-plugins` to get the latest guidelines

## Development

To modify or add plugins:

```
   plugins/<name>/
   ├── CLAUDE_.md                  # SessionStart pointer; lists additional contexts for progressive disclosure
   ├── contexts/
   │   ├── conventions.md          # Coding conventions
   │   ├── engineering.md          # Engineering practices (optional)
   │   ╰── rules.json              # Declarative trigger→context map for the PreToolUse hook
   ├── hooks/
   │   ╰── hooks.json              # Hook configuration (SessionStart + PreToolUse)
   ╰── scripts/
       ├── <name>-session-start.py  # SessionStart script (unique name per plugin)
       ╰── <name>-context-inject.py # PreToolUse injector (unique name, byte-identical content)
```

3. After changes, validate:
   ```bash
   /plugin validate .
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Individual plugin content is based on community best practices, official documentation, and established coding conventions.
