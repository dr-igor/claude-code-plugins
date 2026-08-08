#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "scripts"
BUDGET = ".claude/expository-content-budget.json"
REPO = Path(os.environ.get("TMPDIR", "/tmp")) / "expository-budget-harness"

SAMPLE_PY = '''"""Module."""

# a comment
# continued


def f(x):
    """Doc."""
    return x  # trailing
'''

SAMPLE_TS = """// one
// two
const x = 1; // trailing
/* block */
export const y = x / 2;
"""

SAMPLE_SH = """#!/usr/bin/env bash
echo hi  # trailing
"""

SAMPLE_GO = """//go:build linux

package main

func main() {} // done
"""

SAMPLE_RS = """fn f<'a>(s: &'a str) -> &'a str { s } // keep
"""

failures: list[str] = []


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: got {actual!r}, want {expected!r}")
        failures.append(name)


def run_hook(script: str, event: dict, overrides: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env.update(overrides or {})
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return {"code": done.returncode, "out": done.stdout.strip(), "err": done.stderr.strip()}


def session_start(source: str) -> dict:
    return run_hook(
        "expository-budget-session-start.py",
        {"session_id": "t", "cwd": str(REPO), "hook_event_name": "SessionStart", "source": source},
    )


def post_edit(relative: str) -> dict:
    return run_hook(
        "expository-budget-check.py",
        {
            "cwd": str(REPO),
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(REPO / relative)},
        },
    )


def post_bash(command: str) -> dict:
    return run_hook(
        "expository-budget-check.py",
        {
            "cwd": str(REPO),
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )


def reason_of(result: dict) -> str:
    return json.loads(result["out"]).get("reason", "") if result["out"] else ""


def budget() -> dict:
    return json.loads((REPO / BUDGET).read_text())


def write(relative: str, text: str) -> None:
    target = REPO / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def build_repo() -> None:
    if REPO.exists():
        shutil.rmtree(REPO)
    REPO.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(REPO)], check=True)
    write("sample.py", SAMPLE_PY)
    write("sample.ts", SAMPLE_TS)
    write("sample.sh", SAMPLE_SH)
    write("main.go", SAMPLE_GO)
    write("lib.rs", SAMPLE_RS)
    write("notes.md", "# A heading\n\nProse that must not count.\n")


def scan_counts() -> dict:
    sys.path.insert(0, str(SCRIPTS))
    import expository_scan

    return expository_scan.counts_for_tree(REPO)


print("scanner counts")
build_repo()
counts = scan_counts()
check("sample.py blocks", counts.get("sample.py"), 4)
check("sample.ts blocks", counts.get("sample.ts"), 3)
check("sample.sh blocks (shebang excluded)", counts.get("sample.sh"), 1)
check("main.go blocks (build tag excluded)", counts.get("main.go"), 1)
check("lib.rs blocks (lifetimes are not strings)", counts.get("lib.rs"), 1)
check("notes.md not scanned", "notes.md" in counts, False)

print("session start records the budget")
first = session_start("startup")
check("exit code", first["code"], 0)
check("budget written", budget().get("sample.py"), 4)
check("briefing emitted", "Expository-content budget active" in first["out"], True)
check("budget is untracked-aware", budget().get("lib.rs"), 1)

print("post-tool-use blocks an addition")
write("sample.py", SAMPLE_PY + "\n# one more\n")
blocked = post_edit("sample.py")
decision = json.loads(blocked["out"]) if blocked["out"] else {}
check("decision", decision.get("decision"), "block")
check("reason names the count", "holds 5" in decision.get("reason", ""), True)
check("budget unchanged by a refusal", budget().get("sample.py"), 4)

print("post-tool-use keeps firing until the budget is met")
still = post_edit("sample.py")
check("fires again", json.loads(still["out"]).get("decision"), "block")

print("post-tool-use ratchets down")
write("sample.py", '"""Module."""\n\n\ndef f(x):\n    return x  # trailing\n')
lowered = post_edit("sample.py")
check("no refusal", lowered["out"], "")
check("ceiling lowered", budget().get("sample.py"), 2)

print("a new file has no budget to spend")
write("fresh.py", '"""Fresh."""\n')
fresh = post_edit("fresh.py")
check("new file refused", json.loads(fresh["out"]).get("decision"), "block")
check("refusal names the zero budget", "fresh.py: holds 1, budget 0" in reason_of(fresh), True)

