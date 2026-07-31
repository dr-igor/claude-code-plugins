#!/usr/bin/env python3
"""PreToolUse/PostToolUse hook: dispatch the edit event to `belphegor inspect`.

Resolves the project-relative config (overridable via ``QUALITY_INSPECTOR_CONFIG``)
and locates the belphegor executable (``BELPHEGOR_BIN`` -> ``PATH``), then execs
``belphegor inspect <abs-config>`` so the hook's stdin/stdout/stderr and belphegor's
exit code all pass through untouched. belphegor reads the hook JSON on stdin and maps
its resolution to an exit code (0 = clean, 2 = findings on stderr, 1 = dispatch failed).

Fails open: if the config or executable is missing, exit 0 silently so an edit is never
blocked by a packaging/config problem. The SessionStart hook warns about the absence.
"""
import os
import shutil
import sys
from pathlib import Path

CONFIG_ENV = "QUALITY_INSPECTOR_CONFIG"
BIN_ENV = "BELPHEGOR_BIN"
DEFAULT_CONFIG_NAME = "quality-inspector.yaml"


def resolve_config():
    override = os.environ.get(CONFIG_ENV)
    return Path(override).expanduser() if override else Path.cwd() / DEFAULT_CONFIG_NAME


def resolve_bin():
    override = os.environ.get(BIN_ENV)
    if override and os.access(override, os.X_OK):
        return override
    return shutil.which("belphegor")


def main():
    config = resolve_config()
    if not config.is_file():
        sys.exit(0)  # fail open; startup hook warns
    bin_path = resolve_bin()
    if not bin_path:
        sys.exit(0)  # fail open; startup hook warns
    try:
        os.execv(bin_path, [bin_path, "inspect", str(config.resolve())])
    except OSError:
        sys.exit(0)


if __name__ == "__main__":
    main()
