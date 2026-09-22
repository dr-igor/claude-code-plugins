---
name: auto
description: Let presence decide for this Claude Code session - a locked screen or a window that is not frontmost auto-denies permission prompts, and being at the keyboard lets them through.
disable-model-invocation: true
---

away-mode's UserPromptExpansion hook did not run, so `/auto` had no effect. Tell the user that, and that the hook needs checking. Do not edit any away-mode state yourself.
