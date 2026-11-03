#!/usr/bin/env python3
"""PermissionRequest hook: deny every Bash permission prompt.

``PermissionRequest`` fires only when a permission dialog is about to be shown, so
commands that never prompt (sandboxed, read-only, or matching an allow rule) never reach
this hook, and the ``Bash`` matcher in ``hooks.json`` leaves every other tool's dialog
alone. ``interrupt`` is left unset so Claude keeps working rather than stopping.

The dialog's "always allow" options arrive as ``permission_suggestions``. They are not
forwarded to Claude; they are appended to a denial log for the user to review.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_ENV = "AWAY_MODE_LOG"
DEFAULT_LOG = Path.home() / ".claude" / "away-mode" / "denials.jsonl"
PREFIX = "cc-plugins-igorlabworks/away-mode"

DENIAL_MESSAGE = (
    "If you see this, the requested tool use resulted in a permission prompt. This "
    "session is autonomous and not monitored. You can see if you can achieve your goals "
    "by requesting simpler tool usages. If you are blocked on completing a particular "
    "task by this rejection, log it and report it in your response in a section titled "
    '"Blocking Permission Rejections", briefly describing what you were trying to '
    "achieve by the command, to what end, and what minimal sandbox setting (preferred) "
    "or Allow permission would unblock you. These will be reviewed, applied or not, and "
    "you will be directed on how to continue."
)


def main() -> None:
    event = read_event()
    record_denial(event)
    print(json.dumps(denial(str(event.get("tool_name") or "tool"))))


def read_event() -> dict[str, object]:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return {}
    return event if isinstance(event, dict) else {}


def record_denial(event: dict[str, object]) -> None:
    try:
        log = resolve_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "session_id": event.get("session_id"),
                        "cwd": event.get("cwd"),
                        "tool_name": event.get("tool_name"),
                        "tool_input": event.get("tool_input"),
                        "permission_suggestions": event.get("permission_suggestions"),
                    }
                )
                + "\n"
            )
    except OSError:
        return


def resolve_log() -> Path:
    override = os.environ.get(LOG_ENV)
    return Path(override).expanduser() if override else DEFAULT_LOG


def denial(tool_name: str) -> dict[str, object]:
    return {
        "systemMessage": f"{PREFIX}: denied {tool_name}.",
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": DENIAL_MESSAGE},
        },
    }


if __name__ == "__main__":
    main()
