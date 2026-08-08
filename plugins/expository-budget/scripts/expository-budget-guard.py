#!/usr/bin/env python3

from __future__ import annotations

import json
import sys

from expository_scan import BUDGET_NAME

REASON = (
    f"{BUDGET_NAME} records what the codebase is allowed to say in prose, and it is the "
    "user's file: nothing Claude Code does may raise a ceiling, so this edit is refused "
    "whatever it contains. Ceilings fall on their own as comments and docstrings are "
    "removed. If a comment has genuinely earned its place, stop and ask the user to raise "
    "its number by hand."
)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    try:
        if targets_budget(event):
            deny()
    except (OSError, ValueError):
        return


def targets_budget(event: dict[str, object]) -> bool:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    if event.get("tool_name") == "Bash":
        command = tool_input.get("command")
        return isinstance(command, str) and BUDGET_NAME in command
    named = tool_input.get("file_path") or tool_input.get("notebook_path")
    return isinstance(named, str) and named.endswith(BUDGET_NAME)


def deny() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }))


if __name__ == "__main__":
    main()
