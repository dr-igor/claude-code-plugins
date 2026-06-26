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
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta
from os import environ
from typing import Annotated, Literal, TypedDict

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
        + "|"
        + factory.braille_progress()
        + "|"
        + factory.reset_times()
    )


def _setup_logger():
    debug = environ.get("STATUSLINE_DEBUG", "false").lower() == "true"
    if debug:
        logging.basicConfig(filename="statusline.log", level=logging.INFO)


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

    def braille_progress(self) -> Text:
        # Top to bottom: 5h rate limit, 7d rate limit, context window, cost.
        rate_limits = self.payload.get("rate_limits", {})
        five_hour = _pct(rate_limits.get("five_hour", {}).get("used_percentage"))
        seven_day = _pct(rate_limits.get("seven_day", {}).get("used_percentage"))
        context = _pct(self.payload.get("context_window", {}).get("used_percentage"))
        cost = _pct(self.payload.get("cost", {}).get("total_cost_usd"))

        percent_to_5h_reset = (
            (
                datetime.fromtimestamp(
                    rate_limits.get("five_hour", {}).get("resets_at")
                )
                - datetime.now()
            ).total_seconds()
            / timedelta(hours=5).total_seconds()
            * 100
        )
        percent_to_7d_reset = (
            (
                datetime.fromtimestamp(
                    rate_limits.get("seven_day", {}).get("resets_at")
                )
                - datetime.now()
            ).total_seconds()
            / timedelta(days=7).total_seconds()
            * 100
        )

        text = Text()
        for i, cell in enumerate(
            braille_bar_cells(
                (five_hour, seven_day, context, cost),
                markers=[
                    (0, 0, False),
                    (1, 0, False),
                    (2, 0, False),
                    (3, 0, False),
                    (0, 100 - percent_to_5h_reset, True),
                    (1, 100 - percent_to_7d_reset, True),
                ],
            )
        ):
            text.append(cell, style=braille_bar_color(i))
        return text

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


model_base_extractor = re.compile(r"(?P<model_base>haiku|sonnet|opus|epic)")

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
        return "orange"
    return "red"


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

        if invert_overlap:
            segments[segment_index] ^= indicator
        else:
            segments[segment_index] |= indicator

    return [chr(ord("⠀") | bits) for bits in segments]


def position_from_percentage(
    percentage: float, *, size: int = PROGRESS_BAR_SEGMENTS
) -> int:
    return round(clamp(percentage) * (2 * size / 100))


def clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(max_value, value))


def braille_bar_color(cell_index: int, *, size: int = PROGRESS_BAR_SEGMENTS) -> str:
    start_pct = cell_index * (100.0 / size)
    if start_pct >= 90:
        return "red"
    if start_pct >= 60:
        return "yellow"
    return "green"


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
    vim: Vim


class Model(TypedDict):
    id: str
    display_name: str


class Effort(TypedDict):
    level: (
        Literal["low"]
        | Literal["medium"]
        | Literal["high"]
        | Literal["xhigh"]
        | Literal["max"]
    )


class Repo(TypedDict):
    host: str
    owner: str
    name: str


class Workspace(TypedDict):
    repo: Repo


class Thinking(Workspace):
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
    mode: Literal["INSERT"] | Literal["NORMAL"] | Literal["VISUAL"] | Literal["REPLACE"]


if __name__ == "__main__":
    app()
