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

Issue 07 adds three presentation controls that share this one engine pass:

- **Sort applies within each Bucket, never globally** (architecture.md §2
  "Table semantics"): a day × Actor report keeps its days in chronological
  order and reorders only the rows inside each day. `_sort_rows_within_bucket`
  groups the already-built row list into contiguous per-Bucket runs (the
  builders above already emit rows Bucket-major) and sorts each run
  independently — a `granularity: "total"` report has exactly one run, so
  the *same* code path ranks the whole table, which is what makes a
  leaderboard preset work without a special case.
- **A `None` duration cell always sorts last, in both directions.** Coercing
  it to `0.0` would float a zero-ticket Actor to the top of an ascending
  leaderboard — exactly the defect issue 05 fixed at the cell level; letting
  Python's default `sorted()` compare `None` to a `float` instead raises
  `TypeError`. `_sort_rows_within_bucket` treats "no data" as "not ranked
  among those that have it" and puts it after every real value regardless of
  `direction`.
- **Column order and pivot layout share the same `ReportTable.columns`
  list** that the frontend and the (issue 10/11) exporters both read, so
  ordering only needs to be correct once, here. `columns_order` reorders the
  metric columns (`_ordered_metrics`); `layout == "pivot"` replaces them
  entirely with one column per Bucket, rendering only `chart_metric` — never
  silently dropping the user's other selected columns, a warning says so.
