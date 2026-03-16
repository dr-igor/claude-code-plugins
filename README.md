# Claude Code Plugin Marketplace

Personal marketplace for Claude Code plugins that inject language-specific coding guidelines into your development sessions.

## Overview

This marketplace provides plugins that automatically inject best practices and coding guidelines whenever you work on projects in specific languages. Each plugin uses a `SessionStart` hook to seamlessly add relevant context to your Claude Code sessions.

## Prerequisites

- **Python 3**: All plugins require Python 3 to be installed and available in your PATH.
- **Claude Code**: These plugins are designed for use with Claude Code.

## Available Plugins

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

## Installation

### 1. Add this marketplace to Claude Code

```bash
/plugin marketplace add /Users/igor/Documents/dev/cc-plugins
```

### 2. Install plugins you need

Install one or more plugins:

```bash
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

- A `SessionStart` hook that runs automatically when you start a Claude Code session
- A `CLAUDE_.md` file with language-specific guidelines
- A Python script that safely injects the guidelines as additional context

When you start a session in a project with an enabled plugin, Claude automatically receives the relevant coding guidelines without any manual intervention.

## Usage Tips

- **Enable project-specific plugins**: Use `/plugin enable <name>` in each project directory to only inject relevant guidelines
- **Check active plugins**: Use `/plugin list` to see which plugins are enabled
- **Verify hook execution**: Enable verbose mode (Ctrl+O) to see the `SessionStart` hook output
- **Update plugins**: Use `/plugin update <name>@cc-plugins` to get the latest guidelines

## Development

To modify or add plugins:

```
   plugins/<name>/
   ├── CLAUDE_.md                  # Context to be automatically injected; lists additional contexts for progressive disclosure
   ├── contexts/
   │   ├── conventions.md          # Coding conventions
   │   ╰── engineering.md          # Engineering practices (optional)
   ├── hooks/
   │   ╰── hooks.json              # Hook configuration
   ╰── scripts/
       ╰── <name>-session-start.py # Hook execution script (unique per plugin)
```

3. After changes, validate:
   ```bash
   /plugin validate .
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Individual plugin content is based on community best practices, official documentation, and established coding conventions.
