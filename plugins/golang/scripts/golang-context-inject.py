#!/usr/bin/env python3
"""Deterministically inject language/context files on matching tool calls.

PreToolUse hook. Reads a plugin-local ``contexts/rules.json`` describing which
context files to inject for which tools/files/commands, then injects any that
have not already been loaded into the conversation since the last compaction
boundary. No LLM/agent involvement — pure rule evaluation plus a transcript
dedup pass. Any failure exits 0 with no output so a hook error never breaks the
triggering tool call.
"""
import json
import os
import re
import sys
from pathlib import Path

MARKER_WALK_CAP = 30

# Bash commands that constitute "reading" a file's contents into the conversation.
PAGER_RE = re.compile(r"\b(cat|head|tail|less|more|bat)\b")


def load_stdin():
    return json.load(sys.stdin)


def target_from_input(tool_name, tool_input):
    """Return (path, command) for the triggering tool, either may be None."""
    if tool_name in ("Edit", "Write"):
        return tool_input.get("file_path"), None
    if tool_name == "NotebookEdit":
        return tool_input.get("notebook_path"), None
    if tool_name == "Bash":
        return None, tool_input.get("command")
    return None, None


def abs_path(file_path, cwd):
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(cwd) / p
    return os.path.normpath(str(p)).replace(os.sep, "/")


def has_marker(file_abs, markers):
    """Walk up from the file's directory looking for any project marker."""
    d = Path(file_abs).parent
    for _ in range(MARKER_WALK_CAP):
        for m in markers:
            if (d / m).exists():
                return True
        if (d / ".git").exists():
            return False
        if d.parent == d:
            return False
        d = d.parent
    return False


def rule_matches(rule, tool_name, file_abs, command):
    if tool_name not in rule.get("tools", []):
        return False

    exts = rule.get("extensions")
    path_regex = rule.get("path_regex")
    markers = rule.get("project_markers")
    command_regex = rule.get("command_regex")

    if exts or path_regex or markers:
        if not file_abs:
            return False
        lower = file_abs.lower()
        if exts and not any(lower.endswith(e.lower()) for e in exts):
            return False
        if path_regex and not re.search(path_regex, file_abs):
            return False
        if markers and not has_marker(file_abs, markers):
            return False

    if command_regex:
        if not command or not re.search(command_regex, command, re.IGNORECASE):
            return False

    return True


def resolve_context(context, plugin_root):
    p = Path(context).expanduser()
    if not p.is_absolute():
        p = Path(plugin_root) / p
    try:
        return p.resolve()
    except OSError:
        return None


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
        data = load_stdin()
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input") or {}
        cwd = data.get("cwd") or os.getcwd()
        transcript_path = data.get("transcript_path")

        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
        plugin_name = Path(plugin_root).name
        rules_file = Path(plugin_root) / "contexts" / "rules.json"
        if not rules_file.is_file():
            return
        rules = json.loads(rules_file.read_text()).get("rules", [])

        file_path, command = target_from_input(tool_name, tool_input)
        file_abs = abs_path(file_path, cwd) if file_path else None

        matched = []  # list of (abs_context_path_str, resolved_path)
        for rule in rules:
            if not rule_matches(rule, tool_name, file_abs, command):
                continue
            resolved = resolve_context(rule.get("context", ""), plugin_root)
            if resolved is None or not resolved.is_file():
                continue
            key = str(resolved)
            if key not in [m[0] for m in matched]:
                matched.append((key, resolved))

        if not matched:
            return

        needed = [m[0] for m in matched]
        inject_keys = dedup(needed, transcript_path)
        to_inject = [(k, r) for k, r in matched if k in inject_keys]
        if not to_inject:
            return

        blocks = []
        names = []
        for key, resolved in to_inject:
            blocks.append(f"Contents of {key}:\n\n{resolved.read_text()}")
            names.append(resolved.name)

        print(
            json.dumps(
                {
                    "systemMessage": f"cc-plugins-igorlabworks/{plugin_name}: {', '.join(names)} added to context.",
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": "\n\n---\n\n".join(blocks),
                    },
                }
            )
        )
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