print("compaction does not absorb")
write("sample.ts", SAMPLE_TS + "// added by the agent\n")
compacted = session_start("compact")
check("ceiling held at the old value", budget().get("sample.ts"), 3)
check("new file not granted a budget", "fresh.py" in budget(), False)
check("unrelated ratchet still applies", budget().get("sample.py"), 2)

print("startup absorbs what changed between sessions")
session_start("startup")
check("ceiling absorbed", budget().get("sample.ts"), 4)
check("new file absorbed", budget().get("fresh.py"), 1)

print("nothing slips through a shell command")
write("snuck.py", '"""Written by a shell command."""\n\n# and a comment\n')
sneaky = post_bash("printf '...' > snuck.py")
check("shell-written file refused", json.loads(sneaky["out"]).get("decision"), "block")
check("refusal names it", "snuck.py: holds 2, budget 0" in reason_of(sneaky), True)
check("refusal counts the excess", "2 comment, block-comment or docstring block(s)" in reason_of(sneaky), True)
check("refusal warns off other people's prose", "do NOT" in reason_of(sneaky), True)
(REPO / "snuck.py").unlink()
check("green once removed", post_bash("rm snuck.py")["out"], "")

print("the ratchet is global, not just the edited file")
write("sample.ts", "const x = 1;\nexport const y = x / 2;\n")
check("untouched file still ratchets", post_bash("true")["out"], "")
check("emptied file leaves the budget", "sample.ts" in budget(), False)

print("many overruns are listed together")
write("a.py", '"""A."""\n')
write("b.py", '"""B."""\n')
many = post_bash("true")
check("both named", ("a.py: holds 1" in reason_of(many), "b.py: holds 1" in reason_of(many)), (True, True))
check("counted together", "across 2 file(s)" in reason_of(many), True)
(REPO / "a.py").unlink()
(REPO / "b.py").unlink()

print("the guard refuses the budget file")
denied = run_hook(
    "expository-budget-guard.py",
    {"cwd": str(REPO), "tool_name": "Edit", "tool_input": {"file_path": str(REPO / BUDGET)}},
)
check("edit denied", json.loads(denied["out"])["hookSpecificOutput"]["permissionDecision"], "deny")
shell = run_hook(
    "expository-budget-guard.py",
    {
        "cwd": str(REPO),
        "tool_name": "Bash",
        "tool_input": {"command": "python3 -c 'open(\".claude/expository-content-budget.json\",\"w\")'"},
    },
)
check("bash denied", json.loads(shell["out"])["hookSpecificOutput"]["permissionDecision"], "deny")
allowed = run_hook(
    "expository-budget-guard.py",
    {"cwd": str(REPO), "tool_name": "Edit", "tool_input": {"file_path": str(REPO / "sample.py")}},
)
check("unrelated edit untouched", (allowed["out"], allowed["code"]), ("", 0))

print("failure behaviour")
plain = Path(os.environ.get("TMPDIR", "/tmp")) / "expository-budget-notarepo"
plain.mkdir(exist_ok=True)
outside = run_hook(
    "expository-budget-session-start.py",
    {"cwd": str(plain), "hook_event_name": "SessionStart", "source": "startup"},
)
check("no git worktree is silent", (outside["out"], outside["code"]), ("", 0))
before_git_failure = (REPO / BUDGET).read_text()
broken = run_hook(
    "expository-budget-session-start.py",
    {"cwd": str(REPO), "hook_event_name": "SessionStart", "source": "startup"},
    overrides={"PATH": "/nonexistent"},
)
check("git failure is silent", (broken["out"], broken["code"]), ("", 0))
check("git failure preserves the budget", (REPO / BUDGET).read_text(), before_git_failure)
garbage = run_hook("expository-budget-check.py", {"cwd": str(REPO), "tool_name": "Edit"})
check("missing tool_input is silent", (garbage["out"], garbage["code"]), ("", 0))
(REPO / BUDGET).write_text("{ not json")
recovered = post_edit("sample.py")
check("unreadable budget is rebuilt", (REPO / BUDGET).exists() and "READ-THIS-FIRST" in (REPO / BUDGET).read_text(), True)
check("rebuild does not refuse", recovered["out"], "")

print("scan cost")
for repo in dict.fromkeys([str(PLUGIN.parent.parent), *sys.argv[1:]]):
    started = time.monotonic()
    total = subprocess.run(
        [sys.executable, str(SCRIPTS / "expository_scan.py")],
        capture_output=True, text=True, cwd=repo, check=False,
    ).stdout.strip().splitlines()[-1]
    print(f"  {Path(repo).name}: {time.monotonic() - started:.2f}s — {total}")

print()
print(f"{len(failures)} failure(s)" if failures else "all checks passed")
