"""The nine Assistant tools and the repair taxonomy (issue 16, architecture.md
§5, ADR-0002).

Seven **write** tools, each scoped to a cohesive unit of the Report Spec
rather than a raw field (`set_date_range` takes both bounds together — a
two-tool version would allow an inverted range mid-sequence). Two **read**
tools (`run_report`, `get_meta`) let the Assistant look before it speaks.

Every function here is pure: `ReportSpec` (+ `Dataset` for the two tools that
need coverage/catalogue/report data) in, a `ToolOutcome` out. No I/O, no
model, no SSE — that is what makes `apply_batch` testable without a server or
a model (architecture.md §12 level 1, this issue's "heaviest test slice").

**Repair, don't reject.** When a write invalidates an earlier field — a
dropped metric orphaning `chart_metric` or `sort`, a chart pointed at a
metric that isn't selected yet — the tool repairs the spec in place and
reports what it did via `ToolOutcome.adjusted`, a list of `Repair`s built
from the closed `RepairCode` enum (`app/agent/events.py`) — never free text,
by construction (issue 15's `Repair.code` cannot hold a string outside the
enum). Genuine input errors (unknown metric, malformed date, empty metric
list, a range outside the Coverage Window) return `ok=False` with a fixed
`error_category` instead, for the caller to feed back to the model as one
retry.

**One taxonomy row needed an interpretive call.** architecture.md §5 lists
"`set_grouping` orphans a sort on a group column | Repair — clear sort".
`SortSpec.column` is validated (`app/models.py`) to always name a *metric*
that's currently selected — never a grouping/group-label column — so
changing `group_by` alone can never make an existing `sort` reference an
invalid column under the committed `ReportSpec` schema; that literal trigger
does not exist. The reading applied here: a `sort` ranks rows *within* a
Bucket (architecture.md "Table semantics"), and with `group_by == "none"`
there is exactly one row per Bucket — nothing left to rank. Switching
grouping *away* from `"agent"`/`"mailbox"` to `"none"` orphans a sort that
existed to rank the group rows, so it is cleared and reported, matching the
row's verdict ("Repair — clear sort") on the only reading of "a sort on a
group column" the current schema can express. See
`TestSetGroupingOrphaningSort` in `tests/test_agent_tools.py` for the case
this covers.

**Batch reconciliation** (architecture.md §5, ADR-0002): `apply_batch` applies
several tool calls from one model message in order, then discards any
`Repair` reported by an earlier call in the batch if a *later* call in the
same batch explicitly sets the field that Repair touched — a
`dict[field, adjustment]`-shaped rule with "delete on explicit set", no
net-diffing (`_reconcile_batch` below). Without it, "set_metrics then
set_sort" would report a sort clearing that did not survive the turn, and the
Assistant would narrate something untrue (user story 46).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.events import Repair, RepairCode
from app.engine import CoverageRefusedError, UnsupportedMetricError, clamp_to_coverage, execute
from app.models import Metric, ReportSpec
from app.upstream import METRIC_CATALOGUE, Dataset

# The exact nine tool names architecture.md §5 lists — `app/agent/presenter.py`'s
# `_STATUS_TEXT` lookup (issue 15) already keys on this same set.
TOOL_NAMES: frozenset[str] = frozenset(
    {
        "set_date_range",
        "set_metrics",
        "set_grouping",
        "set_sort",
        "set_columns",
        "set_chart",
        "set_layout",
        "run_report",
        "get_meta",
    }
)

ErrorCategory = Literal["validation", "coverage"]


# ── Tool argument schemas — strict, closed-enum where the taxonomy demands it ──


class SetDateRangeArgs(BaseModel):
    """Both bounds together (module docstring) — never settable separately."""

    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date


class SetMetricsArgs(BaseModel):
    """`min_length=1`: "a report with no metrics isn't a report" (architecture.md
    §5) is an error at the schema level, not a spec-validator round trip.
    `list[Metric]` means an invented metric name can never parse — it is a
    validation error here, before it ever reaches `ReportSpec` (user story 44)."""

    model_config = ConfigDict(extra="forbid")

    metrics: list[Metric] = Field(min_length=1)


class SetGroupingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: Literal["none", "agent", "mailbox"]


class SetSortArgs(BaseModel):
    """`column` is a validated `Metric`, not a raw string — an invented or
    unselected column name is caught here (bad enum) or, if it's a real
    metric that just isn't on the report, by `ReportSpec`'s own validator
    when the patch is merged (`_merge` below) — either way, an `Error`."""

    model_config = ConfigDict(extra="forbid")

    column: Metric
    direction: Literal["asc", "desc"] = "desc"


class SetColumnsArgs(BaseModel):
    """Plain strings, not `list[Metric]`: unlike `set_chart`/`set_sort`, a
    column name that doesn't exist is not an invented **Metric** — it is
    handled as `COLUMN_DROPPED`, a Repair, not an Error (architecture.md §5)."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]


