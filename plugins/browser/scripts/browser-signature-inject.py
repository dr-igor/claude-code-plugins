#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

CONTEXT = "contexts/sandbox-interop.md"

SIGNATURES = [
    (
        "Chromium could not register its Mach rendezvous service",
        re.compile(
            r"(bootstrap_check_in|MachPortRendezvousServer)[^\n]*Permission denied"
        ),
    ),
    (
        "Chromium could not lock its profile directory",
        re.compile(r"Failed to create a ProcessSingleton"),
    ),
    (
        "a Unix socket bind was refused",
        re.compile(r"listen EPERM: operation not permitted [^\s\"]+\.sock"),
    ),
    (
        "the browser closed while opening a page",
        re.compile(r"Target page, context or browser has been closed"),
    ),
]


def result_text(data):
    if data.get("hook_event_name") == "PostToolUseFailure":
        return data.get("error") or ""
    return "\n".join(strings_in(data.get("tool_response")))


def strings_in(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings_in(item)]
    if isinstance(value, list):
        return [text for item in value for text in strings_in(item)]
    return []


def matched_labels(text):
    return [label for label, pattern in SIGNATURES if pattern.search(text)]


def already_loaded(context_path, transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
    sentinel = f"Contents of {context_path}:"
    read_marker = json.dumps(context_path)
    loaded = False
    with open(transcript_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"compact_boundary"' in line:
                loaded = False
            elif sentinel in line or (read_marker in line and '"Read"' in line):
                loaded = True
    return loaded


def is_reading_context(data, context_path):
    file_path = (data.get("tool_input") or {}).get("file_path")
    return bool(file_path) and Path(file_path).resolve() == Path(context_path)


def main():
    try:
        data = json.load(sys.stdin)
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
        context_path = str((Path(plugin_root) / CONTEXT).resolve())
        if is_reading_context(data, context_path):
            return
        labels = matched_labels(result_text(data))
        if not labels:
            return
        note = f"This tool result matches a known browser-in-sandbox failure: {'; '.join(labels)}."
        if already_loaded(context_path, data.get("transcript_path")):
            context = f"{note} See {context_path}, already in context."
            message = f"cc-plugins-igorlabworks/browser: matched {', '.join(labels)}."
        else:
            context = f"{note}\n\nContents of {context_path}:\n\n{Path(context_path).read_text()}"
            message = (
                "cc-plugins-igorlabworks/browser: sandbox-interop.md added to context."
            )
        print(
            json.dumps(
                {
                    "systemMessage": message,
                    "hookSpecificOutput": {
                        "hookEventName": data.get("hook_event_name", "PostToolUse"),
                        "additionalContext": context,
                    },
                }
            )
        )
    except (OSError, ValueError, TypeError, AttributeError):
        sys.exit(0)


if __name__ == "__main__":
    main()
