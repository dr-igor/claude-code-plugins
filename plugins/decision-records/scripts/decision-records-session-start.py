#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
content_file = Path(plugin_root) / "CLAUDE_.md"

if not content_file.is_file():
    sys.exit(0)

absolute_path = content_file.resolve()
content = content_file.read_text()
formatted_content = f"Contents of {absolute_path}:\n\n{content}"

print(
    json.dumps(
        {
            "systemMessage": f"cc-plugins-igorlabworks/decision-records: {absolute_path} added to context.",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": formatted_content,
            },
        }
    )
)