"""

import hashlib
from datetime import date

from app.models import (
    ChartData,
    ChartPoint,
    ChartSeries,
    ColumnMeta,
    Metric,
    ReportRow,
    ReportSpec,
    ReportTable,
    SortSpec,
)
from app.upstream import METRIC_CATALOGUE, CoverageWindow, Dataset, EntityBreakdown

# The chart's fixed categorical palette has exactly 8 slots (issue 14,
# architecture.md §7, dataviz skill's validated default order) — "never
# generate a 9th hue" is enforced structurally by capping selection at this
# many series, not by clamping an out-of-range index.
_CHART_PALETTE_SIZE = 8

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


class CoverageRefusedError(ValueError):
    """Raised when a requested date range has zero overlap with the
    Coverage Window (issue 08, CONTEXT.md "Coverage Window",
    api-report-fresh.md §3.3).

    The upstream itself fails open on an out-of-range query — asked for
    June, it silently answers with July's numbers rather than nothing. This
    error is what stands between a request like that and the upstream: it
    must be raised, and obeyed, *before* any upstream call is made, so an
    out-of-range date can never reach it. `coverage` carries the real
    window so the caller (the report route, and later the Assistant) can
    offer the user a range that actually has data — never substitute one
    silently."""

    def __init__(self, coverage: CoverageWindow) -> None:
        self.coverage = coverage
        super().__init__(
            "requested date range has no overlap with the Coverage Window "
            f"{coverage.from_date}..{coverage.to_date}"
        )


def clamp_to_coverage(
    spec: ReportSpec, coverage: CoverageWindow
) -> tuple[ReportSpec, list[str]]:
    """Validate `spec`'s date range against the Coverage Window (issue 08).

    Must run before `upstream.get_dataset()` is ever called for this
    request — that is the only way to guarantee an out-of-range date never
    reaches the upstream, which would otherwise fail open and hand back its
    whole window as though it answered the question asked.

    - **Zero overlap** (`spec`'s range and the window don't touch at all):
      raises `CoverageRefusedError` carrying the real window. Never
      substitutes.
    - **Partial overlap** (either edge, or both — a range that strictly
      contains the window clamps on both sides at once): returns a copy of
      `spec` with `date_from`/`date_to` narrowed to the overlap, plus one
      Warning naming the range actually applied.
    - **Full containment** (`spec`'s range already fits inside the window):
      returns `spec` unchanged and no warning — clamping to a no-op range
      would be a warning about nothing.

    Touching the window by exactly one day (e.g. `date_to` equal to the
    window's first day) is real overlap, not zero overlap, and clamps to
    that single day rather than refusing.
    """
    window_from = date.fromisoformat(coverage.from_date)
    window_to = date.fromisoformat(coverage.to_date)

    if spec.date_to < window_from or spec.date_from > window_to:
        raise CoverageRefusedError(coverage)

    clamped_from = max(spec.date_from, window_from)
    clamped_to = min(spec.date_to, window_to)

    if clamped_from == spec.date_from and clamped_to == spec.date_to:
        return spec, []

    warning = (
        f"Requested range {spec.date_from.isoformat()}..{spec.date_to.isoformat()} "
        "was outside the Coverage Window and has been clamped to the "
        f"overlap {clamped_from.isoformat()}..{clamped_to.isoformat()}."
    )
    clamped_spec = spec.model_copy(update={"date_from": clamped_from, "date_to": clamped_to})
    return clamped_spec, [warning]


def execute(spec: ReportSpec, dataset: Dataset) -> ReportTable:
    """`ReportSpec` + `Dataset` -> `ReportTable` (module docstring).

    Coverage validation (issue 08) is enforced *here*, not by any caller —
    `dataset.coverage` is already carried on every `Dataset`, so this
    function has everything it needs to refuse or clamp on its own, with no
    new parameter and no I/O. This is deliberate: `execute()` is the one
    place every caller — the `/report` route today, the Assistant's
    in-process `run_report` tool later (issue 16) — necessarily passes
    through to get a `ReportTable` at all, so enforcing the rule here is
    the only way to make it structural rather than a convention a future
    caller could forget to repeat. A caller that reaches straight for
    `execute()` and skips a route-level check still gets the guard; a
    caller that wants the clamp-and-report-adjustment shape ahead of time
    (issue 16's Repair narration) can still call `clamp_to_coverage`
    directly — it stays exported for exactly that.

    Without this, an out-of-range spec would not error and would not
    silently borrow another window's numbers (the upstream's own failure
    mode) — it would return a clean, confident all-zero table with no
    warnings, since every bucket index would simply select nothing. A
    dashboard or an Assistant narrating "0 tickets resolved" for a month
    with no data at all is a worse lie than an obviously wrong number:
    refusing outright is the only honest response.
    """
    unsupported = [m.value for m in spec.metrics if m.value not in _SUPPORTED_KEYS]
    if unsupported:
        raise UnsupportedMetricError(
            f"engine.execute aggregates Counters and Duration Metrics only; got "
            f"unsupported metric(s) {unsupported!r} (kind == 'sum' is out of scope)."
        )

    spec, coverage_warnings = clamp_to_coverage(spec, dataset.coverage)

    indices = _selected_bucket_indices(dataset.ticks, spec.date_from, spec.date_to)
    partial_day_warnings = _partial_final_day_warning(dataset, indices)
    chart = _build_chart(spec, dataset, indices)

    if spec.layout == "pivot":
        table = _execute_pivot(spec, dataset, indices)
        table.warnings = coverage_warnings + partial_day_warnings + table.warnings
        table.chart = chart
        return table

    columns = [_column_meta(m) for m in _ordered_metrics(spec)]

    if spec.group_by == "none":
        rows = _rows_ungrouped(spec, dataset, indices)
    else:
        entities = dataset.actors if spec.group_by == "agent" else dataset.mailboxes
        rows = _rows_grouped(spec, entities, dataset.ticks, indices)

    rows = _sort_rows_within_bucket(rows, spec.sort)

    totals, total_counts, warnings = _totals(spec, dataset, indices)
    return ReportTable(
        columns=columns,
        rows=rows,
        totals=totals,
        total_counts=total_counts,
        warnings=coverage_warnings + partial_day_warnings + warnings,
        chart=chart,
    )


def _ordered_metrics(spec: ReportSpec) -> list[Metric]:
    """Column order (issue 07, user story 12): `columns_order` names metric
    keys in the desired left-to-right order. Unknown keys are ignored (no
    crash on stale state, e.g. after a metric was dropped) and any selected
    metric not mentioned is appended afterwards in its original `metrics`
    order — so a partial reorder never drops a column. `None` keeps
    `metrics` order as given."""
    if spec.columns_order is None:
        return spec.metrics
    by_key = {m.value: m for m in spec.metrics}
    ordered = [by_key[key] for key in spec.columns_order if key in by_key]
    seen = {m.value for m in ordered}
    remaining = [m for m in spec.metrics if m.value not in seen]
    return ordered + remaining


def _sort_rows_within_bucket(rows: list[ReportRow], sort: SortSpec | None) -> list[ReportRow]:
    """Sort each Bucket's rows independently, preserving Bucket order
    (architecture.md §2 "Table semantics", issue 07 user stories 9-10).

    Rows arrive already grouped Bucket-major (every row builder above loops
    Buckets in the outer loop), so a stable pass that buckets the existing
    list into contiguous same-`bucket` runs — without re-sorting the runs
    themselves — and sorts inside each run reproduces "days stay
    chronological, rows reorder within a day". A `granularity: "total"`
    report has exactly one run, so the same code sorts the whole table,
    which is what makes the leaderboard preset a ranking rather than a
    special case.

    A `None` cell (an undefined Duration Metric average, issue 05) is never
    compared to a `float` — that raises `TypeError` in plain `sorted()` — and
    is never coerced to `0.0`, which would rank a zero-ticket entity above
    everyone who did the work on an ascending sort. It sorts last,
    regardless of `direction`: an entity with no data is not ranked among
    those that have it.
    """
    if sort is None:
        return rows

    reverse = sort.direction == "desc"

    def sort_key(row: ReportRow) -> tuple[int, float]:
        value = row.values.get(sort.column)
        if value is None:
            return (1, 0.0)
        return (0, -value if reverse else value)

    ordered_buckets: list[str] = []
    runs: dict[str, list[ReportRow]] = {}
    for row in rows:
        if row.bucket not in runs:
            runs[row.bucket] = []
            ordered_buckets.append(row.bucket)
        runs[row.bucket].append(row)

    sorted_rows: list[ReportRow] = []
    for bucket in ordered_buckets:
        sorted_rows.extend(sorted(runs[bucket], key=sort_key))
    return sorted_rows


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


def _partial_final_day_warning(dataset: Dataset, indices: list[int]) -> list[str]:
    """Issue 09 hygiene touch: the Coverage Window's last day is a partial
    day upstream (api-report-fresh.md §5.3 — 2026-07-23 has ~17% of the
    preceding weekday's volume, consistent with a capture mid-day rather
    than a real drop). Any average or trend that folds it in will read as
    worse than reality. Flagged here, once, so every layout (long, pivot,
    any granularity) that includes that Bucket carries the same warning
    rather than each caller remembering to check."""
    if not indices:
        return []
    window_last_day = date.fromisoformat(dataset.coverage.to_date)
    if _bucket_day(dataset.ticks[max(indices)]) != window_last_day:
        return []
    return [
        f"{window_last_day.isoformat()} is the final day of the Coverage Window and holds "
        "partial data — it will drag down any trailing average or trend that includes it."
    ]


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


def _color_slot(entity_id: str) -> int:
    """A palette slot (0-7) from a stable hash of `entity_id` — never from
    its position in a ranking (architecture.md §7, issue 14 user story 57).

    `hashlib.sha256` is used deliberately instead of the builtin `hash()`:
    Python randomises `hash()` for `str` per process (`PYTHONHASHSEED`), so
    the same Actor would get a different slot on every server restart. A
    cryptographic hash is overkill for the purpose but is stable across
    processes and versions, which is the one property that matters here.
    """
    digest = hashlib.sha256(entity_id.encode("utf-8")).digest()
    return digest[0] % _CHART_PALETTE_SIZE


def _build_chart(spec: ReportSpec, dataset: Dataset, indices: list[int]) -> ChartData | None:
    """The chart's own view of the same Report Table (module docstring,
    issue 14) — never a second data path: it is built from the identical
    `_rows_ungrouped`/`_rows_grouped` the long layout uses, over the same
    `indices`, so a chart point is always the exact number the day×group
    table cell would show.

    Hidden entirely when the report has no time axis to plot
    (`granularity == "total"`, user story 60) — returns `None` rather than
    a chart with one point per series.

    Series are capped at the eight largest by **raw `Σvalue`** (never a
    display value): ranking by an already-averaged `duration_display ==
    "avg"` cell would be exactly the "averaging averages" defect the module
    docstring warns against, so this reuses `_metric_total_and_count`'s
    `total_value` — the same quantity `_totals` computes — rather than
    summing the per-day cells the chart plots.
    """
    if spec.granularity == "total":
        return None

    metric = spec.effective_chart_metric

    if spec.group_by == "none":
        rows = _rows_ungrouped(spec, dataset, indices)
        points = [ChartPoint(bucket=row.bucket, value=row.values[metric.value]) for row in rows]
        series = [ChartSeries(key="total", label=_label(metric.value), color_slot=0, points=points)]
        return ChartData(metric=metric.value, series=series, dropped=0)

    entities = dataset.actors if spec.group_by == "agent" else dataset.mailboxes
    rows = _rows_grouped(spec, entities, dataset.ticks, indices)

    points_by_entity: dict[str, list[ChartPoint]] = {entity.id: [] for entity in entities}
    for row in rows:
        assert row.group_key is not None  # group_by != "none" here
        points_by_entity[row.group_key].append(
            ChartPoint(bucket=row.bucket, value=row.values[metric.value])
        )

    def _ranking_total(entity: EntityBreakdown) -> float:
        total_value, _ = _metric_total_and_count(entity.metrics, entity.counts, metric, indices)
        return total_value

    ranked = sorted(entities, key=_ranking_total, reverse=True)
    top = ranked[:_CHART_PALETTE_SIZE]
    dropped = len(ranked) - len(top)

    series = [
        ChartSeries(
            key=entity.id,
            label=entity.name,
            color_slot=_color_slot(entity.id),
            points=points_by_entity[entity.id],
        )
        for entity in top
    ]
    return ChartData(metric=metric.value, series=series, dropped=dropped)


def _execute_pivot(spec: ReportSpec, dataset: Dataset, indices: list[int]) -> ReportTable:
    """Buckets across the top as columns (architecture.md §2, issue 07):
    a compact scan of exactly one metric — `spec.effective_chart_metric`,
    defaulting to `metrics[0]` — over the period. Several metrics would
    multiply the column count and make the export unreadable, so pivot
    always renders the chart metric only; the caller is told via
    `ReportTable.warnings`, never left to silently lose the other selected
    columns (user story 17).

    Rows are entities (`group_by != "none"`) or a single row for the whole
    selection (`group_by == "none"`); each row's `values` are keyed by
    Bucket (an ISO day, or `"total"` under `granularity: "total"`, when
    there is exactly one Bucket-column) rather than by metric key — the same
    `ColumnMeta`/`values`-by-`column.key` contract as the long layout, just
    with Buckets standing in the metric-column slot. `spec.sort` is not
    applied here: it is validated to name a metric, and pivot's column keys
    are Bucket dates, so there is no meaningful column for it to rank by in
    this layout.
    """
    chart_metric = spec.effective_chart_metric
    info = _METRIC_INFO_BY_KEY[chart_metric.value]

    if spec.granularity == "total":
        bucket_columns: list[tuple[str, str, list[int]]] = [("total", "total", indices)]
        row_bucket = "total"
    else:
        bucket_columns = []
        for i in indices:
            day = _bucket_day(dataset.ticks[i]).isoformat()
            bucket_columns.append((day, day, [i]))
        row_bucket = "pivot"

    columns = [
        ColumnMeta(key=key, label=label, kind=info.kind, unit=info.unit)
        for key, label, _ in bucket_columns
    ]

    def cell(
        values: dict[str, list[float]], counts: dict[str, list[float]], idxs: list[int]
    ) -> tuple[float | None, float | None]:
        total_value, total_count = _metric_total_and_count(values, counts, chart_metric, idxs)
        return _display_value(total_value, total_count, spec.duration_display), total_count

    def build_row(
        values_source: dict[str, list[float]],
        counts_source: dict[str, list[float]],
        group_key: str | None,
        group_label: str | None,
    ) -> ReportRow:
        row_values: dict[str, float | None] = {}
        row_counts: dict[str, float] = {}
        for key, _, idxs in bucket_columns:
            value, count = cell(values_source, counts_source, idxs)
            row_values[key] = value
            if count is not None:
                row_counts[key] = count
        return ReportRow(
            bucket=row_bucket,
            group_key=group_key,
            group_label=group_label,
            values=row_values,
            counts=row_counts,
        )

    if spec.group_by == "none":
        rows = [build_row(dataset.metrics, dataset.counts, None, None)]
    else:
        entities = dataset.actors if spec.group_by == "agent" else dataset.mailboxes
        rows = [build_row(e.metrics, e.counts, e.id, e.name) for e in entities]

    is_chart_metric_non_additive = chart_metric.value == _NON_ADDITIVE_ACROSS_ACTORS
    non_additive = spec.group_by == _NON_ADDITIVE_GROUPING and is_chart_metric_non_additive
    warnings = [
        f"Pivot layout shows the chart metric only ({_label(chart_metric.value)}); "
        "your other selected metrics are not displayed in this layout."
    ]
    if non_additive:
        warnings.append(
            "actioned_emails is not additive across Actors: an email actioned by "
            "several Actors is credited to each of them, so the total would "
            "over-count by roughly 52% (api-report-fresh.md §4.5). Shown per "
            "Actor, omitted as a total."
        )

    totals: dict[str, float | None] = {}
    total_counts: dict[str, float] = {}
    for key, _, idxs in bucket_columns:
        if non_additive:
            totals[key] = None
            continue
        value, count = cell(dataset.metrics, dataset.counts, idxs)
        totals[key] = value
        if count is not None:
            total_counts[key] = count

    return ReportTable(
        columns=columns, rows=rows, totals=totals, total_counts=total_counts, warnings=warnings
    )
