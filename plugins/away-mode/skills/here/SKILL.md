---
name: here
description: Mark this Claude Code session attended, so permission prompts wait for you. Takes an optional duration, after which the session falls back to presence detection.
argument-hint: "[duration, e.g. 30m]"
disable-model-invocation: true
---

away-mode's UserPromptExpansion hook did not run, so `/here` had no effect. Tell the user that, and that the hook needs checking. Do not edit any away-mode state yourself.
