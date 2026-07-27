"""The presenter — the chokepoint between raw model/tool internals and the
browser (architecture.md §6, issue 15).

`present()` is a **pure function**: raw events in, presenter events out, no
I/O, no globals, no clock dependency it doesn't take as an argument. That is
what makes the negative-leak test in `tests/test_agent_presenter.py`
meaningful — it can construct `RawEvent`s with sentinel values in every
internal position and assert the *return value* never contains them, without
needing a server, a socket, or a real model.

Translation rules (architecture.md §6):

- `thinking: start` fires on the first `ReasoningDelta` of a Tool Step;
  `thinking: end` fires on the first event after it that is NOT a
  `ReasoningDelta` (a tool call or prose) — it fires once per Tool Step, so a
  multi-step turn shows the indicator repeatedly.
- `ReasoningDelta.text` is **never** forwarded except into `ThinkingTextEvent`,
  and only when the caller passes `include_reasoning_text=True` (the router
  gates that on `settings.is_development` — this function never reads
  settings itself).
- `ToolCallStarted.name` selects a fixed, pre-written status phrase via a
  lookup table with a generic fallback — the name itself is never
  interpolated into any emitted string.
- `ToolCallFinished` (success) emits `chips` (derived from diffing the
  validated spec, never from `args`) then the full `spec`.
- `ToolCallFinished` (failure) and `TurnError` both emit a fixed, sanitised
  `ErrorEvent` selected by `category`/`ok` — `args`/`detail` are logged
  server-side by the caller, never passed to this function's output.
- `ContentDelta` -> `token`; `TurnDone` -> `done`, carrying a running count of
  `spec` events emitted this turn as `spec_version` (issue 15 has no
  cross-turn session state yet — each request is a fresh turn seeded from
  the caller's current spec, see `app/api/v1/routers/agent.py`).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable, Iterator

from app.agent.events import (
    ChipsEvent,
    ContentDelta,
    DoneEvent,
    ErrorEvent,
    PresenterEvent,
    RawEvent,
    ReasoningDelta,
    Repair,
    RepairCode,
    SpecEvent,
    StatusEvent,
    ThinkingEvent,
    ThinkingTextEvent,
    TokenEvent,
    ToolCallFinished,
    ToolCallStarted,
    TurnDone,
    TurnError,
)
from app.models import Metric, ReportSpec

# CONTEXT.md: "agent" is banned unqualified in prose/UI copy — the wire value
# `group_by` uses stays `"agent"`/`"mailbox"` (ReportSpec, unchanged), but
# anything a user reads must say Actor/Mailbox. Mirrors the vocabulary
# `app/exporters.py`'s `_GROUP_COLUMN_LABELS` and `frontend/src/ReportTable.tsx`'s
# `groupColumnLabel` already use for the same rule elsewhere in the app.
_GROUP_BY_LABEL: dict[str, str] = {"agent": "Actor", "mailbox": "Mailbox", "none": "none"}


def _metric_label(metric: Metric) -> str:
    """Mirrors `app/engine.py::_label` (`key.replace("_", " ").capitalize()`)
    — not imported directly since that's engine-internal, but the same
    formatting rule, applied to the same enum every column header already
    uses."""
    return metric.value.replace("_", " ").capitalize()

# Fixed, pre-written phrases only — `ToolCallStarted.name` is a dict KEY here,
# never interpolated into a string, so an unrecognised (or hostile) name
# falls through to the generic default rather than ever being echoed.
_STATUS_TEXT: dict[str, str] = {
    "set_date_range": "Updating the date range…",
    "set_metrics": "Updating the metrics…",
    "set_grouping": "Updating the grouping…",
    "set_sort": "Updating the sort…",
    "set_columns": "Reordering the columns…",
    "set_chart": "Updating the chart…",
    "set_layout": "Updating the layout…",
    "run_report": "Running the report…",
    "get_meta": "Looking up the data…",
}
_DEFAULT_STATUS_TEXT = "Updating the report…"

# Fixed, pre-written messages only — `TurnError.category` (a closed enum) is
# the only thing selecting one; `TurnError.detail` is never read here.
_ERROR_TEXT: dict[str, str] = {
    "validation": "I couldn't apply that change — one of the values wasn't valid.",
    "coverage": "That date range has no data in the Coverage Window.",
    "budget": (
        "I've used up this turn's work allowance. Here's where I got to — "
        "send another message to continue."
    ),
    "unavailable": "The assistant isn't available right now.",
    "internal": "Something went wrong while building that report.",
}
_DEFAULT_ERROR_TEXT = "Something went wrong while building that report."

# Failed tool calls (`ToolCallFinished.ok is False`) are always genuine input
# errors in the taxonomy (architecture.md §5) — always presented the same as
# a "validation" `TurnError`.
_TOOL_FAILURE_TEXT = _ERROR_TEXT["validation"]

# Fixed, pre-written phrases only — `RepairCode` is a closed enum (five
# members, `app/agent/events.py`), so this dict's `.get(..., default)` can
# never be asked for a value it wasn't written to have. `METRIC_AUTO_ADDED`
# is handled separately in `_repair_chip` below, since it's the one Repair
# that names something (always a validated `Metric`, never raw text).
_REPAIR_TEXT: dict[RepairCode, str] = {
    RepairCode.CHART_METRIC_RESET: "chart metric reset to the first selected metric",
    RepairCode.SORT_CLEARED: "sort cleared",
    RepairCode.COLUMN_DROPPED: "a removed column was dropped from the column order",
    RepairCode.DATE_RANGE_CLAMPED: "date range clamped to the Coverage Window",
    RepairCode.ENTITY_FILTER_IGNORED: (
        "entity filter has no effect without grouping by Actor or Mailbox"
    ),
}
_DEFAULT_REPAIR_TEXT = "the report was adjusted"


def _repair_chip(repair: Repair) -> str:
    if repair.code is RepairCode.METRIC_AUTO_ADDED and repair.metric is not None:
        return f"Adjusted: added {_metric_label(repair.metric)} to the report"
    return f"Adjusted: {_REPAIR_TEXT.get(repair.code, _DEFAULT_REPAIR_TEXT)}"


class _PresenterState:
    """The translation state machine shared by `present()` (sync — the fake
    model, issue 15/16) and `present_async()` (async — the real model loop,
    issue 17, which must `await` the provider between events). Both callers
    just feed `RawEvent`s to `handle()` one at a time and forward whatever
    `PresenterEvent`s come back; keeping the state here means the actual
    translation rules exist in exactly one place regardless of which loop
    drives them.
    """

    def __init__(
        self, *, include_reasoning_text: bool, now: Callable[[], float]
    ) -> None:
        self._include_reasoning_text = include_reasoning_text
        self._now = now
        self._in_reasoning = False
        self._reasoning_started_at: float | None = None
        self.spec_version = 0

    def handle(self, event: RawEvent) -> list[PresenterEvent]:
        out: list[PresenterEvent] = []

        if isinstance(event, ReasoningDelta):
            if not self._in_reasoning:
                self._in_reasoning = True
                self._reasoning_started_at = self._now()
                out.append(ThinkingEvent(state="start"))
            if self._include_reasoning_text:
                out.append(ThinkingTextEvent(text=event.text))
            return out

        if self._in_reasoning:
            elapsed_ms = 0
            if self._reasoning_started_at is not None:
                elapsed_ms = max(0, round((self._now() - self._reasoning_started_at) * 1000))
            out.append(ThinkingEvent(state="end", ms=elapsed_ms))
            self._in_reasoning = False
            self._reasoning_started_at = None

        if isinstance(event, ToolCallStarted):
            out.append(StatusEvent(text=_STATUS_TEXT.get(event.name, _DEFAULT_STATUS_TEXT)))

        elif isinstance(event, ToolCallFinished):
            if event.ok and event.spec_after is not None:
                chips = _diff_chips(event.spec_before, event.spec_after, event.adjusted)
                out.append(ChipsEvent(chips=chips))
                out.append(SpecEvent(spec=event.spec_after))
                self.spec_version += 1
            else:
                out.append(ErrorEvent(text=_TOOL_FAILURE_TEXT))

        elif isinstance(event, ContentDelta):
            out.append(TokenEvent(text=event.text))

        elif isinstance(event, TurnDone):
            out.append(DoneEvent(summary=event.summary, spec_version=self.spec_version))

        elif isinstance(event, TurnError):
            out.append(ErrorEvent(text=_ERROR_TEXT.get(event.category, _DEFAULT_ERROR_TEXT)))

        return out


def present(
    raw_events: Iterable[RawEvent],
    *,
    include_reasoning_text: bool = False,
    now: Callable[[], float] = time.monotonic,
) -> Iterator[PresenterEvent]:
    """Translate a stream of `RawEvent`s into `PresenterEvent`s.

    `include_reasoning_text` must only ever be set from
    `settings.is_development` by the caller (`routers/agent.py`) — this
    function does not know or care why, it just gates `ThinkingTextEvent`.
    `now` is an injection seam for tests that need a deterministic `ms`.
    """
    state = _PresenterState(include_reasoning_text=include_reasoning_text, now=now)
    for event in raw_events:
        yield from state.handle(event)


async def present_async(
    raw_events: AsyncIterable[RawEvent],
    *,
    include_reasoning_text: bool = False,
    now: Callable[[], float] = time.monotonic,
) -> AsyncIterator[PresenterEvent]:
    """`present()`'s async twin (issue 17): the real model loop is an
    `AsyncIterator[RawEvent]` because it awaits the provider between
    events, so the router needs an `async for`-able translator too. Same
    `_PresenterState`, same rules — see `present()`'s docstring."""
    state = _PresenterState(include_reasoning_text=include_reasoning_text, now=now)
    async for event in raw_events:
        for ui_event in state.handle(event):
            yield ui_event


