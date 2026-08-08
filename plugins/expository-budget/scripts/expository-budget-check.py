#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from expository_scan import (
    BUDGET_NAME,
    counts_for_tree,
    load_budget,
    overruns,
    repo_root,
    write_budget,
)

LISTED_AT_MOST = 25


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    try:
        enforce(event)
    except (OSError, ValueError, subprocess.SubprocessError):
        return


def enforce(event: dict[str, object]) -> None:
    project = project_dir(event)
    root = repo_root(project)
    if root is None:
        return
    budget_path = project / ".claude" / BUDGET_NAME
    ceilings = load_budget(budget_path)
    counts = counts_for_tree(root)
    if ceilings is None:
        write_budget(budget_path, counts)
        return
    lowered = ratchet(ceilings, counts)
    if lowered != ceilings:
        write_budget(budget_path, lowered)
    over = overruns(counts, lowered)
    if over:
        print(json.dumps({
            "decision": "block",
            "reason": refusal(over, lowered, budget_path),
            "systemMessage": summary(over, lowered),
        }))


def project_dir(event: dict[str, object]) -> Path:
    override = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(override) if override else Path(str(event.get("cwd") or Path.cwd()))


def ratchet(ceilings: dict[str, int], counts: dict[str, int]) -> dict[str, int]:
    lowered = {
        name: min(allowed, counts.get(name, 0)) for name, allowed in ceilings.items()
    }
    return {name: allowed for name, allowed in lowered.items() if allowed}


def refusal(over: dict[str, int], ceilings: dict[str, int], budget_path: Path) -> str:
    excess = sum(count - ceilings.get(name, 0) for name, count in over.items())
    return (
        f"REFUSED by the expository-content budget. {excess} comment, block-comment or "
        f"docstring block(s) beyond budget, across {len(over)} file(s):\n"
        f"{listing(over, ceilings)}\n"
        f"Bring the tree back within budget before doing anything else. This hook scans "
        f"the whole worktree after every edit and every shell command, so it will refuse "
        f"again, and keep refusing, until it is green.\n"
        f"For prose you added: express it in the code itself (a clearer name, a smaller "
        f"function), or in a decision record, or in the commit message. A docstring that "
        f"restates a signature, a comment that restates the line below it, and a note "
        f"about how the code used to work are all removable.\n"
        f"For prose you did not add - a file you have not touched this session - do NOT "
        f"delete it. Stop and tell the user which file is over and by how much.\n"
        f"Do not attempt to raise a ceiling: {budget_path} is not editable by you, by any "
        f"command you run, or by any hook. Only the user can raise a number."
    )


def listing(over: dict[str, int], ceilings: dict[str, int]) -> str:
    shown = list(over.items())[:LISTED_AT_MOST]
    lines = [
        f"  {name}: holds {count}, budget {ceilings.get(name, 0)}"
        for name, count in shown
    ]
    if len(over) > LISTED_AT_MOST:
        lines.append(f"  ... and {len(over) - LISTED_AT_MOST} more")
    return "\n".join(lines)


def summary(over: dict[str, int], ceilings: dict[str, int]) -> str:
    name, count = next(iter(over.items()))
    first = f"{name} holds {count}, budget {ceilings.get(name, 0)}"
    return (
        f"expository-budget: {first}"
        if len(over) == 1
        else f"expository-budget: {len(over)} files over budget, including {first}"
    )


if __name__ == "__main__":
    main()
