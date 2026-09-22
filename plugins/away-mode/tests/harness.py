#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
STATUSLINE = Path(__file__).resolve().parents[3] / "statusline" / "statusline.py"
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
BADGE_PATTERN = re.compile(r"\[(?P<badge>(?:HERE|AWAY)[^\]]*)\]")
FIXTURE = Path(os.environ.get("TMPDIR", "/tmp")) / "away-mode-harness"
SESSIONS = FIXTURE / "sessions"
STUB_BIN = FIXTURE / "bin"
LOG = FIXTURE / "denials.jsonl"
SESSION = "session-under-test"

LOCKED_REGISTRY_LINE = (
    '      "IOConsoleUsers" = ({"kCGSSessionOnConsoleKey"=Yes,"kSCSecuritySessionID"=100023,'
    '"kCGSSessionSystemSafeBoot"=No,"kCGSessionLoginDoneKey"=Yes,"kCGSSessionIDKey"=257,'
    '"kCGSSessionUserNameKey"="igor","kCGSSessionGroupIDKey"=20,'
    '"CGSSessionUniqueSessionUUID"="4CF7257A-523A-4833-8B8D-55F6C866C366",'
    '"CGSSessionScreenLockedTime"=1789877549,"kCGSessionLongUserNameKey"="Igor Petrik",'
    '"CGSSessionScreenIsLocked"=Yes,"kCGSSessionAuditIDKey"=100023,'
    '"kCGSSessionLoginwindowSafeLogin"=No,"kCGSSessionUserIDKey"=501})'
)

UNLOCKED_REGISTRY_LINE = (
    '      "IOConsoleUsers" = ({"kCGSSessionOnConsoleKey"=Yes,"kSCSecuritySessionID"=100023,'
    '"kCGSSessionSystemSafeBoot"=No,"kCGSessionLoginDoneKey"=Yes,"kCGSSessionIDKey"=257,'
    '"kCGSSessionUserNameKey"="igor","kCGSSessionGroupIDKey"=20,'
    '"CGSSessionUniqueSessionUUID"="4CF7257A-523A-4833-8B8D-55F6C866C366",'
    '"kCGSessionLongUserNameKey"="Igor Petrik","kCGSSessionAuditIDKey"=100023,'
    '"kCGSSessionLoginwindowSafeLogin"=No,"kCGSSessionUserIDKey"=501})'
)

IOREG_STUB = f"""#!/bin/sh
if [ "$AWAY_MODE_STUB_IOREG" = "fail" ]; then exit 1; fi
if [ "$AWAY_MODE_STUB_LOCKED" = "yes" ]; then
  cat <<'LINE'
{LOCKED_REGISTRY_LINE}
LINE
else
  cat <<'LINE'
{UNLOCKED_REGISTRY_LINE}
LINE
fi
"""

LSAPPINFO_STUB = """#!/bin/sh
if [ "$AWAY_MODE_STUB_LSAPPINFO" = "fail" ]; then exit 1; fi
if [ "$1" = "front" ]; then echo "ASN:0x0-0x1a01a:"; exit 0; fi
printf '"CFBundleIdentifier"="%s"\\n' "$AWAY_MODE_STUB_FRONT"
"""

failures: list[str] = []