def _diff_chips(before: ReportSpec, after: ReportSpec, adjusted: list[Repair]) -> list[str]:
    """Human-readable chips from a validated spec diff (architecture.md §6:
    "from validated spec diff") — never from raw tool arguments. Dates are
    real `ReportSpec` values the user already sees in the builder. Metric
    *keys* (`"handle_time"`), like `group_by`'s wire values
    (`"agent"`/`"mailbox"`), are NOT shown verbatim — every chip that names a
    metric (added/removed, chart, sort) goes through `_metric_label` first,
    the same way `_GROUP_BY_LABEL` translates `group_by` to "Actor"/"Mailbox"
    (CONTEXT.md bans unqualified "agent" in UI copy, and a raw metric key is
    the same class of leak)."""
    chips: list[str] = []

    if before.metrics != after.metrics:
        before_values = {m.value for m in before.metrics}
        after_values = {m.value for m in after.metrics}
        for m in after.metrics:
            if m.value not in before_values:
                chips.append(f"Added metric: {_metric_label(m)}")
        for m in before.metrics:
            if m.value not in after_values:
                chips.append(f"Removed metric: {_metric_label(m)}")

    if before.date_from != after.date_from or before.date_to != after.date_to:
        chips.append(f"Date range: {after.date_from} – {after.date_to}")

    if before.granularity != after.granularity:
        chips.append(
            "Granularity: whole period" if after.granularity == "total" else "Granularity: per day"
        )

    if before.group_by != after.group_by:
        label = _GROUP_BY_LABEL.get(after.group_by, after.group_by)
        chips.append("Grouping: none" if after.group_by == "none" else f"Grouping: by {label}")

    if before.duration_display != after.duration_display:
        label = "average" if after.duration_display == "avg" else "total"
        chips.append(f"Duration display: {label}")

    if before.sort != after.sort:
        if after.sort is None:
            chips.append("Sort cleared")
        else:
            direction = "descending" if after.sort.direction == "desc" else "ascending"
            column_label = _metric_label(Metric(after.sort.column))
            chips.append(f"Sort: {column_label} ({direction})")

    if before.columns_order != after.columns_order:
        chips.append("Reordered columns")

    if before.layout != after.layout:
        chips.append(f"Layout: {after.layout}")

    if before.chart_metric != after.chart_metric:
        chips.append(
            f"Chart: {_metric_label(after.chart_metric)}"
            if after.chart_metric
            else "Chart: default"
        )

    if before.entity_filter != after.entity_filter:
        chips.append(
            f"Filter: {after.entity_filter}" if after.entity_filter else "Filter cleared"
        )

    for repair in adjusted:
        chips.append(_repair_chip(repair))

    if not chips:
        chips.append("Updated the report")

    return chips
