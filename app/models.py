"""The Report Spec and Report Table (architecture.md §2, §10).

`ReportSpec` is the single validated contract shared by the builder UI, the
report route, and — in later slices — the Assistant and the URL. This module
only carries the fields issue 04 needs: `metrics`, a date range and a single
`group_by`. The remaining contract fields (`sort`, `columns_order`, `layout`,
`chart_metric`, `duration_display`) belong to later slices (05–07) and are
deliberately absent here — adding them early would let code start depending
on fields the engine cannot yet execute.

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
    values: dict[str, float]


class ReportTable(BaseModel):
    """The executed result of a Report Spec (CONTEXT.md): columns, rows,
    totals — raw numbers and metadata, formatting happens at render time.
    """

    columns: list[ColumnMeta]
    rows: list[ReportRow]
    totals: dict[str, float]
    warnings: list[str] = Field(default_factory=list)