class SetChartArgs(BaseModel):
    """`metric: Metric` — an invented chart metric is a schema-level Error
    (user story 44); a real metric that isn't currently selected is the one
    Repair that adds something (`METRIC_AUTO_ADDED`)."""

    model_config = ConfigDict(extra="forbid")

    metric: Metric


class SetLayoutArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    granularity: Literal["day", "total"]
    layout: Literal["long", "pivot"]


class RunReportArgs(BaseModel):
    """No fields — extra args from a confused model are ignored, not fatal."""

    model_config = ConfigDict(extra="ignore")


class GetMetaArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


_ARGS_MODEL: dict[str, type[BaseModel]] = {
    "set_date_range": SetDateRangeArgs,
    "set_metrics": SetMetricsArgs,
    "set_grouping": SetGroupingArgs,
    "set_sort": SetSortArgs,
    "set_columns": SetColumnsArgs,
    "set_chart": SetChartArgs,
    "set_layout": SetLayoutArgs,
    "run_report": RunReportArgs,
    "get_meta": GetMetaArgs,
}


# ── Call / outcome shapes ────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolCall:
    """One model-requested tool call — the pure-function stand-in for the
    real loop's (issue 17) parsed `tool_calls` entry."""

    name: str
    args: dict


@dataclass(frozen=True)
class ToolOutcome:
    """Mirrors `app/agent/events.ToolCallFinished`'s shape (issue 15) plus a
    `result` payload for the two read tools and an `error_category` a future
    caller can map straight onto `TurnError.category`.

    `spec_after` is `None` only when `ok is False`; for the read tools it
    equals `spec_before` (they never change the spec)."""

    name: str
    args: dict
    ok: bool
    adjusted: list[Repair]
    spec_before: ReportSpec
    spec_after: ReportSpec | None
    error_category: ErrorCategory | None = None
    result: dict | None = None


def _ok(
    name: str,
    args: dict,
    spec_before: ReportSpec,
    spec_after: ReportSpec,
    *,
    adjusted: list[Repair] | None = None,
    result: dict | None = None,
) -> ToolOutcome:
    return ToolOutcome(
        name=name,
        args=args,
        ok=True,
        adjusted=adjusted or [],
        spec_before=spec_before,
        spec_after=spec_after,
        result=result,
    )


def _err(
    name: str, args: dict, spec_before: ReportSpec, category: ErrorCategory
) -> ToolOutcome:
    return ToolOutcome(
        name=name,
        args=args,
        ok=False,
        adjusted=[],
        spec_before=spec_before,
        spec_after=None,
        error_category=category,
    )


def _merge(spec: ReportSpec, patch: dict) -> ReportSpec:
    """Dict-merge + re-validate (scratch/agent-spec-lab's proven pattern,
    LAB_NOTES.md): dump the base spec to JSON-mode dict, overlay the patch,
    re-validate the whole thing through `ReportSpec.model_validate` — never
    `model_copy(update=...)`, which skips nested-model validation/coercion.
    Cross-field rules (`sort.column` must still be selected, `date_from <=
    date_to`) only exist post-merge, so validating the merged dict is the
    only way to catch them. Raises `pydantic.ValidationError` on failure —
    every caller below catches it and reports a `"validation"` `ToolOutcome`."""
    data = spec.model_dump(mode="json")
    data.update(patch)
    return ReportSpec.model_validate(data)


