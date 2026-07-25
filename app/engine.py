"""`execute(spec, dataset) -> ReportTable` — pure function (architecture.md §3).

No I/O, no upstream calls: given a validated `ReportSpec` and a normalised
`Dataset` (already fetched by `upstream.py`), this module slices the date
range, groups by Actor/Mailbox/none, sums, and lays the result out as a
`ReportTable` of raw numbers plus column metadata.

This slice (issue 04) handles **Counters only** — they simply sum. Duration
Metric aggregation (`Σvalue / Σcount`, never an average of averages) is
issue 05's scope; requesting one here raises `UnsupportedMetricError` rather
than silently summing a quantity that must be count-weighted.
"""

from datetime import date

from app.models import ColumnMeta, Metric, ReportRow, ReportSpec, ReportTable
from app.upstream import METRIC_CATALOGUE, Dataset, EntityBreakdown

_METRIC_INFO_BY_KEY = {info.key: info for info in METRIC_CATALOGUE}
_COUNTER_KEYS = frozenset(info.key for info in METRIC_CATALOGUE if info.kind == "counter")


class UnsupportedMetricError(ValueError):
    """A requested Metric is not a Counter, and this slice of the engine only
    aggregates Counters (Duration Metrics arrive in issue 05)."""


def execute(spec: ReportSpec, dataset: Dataset) -> ReportTable:
    unsupported = [m.value for m in spec.metrics if m.value not in _COUNTER_KEYS]
    if unsupported:
        raise UnsupportedMetricError(
            f"engine.execute (issue 04) only aggregates Counters; got non-Counter "
            f"metric(s) {unsupported!r} — Duration Metric aggregation is issue 05's scope."
        )

    indices = _selected_bucket_indices(dataset.ticks, spec.date_from, spec.date_to)
    columns = [_column_meta(m) for m in spec.metrics]

    if spec.group_by == "none":
        rows = _rows_ungrouped(spec, dataset, indices)
    else:
        entities = dataset.actors if spec.group_by == "agent" else dataset.mailboxes
        rows = _rows_grouped(spec, entities, dataset.ticks, indices)

    return ReportTable(columns=columns, rows=rows, totals=_totals(spec, rows))


def _column_meta(metric: Metric) -> ColumnMeta:
    info = _METRIC_INFO_BY_KEY[metric.value]
    return ColumnMeta(key=metric.value, label=_label(metric.value), kind=info.kind, unit=info.unit)


def _label(key: str) -> str:
    return key.replace("_", " ").capitalize()


def _bucket_day(tick: str) -> date:
    return date.fromisoformat(tick[:10])


def _selected_bucket_indices(ticks: list[str], date_from: date, date_to: date) -> list[int]:
    """Indices into the per-day value arrays whose bucket falls in
    [date_from, date_to] inclusive. `ticks` has one more entry than the value
    arrays (api-report-fresh.md §4.2: value[i] is anchored to ticks[i]), so
    the final tick is a boundary, never a bucket, and is excluded here."""
    return [i for i, tick in enumerate(ticks[:-1]) if date_from <= _bucket_day(tick) <= date_to]


def _values_at(
    source: dict[str, list[float]], metrics: list[Metric], index: int
) -> dict[str, float]:
    return {m.value: source[m.value][index] for m in metrics}


def _values_summed(
    source: dict[str, list[float]], metrics: list[Metric], indices: list[int]
) -> dict[str, float]:
    return {m.value: sum(source[m.value][i] for i in indices) for m in metrics}


def _rows_ungrouped(spec: ReportSpec, dataset: Dataset, indices: list[int]) -> list[ReportRow]:
    if spec.granularity == "total":
        values = _values_summed(dataset.metrics, spec.metrics, indices)
        return [ReportRow(bucket="total", group_key=None, group_label=None, values=values)]

    return [
        ReportRow(
            bucket=_bucket_day(dataset.ticks[i]).isoformat(),
            group_key=None,
            group_label=None,
            values=_values_at(dataset.metrics, spec.metrics, i),
        )
        for i in indices
    ]


def _rows_grouped(
    spec: ReportSpec,
    entities: list[EntityBreakdown],
    ticks: list[str],
    indices: list[int],
) -> list[ReportRow]:
    if spec.granularity == "total":
        return [
            ReportRow(
                bucket="total",
                group_key=entity.id,
                group_label=entity.name,
                values=_values_summed(entity.metrics, spec.metrics, indices),
            )
            for entity in entities
        ]

    rows: list[ReportRow] = []
    for i in indices:
        day = _bucket_day(ticks[i]).isoformat()
        for entity in entities:
            rows.append(
                ReportRow(
                    bucket=day,
                    group_key=entity.id,
                    group_label=entity.name,
                    values=_values_at(entity.metrics, spec.metrics, i),
                )
            )
    return rows


def _totals(spec: ReportSpec, rows: list[ReportRow]) -> dict[str, float]:
    """Grand total per metric, summed across every row. Because Counters
    reconcile identically whether summed day-by-day, entity-by-entity, or
    both at once (api-report-fresh.md §4.5), this single generic sum lands on
    the same figure regardless of `group_by` — which is exactly the
    reconciliation property the issue's acceptance criteria check for."""
    totals = {m.value: 0.0 for m in spec.metrics}
    for row in rows:
        for key, value in row.values.items():
            totals[key] += value
    return totals
