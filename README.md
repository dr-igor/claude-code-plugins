# Claude Code Plugin Marketplace

Personal marketplace for Claude Code plugins that inject language-specific coding guidelines into your development sessions.

## Overview

This marketplace provides plugins that automatically inject best practices and coding guidelines whenever you work on projects in specific languages. Each plugin uses a `SessionStart` hook to seamlessly add relevant context to your Claude Code sessions.

## Prerequisites

- **Python 3**: All plugins require Python 3 to be installed and available in your PATH.
- **Claude Code**: These plugins are designed for use with Claude Code.

## Available Plugins

### Python (`python`)
Injects Python coding guidelines covering PEP 8, type hints, modern Python patterns, async/await, testing with pytest, and more.

**Best for**: Python projects using modern Python 3.9+

### TypeScript (`typescript`)
Injects TypeScript best practices including strict mode patterns, type safety, async patterns, error handling, and testing conventions.

**Best for**: TypeScript/JavaScript projects

### Rust (`rust`)
Injects Rust idioms covering ownership patterns, error handling with thiserror/anyhow, async with tokio, iterator patterns, and testing.

**Best for**: Rust projects and CLI tools

### Go (`golang`)
Injects Go conventions from Effective Go, including error handling, interface design, concurrency patterns, and testing.

**Best for**: Go projects and services

### GitHub Actions (`gha`)
Injects GitHub Actions workflow best practices covering security, reusability, performance optimization, and debugging.

**Best for**: Repositories with `.github/workflows/` CI/CD pipelines

### Fish (`fish`)
Injects Fish shell scripting guidelines covering Fish-specific syntax, variable scoping, functions, completions, and patterns.

**Best for**: Fish shell script development and configuration

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
- **Verify hook execution**: Enable verbose mode (Ctrl+O) to see the SessionStart hook output
- **Update plugins**: Use `/plugin update <name>@cc-plugins` to get the latest guidelines

## Development

To modify or add plugins:

1. Each plugin lives in `plugins/<name>/`
2. Plugin structure:
   - `.claude-plugin/plugin.json` - Plugin manifest
   - `hooks/hooks.json` - Hook configuration
   - `scripts/session-start.py` - Hook execution script (must be executable)
   - `CLAUDE_.md` - The actual guidelines content

3. After changes, validate:
   ```bash
   /plugin validate .
   ```

## License

Personal use marketplace. Individual plugin content is based on community best practices and official documentation.
