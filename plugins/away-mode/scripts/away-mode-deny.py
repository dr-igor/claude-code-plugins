#!/usr/bin/env python3
"""PermissionRequest hook: deny permission prompts while a session is unattended.

``PermissionRequest`` fires only when a permission dialog is about to be shown, so this
hook sees exactly the calls that would have blocked on the user -- auto-allowed tools
(reads, read-only Bash, anything matching an allow rule) never reach it. Whether a call is
denied is decided per session, at the moment the prompt appears, by ``away_mode_state``:
``away`` denies, ``here`` passes through, and ``auto`` denies only on positive evidence
that the user is absent. Because this script is spawned fresh for every event, a mode
change takes effect on the very next prompt, mid-turn.

Each denial carries a standing message telling Claude to continue within the tools it
already has, and ``interrupt`` is left unset so Claude keeps working rather than stopping.

``ExitPlanMode`` and ``AskUserQuestion`` are exempt: the hook's matcher in ``hooks.json``
excludes them, so plan approval and direct questions still prompt and wait for the user.

The dialog's "always allow" options arrive as ``permission_suggestions``. They are not
forwarded to Claude -- they are appended to a denial log for the user to review later.

Fails open: on any unexpected error the hook exits 0, which shows the prompt as it would
have appeared without the plugin. A hook bug must never silently deny work -- which now
matters more, because a mode exists that can deny without having been asked to.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from away_mode_state import increment_denials, resolve_decision

LOG_ENV = "AWAY_MODE_LOG"
DEFAULT_LOG = Path.home() / ".claude" / "away-mode" / "denials.jsonl"
PREFIX = "cc-plugins-igorlabworks/away-mode"

DENIAL_MESSAGE = (
    "I would like you to keep trying to do your work, but I am away and cannot approve "
    "requests right now. If you see this, the requested tool use resulted in a permission "
    "prompt. You can see if you can achieve your goals by requesting simpler tool usages "
    "that will be auto allowed, or suggest the most limited allow rule you can think of "
    "that would allow you to perform the intent of your work without fully opening "
    "permissions, and I will review and possibly add it later to unblock you in future "
    "efforts. For now, do your best to continue the task you were asked to do within "
    "these constraints."
)


def main():
    try:
        data = json.load(sys.stdin)
        session_id = data.get("session_id") or ""
        if resolve_decision(session_id, now=datetime.now(timezone.utc)) == "ask":
            print(json.dumps(passthrough()))
            return
        record_denial(data)
        increment_denials(session_id)
        print(json.dumps(denial(data.get("tool_name") or "tool")))
    except Exception:
        sys.exit(0)


def passthrough():
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "ask"},
        }
    }


def record_denial(data):
    """Append the blocked call to the denial log. Best-effort: never changes the decision."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": data.get("session_id"),
            "cwd": data.get("cwd"),
            "tool_name": data.get("tool_name"),
            "tool_input": data.get("tool_input"),
            "permission_suggestions": data.get("permission_suggestions"),
        }
        log = resolve_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def resolve_log():
    override = os.environ.get(LOG_ENV)
    return Path(override).expanduser() if override else DEFAULT_LOG


def denial(tool_name):
    return {
        "systemMessage": f"{PREFIX}: denied {tool_name} (away mode).",
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "deny",
                "message": DENIAL_MESSAGE,
            },
        },
    }


if __name__ == "__main__":
    main()
