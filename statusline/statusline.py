# /// script
# dependencies = [
#   "typer",
#   "rich",
# ]
# ///
"""Claude Code status line renderer.

Configure in ~/.claude/settings.json:

    {
      "statusLine": {
        "type": "command",
        "command": "uv run /path/to/statusline.py",
        "padding": 0
      }
    }
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta
from math import ceil
from os import X_OK, access, environ
from pathlib import Path
from typing import Annotated, Literal, NamedTuple, NotRequired, TypedDict, TypeGuard

import typer
from rich.console import Console
from rich.text import Text

console = Console(force_terminal=True, color_system="truecolor")

logger = logging.getLogger("__main__")

app = typer.Typer()


@app.command()
def main(
    payload: Annotated[
        Payload,
        typer.Argument(
            default_factory=lambda: sys.stdin,
            show_default="sys.stdin",
            parser=json.load,
        ),
    ],
):
    _setup_logger()

    logger.info(f"Received payload: {json.dumps(payload, indent=2)}")

    factory = ComponentFactory(payload)

    console.print(
        factory.model_braile()
        + " "
        + factory.thinking_indicator()
        + factory.mode_bar_block()
        + factory.inspector()
        + factory.away_mode()
        + factory.reset_times()
    )


def _setup_logger():
    debug = environ.get("STATUSLINE_DEBUG", "false").lower() == "true"
    if debug:
        logging.basicConfig(filename="statusline.log", level=logging.INFO)
    else:
        # So that we don't write to stderr (default)
        logger.addHandler(logging.NullHandler())


class ComponentFactory:
    def __init__(self, payload: Payload):
        self.payload = payload

    def model_braile(self) -> Text:
        model_short = None
        model_rank = 0

        if m := model_base_extractor.search(self.payload["model"]["id"]):
            model_short = m.group("model_base")
            model_rank = MODEL_RANK.get(model_short, 0)

        effort = self.payload.get("effort", {}).get("level", "")
        effort_rank = EFFORT_RANK.get(effort, 0)

        model_effort_braile = chr(
            ord(MODEL_BRAILE.get(model_short, "⠀"))
            | ord(EFFORT_BRAILE.get(effort, "⠀"))
        )

        return Text(
            model_effort_braile,
            style=f"bold {total_rank_to_color(model_rank + effort_rank)}",
        )

    def thinking_indicator(self) -> str:
        if self.payload["thinking"]["enabled"]:
            return "🤔 "
        return ""

    def mode_bar_block(self) -> Text:
        style = self.vim_style()
        if style is None:
            return Text("|") + self.braille_progress() + Text("|")

        block = Text(style=f"on {style.background}")
        block.append(f" {style.letter} ", style=f"bold {style.foreground}")
        block.append("|")
        block.append_text(self.braille_progress())
        block.append("|")
        return block

    def vim_style(self) -> VimModeStyle | None:
        mode = self.payload.get("vim", {}).get("mode", "")
        return VIM_MODE_STYLES.get(VIM_MODE_ALIASES.get(mode, mode))

    def braille_progress(self) -> Text:
        # Top to bottom: 5h rate limit, 7d rate limit, context window, cost.
        rate_limits = self.payload.get("rate_limits", {})
        five_hour = _pct(rate_limits.get("five_hour", {}).get("used_percentage"))
        seven_day = _pct(rate_limits.get("seven_day", {}).get("used_percentage"))
        context = _pct(self.payload.get("context_window", {}).get("used_percentage"))
        cost = _pct(self.payload.get("cost", {}).get("total_cost_usd"))

        resets_at_5h = rate_limits.get("five_hour", {}).get("resets_at")
        resets_at_7d = rate_limits.get("seven_day", {}).get("resets_at")

        percent_to_5h_reset = 100
        percent_to_7d_reset = 100

        limit_markers = []
        if resets_at_5h is not None:
            percent_to_5h_reset = (
                (datetime.fromtimestamp(resets_at_5h) - datetime.now()).total_seconds()
                / timedelta(hours=5).total_seconds()
                * 100
            )
            limit_markers.append((0, 100 - percent_to_5h_reset, True))
        if resets_at_7d is not None:
            percent_to_7d_reset = (
                (datetime.fromtimestamp(resets_at_7d) - datetime.now()).total_seconds()
                / timedelta(days=7).total_seconds()
                * 100
            )
            limit_markers.append((1, 100 - percent_to_7d_reset, True))

        text = Text()
        for i, cell in enumerate(
            braille_bar_cells(
                (five_hour, seven_day, context, cost),
                markers=[
                    (0, 0, False),
                    (1, 0, False),
                    (2, 0, False),
                    (3, 0, False),
                ]
                + limit_markers,
            )
        ):
            text.append(cell, style=braille_bar_color(i))
        return text

    def inspector(self) -> Text:
        # Unlike every other cell, this one depends on an external process and the
        # filesystem. A quality-inspection hiccup must never cost the whole status line.
        try:
            return render_inspector(query_inspector(self.payload))
        except Exception:
            logger.warning("inspector cell failed", exc_info=True)
            return Text()

    def away_mode(self) -> Text:
        try:
            return render_away_mode(query_away_mode(self.payload))
        except Exception:
            logger.warning("away mode cell failed", exc_info=True)
            return Text()

    def reset_times(self) -> Text:
        rate_limits = self.payload.get("rate_limits", {})
        five_hour = rate_limits.get("five_hour", {}).get("resets_at")
        seven_day = rate_limits.get("seven_day", {}).get("resets_at")

        text = Text()
        if five_hour:
            text.append(f" 🕙 {datetime.fromtimestamp(five_hour):%H:%M}", style="dim")
        if seven_day:
            text.append(
                f" 🗓️ {datetime.fromtimestamp(seven_day):%b %d %H:%M}", style="dim"
            )
        return text


model_base_extractor = re.compile(r"(?P<model_base>haiku|sonnet|opus|fable|mythos)")

MODEL_RANK = {
    "haiku": 2,
    "sonnet": 4,
    "opus": 6,
    "fable": 8,
    "mythos": 8,
}

MODEL_BRAILE = {
    "haiku": "⡀",
    "sonnet": "⡄",
    "opus": "⡆",
    "fable": "⡇",
    "mythos": "⡇",
}

EFFORT_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "xhigh": 3,
    "max": 4,
}

EFFORT_BRAILE = {
    "low": "⠀",
    "medium": "⢀",
    "high": "⢠",
    "xhigh": "⢰",
    "max": "⢸",
}


def total_rank_to_color(total_rank: int) -> str:
    if total_rank <= 3:
        return "green"
    elif total_rank <= 6:
        return "yellow"
    elif total_rank <= 8:
        return "orange1"
    return "red"


class VimModeStyle(NamedTuple):
    letter: str
    foreground: str
    background: str


VIM_MODE_STYLES = {
    "NORMAL": VimModeStyle("N", "#7aa2f7", "#1c2e4a"),
    "INSERT": VimModeStyle("I", "#9ece6a", "#16351f"),
    "VISUAL": VimModeStyle("V", "#bb9af7", "#2e1f3d"),
}

VIM_MODE_ALIASES = {"VISUAL LINE": "VISUAL"}


def _pct(value: float | None) -> float:
    return float(value or 0)


PROGRESS_BAR_SEGMENTS = 20

_PER_SEGMENT_INDICATORS = (
    (ord("⠁"), ord("⠈")),
    (ord("⠂"), ord("⠐")),
    (ord("⠄"), ord("⠠")),
    (ord("⡀"), ord("⢀")),
)


def braille_bar_cells(
    percentages: tuple[float, float, float, float],
    *,
    size: int = PROGRESS_BAR_SEGMENTS,
    markers: Iterable[tuple[int, int, bool]] = [],
) -> list[str]:
    segments = [0] * size

    for row_indicators, row_percent in zip(_PER_SEGMENT_INDICATORS, percentages):
        for pos in range(position_from_percentage(row_percent, size=size)):
            segments[pos // 2] |= row_indicators[pos % 2]

    for marker_row, marker_percentage, invert_overlap in markers:
        marker_pos = position_from_percentage(marker_percentage, size=size)

        segment_index = marker_pos // 2
        indicator = _PER_SEGMENT_INDICATORS[marker_row][marker_pos % 2]

        try:
            if invert_overlap:
                segments[segment_index] ^= indicator
            else:
                segments[segment_index] |= indicator
        except IndexError:
            logger.warning(
                f"Marker {marker_row=} {marker_percentage=} {invert_overlap=} "
                f"out of bounds for segments {segments=};\n{segment_index=} {marker_pos=}"
            )

    return [chr(ord("⠀") | bits) for bits in segments]


def position_from_percentage(
    percentage: float, *, size: int = PROGRESS_BAR_SEGMENTS
) -> int:
    return round(clamp(percentage) * (2 * size - 1) / 100)


def clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(max_value, value))


def braille_bar_color(cell_index: int, *, size: int = PROGRESS_BAR_SEGMENTS) -> str:
    start_pct = cell_index * (100.0 / size)
    if start_pct >= 90:
        return "red"
    if start_pct >= 60:
        return "yellow"
    return "green"


def query_inspector(payload: Payload) -> InspectorState | None:
    config = resolve_inspector_config(payload)
    bin_path = resolve_inspector_bin()
    if bin_path is None or not config.is_file():
        return None

    # The socket identity hashes the link-resolved config path alongside its content,
    # so this must resolve exactly as the hook's `str(config.resolve())` does or we
    # look for a different daemon than the one the hooks dispatch to.
    command = [bin_path, "status", str(config.resolve())]
    if session_id := payload.get("session_id"):
        command += ["--session", session_id]
    command.append("--status-server")

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=INSPECTOR_STATUS_TIMEOUT,
            check=False,
        )
        return reduce_inspector_status(json.loads(completed.stdout))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logger.warning(f"belphegor status failed: {error!r}")
        return InspectorState()


def resolve_inspector_config(payload: Payload) -> Path:
    if override := environ.get(INSPECTOR_CONFIG_ENV):
        return Path(override).expanduser()
    return Path(payload.get("cwd") or Path.cwd()) / INSPECTOR_CONFIG_NAME


def resolve_inspector_bin() -> str | None:
    override = environ.get(INSPECTOR_BIN_ENV)
    if override and access(override, X_OK):
        return override
    return shutil.which("belphegor")


def reduce_inspector_status(raw: InspectorStatus) -> InspectorState:
    if not raw.get("running"):
        return InspectorState()
    if raw.get("error"):
        return InspectorState(is_reachable=True)

    status_url = resolve_inspector_url(raw)
    session = next((s for s in raw.get("sessions", []) if is_full_session(s)), None)
    if session is None:
        return InspectorState(is_reachable=True, is_usable=True, status_url=status_url)

    last_result = session.get("last_result")
    return InspectorState(
        is_reachable=True,
        is_usable=True,
        is_seen=True,
        phase=session.get("phase", ""),
        resolving=int(session.get("resolving") or 0),
        settle_remaining=session.get("settle_remaining"),
        result="" if last_result is None else last_result.get("status", ""),
        findings=(
            0 if last_result is None else int(last_result.get("message_count") or 0)
        ),
        status_url=status_url,
    )


def resolve_inspector_url(raw: InspectorStatus) -> str:
    # A dashboard that cannot start never costs the status answer: belphegor reports it
    # beside the usual fields and still exits 0, so this only ever suppresses the link.
    if error := raw.get("status_server_error"):
        logger.warning(f"belphegor status server unavailable: {error}")
    url = raw.get("status_url")
    return url if isinstance(url, str) else ""


def is_full_session(entry: InspectorSession) -> TypeGuard[InspectorSessionStatus]:
    return entry.get("detail") == "full"


def render_inspector(state: InspectorState | None) -> Text:
    if state is None:
        return Text()
    return inspector_cell(state) + inspector_link(state.status_url)


def inspector_cell(state: InspectorState) -> Text:
    if not state.is_reachable:
        return Text(" ○", style="dim")
    if not state.is_usable:
        return Text(" ○?", style="dim")
    if not state.is_seen:
        return Text(" ●", style="dim")
    if state.phase == "priming":
        return Text(" ●⇣", style="yellow")

    activity = inspector_activity(state)
    outcome = inspector_outcome(state)

    text = Text(" ")
    text.append("●", style="yellow" if activity else "red" if outcome else "green")
    if activity:
        text.append(activity, style="yellow")
    if outcome:
        text.append(outcome, style="red")
    return text


def inspector_link(url: str) -> Text:
    if not url:
        return Text()
    return Text(f" {url}", style=f"dim link {url}")


def inspector_activity(state: InspectorState) -> str:
    if state.resolving:
        return f"⟳{_capped(state.resolving)}"
    if state.phase == "armed":
        return f"⟳{_capped(ceil(state.settle_remaining or 0))}s"
    return ""


def inspector_outcome(state: InspectorState) -> str:
    if state.result == "messages":
        return f"✗{_capped(state.findings)}"
    if state.result == "failed":
        return "!"
    return ""


def _capped(count: int) -> int:
    return min(count, INSPECTOR_COUNT_CEILING)


def query_away_mode(payload: Payload) -> AwayModeState:
    session_id = str(payload.get("session_id") or "")
    record = away_mode_record(session_id)
    until = away_mode_until(record.get("until"))
    denials = record.get("denials")
    mode = record.get("mode")
    return AwayModeState(
        status=away_mode_status(
            str(mode) if mode in AWAY_MODE_MODES else AWAY_MODE_DEFAULT,
            until,
            session_id,
        ),
        until=until,
        denials=_capped(denials) if isinstance(denials, int) else 0,
    )


def away_mode_record(session_id: str) -> dict[str, object]:
    path = away_mode_path(session_id)
    if path is None:
        return {}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}


def away_mode_path(session_id: str) -> Path | None:
    if not AWAY_MODE_SESSION_ID.match(session_id):
        return None
    override = environ.get(AWAY_MODE_SESSIONS_ENV)
    root = Path(override).expanduser() if override else AWAY_MODE_SESSIONS
    return root / f"{session_id}.json"


def away_mode_until(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def away_mode_status(mode: str, until: datetime | None, session_id: str) -> str:
    if mode == "away":
        return "away"
    if mode == "here" and not away_mode_expired(until):
        return "here"
    return "away" if away_mode_presence(session_id) == "absent" else "here"


def away_mode_expired(until: datetime | None) -> bool:
    return until is not None and until <= datetime.now(until.tzinfo)


def away_mode_presence(session_id: str) -> str:
    script = away_mode_state_script()
    if script is None:
        return "unknown"
    try:
        completed = subprocess.run(
            [str(script), session_id],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=AWAY_MODE_PRESENCE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning(f"away mode presence failed: {error!r}")
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def away_mode_state_script() -> Path | None:
    override = environ.get(AWAY_MODE_SCRIPT_ENV)
    script = Path(override).expanduser() if override else AWAY_MODE_SCRIPT
    return script if access(script, X_OK) else None


def render_away_mode(state: AwayModeState) -> Text:
    label = AWAY_MODE_LABELS[state.status]
    if remaining := away_mode_remaining(state.until):
        label += f" {remaining}"
    if state.denials:
        label += f" {AWAY_MODE_DENIED}{state.denials}"
    return Text(" ") + Text(f"[{label}]", style=AWAY_MODE_STYLES[state.status])


def away_mode_remaining(until: datetime | None) -> str:
    if until is None:
        return ""
    minutes = ceil((until - datetime.now(until.tzinfo)).total_seconds() / 60)
    if minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes}m"
    hours = ceil(minutes / 60)
    return f"{hours}h" if hours < 48 else f"{ceil(hours / 24)}d"


INSPECTOR_CONFIG_ENV = "QUALITY_INSPECTOR_CONFIG"
INSPECTOR_BIN_ENV = "BELPHEGOR_BIN"
INSPECTOR_CONFIG_NAME = "quality-inspector.yaml"
# Measured round trip is ~155ms, almost entirely belphegor's interpreter startup rather
# than the socket read. A timeout renders as "daemon down", so the cap is set well clear
# of that floor: a loaded machine must not make a live daemon look dead. `--status-server`
# adds a second connect, and the very first one also binds a loopback port and starts the
# dashboard's HTTP runner before it can answer -- unmeasured here, since a daemon cannot
# be spawned in this sandbox.
INSPECTOR_STATUS_TIMEOUT = 1.0
INSPECTOR_COUNT_CEILING = 99

AWAY_MODE_SESSIONS_ENV = "AWAY_MODE_SESSIONS"
AWAY_MODE_SESSIONS = Path.home() / ".claude" / "away-mode" / "sessions"
AWAY_MODE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
AWAY_MODE_DEFAULT = "auto"
AWAY_MODE_MODES = ("away", "here", "auto")
AWAY_MODE_LABELS = {"away": "AWAY", "here": "HERE"}
AWAY_MODE_STYLES = {"away": "bold yellow", "here": "dim"}
AWAY_MODE_DENIED = "x"
AWAY_MODE_SCRIPT_ENV = "AWAY_MODE_STATE_SCRIPT"
AWAY_MODE_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "away-mode"
    / "scripts"
    / "away_mode_state.py"
)
AWAY_MODE_PRESENCE_TIMEOUT = 2.0


class AwayModeState(NamedTuple):
    status: str = "here"
    until: datetime | None = None
    denials: int = 0


class InspectorState(NamedTuple):
    is_reachable: bool = False
    is_usable: bool = False
    is_seen: bool = False
    phase: str = ""
    resolving: int = 0
    settle_remaining: float | None = None
    result: str = ""
    findings: int = 0
    status_url: str = ""


class Payload(TypedDict):
    version: str
    session_id: str
    cwd: str
    model: Model
    thinking: Thinking
    effort: Effort
    fast_mode: bool
    workspace: Workspace
    cost: Cost
    context_window: ContextWindow
    rate_limits: RateLimits
    vim: NotRequired[Vim]


class Model(TypedDict):
    id: str
    display_name: str


class Effort(TypedDict):
    level: Literal["low", "medium", "high", "xhigh", "max"]


class Repo(TypedDict):
    host: str
    owner: str
    name: str


class Workspace(TypedDict):
    repo: Repo


class Thinking(TypedDict):
    enabled: bool


class Cost(TypedDict):
    total_cost_usd: float
    total_duration_ms: int
    total_api_durration_ms: int
    total_lines_added: int
    total_lines_removed: int


class RateLimit(TypedDict):
    used_percentage: float
    resets_at: int


class RateLimits(TypedDict):
    five_hour: RateLimit
    seven_day: RateLimit


class ContextWindow(TypedDict):
    total_input_tokens: int
    total_output_tokens: int
    context_window_size: int
    current_usage: int | None
    used_percentage: float | None
    remaining_percentage: float | None


class Vim(TypedDict):
    mode: Literal["NORMAL", "INSERT", "VISUAL", "VISUAL LINE"]


class InspectorStatus(TypedDict):
    v: int
    running: bool
    type: NotRequired[str]
    error: NotRequired[str]
    daemon: NotRequired[InspectorDaemon]
    sessions: NotRequired[list[InspectorSession]]
    status_url: NotRequired[str]
    status_server_error: NotRequired[str]


class InspectorDaemon(TypedDict):
    mode: str
    pid: int
    version: str
    config_path: str
    socket_path: str
    uptime: float
    idle_timeout: float
    idle_shutdown_in: float
    settle: float
    command_timeout: float
    commands: list[str]
    waiting_clients: int


class InspectorSessionStatus(TypedDict):
    detail: Literal["full"]
    session_id: str
    # Reported verbatim from the daemon's phase enum, so treat the set as open:
    # idle | priming | no_listener | allow_reprime | armed.
    phase: str
    settle_remaining: float | None
    baseline: bool
    resolving: int
    queued: int
    last_event_age: float | None
    last_result: InspectorResult | None


class InspectorSessionRef(TypedDict):
    detail: Literal["id"]
    session_id: str


class InspectorResult(TypedDict):
    status: Literal["ok", "messages", "failed"]
    age: float
    message_count: NotRequired[int]
    error: NotRequired[str]


InspectorSession = InspectorSessionStatus | InspectorSessionRef


if __name__ == "__main__":
    app()
