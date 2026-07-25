"""
Pydantic v2 models for the report spec contract.

Design note (patch vs replace) — see FINDINGS.md for the full writeup.
Short version: the LLM agent edits the spec via `SpecPatch` (partial update),
never by re-emitting the full `ReportSpec`. `SpecPatch.apply()` merges onto
the existing spec and re-validates the *result* as a whole `ReportSpec`, so
we get full-model validation (cross-field checks like date_from<=date_to)
without forcing the LLM to restate fields it isn't touching.
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Metric(StrEnum):
    """The 15 documented API metrics (see api-probe-findings.md doc section 3a).

    Note several of these are "totals in hours" with a companion `_count`
    field needed to compute a per-ticket average — NOT already averaged.
    """

    ACTIONED_EMAILS = "actioned_emails"
    RESOLVED = "resolved"
    NEW_TICKETS = "new_tickets"
    OPEN = "open"
    REPLIES = "replies"
    NEW_EMAILS = "new_emails"
    REPLIES_TO_RESOLVE = "replies_to_resolve"
    RESOLVE_TIME = "resolve_time"
    RESPONSE_TIME = "response_time"
    TIME_TO_FIRST_REPLY = "time_to_first_reply"
    RESOLVE_TIME_BUSINESS_HOURS = "resolve_time_business_hours"
    RESPONSE_TIME_BUSINESS_HOURS = "response_time_business_hours"
    TIME_TO_FIRST_REPLY_BUSINESS_HOURS = "time_to_first_reply_business_hours"
    HANDLE_TIME = "handle_time"
    SLA_BREACHES = "sla_breaches"


# Metrics that are stored as totals-in-hours with a `<metric>_count` companion
# needed to compute a weighted average. Every metric in this set has an
# implicit sibling column when a per-ticket average is requested.
TIME_METRICS: frozenset[Metric] = frozenset(
    {
        Metric.RESOLVE_TIME,
        Metric.RESPONSE_TIME,
        Metric.TIME_TO_FIRST_REPLY,
        Metric.RESOLVE_TIME_BUSINESS_HOURS,
        Metric.RESPONSE_TIME_BUSINESS_HOURS,
        Metric.TIME_TO_FIRST_REPLY_BUSINESS_HOURS,
        Metric.HANDLE_TIME,
        Metric.REPLIES_TO_RESOLVE,
    }
)

METRIC_DESCRIPTIONS: dict[Metric, str] = {
    Metric.ACTIONED_EMAILS: "Emails actioned (replied to, forwarded, etc.) in the period.",
    Metric.RESOLVED: "Tickets marked resolved in the period.",
    Metric.NEW_TICKETS: "New tickets created in the period.",
    Metric.OPEN: "Tickets open at end of period (snapshot, not a flow metric).",
    Metric.REPLIES: "Replies sent in the period.",
    Metric.NEW_EMAILS: "New inbound emails received in the period.",
    Metric.REPLIES_TO_RESOLVE: "Total replies-to-resolve across tickets; has a _count companion, average = replies_to_resolve / replies_to_resolve_count.",
    Metric.RESOLVE_TIME: "TOTAL time-to-resolve in HOURS across tickets, not an average. Divide by resolve_time_count for the average hours-to-resolve per ticket.",
    Metric.RESPONSE_TIME: "TOTAL response time in HOURS across tickets. Divide by response_time_count for the per-ticket average.",
    Metric.TIME_TO_FIRST_REPLY: "TOTAL time-to-first-reply in HOURS across tickets. Divide by time_to_first_reply_count for the per-ticket average.",
    Metric.RESOLVE_TIME_BUSINESS_HOURS: "Same as resolve_time but counting business hours only. Divide by its _count for the average.",
    Metric.RESPONSE_TIME_BUSINESS_HOURS: "Same as response_time but counting business hours only. Divide by its _count for the average.",
    Metric.TIME_TO_FIRST_REPLY_BUSINESS_HOURS: "Same as time_to_first_reply but counting business hours only. Divide by its _count for the average.",
    Metric.HANDLE_TIME: "TOTAL agent handle time in HOURS across tickets. Divide by handle_time_count for the per-ticket average (this is usually what a user means by 'average handle time').",
    Metric.SLA_BREACHES: "Count of SLA breaches in the period.",
}

Granularity = Literal["day", "week", "total"]
GroupBy = Literal["agent", "mailbox", "none"]
SortDirection = Literal["asc", "desc"]
Layout = Literal["long", "pivot"]


class SortSpec(BaseModel):
    field: str
    direction: SortDirection = "desc"


class ReportSpec(BaseModel):
    """The single contract: the entire state of a report, editable by the agent."""

    metrics: list[Metric] = Field(default_factory=lambda: [Metric.RESOLVED])
    date_from: date
    date_to: date
    granularity: Granularity = "day"
    group_by: GroupBy = "none"
    agent_ids: list[str] = Field(default_factory=list)
    mailbox_ids: list[str] = Field(default_factory=list)
    sort: Optional[SortSpec] = None
    columns_order: list[str] = Field(default_factory=list)
    layout: Layout = "long"

    @model_validator(mode="after")
    def _validate(self) -> "ReportSpec":
        if not self.metrics:
            raise ValueError("metrics must be non-empty: a report needs at least one metric")
        if self.date_from > self.date_to:
            raise ValueError(
                f"date_from ({self.date_from}) must be <= date_to ({self.date_to})"
            )
        if self.columns_order:
            available = self.available_columns()
            unknown = [c for c in self.columns_order if c not in available]
            if unknown:
                raise ValueError(
                    f"columns_order contains columns not in the report: {unknown}. "
                    f"Available columns: {sorted(available)}"
                )
        if self.sort is not None:
            available = self.available_columns()
            if self.sort.field not in available:
                raise ValueError(
                    f"sort.field {self.sort.field!r} must be one of the report's "
                    f"columns (an included metric, or 'group'/'period' where "
                    f"applicable): {sorted(available)}"
                )
        return self

    def available_columns(self) -> set[str]:
        """Columns that will actually exist in the rendered table for this spec."""
        cols: set[str] = set()
        if self.granularity != "total":
            cols.add("period")
        if self.group_by != "none":
            cols.add("group")
        for m in self.metrics:
            cols.add(m.value)
            if m in TIME_METRICS:
                cols.add(f"{m.value}_avg")
        return cols


class SpecPatch(BaseModel):
    """Partial update to a ReportSpec. All fields optional; unset fields are left alone.

    `apply()` merges set fields onto the base spec and re-validates the
    *whole resulting spec* (not just the patch) so cross-field invariants
    (date_from<=date_to, columns_order subset) always hold post-merge.
    """

    metrics: Optional[list[Metric]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    granularity: Optional[Granularity] = None
    group_by: Optional[GroupBy] = None
    agent_ids: Optional[list[str]] = None
    mailbox_ids: Optional[list[str]] = None
    sort: Optional[SortSpec] = None
    columns_order: Optional[list[str]] = None
    layout: Optional[Layout] = None

    def apply(self, spec: ReportSpec) -> ReportSpec:
        base = spec.model_dump(mode="json")
        updates = self.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        base.update(updates)
        # Validate the whole merged dict from scratch so cross-field
        # invariants (date_from<=date_to, columns_order subset) always hold,
        # and nested models (SortSpec) are coerced properly (avoids
        # model_copy's un-validated shallow merge + serializer warnings).
        return ReportSpec.model_validate(base)