def main() -> None:
    build_fixture()

    print("mode resolution")
    check("no state file asks while present", decide(None), "ask")
    check("no state file denies while locked", decide(None, locked="yes"), "deny")
    check("away denies", decide({"mode": "away"}), "deny")
    check("here asks", decide({"mode": "here"}), "ask")
    check("unknown mode falls back to default", decide({"mode": "nonsense"}), "ask")
    check("corrupt state file asks", decide_with_raw("{not json"), "ask")
    check("empty state file asks", decide_with_raw(""), "ask")

    print("here expiry")
    check("future expiry asks", decide({"mode": "here", "until": stamp(60)}), "ask")
    check("past expiry falls back", decide({"mode": "here", "until": stamp(-60)}), "ask")
    check("expiry one second ahead asks", decide({"mode": "here", "until": stamp(1)}), "ask")
    check(
        "expired here falls back to presence, denying while locked",
        decide({"mode": "here", "until": stamp(-1)}, locked="yes"),
        "deny",
    )
    check(
        "unexpired here ignores the lock",
        decide({"mode": "here", "until": stamp(60)}, locked="yes"),
        "ask",
    )
    check(
        "away ignores presence entirely",
        decide({"mode": "away"}, front="com.example.Host"),
        "deny",
    )
    check("naive expiry is read as utc", decide({"mode": "here", "until": naive(-60)}), "ask")

    print("auto and detectors")
    bound = {"mode": "auto", "host_bundle_id": "com.example.Host"}
    check("auto focused asks", decide(bound, front="com.example.Host"), "ask")
    check("auto unfocused denies", decide(bound, front="com.other.App"), "deny")
    check("auto locked denies", decide(bound, front="com.example.Host", locked="yes"), "deny")
    check("auto with both detectors failing asks", decide(bound, ioreg="fail", lsappinfo="fail"), "ask")
    check("auto with focus detector failing asks", decide(bound, lsappinfo="fail"), "ask")
    check(
        "auto with lock detector failing still honors focus",
        decide(bound, front="com.other.App", ioreg="fail"),
        "deny",
    )
    check("auto unbound host ignores focus", decide({"mode": "auto"}, front="com.other.App"), "ask")
    check(
        "auto unbound host still honors lock",
        decide({"mode": "auto"}, locked="yes"),
        "deny",
    )
    check(
        "host override beats recorded binding",
        decide(bound, front="com.other.App", host_override="com.other.App"),
        "ask",
    )

    print("denial accounting")
    reset_log()
    write_state({"mode": "away", "denials": 4})
    permission_request()
    check("denial appends one log line", log_lines(), 1)
    check("denial increments the counter", read_state().get("denials"), 5)
    reset_log()
    write_state({"mode": "here", "denials": 0})
    permission_request()
    check("passthrough writes no log line", log_lines(), 0)
    check("passthrough leaves the counter alone", read_state().get("denials"), 0)

    print("session id handling")
    check("traversing session id asks", decide({"mode": "away"}, session="../escape"), "ask")
    check("slashed session id asks", decide({"mode": "away"}, session="a/b"), "ask")
    check("empty session id asks", decide({"mode": "away"}, session=""), "ask")
    check("an unusable session id writes nothing anywhere", escaping_writes(), [])

    print("commands")
    check("away command sets away", mode_and_expiry(command("away")), ("away", None))
    check("auto command sets auto", mode_and_expiry(command("auto")), ("auto", None))
    check("here command clears expiry", mode_and_expiry(command("here")), ("here", None))
    check("here command blocks expansion", command_decision("away-mode:here"), "block")
    check("bare command name works too", command_decision("here"), "block")
    check("the block reason names the mode", "HERE" in command_reason("away-mode:here"), True)
    check("here with minutes expires", expiry_minutes(command("here", "30m")), 30)
    check("here with bare number means minutes", expiry_minutes(command("here", "45")), 45)
    check("here with hours expires", expiry_minutes(command("here", "2h")), 120)
    check("here with seconds expires", expiry_minutes(command("here", "90s")), 1)
    check("here with nonsense stays indefinite", command("here", "banana")["until"], None)
    check("away ignores an argument", command("away", "30m")["until"], None)
    check("an unrelated command does not block", command_decision("deploy"), None)
    check("a command merely containing here does not block", command_decision("adhere"), None)

    print("host binding")
    write_state({"mode": "auto", "host_bundle_id": ""})
    session_hook("SessionStart", front="com.example.Bound")
    check("session start binds the host app", read_state().get("host_bundle_id"), "com.example.Bound")
    write_state({"mode": "auto", "host_bundle_id": "com.example.Stale"})
    command("here", front="com.example.Rebound")
    check("here rebinds the host app", read_state().get("host_bundle_id"), "com.example.Rebound")
    write_state({"mode": "auto", "host_bundle_id": "com.example.Kept"})
    command("away", front="com.example.Other")
    check("away leaves the binding alone", read_state().get("host_bundle_id"), "com.example.Kept")
    write_state({"mode": "auto", "host_bundle_id": "com.example.Kept"})
    session_hook("SessionStart", lsappinfo="fail")
    check("unreadable front app leaves the binding alone", read_state().get("host_bundle_id"), "com.example.Kept")

    print("session lifecycle")
    write_state({"mode": "away"})
    session_hook("SessionEnd", reason="other")
    check("session end clears state", state_path().exists(), False)
    write_state({"mode": "away"})
    session_hook("SessionEnd", reason="resume")
    check("resume keeps state", read_state().get("mode"), "away")

    print("atomicity")
    check("interleaved writes never expose a partial file", interleaved_reads_parse(), True)

    print("status line badge")
    if badge_runner() is None:
        print("  ....  skipped, uv or statusline.py not found")
    else:
        auto = {"mode": "auto", "host_bundle_id": "com.example.Host"}
        check("no state file, present", badge(None), "HERE")
        check("no state file, locked", badge(None, locked="yes"), "AWAY")
        check("auto, focused", badge(auto), "HERE")
        check("auto, other app frontmost", badge(auto, front="com.other.App"), "AWAY")
        check("auto, screen locked", badge(auto, locked="yes"), "AWAY")
        check("auto, focus detector fails", badge(auto, lsappinfo="fail"), "HERE")
        check("auto, lock detector fails", badge(auto, ioreg="fail"), "HERE")
        check(
            "away pinned outranks being present",
            badge({"mode": "away", "denials": 7}),
            "AWAY x7",
        )
        check(
            "here pinned outranks a locked screen",
            badge({"mode": "here"}, locked="yes"),
            "HERE",
        )
        check(
            "timed here shows its remaining minutes",
            badge({"mode": "here", "until": stamp(28 * 60)}, locked="yes"),
            "HERE 28m",
        )
        check(
            "expired here follows presence, away",
            badge({**auto, "mode": "here", "until": stamp(-60), "denials": 3},
                  front="com.other.App"),
            "AWAY x3",
        )
        check(
            "expired here follows presence, present",
            badge({**auto, "mode": "here", "until": stamp(-60), "denials": 3}),
            "HERE x3",
        )
        check("corrupt state file still renders", badge_with_raw("{not json"), "HERE")
        check("denial count is capped", badge({"mode": "away", "denials": 250}), "AWAY x99")

    print(f"{len(failures)} failure(s)" if failures else "all checks passed")
    sys.exit(1 if failures else 0)


