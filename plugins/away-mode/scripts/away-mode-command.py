#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from away_mode_state import (
    Mode,
    SessionState,
    frontmost_bundle_id,
    parse_duration,
    set_mode,
)

PREFIX = "cc-plugins-igorlabworks/away-mode"
COMMAND_LOG_ENV = "AWAY_MODE_COMMAND_LOG"
DEFAULT_COMMAND_LOG = Path.home() / ".claude" / "away-mode" / "commands.jsonl"
COMMAND_NAME_PATTERN = re.compile(r"(^|:)(?P<mode>away|here|auto)$")
REBINDING_MODES = ("here", "auto")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    mode = mode_from_command_name(str(event.get("command_name") or ""))
    record_invocation(event, mode)
    if mode is None:
        return
    try:
        announcement = apply_mode(
            str(event.get("session_id") or ""),
            mode,
            str(event.get("command_args") or ""),
        )
    except (OSError, ValueError):
        return
    print(json.dumps({"decision": "block", "reason": announcement}))


def mode_from_command_name(command_name: str) -> Mode | None:
    found = COMMAND_NAME_PATTERN.search(command_name)
    return cast(Mode, found.group("mode")) if found else None


def apply_mode(session_id: str, mode: Mode, command_args: str) -> str:
    state = set_mode(
        session_id,
        mode,
        until=expiry_for(mode, command_args),
        host_bundle_id=frontmost_bundle_id() if mode in REBINDING_MODES else None,
    )
    return f"{PREFIX}: {described(state)}"


def expiry_for(mode: Mode, command_args: str) -> datetime | None:
    if mode != "here" or not command_args.split():
        return None
    duration = parse_duration(command_args.split()[0])
    return None if duration is None else datetime.now(timezone.utc) + duration


def described(state: SessionState) -> str:
    if state.mode == "here" and state.until is not None:
        return f"HERE until {state.until.astimezone():%H:%M}, then presence decides"
    if state.mode == "here":
        return "HERE, prompts will wait for you"
    if state.mode == "away":
        return "AWAY, prompts will be denied until you return"
    return "AUTO, presence decides"


def record_invocation(event: dict[str, object], mode: Mode | None) -> None:
    try:
        log = resolve_command_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "session_id": event.get("session_id"),
                        "expansion_type": event.get("expansion_type"),
                        "command_name": event.get("command_name"),
                        "command_args": event.get("command_args"),
                        "mode": mode,
                    }
                )
                + "\n"
            )
    except (OSError, ValueError):
        return


def resolve_command_log() -> Path:
    override = os.environ.get(COMMAND_LOG_ENV)
    return Path(override).expanduser() if override else DEFAULT_COMMAND_LOG


if __name__ == "__main__":
    main()
