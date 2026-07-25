"""`execute(spec, dataset) -> ReportTable` — pure function (architecture.md §3).

No I/O, no upstream calls: given a validated `ReportSpec` and a normalised
`Dataset` (already fetched by `upstream.py`), this module slices the date
range, groups by Actor/Mailbox/none, aggregates, and lays the result out as a
`ReportTable` of raw numbers plus column metadata.

Issue 04 handled **Counters only** — they simply sum. This slice (issue 05)
adds **Duration Metrics**: each is a *sum* with a `_count` companion, and
must be aggregated as `Σvalue / Σcount` — a count-weighted mean — across both
days and entities, never by averaging per-bucket averages (CONTEXT.md,
api-report-fresh.md §6.1). `replies_to_resolve` (`kind == "sum"`) is still
out of this slice's scope and continues to raise `UnsupportedMetricError`.

Two rules only this module enforces:

- **Totals are recomputed from the top-level dataset**, never by summing
  already-aggregated row values. A row showing a per-ticket average cannot be
  summed with its peers to produce a correct total average — that is exactly
  the "averaging averages" defect. Because Actor and Mailbox are independent
  marginals of the same top-level arrays (api-report-fresh.md §6.1), a
  top-level `Σvalue / Σcount` over the selected buckets is *also* the
  correct grand total regardless of `group_by` — with one deliberate
  exception, below.
- **`actioned_emails` grouped by Actor is non-additive** (api-report-fresh.md
  §4.5: summing it across Actors over-counts by ~52%, and only across
  Actors). Its totals cell is withheld (`None`, rendered as a dash) rather
  than showing either the correct-but-inconsistent-with-the-rows top-level
  figure or the wrong summed-rows figure, and a `Warning` explains why.
- **A zero-count Duration Metric average is `None`, never `0.0`.** `Σvalue /
  Σcount` is undefined with `Σcount == 0`; displaying `0.0` would read as
  "resolved instantly" rather than "no data", and would float an Actor who
  did nothing to the top of an ascending leaderboard (issue 07). This
  applies wherever the average is computed — per-row cells, per-entity
  totals, and the grand totals row — via the single `_display_value` used by
  all three. `duration_display == "total"` is unaffected: a period total of
  `0.0` for an entity that did no work is a true, not undefined, number.
"""

from datetime import date

from app.models import ColumnMeta, Metric, ReportRow, ReportSpec, ReportTable
from app.upstream import METRIC_CATALOGUE, Dataset, EntityBreakdown

_METRIC_INFO_BY_KEY = {info.key: info for info in METRIC_CATALOGUE}
_COUNTER_KEYS = frozenset(info.key for info in METRIC_CATALOGUE if info.kind == "counter")
_DURATION_KEYS = frozenset(info.key for info in METRIC_CATALOGUE if info.kind == "duration")
_SUPPORTED_KEYS = _COUNTER_KEYS | _DURATION_KEYS

# The one metric that double-counts when summed across Actors (CONTEXT.md,
# api-report-fresh.md §4.5) — and only across Actors; it reconciles exactly
# across Mailboxes. `group_by == "agent"` is the upstream/spec spelling for
# what CONTEXT.md calls the Actor breakdown.
_NON_ADDITIVE_ACROSS_ACTORS = Metric.ACTIONED_EMAILS.value
_NON_ADDITIVE_GROUPING = "agent"


class UnsupportedMetricError(ValueError):
    """A requested Metric is neither a Counter nor a Duration Metric — this
    slice of the engine does not aggregate `kind == "sum"` metrics
    (`replies_to_resolve`)."""


def execute(spec: ReportSpec, dataset: Dataset) -> ReportTable:
    unsupported = [m.value for m in spec.metrics if m.value not in _SUPPORTED_KEYS]
    if unsupported:
        raise UnsupportedMetricError(
            f"engine.execute aggregates Counters and Duration Metrics only; got "
            f"unsupported metric(s) {unsupported!r} (kind == 'sum' is out of scope)."
        )

    indices = _selected_bucket_indices(dataset.ticks, spec.date_from, spec.date_to)
    columns = [_column_meta(m) for m in spec.metrics]

    if spec.group_by == "none":
        rows = _rows_ungrouped(spec, dataset, indices)
    else:
        entities = dataset.actors if spec.group_by == "agent" else dataset.mailboxes
        rows = _rows_grouped(spec, entities, dataset.ticks, indices)

    totals, total_counts, warnings = _totals(spec, dataset, indices)
    return ReportTable(
        columns=columns, rows=rows, totals=totals, total_counts=total_counts, warnings=warnings
    )


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


