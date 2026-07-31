#!/usr/bin/env python3
"""UserPromptSubmit hook: inject the plan-document conventions while in plan mode.

Fires on every prompt but does nothing unless ``permission_mode`` is ``"plan"``.
The conventions file is injected at most once per compaction window, verified by
scanning the conversation transcript for the ``Contents of <path>:`` sentinel —
the same dedup pass the context-injector plugins use. Any failure exits 0 with no
output so a hook error never blocks the prompt.
"""
import json
import os
import re
import sys
from pathlib import Path

CONTEXT_FILE = "contexts/plan-document-conventions.md"

# Bash commands that constitute "reading" a file's contents into the conversation.
PAGER_RE = re.compile(r"\b(cat|head|tail|less|more|bat)\b")


def abs_path(file_path, cwd):
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(cwd) / p
    return os.path.normpath(str(p)).replace(os.sep, "/")


def dedup(needed, transcript_path):
    """Return the subset of ``needed`` (abs path strings) not yet seen since the
    last compaction boundary in the transcript."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return set(needed)
    seen = set()
    sentinels = {p: f"Contents of {p}:" for p in needed}
    # Cheap substring gate before JSON parsing. The absolute path covers our own
    # sentinel, absolute Reads, and Bash reads that name the file absolutely; the
    # basename additionally admits Reads that used a path relative to their cwd
    # (which read_tool_use_of then resolves and confirms exactly).
    basenames = {p: os.path.basename(p) for p in needed}
    with open(transcript_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"compact_boundary"' in line:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("type") == "system" and obj.get("subtype") == "compact_boundary":
                    seen.clear()
                continue
            for p in needed:
                if p in seen:
                    continue
                if p not in line and basenames[p] not in line:
                    continue
                if sentinels[p] in line:
                    seen.add(p)
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if read_tool_use_of(obj, p):
                    seen.add(p)
    return set(needed) - seen


def read_tool_use_of(obj, path):
    """True if this transcript entry evidences the agent already reading ``path``.

    Detects both a ``Read`` tool_use of the file and a ``Bash`` pager-style read
    (``cat``/``head``/…). Relative ``Read`` paths are resolved against the
    entry's own ``cwd`` — never against ``/`` — and treated as unmatched if the
    entry carries no ``cwd``.
    """
    message = obj.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    entry_cwd = obj.get("cwd")
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name")
        inp = block.get("input") or {}
        if name == "Read":
            fp = inp.get("file_path")
            if not fp:
                continue
            if Path(fp).is_absolute():
                if abs_path(fp, "/") == path:
                    return True
            elif entry_cwd and abs_path(fp, entry_cwd) == path:
                return True
        elif name == "Bash":
            command = inp.get("command")
            if command and path in command and PAGER_RE.search(command):
                return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("permission_mode") != "plan":
            return

        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
        context = Path(plugin_root) / CONTEXT_FILE
        if not context.is_file():
            return
        resolved = context.resolve()
        key = str(resolved)

        if key not in dedup([key], data.get("transcript_path")):
            return

        print(
            json.dumps(
                {
                    "systemMessage": f"cc-plugins-igorlabworks/planning: {resolved.name} added to context.",
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": f"Contents of {key}:\n\n{resolved.read_text()}",
                    },
                }
            )
        )
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