# ── Write tools ──────────────────────────────────────────────────────────


def _set_date_range(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetDateRangeArgs.model_validate(args)
    except ValidationError:
        return _err("set_date_range", args, spec, "validation")

    try:
        candidate = _merge(
            spec,
            {"date_from": parsed.date_from.isoformat(), "date_to": parsed.date_to.isoformat()},
        )
    except ValidationError:
        # Inverted range (date_from > date_to) — the single-call pair tool
        # still rejects a genuinely backwards request; it just can never be
        # asked to leave the range inverted *mid-sequence* (module docstring).
        return _err("set_date_range", args, spec, "validation")

    try:
        clamped, warnings = clamp_to_coverage(candidate, dataset.coverage)
    except CoverageRefusedError:
        # Zero overlap: architecture.md §5 — error and refuse, never repair.
        return _err("set_date_range", args, spec, "coverage")

    adjusted = [Repair(code=RepairCode.DATE_RANGE_CLAMPED)] if warnings else []
    return _ok("set_date_range", args, spec, clamped, adjusted=adjusted)


def _set_metrics(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetMetricsArgs.model_validate(args)
    except ValidationError:
        # Covers both the empty-list case (schema `min_length=1`) and an
        # unknown/invented metric name (schema `list[Metric]`).
        return _err("set_metrics", args, spec, "validation")

    new_values = {m.value for m in parsed.metrics}
    adjusted: list[Repair] = []
    patch: dict = {"metrics": [m.value for m in parsed.metrics]}

    if spec.chart_metric is not None and spec.chart_metric.value not in new_values:
        patch["chart_metric"] = None
        adjusted.append(Repair(code=RepairCode.CHART_METRIC_RESET))

    if spec.sort is not None and spec.sort.column not in new_values:
        patch["sort"] = None
        adjusted.append(Repair(code=RepairCode.SORT_CLEARED))

    try:
        spec_after = _merge(spec, patch)
    except ValidationError:
        return _err("set_metrics", args, spec, "validation")

    return _ok("set_metrics", args, spec, spec_after, adjusted=adjusted)


def _set_grouping(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetGroupingArgs.model_validate(args)
    except ValidationError:
        return _err("set_grouping", args, spec, "validation")

    adjusted: list[Repair] = []
    patch: dict = {"group_by": parsed.by}

    # See module docstring: grouping away from agent/mailbox to "none"
    # orphans a sort that ranked group rows within a Bucket — nothing is
    # left to rank with a single row per Bucket, so it's cleared.
    if spec.group_by != "none" and parsed.by == "none" and spec.sort is not None:
        patch["sort"] = None
        adjusted.append(Repair(code=RepairCode.SORT_CLEARED))

    try:
        spec_after = _merge(spec, patch)
    except ValidationError:
        return _err("set_grouping", args, spec, "validation")

    return _ok("set_grouping", args, spec, spec_after, adjusted=adjusted)


def _set_sort(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetSortArgs.model_validate(args)
    except ValidationError:
        return _err("set_sort", args, spec, "validation")

    try:
        spec_after = _merge(
            spec, {"sort": {"column": parsed.column.value, "direction": parsed.direction}}
        )
    except ValidationError:
        # A real Metric that just isn't one of `spec.metrics` right now —
        # ReportSpec's own cross-field validator catches this on merge.
        return _err("set_sort", args, spec, "validation")

    return _ok("set_sort", args, spec, spec_after)


def _set_columns(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetColumnsArgs.model_validate(args)
    except ValidationError:
        return _err("set_columns", args, spec, "validation")

    metric_values = {m.value for m in spec.metrics}
    kept = [key for key in parsed.order if key in metric_values]
    dropped_any = len(kept) != len(parsed.order)
    adjusted = [Repair(code=RepairCode.COLUMN_DROPPED)] if dropped_any else []

    try:
        spec_after = _merge(spec, {"columns_order": kept})
    except ValidationError:
        return _err("set_columns", args, spec, "validation")

    return _ok("set_columns", args, spec, spec_after, adjusted=adjusted)


def _set_chart(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetChartArgs.model_validate(args)
    except ValidationError:
        # An invented metric name (user story 44) — never auto-added,
        # always an Error.
        return _err("set_chart", args, spec, "validation")

    adjusted: list[Repair] = []
    patch: dict = {"chart_metric": parsed.metric.value}

    if parsed.metric not in spec.metrics:
        new_metrics = [*spec.metrics, parsed.metric]
        patch["metrics"] = [m.value for m in new_metrics]
        adjusted.append(Repair(code=RepairCode.METRIC_AUTO_ADDED, metric=parsed.metric))

    try:
        spec_after = _merge(spec, patch)
    except ValidationError:
        return _err("set_chart", args, spec, "validation")

    return _ok("set_chart", args, spec, spec_after, adjusted=adjusted)


def _set_layout(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    try:
        parsed = SetLayoutArgs.model_validate(args)
    except ValidationError:
        return _err("set_layout", args, spec, "validation")

    try:
        spec_after = _merge(spec, {"granularity": parsed.granularity, "layout": parsed.layout})
    except ValidationError:
        return _err("set_layout", args, spec, "validation")

    return _ok("set_layout", args, spec, spec_after)


# ── Read tools ───────────────────────────────────────────────────────────


def _run_report(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    """Executes the *current* spec via `engine.execute` — the one function
    every caller passes through to get a `ReportTable` at all (`engine.py`'s
    own docstring names this exact use). Coverage validation therefore comes
    for free: this function never re-checks the range itself, it just lets
    `CoverageRefusedError` propagate into an Error, same as any other genuine
    input problem (constraint 2 in the issue brief)."""
    try:
        parsed_args = RunReportArgs.model_validate(args)
    except ValidationError:
        return _err("run_report", args, spec, "validation")
    del parsed_args  # no fields; validated only to reject unexpected shapes

    try:
        table = execute(spec, dataset)
    except CoverageRefusedError:
        return _err("run_report", args, spec, "coverage")
    except UnsupportedMetricError:
        return _err("run_report", args, spec, "validation")

    result = {
        "columns": [c.key for c in table.columns],
        "row_count": len(table.rows),
        "rows": [
            {"bucket": r.bucket, "group_label": r.group_label, "values": r.values}
            for r in table.rows[:8]
        ],
        "totals": table.totals,
        "warnings": table.warnings,
    }
    return _ok("run_report", args, spec, spec, result=result)


def _get_meta(spec: ReportSpec, dataset: Dataset, args: dict) -> ToolOutcome:
    """Actors/Mailboxes/Metrics/Coverage Window, so the model can resolve
    names to ids and never guess a Metric key (architecture.md §5)."""
    try:
        parsed_args = GetMetaArgs.model_validate(args)
    except ValidationError:
        return _err("get_meta", args, spec, "validation")
    del parsed_args

    result = {
        "coverage": {"from": dataset.coverage.from_date, "to": dataset.coverage.to_date},
        "metrics": [
            {"key": info.key, "kind": info.kind, "unit": info.unit} for info in METRIC_CATALOGUE
        ],
        "actors": [{"id": a.id, "name": a.name} for a in dataset.actors],
        "mailboxes": [{"id": m.id, "name": m.name} for m in dataset.mailboxes],
    }
    return _ok("get_meta", args, spec, spec, result=result)


_DISPATCH = {
    "set_date_range": _set_date_range,
    "set_metrics": _set_metrics,
    "set_grouping": _set_grouping,
    "set_sort": _set_sort,
    "set_columns": _set_columns,
    "set_chart": _set_chart,
    "set_layout": _set_layout,
    "run_report": _run_report,
    "get_meta": _get_meta,
}


def apply_one(spec: ReportSpec, dataset: Dataset, call: ToolCall) -> ToolOutcome:
    """Apply a single tool call to `spec`. Unknown tool names (never expected
    from a real dispatch over `TOOL_NAMES`, but defensive against a
    malformed call) are a `"validation"` Error, never a crash."""
    handler = _DISPATCH.get(call.name)
    if handler is None:
        return _err(call.name, call.args, spec, "validation")
    return handler(spec, dataset, call.args)


# Which spec field(s) each tool *explicitly* sets when it succeeds — the
# `dict[field, adjustment]` key space the batch-reconciliation rule
# (ADR-0002, module docstring) discards on.
_TOOL_TARGET_FIELDS: dict[str, frozenset[str]] = {
    "set_date_range": frozenset({"date_from", "date_to"}),
    "set_metrics": frozenset({"metrics"}),
    "set_grouping": frozenset({"group_by"}),
    "set_sort": frozenset({"sort"}),
    "set_columns": frozenset({"columns_order"}),
    "set_chart": frozenset({"chart_metric"}),
    "set_layout": frozenset({"granularity", "layout"}),
    "run_report": frozenset(),
    "get_meta": frozenset(),
}

# Which field each Repair code adjusts — the other half of the same rule.
_REPAIR_TARGET_FIELDS: dict[RepairCode, frozenset[str]] = {
    RepairCode.CHART_METRIC_RESET: frozenset({"chart_metric"}),
    RepairCode.SORT_CLEARED: frozenset({"sort"}),
    RepairCode.COLUMN_DROPPED: frozenset({"columns_order"}),
    RepairCode.METRIC_AUTO_ADDED: frozenset({"metrics"}),
    RepairCode.DATE_RANGE_CLAMPED: frozenset({"date_from", "date_to"}),
}


def _reconcile_batch(outcomes: list[ToolOutcome]) -> list[ToolOutcome]:
    """Discard any `Repair` an earlier call reported if a *later* call in the
    same batch explicitly set the field that Repair touched (ADR-0002,
    module docstring). Only successful later calls count — a call that
    itself errored never set anything.

    This never rewrites `spec_after` (already net-correct, being derived
    from the validated spec diff — ADR-0002); it only prunes what gets
    narrated as a Repair, which is what protects the Assistant's prose from
    describing an adjustment that did not survive the turn."""
    reconciled: list[ToolOutcome] = []
    for i, outcome in enumerate(outcomes):
        if not outcome.adjusted:
            reconciled.append(outcome)
            continue

        later_fields: set[str] = set()
        for later in outcomes[i + 1 :]:
            if later.ok:
                later_fields |= _TOOL_TARGET_FIELDS.get(later.name, frozenset())

        surviving = [
            repair
            for repair in outcome.adjusted
            if not (_REPAIR_TARGET_FIELDS.get(repair.code, frozenset()) & later_fields)
        ]
        if surviving == outcome.adjusted:
            reconciled.append(outcome)
        else:
            reconciled.append(replace(outcome, adjusted=surviving))

    return reconciled


def apply_batch(spec: ReportSpec, dataset: Dataset, calls: list[ToolCall]) -> list[ToolOutcome]:
    """Apply several tool calls from one model message, in order (verified
    live: three at a time, architecture.md §5), then reconcile Repairs across
    the batch (`_reconcile_batch`). Each write applies immediately against
    the *running* spec — a later call in the batch sees the prior calls'
    effects, which is what makes progressive, one-field-at-a-time
    application meaningful for a real multi-call turn."""
    outcomes: list[ToolOutcome] = []
    current = spec
    for call in calls:
        outcome = apply_one(current, dataset, call)
        outcomes.append(outcome)
        if outcome.ok and outcome.spec_after is not None:
            current = outcome.spec_after
    return _reconcile_batch(outcomes)