def _metric_total_and_count(
    values: dict[str, list[float]],
    counts: dict[str, list[float]],
    metric: Metric,
    indices: list[int],
) -> tuple[float, float | None]:
    """`(Σvalue, Σcount)` over `indices` for one metric. `Σcount` is `None`
    for a Counter (no `_count` companion, CONTEXT.md); for a Duration Metric
    it is the denominator `_display_value` needs, and the number the
    `_count` tooltip (user story 23) shows."""
    total_value = sum(values[metric.value][i] for i in indices)
    if metric.value not in counts:
        return total_value, None
    total_count = sum(counts[metric.value][i] for i in indices)
    return total_value, total_count


def _display_value(
    total_value: float, total_count: float | None, duration_display: str
) -> float | None:
    """A Counter (`total_count is None`) is always its raw sum.

    A Duration Metric under `duration_display == "total"` is also always its
    raw sum: `0.0` there is an honest "did no work" — not the number this
    function is careful about.

    Under `"avg"` it is the count-weighted mean `Σvalue / Σcount` ("how
    fast") — computed here, never as an average of per-bucket averages
    (CONTEXT.md). With `total_count == 0` that mean is *undefined*, not
    zero: `0.0` would read on screen as the fastest possible resolution,
    the exact plausible-looking wrong number this slice exists to catch
    (an Actor who resolved nothing must not rank first on an ascending
    leaderboard in issue 07). So a zero-count average is withheld as `None`
    — the same sentinel `actioned_emails` already uses for a total the
    engine cannot honestly produce — and rendered as a dash, never `0.0`
    and never a crash."""
    if total_count is None or duration_display == "total":
        return total_value
    if total_count == 0:
        return None
    return total_value / total_count


def _row_values(
    spec: ReportSpec,
    values: dict[str, list[float]],
    counts: dict[str, list[float]],
    indices: list[int],
) -> tuple[dict[str, float | None], dict[str, float]]:
    row_values: dict[str, float | None] = {}
    row_counts: dict[str, float] = {}
    for m in spec.metrics:
        total_value, total_count = _metric_total_and_count(values, counts, m, indices)
        row_values[m.value] = _display_value(total_value, total_count, spec.duration_display)
        if total_count is not None:
            row_counts[m.value] = total_count
    return row_values, row_counts


def _rows_ungrouped(spec: ReportSpec, dataset: Dataset, indices: list[int]) -> list[ReportRow]:
    if spec.granularity == "total":
        values, counts = _row_values(spec, dataset.metrics, dataset.counts, indices)
        return [
            ReportRow(
                bucket="total", group_key=None, group_label=None, values=values, counts=counts
            )
        ]

    rows = []
    for i in indices:
        values, counts = _row_values(spec, dataset.metrics, dataset.counts, [i])
        rows.append(
            ReportRow(
                bucket=_bucket_day(dataset.ticks[i]).isoformat(),
                group_key=None,
                group_label=None,
                values=values,
                counts=counts,
            )
        )
    return rows


def _rows_grouped(
    spec: ReportSpec,
    entities: list[EntityBreakdown],
    ticks: list[str],
    indices: list[int],
) -> list[ReportRow]:
    if spec.granularity == "total":
        rows = []
        for entity in entities:
            values, counts = _row_values(spec, entity.metrics, entity.counts, indices)
            rows.append(
                ReportRow(
                    bucket="total",
                    group_key=entity.id,
                    group_label=entity.name,
                    values=values,
                    counts=counts,
                )
            )
        return rows

    rows = []
    for i in indices:
        day = _bucket_day(ticks[i]).isoformat()
        for entity in entities:
            values, counts = _row_values(spec, entity.metrics, entity.counts, [i])
            rows.append(
                ReportRow(
                    bucket=day,
                    group_key=entity.id,
                    group_label=entity.name,
                    values=values,
                    counts=counts,
                )
            )
    return rows


def _totals(
    spec: ReportSpec, dataset: Dataset, indices: list[int]
) -> tuple[dict[str, float | None], dict[str, float], list[str]]:
    """Grand total per metric, computed from the top-level dataset arrays
    over the selected buckets — see the module docstring for why this beats
    summing rows. `actioned_emails` grouped by Actor is the one deliberate
    exception: a `None` total plus a `Warning`, never a number."""
    totals: dict[str, float | None] = {}
    total_counts: dict[str, float] = {}
    warnings: list[str] = []

    for m in spec.metrics:
        if spec.group_by == _NON_ADDITIVE_GROUPING and m.value == _NON_ADDITIVE_ACROSS_ACTORS:
            totals[m.value] = None
            warnings.append(
                "actioned_emails is not additive across Actors: an email actioned by "
                "several Actors is credited to each of them, so the total would "
                "over-count by roughly 52% (api-report-fresh.md §4.5). Shown per "
                "Actor, omitted as a total."
            )
            continue

        total_value, total_count = _metric_total_and_count(
            dataset.metrics, dataset.counts, m, indices
        )
        totals[m.value] = _display_value(total_value, total_count, spec.duration_display)
        if total_count is not None:
            total_counts[m.value] = total_count

    return totals, total_counts, warnings
