"""
Typed internal event stream + mapping to friendly UI events.

The key discipline being tested here: internal events may carry raw tool
names, raw JSON args, validation errors, retry attempts — all useful for
logs/debugging but NOT for the end user. `to_ui_event()` is the one place
allowed to turn "backend truth" into "user-facing message + tag chips", and
it must never leak raw args/prompts/tool names into the UI text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

from models import ReportSpec

# ---------------------------------------------------------------------------
# Internal events (backend-only; may contain raw args, errors, prompts)
# ---------------------------------------------------------------------------


@dataclass
class ToolCallStarted:
    call_id: str
    tool_name: str
    raw_args: dict


@dataclass
class ToolCallFinished:
    call_id: str
    tool_name: str
    ok: bool
    raw_result: Any = None
    error: Optional[str] = None


@dataclass
class SpecUpdated:
    old_spec: ReportSpec
    new_spec: ReportSpec


@dataclass
class AssistantSays:
    text: str


@dataclass
class Error:
    message: str
    retriable: bool = False


@dataclass
class Warning:
    """Data-quality caveat surfaced by a tool (e.g. engine.py clamping a date
    range or flagging unreliable mailbox data). Distinct from Error: nothing
    failed, but the user should know their request wasn't honored literally."""

    message: str


InternalEvent = Union[
    ToolCallStarted, ToolCallFinished, SpecUpdated, AssistantSays, Error, Warning
]


# ---------------------------------------------------------------------------
# UI events (frontend-safe; friendly text + short tag chips, no raw args)
# ---------------------------------------------------------------------------


@dataclass
class UiEvent:
    kind: Literal["status", "spec_change", "message", "warning", "error"]
    text: str
    chips: list[str] = field(default_factory=list)


# Friendly names for tool calls, for "status" events (never the raw tool name+args).
_TOOL_STATUS_TEXT = {
    "get_spec": "Checking the current report...",
    "update_spec": "Updating the report...",
    "run_report": "Running the report...",
}


def _fmt_metric(name: str) -> str:
    return name.replace("_", " ")


def _diff_chips(old: ReportSpec, new: ReportSpec) -> list[str]:
    """Human-readable change chips from a spec diff. This is the one function
    responsible for translating a field-level diff into UI-friendly phrases."""
    chips: list[str] = []

    old_metrics, new_metrics = set(old.metrics), set(new.metrics)
    added = new_metrics - old_metrics
    removed = old_metrics - new_metrics
    for m in sorted(added, key=lambda m: m.value):
        chips.append(f"Added metric: {_fmt_metric(m.value)}")
    for m in sorted(removed, key=lambda m: m.value):
        chips.append(f"Removed metric: {_fmt_metric(m.value)}")

    if old.date_from != new.date_from or old.date_to != new.date_to:
        chips.append(f"Date range: {new.date_from} to {new.date_to}")

    if old.granularity != new.granularity:
        chips.append(f"Granularity: {new.granularity}")

    if old.group_by != new.group_by:
        if new.group_by == "none":
            chips.append("Grouping removed")
        else:
            chips.append(f"Grouping: by {new.group_by}")

    if old.agent_ids != new.agent_ids:
        chips.append(
            f"Agent filter: {len(new.agent_ids)} selected" if new.agent_ids else "Agent filter cleared"
        )

    if old.mailbox_ids != new.mailbox_ids:
        chips.append(
            f"Mailbox filter: {len(new.mailbox_ids)} selected"
            if new.mailbox_ids
            else "Mailbox filter cleared"
        )

    if old.sort != new.sort:
        if new.sort is None:
            chips.append("Sort cleared")
        else:
            chips.append(f"Sort: {_fmt_metric(new.sort.field)} ({new.sort.direction})")

    if old.columns_order != new.columns_order:
        if old.columns_order and new.columns_order and set(old.columns_order) == set(
            new.columns_order
        ):
            chips.append("Swapped columns")
        else:
            chips.append("Columns changed")

    if old.layout != new.layout:
        chips.append(f"Layout: {new.layout}")

    return chips


def to_ui_event(event: InternalEvent) -> Optional[UiEvent]:
    """Map an internal event to a UI event. Returns None for events that
    should stay entirely backend-side (e.g. a ToolCallStarted for get_spec,
    which is not interesting to show the user)."""

    if isinstance(event, ToolCallStarted):
        if event.tool_name == "get_spec":
            return None  # purely internal bookkeeping, not worth a status line
        text = _TOOL_STATUS_TEXT.get(event.tool_name, "Working...")
        return UiEvent(kind="status", text=text)

    if isinstance(event, ToolCallFinished):
        if not event.ok:
            # Validation errors get corrected internally via retry; only
            # surface a lightweight status, never the raw error/args.
            return UiEvent(kind="status", text="That didn't quite work, retrying...")
        if event.tool_name == "run_report":
            return UiEvent(kind="status", text="Report updated.")
        return None

    if isinstance(event, SpecUpdated):
        chips = _diff_chips(event.old_spec, event.new_spec)
        if not chips:
            return None
        return UiEvent(kind="spec_change", text="Report updated", chips=chips)

    if isinstance(event, AssistantSays):
        return UiEvent(kind="message", text=event.text)

    if isinstance(event, Error):
        if event.retriable:
            return None  # internal retry path, not shown to user
        return UiEvent(kind="error", text="Something went wrong updating your report.")

    if isinstance(event, Warning):
        return UiEvent(kind="warning", text=event.message)

    return None
