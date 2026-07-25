"""
Minimal report engine over the real-data fixture
(resp-full-unscoped-latest.json — an unscoped, full-window, all-metrics pull
so the fixture has all ~103 real mailboxes, not the 5-mailbox spec-example
subset the lab originally shipped with).

Just enough to make `run_report` a real tool the fake agent can call and get
back numbers that can be asserted against in tests. Mirrors the empirical
findings in api-probe-findings.md, INCLUDING the second-pass corrections:

- The fixture covers a fixed 14-day window (2026-07-10 .. 2026-07-23, 14
  daily buckets from 15 ticks). Requests outside that window are clamped
  with a warning (mirrors the real API's silent-clamp behavior, except we
  tell the user instead of silently lying).
- CORRECTED: both `actors` and `mailbox` are reliable breakdowns — per-agent
  and per-mailbox sums reconcile with top-level totals for every metric
  EXCEPT `actioned_emails` under the `actors` breakdown specifically (a
  genuine upstream data inconsistency: actor-sum > top-level total). The
  engine checks this dynamically per-metric/per-grouping rather than
  hardcoding "mailbox bad" (pass-1's conclusion, drawn from a 5-mailbox
  sample that happened to be low-volume, was wrong) or "actors always fine"
  (also wrong, for actioned_emails specifically).
- `actors` and `mailbox` are independent, non-nested breakdowns of the same
  top-level totals — there is no agent×mailbox cross-breakdown in the
  upstream data. A spec asking to group by one dimension while also
  filtering by the other cannot be honored without fabricating numbers, so
  the engine raises rather than silently returning something plausible-but-
  wrong.
- A mailbox_ids/agent_ids filter only has an observable effect when
  group_by matches that same dimension (matches the real API's behavior:
  scope/filters don't touch top-level totals, only the mailbox breakdown
  list). Setting a filter that doesn't match group_by is accepted but
  warned about, not silently ignored.
- Time metrics (see models.TIME_METRICS) are stored as totals in HOURS with
  a companion `_count`; averages are `sum(metric) / sum(metric_count)`,
  i.e. a weighted average, not a mean-of-daily-values or mean-of-means.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from models import TIME_METRICS, Metric, ReportSpec

FIXTURE_PATH = Path(__file__).resolve().parent / "resp-full-unscoped-latest.json"

# Absolute tolerance for reconciliation checks (sum-of-breakdown vs top-level
# total). Time metrics are floats with plenty of fractional digits; give a
# little slack for floating point noise while still catching the real
# actioned_emails/actors inconsistency (28941 vs 19024 — nowhere near this).
_RECONCILE_TOLERANCE = 1e-6


@dataclass
class Table:
    columns: list[str]
    rows: list[dict]
    warnings: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.rows) == 0


def _load_fixture() -> dict:
    raw = json.loads(FIXTURE_PATH.read_text())
    return raw["response_json"]


def load_fixture() -> dict:
    """Public loader, for tests and callers outside this module."""
    return _load_fixture()


def _tick_dates(fixture: dict) -> list[date]:
    # ticks has N+1 boundary marks for N buckets; use the first N as bucket-start dates.
    ticks = fixture["ticks"]
    n_buckets = len(fixture["resolved"])
    return [
        datetime.fromisoformat(t.replace("Z", "+00:00")).date() for t in ticks[:n_buckets]
    ]


def data_window(fixture: dict | None = None) -> tuple[date, date]:
    fixture = fixture or _load_fixture()
    dates = _tick_dates(fixture)
    return min(dates), max(dates)


def _clamp_range(
    date_from: date, date_to: date, fixture: dict
) -> tuple[date, date, list[str]]:
    warnings: list[str] = []
    win_from, win_to = data_window(fixture)
    new_from, new_to = date_from, date_to
    if date_to < win_from or date_from > win_to:
        # zero overlap -> clamp to full window (mirrors the API's own fallback,
        # but we surface it instead of silently substituting data)
        warnings.append(
            f"Requested range {date_from}..{date_to} has no overlap with the "
            f"available data window ({win_from}..{win_to}); showing the full "
            f"available window instead."
        )
        new_from, new_to = win_from, win_to
    else:
        if date_from < win_from:
            warnings.append(
                f"date_from {date_from} is before the data window start "
                f"({win_from}); clamped."
            )
            new_from = win_from
        if date_to > win_to:
            warnings.append(
                f"date_to {date_to} is after the data window end ({win_to}); clamped."
            )
            new_to = win_to
    return new_from, new_to, warnings


def _bucket_indices(dates: list[date], date_from: date, date_to: date) -> list[int]:
    return [i for i, d in enumerate(dates) if date_from <= d <= date_to]


def _series_for(source: dict, metric: Metric, idxs: list[int]) -> list[float]:
    return [source[metric.value][i] for i in idxs]


def _weighted_avg(total: float, count: float) -> float | None:
    if not count:
        return None
    return total / count


class CrossBreakdownNotSupported(ValueError):
    """Raised when a spec asks the engine to group by one dimension (agent or
    mailbox) while also filtering by the other. The upstream data has no
    agent×mailbox cross-breakdown -- `actors` and `mailbox` are independent,
    non-nested arrays -- so honoring this would mean fabricating numbers."""


def _check_cross_breakdown(spec: ReportSpec) -> None:
    if spec.group_by == "agent" and spec.mailbox_ids:
        raise CrossBreakdownNotSupported(
            "Cannot group by agent while filtering by mailbox_ids: the upstream "
            "API has no agent x mailbox cross-breakdown (actors and mailbox are "
            "independent, non-nested arrays of the same top-level totals). "
            "Remove the mailbox filter, or switch group_by to 'mailbox'."
        )
    if spec.group_by == "mailbox" and spec.agent_ids:
        raise CrossBreakdownNotSupported(
            "Cannot group by mailbox while filtering by agent_ids: the upstream "
            "API has no agent x mailbox cross-breakdown (actors and mailbox are "
            "independent, non-nested arrays of the same top-level totals). "
            "Remove the agent filter, or switch group_by to 'agent'."
        )


def _filter_effect_warnings(spec: ReportSpec) -> list[str]:
    warnings: list[str] = []
    if spec.mailbox_ids and spec.group_by != "mailbox":
        warnings.append(
            "mailbox_ids is set but group_by is not 'mailbox': the upstream API "
            "does not filter top-level totals by mailbox, so this filter has no "
            "effect on the numbers shown. Set group_by='mailbox' to see "
            "per-mailbox figures."
        )
    if spec.agent_ids and spec.group_by != "agent":
        warnings.append(
            "agent_ids is set but group_by is not 'agent': the upstream API "
            "does not filter top-level totals by agent, so this filter has no "
            "effect on the numbers shown. Set group_by='agent' to see "
            "per-agent figures."
        )
    return warnings


def _reconciliation_warnings(
    spec: ReportSpec, fixture: dict, idxs: list[int]
) -> list[str]:
    """Compare sum-over-breakdown vs top-level total, per requested metric,
    for the active group_by dimension -- but only when that dimension isn't
    itself filtered down to a subset (a genuine subset legitimately sums to
    less than the total; that's not a data-quality problem)."""
    warnings: list[str] = []
    if spec.group_by == "agent" and not spec.agent_ids:
        sources, dim = fixture["actors"], "agent"
    elif spec.group_by == "mailbox" and not spec.mailbox_ids:
        sources, dim = fixture["mailbox"], "mailbox"
    else:
        return warnings

    for m in spec.metrics:
        top_total = sum(fixture[m.value][i] for i in idxs)
        breakdown_total = sum(sum(s[m.value][i] for i in idxs) for s in sources)
        if abs(breakdown_total - top_total) > _RECONCILE_TOLERANCE:
            warnings.append(
                f"{m.value}: per-{dim} breakdown sums to {breakdown_total:g}, "
                f"which does not match the top-level total {top_total:g} -- "
                f"known upstream data inconsistency, treat this metric's "
                f"per-{dim} numbers with caution."
            )
    return warnings


def run_report(spec: ReportSpec, fixture: dict | None = None) -> Table:
    fixture = fixture or _load_fixture()
    warnings: list[str] = []

    _check_cross_breakdown(spec)
    warnings.extend(_filter_effect_warnings(spec))

    clamped_from, clamped_to, clamp_warnings = _clamp_range(
        spec.date_from, spec.date_to, fixture
    )
    warnings.extend(clamp_warnings)

    dates = _tick_dates(fixture)
    idxs = _bucket_indices(dates, clamped_from, clamped_to)

    warnings.extend(_reconciliation_warnings(spec, fixture, idxs))

    if spec.layout == "pivot":
        if spec.group_by == "none" or spec.granularity == "total":
            raise ValueError(
                "layout='pivot' requires both a group axis (group_by != 'none') "
                "and a period axis (granularity != 'total') to pivot on; got "
                f"group_by={spec.group_by!r}, granularity={spec.granularity!r}."
            )
        long_rows = _build_grouped_rows(spec, fixture, dates, idxs)
        if spec.sort:
            long_rows = _sort_rows(long_rows, spec.sort)
        columns, rows = _pivot(long_rows, spec.metrics)
        return Table(columns=columns, rows=rows, warnings=warnings)

    columns = list(spec.columns_order) if spec.columns_order else sorted(
        spec.available_columns()
    )

    if spec.group_by in ("agent", "mailbox"):
        rows = _build_grouped_rows(spec, fixture, dates, idxs)
    else:
        rows = _build_ungrouped_rows(spec, fixture, dates, idxs)

    if spec.sort:
        rows = _sort_rows(rows, spec.sort)

    return Table(columns=columns, rows=rows, warnings=warnings)


def _sort_rows(rows: list[dict], sort) -> list[dict]:
    key = sort.field
    reverse = sort.direction == "desc"
    return sorted(rows, key=lambda r: (r.get(key) is None, r.get(key, 0)), reverse=reverse)


def _build_grouped_rows(
    spec: ReportSpec, fixture: dict, dates: list[date], idxs: list[int]
) -> list[dict]:
    """One row per (source) when granularity=='total', else one row per
    (source, period) -- lets group_by combine meaningfully with day/week
    granularity instead of always collapsing the whole range into one row."""
    if spec.group_by == "agent":
        sources = fixture["actors"]
        if spec.agent_ids:
            sources = [
                a for a in sources if a["id"] in spec.agent_ids or a["user_id"] in spec.agent_ids
            ]
        label_key = "name"
    else:
        sources = fixture["mailbox"]
        if spec.mailbox_ids:
            sources = [m for m in sources if m["id"] in spec.mailbox_ids]
        label_key = "name"

    rows: list[dict] = []
    if spec.granularity == "total":
        for source in sources:
            row = _row_for_source(source, spec, idxs, group_label=source[label_key])
            if any(row.get(m.value, 0) for m in spec.metrics):
                rows.append(row)
    else:
        period_groups = _period_groups(dates, idxs, spec.granularity)
        for source in sources:
            for label, sub_idxs in period_groups:
                row = _row_for_source(
                    source, spec, sub_idxs, group_label=source[label_key], period_label=label
                )
                if any(row.get(m.value, 0) for m in spec.metrics):
                    rows.append(row)
    return rows


def _build_ungrouped_rows(
    spec: ReportSpec, fixture: dict, dates: list[date], idxs: list[int]
) -> list[dict]:
    if spec.granularity == "total":
        return [_row_for_source(fixture, spec, idxs, group_label=None)]
    period_groups = _period_groups(dates, idxs, spec.granularity)
    return [
        _row_for_source(fixture, spec, sub_idxs, group_label=None, period_label=label)
        for label, sub_idxs in period_groups
    ]


def _period_groups(
    dates: list[date], idxs: list[int], granularity: str
) -> list[tuple[str, list[int]]]:
    if granularity == "day":
        return [(dates[i].isoformat(), [i]) for i in idxs]
    if granularity == "week":
        groups: dict[str, list[int]] = {}
        for i in idxs:
            iso_year, iso_week, _ = dates[i].isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"
            groups.setdefault(label, []).append(i)
        return sorted(groups.items())
    raise ValueError(f"unexpected granularity in _period_groups: {granularity}")


def _row_for_source(
    source: dict,
    spec: ReportSpec,
    idxs: list[int],
    group_label: str | None,
    period_label: str | None = None,
) -> dict:
    row: dict = {}
    if group_label is not None:
        row["group"] = group_label
    if period_label is not None:
        row["period"] = period_label
    elif spec.granularity == "total":
        row["period"] = "total"
    for m in spec.metrics:
        series = _series_for(source, m, idxs)
        total = sum(series)
        row[m.value] = round(total, 4)
        if m in TIME_METRICS:
            count_series = source.get(f"{m.value}_count", [])
            count_total = sum(count_series[i] for i in idxs) if count_series else 0
            avg = _weighted_avg(total, count_total)
            row[f"{m.value}_avg"] = round(avg, 4) if avg is not None else None
    return row


def _metric_columns(metrics: list[Metric]) -> list[str]:
    cols: list[str] = []
    for m in metrics:
        cols.append(m.value)
        if m in TIME_METRICS:
            cols.append(f"{m.value}_avg")
    return cols


def _pivot(long_rows: list[dict], metrics: list[Metric]) -> tuple[list[str], list[dict]]:
    """Transpose group_by long-format rows (one per period x group) into a
    period-indexed pivot: one row per period, one column per (group, metric)
    pair, named '<group>::<metric>'. Every value from the long table appears
    exactly once in the pivot -- this is a lossless reshape, not an
    aggregation, so round-tripping long -> pivot must preserve every value."""
    periods: list[str] = []
    groups: list[str] = []
    seen_periods: set[str] = set()
    seen_groups: set[str] = set()
    for r in long_rows:
        if r["period"] not in seen_periods:
            seen_periods.add(r["period"])
            periods.append(r["period"])
        if r["group"] not in seen_groups:
            seen_groups.add(r["group"])
            groups.append(r["group"])

    metric_cols = _metric_columns(metrics)
    index = {(r["period"], r["group"]): r for r in long_rows}

    pivot_rows = []
    for p in periods:
        prow: dict = {"period": p}
        for g in groups:
            src = index.get((p, g))
            for mc in metric_cols:
                prow[f"{g}::{mc}"] = src.get(mc) if src else None
        pivot_rows.append(prow)

    columns = ["period"] + [f"{g}::{mc}" for g in groups for mc in metric_cols]
    return columns, pivot_rows


def compact_summary(table: Table, max_rows: int = 8) -> str:
    """Compact textual summary of a table, for feeding back to the LLM as a tool result."""
    lines = [f"columns: {', '.join(table.columns)}", f"row_count: {len(table.rows)}"]
    for row in table.rows[:max_rows]:
        lines.append(str(row))
    if len(table.rows) > max_rows:
        lines.append(f"... ({len(table.rows) - max_rows} more rows)")
    if table.warnings:
        lines.append("warnings: " + " | ".join(table.warnings))
    return "\n".join(lines)