def check(name: str, actual: object, expected: object) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: got {actual!r}, want {expected!r}")
        failures.append(name)


def build_fixture() -> None:
    shutil.rmtree(FIXTURE, ignore_errors=True)
    SESSIONS.mkdir(parents=True)
    STUB_BIN.mkdir(parents=True)
    for name, body in (("ioreg", IOREG_STUB), ("lsappinfo", LSAPPINFO_STUB)):
        stub = STUB_BIN / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)


def decide(record: dict[str, object] | None, *, session: str = SESSION, **stubs: str) -> str:
    clear_states()
    if record is not None:
        write_state(record, session=session)
    return behavior_of(permission_request(session=session, **stubs))


def decide_with_raw(content: str) -> str:
    clear_states()
    state_path().write_text(content, encoding="utf-8")
    return behavior_of(permission_request())


def permission_request(*, session: str = SESSION, **stubs: str) -> dict[str, object]:
    return run_hook(
        "away-mode-deny.py",
        {
            "session_id": session,
            "hook_event_name": "PermissionRequest",
            "cwd": str(FIXTURE),
            "tool_name": "Bash",
            "tool_input": {"command": "true"},
            "permission_suggestions": [],
        },
        **stubs,
    )[0]


def behavior_of(output: dict[str, object]) -> str:
    specific = output.get("hookSpecificOutput") or {}
    return (specific.get("decision") or {}).get("behavior", "")


def command(mode: str, argument: str = "", **stubs: str) -> dict[str, object]:
    run_command_hook(f"away-mode:{mode}", argument, **stubs)
    return read_state()


def mode_and_expiry(state: dict[str, object]) -> tuple[object, object]:
    return state.get("mode"), state.get("until")


def command_decision(command_name: str, argument: str = "") -> object:
    return run_command_hook(command_name, argument)[0].get("decision")


def command_reason(command_name: str, argument: str = "") -> str:
    return str(run_command_hook(command_name, argument)[0].get("reason") or "")


def escaping_writes() -> list[str]:
    clear_states()
    for stray in FIXTURE.glob("*.json"):
        stray.unlink()
    for unusable in ("../escape", "a/b", "", "!" * 8, "x" * 200):
        run_command_hook("away-mode:away", session=unusable)
    return sorted(
        [path.name for path in FIXTURE.glob("*.json")]
        + [path.name for path in SESSIONS.glob("*.json")]
    )


def run_command_hook(
    command_name: str, argument: str = "", *, session: str = SESSION, **stubs: str
) -> tuple[dict[str, object], int]:
    return run_hook(
        "away-mode-command.py",
        {
            "session_id": session,
            "hook_event_name": "UserPromptExpansion",
            "expansion_type": "slash_command",
            "command_name": command_name,
            "command_args": argument,
            "command_source": "plugin",
            "prompt": f"/{command_name} {argument}".strip(),
            "cwd": str(FIXTURE),
        },
        **stubs,
    )


