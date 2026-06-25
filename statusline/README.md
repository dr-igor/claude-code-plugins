# Status line

Personal Claude Code status line script, vendored here for version control. Not a plugin — Claude Code plugins can't register a main `statusLine` (only `subagentStatusLine` is supported), so this is just a tracked copy you point `settings.json` at directly:

```json
{
  "statusLine": {
    "type": "command",
    "command": "uv run /path/to/statusline.py",
    "padding": 0
  }
}
```

## Braille progress bars

The block delimited by `# --- braille progress bars ... ---` in `statusline.py` is self-contained (stdlib only) and meant to be copied elsewhere as-is. It renders up to 4 percentages (0-100) as the 4 dot-rows of a horizontal run of braille characters, one row per percentage, filled left-to-right, top to bottom.

`BAR_SIZE` is the single variable controlling how many characters represent 100%.

Each character is colored by the percentage slice of the bar it falls in: green below 60%, yellow from 60-89%, red from 90% up.
