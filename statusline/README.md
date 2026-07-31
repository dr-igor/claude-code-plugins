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

`braille_bar_cells()` and its helpers (`position_from_percentage`, `clamp`, `braille_bar_color`) in `statusline.py` are self-contained (stdlib only) and meant to be copied elsewhere as-is. They render up to 4 percentages (0-100) as the 4 dot-rows of a horizontal run of braille characters, one row per percentage, filled left-to-right, top to bottom.

`PROGRESS_BAR_SEGMENTS` is the single constant controlling how many characters represent 100%.

Each character is colored by the percentage slice of the bar it falls in: green below 60%, yellow from 60-89%, red from 90% up.

## Quality inspector cell

Between the bar and the reset times sits a cell reporting the [`quality-inspector`](../plugins/quality-inspector/) plugin's `belphegor` daemon for **this session**. It appears only when a `quality-inspector.yaml` resolves (via `QUALITY_INSPECTOR_CONFIG`, else the session `cwd`) and the `belphegor` executable is on `PATH` (or at `BELPHEGOR_BIN`); otherwise it renders as nothing at all.

Each refresh runs `belphegor status <config> --session <session_id> --status-server`, which never spawns a daemon and never defers its idle shutdown, so polling it is free of side effects.

| Cell  | Meaning                                                      |
| ----- | ------------------------------------------------------------ |
| _(none)_ | no config resolves, or no `belphegor` executable          |
| `○`   | no daemon answering                                           |
| `○?`  | daemon answered, but with no usable status                    |
| `●` dim | daemon up; it has never seen this session                   |
| `●` green | this session is idle and clean                            |
| `●⇣`  | priming a baseline (blocking a `PreToolUse`)                  |
| `●⟳2` | 2 command runs in flight right now                            |
| `●⟳9s`| debouncing; 9s left in the `settle` window                    |
| `●✗3` | last burst introduced 3 findings                              |
| `●!`  | last burst failed to dispatch                                 |

The activity and outcome halves compose — `●⟳9s✗3` is "re-checking, and the previous burst left 3 findings". Counts clamp at 99, which holds the glyphs to 10 columns at worst.

### Dashboard link

`--status-server` rides along on every refresh, so a reachable daemon also reports the URL of its live dashboard — and the cell prints it, dim, right after the glyphs:

```
●⟳9s✗3 http://127.0.0.1:59000/
```

The daemon creates that server lazily on the first ask and returns the same URL forever after, so sending the flag every time is a no-op once it exists. It still never spawns a daemon, and an open dashboard does **not** defer idle shutdown — the tab goes dark at `idle_timeout` and says so in a banner.

The URL is both an OSC 8 hyperlink and literal text, which covers both kinds of terminal: those that honour hyperlink escapes make the text clickable, and those that don't auto-detect the URL. It adds 24 columns, taking the whole cell to 33 at worst.

No URL appears when the daemon is unreachable, when it answers with no usable status, or when the dashboard itself failed to start — belphegor reports that failure as `status_server_error` beside the normal fields, and the status answer is never lost to it. Those reasons (missing web assets, no free port in 59000-59999, a daemon predating the feature) are logged rather than shown.

Set `STATUSLINE_DEBUG=true` to log to `statusline.log` in the working directory — that is where a suppressed `status_server_error` shows up. Without it the script writes nothing to stderr, whatever goes wrong.
