"""Two event vocabularies for the Assistant stream (architecture.md §6).

**Raw events** (`RawEvent`) are what a model/tool loop actually produces:
tool names, tool arguments, reasoning text, prose tokens. They are internal —
issue 15 ships no real tools yet, so `app/agent/fake_model.py` is currently
the only producer, but issue 16/17's real LangGraph loop will emit the same
shapes. Nothing in this module is ever serialized straight to the browser.

**Presenter events** (`PresenterEvent`) are the small, stable, user-facing
vocabulary `app/agent/presenter.py` translates raw events into — the exact
set architecture.md §6 lists: thinking, status, chips, spec, token, done,
error, plus `thinking_text` (ADR-0005: streamed to every user, in every
environment — not dev-only). Each carries an `event_name` (the SSE `event:`
line) and a `to_data()` (the SSE `data:` JSON body) — see
`app/api/v1/routers/agent.py` for where those get framed as SSE.

The module boundary IS the security boundary named in AGENTS.md and issue 15,
for every `PresenterEvent` except `ThinkingTextEvent`: `RawEvent`s carry tool
names/arguments/reasoning; `ThinkingEvent`, `StatusEvent`, `ChipsEvent`,
`SpecEvent`, `TokenEvent`, `DoneEvent` and `ErrorEvent` never do by
construction — none of those dataclasses has a field capable of holding a
tool name, a raw argument, or reasoning prose. `ThinkingTextEvent` is the one
deliberate exception (ADR-0005): it exists precisely to carry raw reasoning
prose to the browser, unfiltered, in a panel visually separate from the
Assistant's actual answer. `presenter.py` is what performs the translation;
this module only defines the two shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import Metric, ReportSpec


class RepairCode(StrEnum):
    """The closed vocabulary of Repairs (architecture.md §5's taxonomy,
    ADR-0002) — an enum, not free text, for the same reason `ReportSpec.
    group_by` is a single `Literal` rather than a pair of booleans
    (CONTEXT.md): the invalid case must be *unrepresentable*, not merely
    checked for. `presenter.py` maps each member to one fixed, pre-written
    phrase; nothing outside this enum's six members can ever reach
    `Repair.code`, so a tool argument or model output has no field left to
    interpolate through issue 16's repair logic.
    """

    CHART_METRIC_RESET = "chart_metric_reset"
    """`set_metrics` dropped the metric `chart_metric` pointed at — reset to
    `metrics[0]`."""
    SORT_CLEARED = "sort_cleared"
    """A field-scoped edit orphaned `sort` (its column removed, or its group
    column changed) — cleared."""
    COLUMN_DROPPED = "column_dropped"
    """`set_columns` referenced a column that no longer exists — dropped
    from the explicit order."""
    METRIC_AUTO_ADDED = "metric_auto_added"
    """`set_chart(m)` where `m` wasn't in `metrics` — `m` was added. The
    only Repair that names something, via `Repair.metric` below."""
    DATE_RANGE_CLAMPED = "date_range_clamped"
    """`set_date_range` partially overlapped the Coverage Window — clamped
    to it."""
    ENTITY_FILTER_IGNORED = "entity_filter_ignored"
    """`entity_filter` was set while `group_by == "none"` — it has no Actor
    or Mailbox breakdown to narrow, so the filter is ignored and the report
    renders ungrouped (table-filter-and-assistant-intro issue 02/07;
    `engine.execute` already emits the equivalent warning text this Repair
    will be constructed from, the same way `clamp_to_coverage`'s warning
    becomes `DATE_RANGE_CLAMPED` above)."""


class Repair(BaseModel):
    """One Repair the backend applied while executing a tool call. A
    pydantic model, not a plain dataclass, so construction itself is the
    enforcement: `Repair(code="anything-not-in-RepairCode")` raises a
    `ValidationError` rather than silently accepting free text — see
    `RepairCode`'s docstring. `metric`, when present, is a validated
    `Metric` enum member (also a closed set), never a raw string — only
    `METRIC_AUTO_ADDED` ever sets it.
    """

    model_config = ConfigDict(frozen=True)

    code: RepairCode
    metric: Metric | None = None


# ── Raw events (internal only — never reaches the browser) ──────────────


@dataclass(frozen=True)
class ReasoningDelta:
    """One chunk of the model's chain-of-thought (architecture.md §5 guard 2:
    87 of 103 chunks in the measured smoke test were exactly this, before the
    first actionable delta). `text` routinely names internal tools and enum
    values — it must never be forwarded to `PresenterEvent` except into
    `ThinkingTextEvent` (ADR-0005: streamed to every user, not dev-only)."""

    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    """A tool call the model requested. `name`/`args` are exactly the
    internals the presenter must never leak (AGENTS.md)."""

    name: str
    args: dict


@dataclass(frozen=True)
class ToolCallFinished:
    """The result of applying a tool call. `spec_before`/`spec_after` are the
    validated Report Spec across the edit — `spec_after` is `None` when
    `ok` is `False` (a genuine input error, architecture.md §5's repair-vs-
    error taxonomy; issue 16 wires real repairs, issue 15's fake model only
    exercises the success path)."""

    name: str
    args: dict
    ok: bool
    adjusted: list[Repair]
    spec_before: ReportSpec
    spec_after: ReportSpec | None = None


@dataclass(frozen=True)
class ContentDelta:
    """One chunk of the Assistant's user-facing prose — the one raw-event
    field that IS safe to forward verbatim, since it's the model's answer to
    the user, not an internal."""

    text: str


@dataclass(frozen=True)
class TurnDone:
    """The Tool Step loop finished this turn. `summary` is assistant prose
    (same safety as `ContentDelta`) — expected to be the concatenation of the
    turn's `ContentDelta`s, not new content invented at the presenter."""

    summary: str


