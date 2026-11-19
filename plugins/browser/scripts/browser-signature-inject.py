#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

INTEROP = "contexts/sandbox-interop.md"
PLAYWRIGHT_CLI = "contexts/playwright-cli.md"

LOG_SUFFIXES = {".err", ".log", ".out", ".output", ".txt"}

SIGNATURES = [
    (
        "Chromium could not register its Mach rendezvous service",
        re.compile(r"MachPortRendezvousServer\.\d+: Permission denied"),
        INTEROP,
    ),
    (
        "Chromium could not lock its profile directory",
        re.compile(r"Failed to create a ProcessSingleton"),
        INTEROP,
    ),
    (
        "a Unix socket bind was refused",
        re.compile(r"listen EPERM: operation not permitted [^\s\"]+\.sock"),
        INTEROP,
    ),
    (
        "the browser closed while opening a page",
        re.compile(r"Target page, context or browser has been closed"),
        INTEROP,
    ),
    (
        "playwright-cli connected to a remote browser without isolated: true",
        re.compile(r"unable to connect to a browser that does not have any contexts"),
        PLAYWRIGHT_CLI,
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


def matches_by_context(text):
    matches = {}
    for label, pattern, context in SIGNATURES:
        if pattern.search(text):
            matches.setdefault(context, []).append(label)
    return matches


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


def is_scannable(data):
    if data.get("tool_name") != "Read":
        return True
    file_path = (data.get("tool_input") or {}).get("file_path") or ""
    return Path(file_path).suffix.lower() in LOG_SUFFIXES


def main():
    try:
        data = json.load(sys.stdin)
        if not is_scannable(data):
            return
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
        matches = matches_by_context(result_text(data))
        if not matches:
            return
        sections = [
            context_section(
                str((Path(plugin_root) / context).resolve()),
                labels,
                data.get("transcript_path"),
            )
            for context, labels in matches.items()
        ]
        print(
            json.dumps(
                {
                    "systemMessage": "\n".join(message for message, _ in sections),
                    "hookSpecificOutput": {
                        "hookEventName": data.get("hook_event_name", "PostToolUse"),
                        "additionalContext": "\n\n---\n\n".join(
                            context for _, context in sections
                        ),
                    },
                }
            )
        )
    except (OSError, ValueError, TypeError, AttributeError):
        sys.exit(0)


def context_section(context_path, labels, transcript_path):
    note = f"This tool result matches a known browser-in-sandbox failure: {'; '.join(labels)}."
    if already_loaded(context_path, transcript_path):
        return (
            f"cc-plugins-igorlabworks/browser: matched {', '.join(labels)}.",
            f"{note} See {context_path}, already in context.",
        )
    return (
        f"cc-plugins-igorlabworks/browser: {Path(context_path).name} added to context.",
        f"{note}\n\nContents of {context_path}:\n\n{Path(context_path).read_text()}",
    )


if __name__ == "__main__":
    main()
