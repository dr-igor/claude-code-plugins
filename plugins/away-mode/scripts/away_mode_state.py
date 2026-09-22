#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, NamedTuple

Mode = Literal["away", "here", "auto"]
Decision = Literal["deny", "ask"]

SESSIONS_ENV = "AWAY_MODE_SESSIONS"
HOST_BUNDLE_ID_ENV = "AWAY_MODE_HOST_BUNDLE_ID"
SESSION_TTL_DAYS_ENV = "AWAY_MODE_SESSION_TTL_DAYS"

DEFAULT_SESSIONS = Path.home() / ".claude" / "away-mode" / "sessions"
DEFAULT_SESSION_TTL_DAYS = 7
DEFAULT_MODE: Mode = "auto"
EXPIRED_HERE_MODE: Mode = "auto"
MODES: tuple[Mode, ...] = ("away", "here", "auto")

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
BUNDLE_ID_PATTERN = re.compile(r'"CFBundleIdentifier"\s*=\s*"(?P<bundle_id>[^"]+)"')
SCREEN_LOCKED_PATTERN = re.compile(r'"CGSSessionScreenIsLocked"\s*=\s*(?P<value>\w+)')
DURATION_PATTERN = re.compile(r"^(?P<amount>\d+)\s*(?P<unit>[smhd]?)$", re.IGNORECASE)
DURATION_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}

CONSOLE_USERS_KEY = "IOConsoleUsers"
SCREEN_LOCK_COMMAND = ("ioreg", "-l", "-w", "0", "-d", "1")
FRONT_APP_COMMAND = ("lsappinfo", "front")
DETECTOR_TIMEOUT = 1.0


class SessionState(NamedTuple):
    mode: Mode = DEFAULT_MODE
    until: datetime | None = None
    host_bundle_id: str = ""
    denials: int = 0


def resolve_decision(session_id: str, *, now: datetime) -> Decision:
    return decision_for(load_state(session_id), now=now)


def decision_for(state: SessionState, *, now: datetime) -> Decision:
    mode = effective_mode(state, now=now)
    if mode == "away":
        return "deny"
    if mode == "here":
        return "ask"
    return "deny" if is_absent(state) is True else "ask"


def effective_mode(state: SessionState, *, now: datetime) -> Mode:
    if state.mode == "here" and state.until is not None and state.until <= now:
        return EXPIRED_HERE_MODE
    return state.mode


def is_absent(state: SessionState) -> bool | None:
    if is_screen_locked():
        return True
    return is_host_unfocused(host_bundle_id_of(state))


def is_screen_locked() -> bool | None:
    output = run_detector(SCREEN_LOCK_COMMAND)
    if output is None:
        return None
    line = next((l for l in output.splitlines() if CONSOLE_USERS_KEY in l), None)
    if line is None:
        return None
    locked = SCREEN_LOCKED_PATTERN.search(line)
    return locked is not None and locked.group("value") == "Yes"


def is_host_unfocused(host_bundle_id: str) -> bool | None:
    if not host_bundle_id:
        return None
    frontmost = frontmost_bundle_id()
    return None if frontmost is None else frontmost != host_bundle_id


def host_bundle_id_of(state: SessionState) -> str:
    return os.environ.get(HOST_BUNDLE_ID_ENV) or state.host_bundle_id


def frontmost_bundle_id() -> str | None:
    asn = run_detector(FRONT_APP_COMMAND)
    if not asn or not asn.strip():
        return None
    info = run_detector(("lsappinfo", "info", "-only", "bundleID", asn.strip()))
    if info is None:
        return None
    found = BUNDLE_ID_PATTERN.search(info)
    return found.group("bundle_id") if found else None


def run_detector(command: tuple[str, ...]) -> str | None:
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=DETECTOR_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def set_mode(
    session_id: str,
    mode: Mode,
    *,
    until: datetime | None = None,
    host_bundle_id: str | None = None,
) -> SessionState:
    state = load_state(session_id)
    updated = state._replace(
        mode=mode,
        until=until,
        host_bundle_id=(
            state.host_bundle_id if host_bundle_id is None else host_bundle_id
        ),
    )
    save_state(session_id, updated)
    return updated


def bind_host(session_id: str) -> None:
    bundle_id = frontmost_bundle_id()
    if bundle_id is None:
        return
    save_state(session_id, load_state(session_id)._replace(host_bundle_id=bundle_id))


def increment_denials(session_id: str) -> None:
    state = load_state(session_id)
    save_state(session_id, state._replace(denials=state.denials + 1))


def load_state(session_id: str) -> SessionState:
    path = session_path(session_id)
    if path is None:
        return SessionState()
    try:
        return state_from(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return SessionState()


def state_from(raw: object) -> SessionState:
    if not isinstance(raw, dict):
        return SessionState()
    mode = raw.get("mode")
    return SessionState(
        mode=mode if mode in MODES else DEFAULT_MODE,
        until=parse_timestamp(raw.get("until")),
        host_bundle_id=str(raw.get("host_bundle_id") or ""),
        denials=denial_count(raw.get("denials")),
    )


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def denial_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def parse_duration(text: str) -> timedelta | None:
    found = DURATION_PATTERN.match(text.strip())
    if found is None:
        return None
    return timedelta(
        **{DURATION_UNITS[found.group("unit").lower() or "m"]: int(found.group("amount"))}
    )


def save_state(session_id: str, state: SessionState) -> None:
    path = session_path(session_id)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, json.dumps(as_record(state)))
        prune_stale_sessions(path.parent)
    except (OSError, ValueError):
        return


def as_record(state: SessionState) -> dict[str, object]:
    return {
        "mode": state.mode,
        "until": state.until.isoformat() if state.until else None,
        "host_bundle_id": state.host_bundle_id,
        "denials": state.denials,
        "updated": datetime.now(timezone.utc).isoformat(),
    }


def write_atomically(path: Path, content: str) -> None:
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def clear_state(session_id: str) -> None:
    path = session_path(session_id)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def prune_stale_sessions(root: Path) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=session_ttl_days())
    for path in root.glob("*.json"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def session_ttl_days() -> int:
    try:
        return int(os.environ.get(SESSION_TTL_DAYS_ENV) or DEFAULT_SESSION_TTL_DAYS)
    except ValueError:
        return DEFAULT_SESSION_TTL_DAYS


def session_path(session_id: str) -> Path | None:
    if not SESSION_ID_PATTERN.match(session_id or ""):
        return None
    return sessions_root() / f"{session_id}.json"


def sessions_root() -> Path:
    override = os.environ.get(SESSIONS_ENV)
    return Path(override).expanduser() if override else DEFAULT_SESSIONS


def main() -> None:
    absent = is_absent(load_state(sys.argv[1] if len(sys.argv) > 1 else ""))
    print("unknown" if absent is None else "absent" if absent else "present")


if __name__ == "__main__":
    main()
