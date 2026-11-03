#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
DENY_SCRIPT = PLUGIN / "scripts" / "away-mode-deny.py"
HOOKS = PLUGIN / "hooks" / "hooks.json"
FIXTURE = Path(os.environ.get("TMPDIR", "/tmp")) / "away-mode-harness"
LOG = FIXTURE / "denials.jsonl"
SECTION_TITLE = '"Blocking Permission Rejections"'

BASH_REQUEST = {
    "session_id": "session-under-test",
    "hook_event_name": "PermissionRequest",
    "cwd": str(FIXTURE),
    "tool_name": "Bash",
    "tool_input": {"command": "curl https://example.com"},
    "permission_suggestions": [{"type": "addRules", "rules": [{"toolName": "Bash"}]}],
}

failures: list[str] = []


def main() -> None:
    build_fixture()

    print("registration")
    check("only PermissionRequest is hooked", sorted(registered_hooks()), ["PermissionRequest"])
    check("the matcher is Bash", permission_request_matchers(), ["Bash"])

    print("denial")
    output = deny(json.dumps(BASH_REQUEST))
    check("a Bash prompt is denied", behavior_of(output), "deny")
    check("the message names the report section", SECTION_TITLE in message_of(output), True)
    check("the message says the session is unmonitored", "not monitored" in message_of(output), True)
    check("the denial does not interrupt", "interrupt" in decision_of(output), False)
    check("the system message names the tool", output.get("systemMessage"), "cc-plugins-igorlabworks/away-mode: denied Bash.")
    check("malformed input still denies", behavior_of(deny("{not json")), "deny")
    check("non-object input still denies", behavior_of(deny("[]")), "deny")
    check("empty input still denies", behavior_of(deny("")), "deny")

    print("denial log")
    LOG.unlink(missing_ok=True)
    deny(json.dumps(BASH_REQUEST))
    check("a denial appends one log line", len(log_entries()), 1)
    check("the log keeps the tool input", log_entries()[0].get("tool_input"), BASH_REQUEST["tool_input"])
    check(
        "the log keeps the permission suggestions",
        log_entries()[0].get("permission_suggestions"),
        BASH_REQUEST["permission_suggestions"],
    )
    deny(json.dumps(BASH_REQUEST))
    check("a second denial appends rather than overwrites", len(log_entries()), 2)
    check(
        "an unwritable log still denies",
        behavior_of(deny(json.dumps(BASH_REQUEST), log=FIXTURE / "blocker" / "denials.jsonl")),
        "deny",
    )

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
    FIXTURE.mkdir(parents=True)
    (FIXTURE / "blocker").write_text("a file where the log directory should be", encoding="utf-8")


def registered_hooks() -> list[str]:
    return list(json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"])


def permission_request_matchers() -> list[str]:
    entries = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["PermissionRequest"]
    return [entry.get("matcher") for entry in entries]


def deny(stdin: str, *, log: Path = LOG) -> dict[str, object]:
    done = subprocess.run(
        [sys.executable, str(DENY_SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "AWAY_MODE_LOG": str(log)},
    )
    try:
        return json.loads(done.stdout)
    except ValueError:
        return {}


def decision_of(output: dict[str, object]) -> dict[str, object]:
    specific = output.get("hookSpecificOutput") or {}
    return specific.get("decision") or {}


def behavior_of(output: dict[str, object]) -> str:
    return str(decision_of(output).get("behavior", ""))


def message_of(output: dict[str, object]) -> str:
    return str(decision_of(output).get("message", ""))


def log_entries() -> list[dict[str, object]]:
    try:
        return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        return []


if __name__ == "__main__":
    main()
