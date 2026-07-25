"""The Report Spec and Report Table (architecture.md §2, §10).

`ReportSpec` is the single validated contract shared by the builder UI, the
report route, and — in later slices — the Assistant and the URL. Issue 04
carried `metrics`, a date range and a single `group_by`; issue 05 adds
`duration_display`, the toggle between the per-ticket average and the period
total for Duration Metrics. The remaining contract fields (`sort`,
`columns_order`, `layout`, `chart_metric`) belong to later slices (06–07) and
are deliberately absent here — adding them early would let code start
depending on fields the engine cannot yet execute.

The load-bearing constraint lives in `group_by`: it is a single
`Literal["none", "agent", "mailbox"]`, never a list or a pair of booleans, so
a report grouped by Actor *and* Mailbox at once is not a validation failure —
it is a value that cannot be constructed in the first place (CONTEXT.md,
architecture.md §2 "Table semantics").
"""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Metric(StrEnum):
    """The upstream metrics this app offers (api-report-fresh.md §4.1),
    excluding `open`, which is always zero and never offered (CONTEXT.md,
    user story 18). Values match the upstream's own field names exactly —
    `app/upstream.py` normalises the wire shape into these same keys.
    """

    ACTIONED_EMAILS = "actioned_emails"
    RESOLVED = "resolved"
    NEW_TICKETS = "new_tickets"
    REPLIES = "replies"
    NEW_EMAILS = "new_emails"
    SLA_BREACHES = "sla_breaches"
    REPLIES_TO_RESOLVE = "replies_to_resolve"
    RESOLVE_TIME = "resolve_time"
    RESPONSE_TIME = "response_time"
    TIME_TO_FIRST_REPLY = "time_to_first_reply"
    RESOLVE_TIME_BUSINESS_HOURS = "resolve_time_business_hours"
    RESPONSE_TIME_BUSINESS_HOURS = "response_time_business_hours"
    TIME_TO_FIRST_REPLY_BUSINESS_HOURS = "time_to_first_reply_business_hours"
    HANDLE_TIME = "handle_time"


class ReportSpec(BaseModel):
    """The declarative definition of a report (CONTEXT.md).

    `group_by` is intentionally a single scalar, never a collection — see
    module docstring. `date_from`/`date_to` are validated for ordering here;
    validating them against the Coverage Window is the report route's job
    (the window is only known at request time, from the upstream `/health`
    memo), not this model's.
    """

    metrics: list[Metric] = Field(min_length=1)
    date_from: date
    date_to: date
    granularity: Literal["day", "total"] = "day"
    group_by: Literal["none", "agent", "mailbox"] = "none"
    duration_display: Literal["avg", "total"] = "avg"
    """Duration Metric display (CONTEXT.md, issue 05): "avg" is the per-ticket,
    count-weighted mean `Σvalue / Σcount` ("how fast" — the default); "total"
    is the raw period sum in hours ("how much work"). Applies only to columns
    of `kind == "duration"`; Counters are unaffected by this field."""

    @model_validator(mode="after")
    def _date_range_is_ordered(self) -> "ReportSpec":
        if self.date_from > self.date_to:
            raise ValueError(f"date_from ({self.date_from}) must be <= date_to ({self.date_to})")
        return self


class ColumnMeta(BaseModel):
    """One Report Table column's metadata — never a formatted string
    (architecture.md §2 "Table semantics"). `kind`/`unit` mirror
    `upstream.MetricInfo` so the frontend can render units and later choose
    duration display without re-deriving them.
    """

    key: str
    label: str
    kind: Literal["counter", "duration", "sum"]
    unit: Literal["count", "hours", "replies"]


class ReportRow(BaseModel):
    """One row of the executed report: raw numeric values only.

    `bucket` is either an ISO day (`granularity: "day"`) or the literal
    `"total"` (`granularity: "total"`). `group_key`/`group_label` are `None`
    when `group_by == "none"`; otherwise they identify the Actor or Mailbox
    the row belongs to.
    """

    bucket: str
    group_key: str | None
    group_label: str | None
    values: dict[str, float | None]
    """`None` marks a Duration Metric cell the engine withholds rather than
    lies about: `duration_display == "avg"` with a zero `_count` is an
    undefined mean, not a real zero (issue 05 fix — a zero-ticket Actor must
    never look like the fastest resolver on the board). `duration_display ==
    "total"` still reports a true `0.0` for the same cell — "did no work" is
    an honest total, only the average is undefined."""
    counts: dict[str, float] = Field(default_factory=dict)
    """The Σcount behind each Duration Metric cell in `values` (issue 05,
    user story 23) — only populated for `kind == "duration"` columns, since a
    Counter has no `_count` companion (CONTEXT.md). Never itself a column;
    the UI surfaces it as a cell tooltip, not a rendered row."""


class ReportTable(BaseModel):
    """The executed result of a Report Spec (CONTEXT.md): columns, rows,
    totals — raw numbers and metadata, formatting happens at render time.
    """

    columns: list[ColumnMeta]
    rows: list[ReportRow]
    totals: dict[str, float | None]
    """`None` marks a cell the engine deliberately withholds rather than
    lies about — currently only `actioned_emails` totalled across Actors
    (issue 05, user story 24): it double-counts by ~52% and only across
    Actors (api-report-fresh.md §4.5), so the total is a dash, not a number
    and not a blank. Every other metric/grouping combination is a float."""
    total_counts: dict[str, float] = Field(default_factory=dict)
    """The Σcount behind each Duration Metric total, mirroring `ReportRow.counts`."""
    warnings: list[str] = Field(default_factory=list)
