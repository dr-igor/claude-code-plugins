#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
content_file = Path(plugin_root) / "CLAUDE_.md"

if not content_file.is_file():
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": content_file.read_text(),
    }
}))
