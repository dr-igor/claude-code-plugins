#!/usr/bin/env python3

from __future__ import annotations

import json
import sys

from away_mode_state import bind_host, clear_state

RESUMABLE_END_REASONS = ("resume",)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    try:
        dispatch(event)
    except (OSError, ValueError):
        return


def dispatch(event: dict[str, object]) -> None:
    session_id = str(event.get("session_id") or "")
    if str(event.get("hook_event_name") or "") != "SessionEnd":
        bind_host(session_id)
        return
    if str(event.get("reason") or "") not in RESUMABLE_END_REASONS:
        clear_state(session_id)


if __name__ == "__main__":
    main()