def session_hook(event: str, *, reason: str = "other", **stubs: str) -> None:
    run_hook(
        "away-mode-session.py",
        {
            "session_id": SESSION,
            "hook_event_name": event,
            "source": "startup",
            "reason": reason,
            "cwd": str(FIXTURE),
        },
        **stubs,
    )


def run_hook(
    script: str,
    event: dict[str, object],
    *,
    locked: str = "no",
    front: str = "com.example.Host",
    ioreg: str = "ok",
    lsappinfo: str = "ok",
    host_override: str = "",
) -> tuple[dict[str, object], int]:
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        env=hook_env(
            locked=locked,
            front=front,
            ioreg=ioreg,
            lsappinfo=lsappinfo,
            host_override=host_override,
        ),
    )
    try:
        return json.loads(done.stdout), done.returncode
    except ValueError:
        return {}, done.returncode


def hook_env(
    *, locked: str, front: str, ioreg: str, lsappinfo: str, host_override: str
) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.update(
        {
            "PATH": f"{STUB_BIN}{os.pathsep}{env.get('PATH', '')}",
            "AWAY_MODE_SESSIONS": str(SESSIONS),
            "AWAY_MODE_LOG": str(LOG),
            "AWAY_MODE_COMMAND_LOG": str(FIXTURE / "commands.jsonl"),
            "AWAY_MODE_STUB_LOCKED": locked,
            "AWAY_MODE_STUB_FRONT": front,
            "AWAY_MODE_STUB_IOREG": ioreg,
            "AWAY_MODE_STUB_LSAPPINFO": lsappinfo,
        }
    )
    if host_override:
        env["AWAY_MODE_HOST_BUNDLE_ID"] = host_override
    return env


def write_state(record: dict[str, object], *, session: str = SESSION) -> None:
    complete = {
        "mode": "here",
        "until": None,
        "host_bundle_id": "",
        "denials": 0,
        "updated": stamp(0),
    }
    complete.update(record)
    path = state_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(complete), encoding="utf-8")


def read_state() -> dict[str, object]:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def state_path(session: str = SESSION) -> Path:
    return SESSIONS / f"{session}.json"


def clear_states() -> None:
    shutil.rmtree(SESSIONS, ignore_errors=True)
    SESSIONS.mkdir(parents=True, exist_ok=True)


def reset_log() -> None:
    LOG.unlink(missing_ok=True)


def log_lines() -> int:
    try:
        return len([line for line in LOG.read_text(encoding="utf-8").splitlines() if line])
    except OSError:
        return 0


def stamp(offset_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def naive(offset_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).replace(
        tzinfo=None
    ).isoformat()


def expiry_minutes(state: dict[str, object]) -> int | None:
    until = state.get("until")
    if not isinstance(until, str):
        return None
    remaining = datetime.fromisoformat(until) - datetime.now(timezone.utc)
    return round(remaining.total_seconds() / 60)


def badge(record: dict[str, object] | None, **stubs: str) -> str:
    clear_states()
    if record is not None:
        write_state(record)
    return rendered_badge(**stubs)


def badge_with_raw(content: str) -> str:
    clear_states()
    state_path().write_text(content, encoding="utf-8")
    return rendered_badge()


def rendered_badge(
    *,
    locked: str = "no",
    front: str = "com.example.Host",
    ioreg: str = "ok",
    lsappinfo: str = "ok",
) -> str:
    runner = badge_runner()
    if runner is None:
        return ""
    env = hook_env(
        locked=locked,
        front=front,
        ioreg=ioreg,
        lsappinfo=lsappinfo,
        host_override="",
    )
    env["AWAY_MODE_STATE_SCRIPT"] = str(SCRIPTS / "away_mode_state.py")
    done = subprocess.run(
        [runner, "run", str(STATUSLINE)],
        input=json.dumps(statusline_payload()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    found = BADGE_PATTERN.search(ANSI_PATTERN.sub("", done.stdout))
    return found.group("badge") if found else ""


def badge_runner() -> str | None:
    if not STATUSLINE.is_file():
        return None
    return shutil.which("uv")


def statusline_payload() -> dict[str, object]:
    return {
        "session_id": SESSION,
        "cwd": str(FIXTURE),
        "model": {"id": "claude-opus-5", "display_name": "Opus 5"},
        "thinking": {"enabled": False},
        "effort": {"level": "high"},
        "rate_limits": {},
        "context_window": {},
        "cost": {},
        "workspace": {},
    }


def interleaved_reads_parse() -> bool:
    write_state({"mode": "here"})
    for _ in range(40):
        run_command_hook("away-mode set away")
        if read_state() == {}:
            return False
    return True


if __name__ == "__main__":
    main()
