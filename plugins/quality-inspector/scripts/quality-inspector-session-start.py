#!/usr/bin/env python3
"""SessionStart hook: warn once, up front, if the quality inspector can't run.

Emits a ``systemMessage`` if the belphegor executable can't be located or the project
config is absent at the expected location. Stays silent (exit 0, no output) when both
are present. Wrapped in a fail-open guard so a hook error never blocks the session.
"""
import json
import os
import shutil
import sys
from pathlib import Path

CONFIG_ENV = "QUALITY_INSPECTOR_CONFIG"
BIN_ENV = "BELPHEGOR_BIN"
DEFAULT_CONFIG_NAME = "quality-inspector.yaml"
PREFIX = "cc-plugins-igorlabworks/quality-inspector"


def resolve_config():
    override = os.environ.get(CONFIG_ENV)
    return Path(override).expanduser() if override else Path.cwd() / DEFAULT_CONFIG_NAME


def resolve_bin():
    override = os.environ.get(BIN_ENV)
    if override and os.access(override, os.X_OK):
        return override
    return shutil.which("belphegor")


def main():
    try:
        problems = []
        if resolve_bin() is None:
            problems.append(
                "belphegor executable not found "
                f"(set {BIN_ENV}, add the pipx bin dir to PATH, or `pipx install belphegor`)"
            )
        config = resolve_config()
        if not config.is_file():
            problems.append(f"config not found at {config} (create it or set {CONFIG_ENV})")
        if problems:
            msg = "; ".join(problems) + ". Quality inspection is disabled until resolved."
            print(json.dumps({"systemMessage": f"{PREFIX}: {msg}"}))
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
