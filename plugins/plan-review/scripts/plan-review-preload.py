#!/usr/bin/env python3
"""PreToolUse(Agent) hook: preload task-relevant context into the Plan subagent.

Fires before a subagent is spawned. When the subagent is a ``Plan`` agent, a fast
model (via ``claude -p``, reusing existing auth) selects which of the plugin's
indexed context files are relevant to the plan agent's task, and the hook rewrites
the Agent ``tool_input`` (``updatedInput``) to append those files' contents to the
subagent's prompt. Any failure, a non-Plan agent, or an empty selection exits 0
without touching the call, so a hook problem never blocks planning.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

INNER_ENV = "PLAN_REVIEW_INNER"
DISABLE_ENV = "PLAN_REVIEW_PRELOAD_DISABLE"
MODEL_ENV = "PLAN_REVIEW_MODEL"
DEFAULT_MODEL = "haiku"
CLASSIFY_TIMEOUT_S = 45


def load_index(plugin_root):
    index_file = Path(plugin_root) / "contexts" / "index.json"
    if not index_file.is_file():
        return []
    return json.loads(index_file.read_text()).get("contexts", [])


def parse_id_array(text):
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    parsed = json.loads(text[start : end + 1])
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def select_relevant(claude_bin, task, index, *, model):
    catalog = "\n".join(f"- {entry['id']}: {entry['description']}" for entry in index)
    prompt = (
        "You select which reference documents are relevant to a software task.\n\n"
        f"TASK:\n{task}\n\n"
        f"AVAILABLE DOCUMENTS:\n{catalog}\n\n"
        "Return ONLY a JSON array of the ids that are clearly relevant to the task "
        "(the array may be empty). Output nothing but the array."
    )
    completed = subprocess.run(
        [claude_bin, "-p", prompt, "--model", model],
        capture_output=True,
        text=True,
        timeout=CLASSIFY_TIMEOUT_S,
        env={**os.environ, INNER_ENV: "1"},
    )
    if completed.returncode != 0:
        return []
    chosen = set(parse_id_array(completed.stdout))
    return [entry for entry in index if entry["id"] in chosen]


def context_block(entry):
    path = Path(entry["path"]).expanduser()
    if not path.is_file():
        return None, None
    resolved = path.resolve()
    return f"Contents of {resolved}:\n\n{resolved.read_text()}", resolved.name


def main():
    try:
        if os.environ.get(INNER_ENV) or os.environ.get(DISABLE_ENV):
            return
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return

        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        if tool_input.get("subagent_type") != "Plan":
            return
        task = tool_input.get("prompt")
        if not task:
            return

        index = load_index(os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
        if not index:
            return

        selected = select_relevant(
            claude_bin, task, index, model=os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        )
        blocks, names = [], []
        for entry in selected:
            block, name = context_block(entry)
            if block:
                blocks.append(block)
                names.append(name)
        if not blocks:
            return

        injected = (
            f"{task}\n\n---\n\n"
            "# Preloaded project context (plan-review)\n"
            "These reference documents were selected as relevant to your task:\n\n"
            + "\n\n---\n\n".join(blocks)
        )
        print(
            json.dumps(
                {
                    "systemMessage": f"cc-plugins-igorlabworks/plan-review: preloaded {', '.join(names)} into Plan agent.",
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "updatedInput": {**tool_input, "prompt": injected},
                    },
                }
            )
        )
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