@dataclass(frozen=True)
class TurnError:
    """Something stopped the turn. `detail` is a raw, potentially internal
    diagnostic (an exception message, a validation error) — logged server-
    side, NEVER forwarded to the browser. Only `category` may influence the
    user-facing text, via presenter.py's fixed lookup table, so no value
    `detail` could ever hold can reach the browser through this event."""

    category: Literal["validation", "coverage", "budget", "unavailable", "internal"]
    detail: str = ""


RawEvent = ReasoningDelta | ToolCallStarted | ToolCallFinished | ContentDelta | TurnDone | TurnError


# ── Presenter events (the only vocabulary the browser ever sees) ────────


@dataclass(frozen=True)
class ThinkingEvent:
    """State only, never reasoning text (issue 15's central rule). `ms` is
    set only on `state == "end"` — how long this Tool Step's reasoning
    preamble lasted, for the UI's elapsed counter."""

    state: Literal["start", "end"]
    ms: int | None = None

    event_name: str = field(default="thinking", init=False)

    def to_data(self) -> dict:
        data: dict = {"state": self.state}
        if self.ms is not None:
            data["ms"] = self.ms
        return data


@dataclass(frozen=True)
class StatusEvent:
    """A short, fixed, user-facing phrase — never the tool name that
    triggered it (presenter.py maps tool name -> phrase via a lookup table,
    so an unrecognised or hostile name can never appear here)."""

    text: str

    event_name: str = field(default="status", init=False)

    def to_data(self) -> dict:
        return {"text": self.text}


@dataclass(frozen=True)
class ChipsEvent:
    """Human-readable descriptions of what changed, derived from the
    validated Report Spec diff — never from tool arguments directly."""

    chips: list[str]

    event_name: str = field(default="chips", init=False)

    def to_data(self) -> dict:
        return {"chips": self.chips}


@dataclass(frozen=True)
class SpecEvent:
    """The full validated Report Spec after a change — idempotent, resilient
    to a dropped chip event (architecture.md §6). The frontend applies this
    to the same store the builder edits, moving the controls."""

    spec: ReportSpec

    event_name: str = field(default="spec", init=False)

    def to_data(self) -> dict:
        return {"spec": self.spec.model_dump(mode="json")}


@dataclass(frozen=True)
class TokenEvent:
    """One chunk of the Assistant's streamed prose."""

    text: str

    event_name: str = field(default="token", init=False)

    def to_data(self) -> dict:
        return {"text": self.text}


@dataclass(frozen=True)
class DoneEvent:
    """The turn is complete."""

    summary: str
    spec_version: int

    event_name: str = field(default="done", init=False)

    def to_data(self) -> dict:
        return {"summary": self.summary, "spec_version": self.spec_version}


@dataclass(frozen=True)
class ErrorEvent:
    """A sanitised, fixed, user-facing error message — never the raw
    exception/validation text that caused it (see `TurnError.detail`)."""

    text: str

    event_name: str = field(default="error", init=False)

    def to_data(self) -> dict:
        return {"text": self.text}


@dataclass(frozen=True)
class ThinkingTextEvent:
    """Raw reasoning text for a collapsible panel, streamed to every user in
    every environment (ADR-0005; architecture.md §6) — not gated on
    `settings.is_development`. `presenter.present()` emits this whenever
    called with `include_reasoning_text=True`. It routinely names internal
    tools and enum values (`ReasoningDelta`'s docstring), which is an
    accepted, deliberate tradeoff for this event specifically; the
    never-leak-internals rule is unchanged for every other `PresenterEvent`."""

    text: str

    event_name: str = field(default="thinking_text", init=False)

    def to_data(self) -> dict:
        return {"text": self.text}


PresenterEvent = (
    ThinkingEvent
    | StatusEvent
    | ChipsEvent
    | SpecEvent
    | TokenEvent
    | DoneEvent
    | ErrorEvent
    | ThinkingTextEvent
)
