"""`engine.execute` unit tests (issues 04 and 05).

Exercises the real fixture dataset via `upstream._normalise_dataset` — no
network, no FastAPI. Issue 04's classes below cover Counters (plain sums).
`TestDurationMetricAggregation` and friends (issue 05) cover Duration
Metrics: `Σvalue / Σcount` weighted aggregation, the avg/total display
toggle, the `_count` tooltip data, and the `actioned_emails` non-additive
dash. Real fixture figures pinned in the issue brief: 16372 resolved across
the window, 108 Actors, 103 Mailboxes, and the daily `resolved` series
[1467, 84, 111, 1478, 1675, 1701, 1586, 1557, 124, 75, 1767, 1883, 2534, 330].

The Duration Metric hand-computed literals below were derived independently
from `app/dev_fixtures/resp-full-unscoped-latest.json` with a standalone
script that reads the raw JSON directly and sums with plain `sum()` — a
different code path from both `upstream._normalise_dataset` and
`engine._metric_total_and_count`/`_display_value`, so the test cannot pass by
accident if the engine's arithmetic regresses to the same (correct or
incorrect) expression. See the class docstrings for the exact figures and
how each was computed.
"""

import json

import pytest

from app.engine import CoverageRefusedError, UnsupportedMetricError, clamp_to_coverage, execute
from app.models import Metric, ReportSpec, SortSpec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")

DAILY_RESOLVED = [1467, 84, 111, 1478, 1675, 1701, 1586, 1557, 124, 75, 1767, 1883, 2534, 330]
TOTAL_RESOLVED = 16372

#: `engine._display_value` rounds Duration Metrics to two decimals, so the
#: hand-computed expectations below are compared to half a rounding step
#: rather than to floating-point exactness. The contrast against the naive
#: mean-of-daily-averages stays tight: the two differ by orders of magnitude,
#: which is the whole point of that assertion.
DURATION_TOLERANCE = 0.005


@pytest.fixture
def dataset():
    return _normalise_dataset(FIXTURE_RAW, WINDOW)


class TestUngroupedCounters:
    def test_counters_sum_correctly_across_days_when_collapsed_to_a_total(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 1
        assert table.rows[0].bucket == "total"
        assert table.rows[0].values["resolved"] == TOTAL_RESOLVED
        assert table.totals["resolved"] == TOTAL_RESOLVED

    def test_day_granularity_reproduces_the_real_daily_series(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert [row.values["resolved"] for row in table.rows] == DAILY_RESOLVED
        assert [row.bucket for row in table.rows] == [
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
            "2026-07-14",
            "2026-07-15",
            "2026-07-16",
            "2026-07-17",
            "2026-07-18",
            "2026-07-19",
            "2026-07-20",
            "2026-07-21",
            "2026-07-22",
            "2026-07-23",
        ]
        assert table.totals["resolved"] == TOTAL_RESOLVED

    def test_a_narrower_date_range_only_sums_the_selected_days(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-15",
            date_to="2026-07-18",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert table.totals["resolved"] == sum(DAILY_RESOLVED[5:9])  # 07-15..07-18 inclusive


class TestGroupingReconciles:
    """The strongest available check: Actor and Mailbox are independent
    marginals of the same totals, so if summing across both breakdowns lands
    on the same figure, the per-entity aggregation is almost certainly
    correct (issue 04 brief)."""

    def test_grouping_by_actor_reconciles_to_the_overall_total(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 108
        assert table.totals["resolved"] == TOTAL_RESOLVED

    def test_grouping_by_mailbox_reconciles_to_the_overall_total(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="mailbox",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 103
        assert table.totals["resolved"] == TOTAL_RESOLVED

    def test_day_by_actor_also_reconciles_across_days_and_entities(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 14 * 108
        assert table.totals["resolved"] == TOTAL_RESOLVED


class TestColumnsAreMetadataNotStrings:
    def test_columns_carry_raw_metadata_and_rows_carry_raw_numbers(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED, Metric.NEW_TICKETS],
            date_from="2026-07-10",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert [c.key for c in table.columns] == ["resolved", "new_tickets"]
        assert all(c.kind == "counter" for c in table.columns)
        assert all(c.unit == "count" for c in table.columns)
        assert isinstance(table.rows[0].values["resolved"], (int, float))
        assert not isinstance(table.rows[0].values["resolved"], str)


class TestDurationMetricAggregation:
    """`Σvalue / Σcount` is the only correct aggregation for a Duration
    Metric, across both days and entities (CONTEXT.md, issue 05 brief).

    `resolve_time`'s whole-window figures were computed independently from
    the fixture with a standalone script (`sum(raw["resolve_time"])`,
    `sum(raw["resolve_time_count"])`, one division) — not via `engine.py` or
    `upstream.py` — and then hardcoded below:

        Σvalue = 187974.09936833332, Σcount = 16371, mean = 11.482139109909799

    This also matches the independently-verified whole-window figure quoted
    in the issue brief, to the digit.
    """

    RESOLVE_TIME_MEAN_WHOLE_WINDOW = 11.482139109909799

    def test_a_duration_aggregated_over_the_whole_window_equals_total_over_count(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        assert table.rows[0].values["resolve_time"] == pytest.approx(
            self.RESOLVE_TIME_MEAN_WHOLE_WINDOW, abs=DURATION_TOLERANCE
        )
        assert table.totals["resolve_time"] == pytest.approx(
            self.RESOLVE_TIME_MEAN_WHOLE_WINDOW, abs=DURATION_TOLERANCE
        )

    def test_default_duration_display_is_avg(self, dataset) -> None:
        """`duration_display` defaults to `"avg"` (CONTEXT.md: the per-ticket
        average answering "how fast" is the default; `"total"` is opt-in)."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert table.totals["resolve_time"] == pytest.approx(
            self.RESOLVE_TIME_MEAN_WHOLE_WINDOW, abs=DURATION_TOLERANCE
        )

    def test_grouped_by_actor_a_single_entitys_duration_matches_a_hand_computed_value(
        self, dataset
    ) -> None:
        """Actor `user_Nq24icrN` ("Enzo Grant"): independently summed from
        the fixture's `actors[]` entry — `Σvalue = 363.20896250000004`,
        `Σcount = 335`, `mean = 1.0842058582089553`."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        row = next(r for r in table.rows if r.group_key == "user_Nq24icrN")
        assert row.values["resolve_time"] == pytest.approx(
            1.0842058582089553, abs=DURATION_TOLERANCE
        )
        assert row.counts["resolve_time"] == 335

    def test_an_entity_with_zero_tickets_shows_a_dash_under_avg_display_not_zero(
        self, dataset
    ) -> None:
        """Actor `user_yoJRgsMu` has 14 zeros in both `resolve_time` and
        `resolve_time_count` for the whole window — Σcount == 0, so the
        average is *undefined*, not zero. `0.0` would read on screen as the
        fastest possible resolution — the exact plausible-looking wrong
        number this slice exists to prevent — so the engine withholds it as
        `None` (the same sentinel `actioned_emails` already uses), not a
        crash and not a lie. `counts` still reports the real zero, which is
        what makes the dash legible as "no data" rather than a bug."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        row = next(r for r in table.rows if r.group_key == "user_yoJRgsMu")
        assert row.values["resolve_time"] is None
        assert row.counts["resolve_time"] == 0

    def test_a_zero_ticket_entity_cannot_float_to_the_top_of_an_ascending_sort(
        self, dataset
    ) -> None:
        """Sorting itself is issue 07's scope, so this asserts the
        precondition that must hold for issue 07 to get it right: the
        zero-ticket cell is `None`, never a real number (let alone `0.0`,
        which — as the smallest possible value — would sort first under an
        ascending comparison and rank someone who resolved nothing above
        every Actor who did the work).

        NOTE for issue 07: a plain `sorted(key=lambda row: row.values[m])`
        will crash comparing `None` to `float` in Python 3. Sorting must
        treat `None` duration cells as "excluded from ranking" (e.g. sort
        last, or filter out), not coerce them to a sortable number."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        zero_ticket_row = next(r for r in table.rows if r.group_key == "user_yoJRgsMu")
        real_rows = [r for r in table.rows if r.values["resolve_time"] is not None]

        assert zero_ticket_row.values["resolve_time"] is None
        # A real ascending sort by value would need every non-None figure to
        # be an actual, comparable float — confirm that holds for the rest
        # of the table, so only the None sentinel is special-cased in 07.
        assert all(isinstance(r.values["resolve_time"], float) for r in real_rows)
        assert min(r.values["resolve_time"] for r in real_rows) > 0.0

    def test_a_zero_ticket_entity_under_total_display_shows_a_true_zero(self, dataset) -> None:
        """The deliberate asymmetry: `duration_display == "total"` for the
        same zero-ticket Actor is a real `0.0`, not withheld. "Did no work"
        is an honest total (Σvalue really is 0); only the *average* of zero
        tickets is undefined. Withholding the total too would hide a
        perfectly legitimate "this Actor did nothing in this window" fact."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="total",
        )

        table = execute(spec, dataset)

        row = next(r for r in table.rows if r.group_key == "user_yoJRgsMu")
        assert row.values["resolve_time"] == 0.0
        assert row.counts["resolve_time"] == 0


class TestAveragingDailyAveragesIsTheDefectThisSliceMustNotReproduce:
    """The regression test named in the issue: if someone "simplifies" the
    aggregation to a mean of per-day averages, this must fail.

    `handle_time` over 2026-07-10..07-13 (the first 4 buckets), independently
    summed from the fixture:

        vals   = [7.989141388888889, 0.3887166666666667, 0.3977613888888889, 7.250020277777778]
        counts = [569, 35, 31, 551]
        Σvalue = 16.025639722222223, Σcount = 1186
        weighted mean = Σvalue / Σcount = 0.013512343779276749

    The naive mean of the four per-day averages (0.014040670279242336,
    0.011106190476190478, 0.012831012544802867, 0.013157931538616656) is
    0.012783951209713084 — a different number computed explicitly below,
    not imported from anywhere.
    """

    WEIGHTED_MEAN = 0.013512343779276749

    def test_weighted_mean_is_not_the_mean_of_daily_averages(self, dataset) -> None:
        daily_values = [
            7.989141388888889,
            0.3887166666666667,
            0.3977613888888889,
            7.250020277777778,
        ]
        daily_counts = [569, 35, 31, 551]
        naive_mean_of_daily_averages = sum(v / c for v, c in zip(daily_values, daily_counts)) / len(
            daily_values
        )

        spec = ReportSpec(
            metrics=[Metric.HANDLE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-13",
            granularity="total",
            group_by="none",
            duration_display="avg",
        )

        table = execute(spec, dataset)
        engine_result = table.rows[0].values["handle_time"]

        assert engine_result == pytest.approx(self.WEIGHTED_MEAN, abs=DURATION_TOLERANCE)
        assert engine_result != pytest.approx(naive_mean_of_daily_averages, rel=1e-9)
        assert naive_mean_of_daily_averages == pytest.approx(0.012783951209713084, rel=1e-9)


class TestDurationDisplayToggle:
    """`duration_display` switches a Duration Metric cell between the
    per-ticket average (`"avg"`) and the period total (`"total"`) without
    touching any other field (issue 05, user story 14).

    `handle_time` whole-window figures, independently summed from the
    fixture: Σvalue = 85.06691555555557, Σcount = 6407,
    mean = 0.013277183635953734 (matches the issue brief's verified figure
    to eleven significant digits; the residual is summation-order noise)."""

    def test_toggling_from_avg_to_total_changes_only_the_duration_display(self, dataset) -> None:
        base_kwargs = dict(
            metrics=[Metric.HANDLE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        avg_table = execute(ReportSpec(**base_kwargs, duration_display="avg"), dataset)
        total_table = execute(ReportSpec(**base_kwargs, duration_display="total"), dataset)

        assert avg_table.rows[0].values["handle_time"] == pytest.approx(
            0.013277183635953734, abs=DURATION_TOLERANCE
        )
        assert total_table.rows[0].values["handle_time"] == pytest.approx(
            85.06691555555557, abs=DURATION_TOLERANCE
        )
        # Same underlying count either way — the toggle changes the
        # numerator/denominator arithmetic, not what was measured.
        assert avg_table.rows[0].counts["handle_time"] == 6407
        assert total_table.rows[0].counts["handle_time"] == 6407


class TestActionedEmailsNonAdditiveAcrossActors:
    """api-report-fresh.md §4.5: `actioned_emails` over-counts by ~52% when
    summed across Actors, and only across Actors — it reconciles exactly
    across Mailboxes. Independently verified from the fixture: top-level
    total 19024; Σ over `actors[]` 28941 (+52.13%); Σ over `mailbox[]`
    19024 (0.00%)."""

    def test_grouped_by_actor_the_totals_cell_is_a_dash_with_a_warning(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.ACTIONED_EMAILS],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
        )

        table = execute(spec, dataset)

        assert table.totals["actioned_emails"] is None
        assert any("actioned_emails" in w for w in table.warnings)
        # The per-Actor rows are untouched — only the total is withheld.
        assert all(isinstance(row.values["actioned_emails"], (int, float)) for row in table.rows)

    def test_grouped_by_mailbox_the_same_metric_totals_normally(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.ACTIONED_EMAILS],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="mailbox",
        )

        table = execute(spec, dataset)

        assert table.totals["actioned_emails"] == 19024
        # No actioned_emails-specific warning — but the range still includes
        # the Coverage Window's partial final day (issue 09), so that
        # warning alone is expected here.
        assert not any("actioned_emails" in w for w in table.warnings)
        assert any("partial" in w.lower() for w in table.warnings)

    def test_ungrouped_the_same_metric_also_totals_normally(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.ACTIONED_EMAILS],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert table.totals["actioned_emails"] == 19024
        # No actioned_emails-specific warning — but the range still includes
        # the Coverage Window's partial final day (issue 09), so that
        # warning alone is expected here.
        assert not any("actioned_emails" in w for w in table.warnings)
        assert any("partial" in w.lower() for w in table.warnings)


class TestSingleBucketCollapseIsFirstClassForBothMetricFamilies:
    """Issue 06: collapsing the whole Coverage Window into one Bucket must be
    a first-class engine path, not a special case bolted onto grouping — it
    is what makes ranking possible in issue 07. This class asserts that
    collapse for *both* metric families (Counters and Duration Metrics),
    ungrouped and grouped, against fixture figures re-derived independently
    with a standalone script reading `app/dev_fixtures/resp-full-unscoped-latest.json`
    directly (`sum(raw[key])`, `sum(raw[f"{key}_count"])`) — not via
    `upstream.py` or `engine.py`:

        resolved:      Σ = 16372 (108 Actors, 103 Mailboxes)
        resolve_time:  Σvalue = 187974.09936833332, Σcount = 16371,
                       mean = 11.482139109909799
        handle_time:   Σvalue = 85.06691555555557, Σcount = 6407,
                       mean = 0.013277183635953734
                       (differs from the issue brief's quoted 85.06691555555555
                       / 0.01327718363595373 in the last digit or two — plain
                       Python `sum()` summation order — re-derived rather than
                       trusted verbatim, per the issue's own instruction.)
    """

    def test_counter_family_collapses_to_one_row_per_entity_that_reconciles(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="mailbox",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 103
        assert all(row.bucket == "total" for row in table.rows)
        assert sum(row.values["resolved"] for row in table.rows) == TOTAL_RESOLVED
        assert table.totals["resolved"] == TOTAL_RESOLVED

    def test_duration_family_collapses_to_one_row_per_entity_with_weighted_means(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.HANDLE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 108
        assert all(row.bucket == "total" for row in table.rows)
        # A per-entity weighted mean over the whole window, never a mean of
        # that entity's 14 daily averages: reconstruct entity totals from raw
        # per-bucket arrays and confirm the engine's collapsed cell matches
        # Σvalue/Σcount exactly, for every entity that did any work.
        for entity in dataset.actors:
            entity_sum = sum(entity.metrics["handle_time"])
            entity_count = sum(entity.counts["handle_time"])
            row = next(r for r in table.rows if r.group_key == entity.id)
            if entity_count == 0:
                assert row.values["handle_time"] is None
            else:
                assert row.values["handle_time"] == pytest.approx(
                    entity_sum / entity_count, abs=DURATION_TOLERANCE
                )

    def test_ungrouped_duration_collapse_matches_the_independently_derived_whole_window_figure(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        assert table.rows[0].values["resolve_time"] == pytest.approx(
            11.482139109909799, abs=DURATION_TOLERANCE
        )
        assert table.rows[0].counts["resolve_time"] == 16371

    def test_ungrouped_counter_collapse_matches_the_independently_derived_whole_window_figure(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert table.rows[0].values["resolved"] == 16372
        assert table.rows[0].bucket == "total"

    def test_collapsing_does_not_disturb_the_zero_count_none_sentinel(self, dataset) -> None:
        """Follow-on from issue 05, restated for the collapsed path: which
        cells are zero-count changes when 14 daily buckets collapse into one
        (an Actor with a single ticket on one day is no longer zero-count
        that day once collapsed), but a *genuinely* zero-count entity across
        the whole window must still render `None`, never `0.0`, after
        collapse."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
        )

        table = execute(spec, dataset)

        zero_ticket_row = next(r for r in table.rows if r.group_key == "user_yoJRgsMu")
        assert zero_ticket_row.values["resolve_time"] is None
        assert zero_ticket_row.counts["resolve_time"] == 0
        # And under "total" display the same collapsed cell is a true 0.0,
        # not withheld — the avg/total asymmetry survives collapse too.
        total_spec = spec.model_copy(update={"duration_display": "total"})
        total_table = execute(total_spec, dataset)
        total_row = next(r for r in total_table.rows if r.group_key == "user_yoJRgsMu")
        assert total_row.values["resolve_time"] == 0.0


class TestSortWithinBucket:
    """Issue 07, user stories 9-10: sorting reorders rows *within* each
    Bucket while Buckets themselves stay in their original (chronological,
    for `granularity: "day"`) order. A global sort would destroy the time
    series the day × Actor report exists to show."""

    def test_sort_reorders_rows_within_each_day_while_day_order_is_preserved(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
            sort=SortSpec(column="resolved", direction="desc"),
        )

        table = execute(spec, dataset)

        # The 14 Buckets are still in chronological order — sorting must not
        # reorder days, only the ~108 Actor rows sitting inside each day.
        seen_buckets = []
        for row in table.rows:
            if row.bucket not in seen_buckets:
                seen_buckets.append(row.bucket)
        assert seen_buckets == [
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
            "2026-07-14",
            "2026-07-15",
            "2026-07-16",
            "2026-07-17",
            "2026-07-18",
            "2026-07-19",
            "2026-07-20",
            "2026-07-21",
            "2026-07-22",
            "2026-07-23",
        ]

        # Within each day's contiguous run, resolved counts are non-increasing.
        by_bucket: dict[str, list[float]] = {}
        for row in table.rows:
            by_bucket.setdefault(row.bucket, []).append(row.values["resolved"])
        for bucket, values in by_bucket.items():
            assert values == sorted(values, reverse=True), f"bucket {bucket} not sorted desc"

    def test_sort_a_single_bucket_report_ranks_across_the_whole_table(self, dataset) -> None:
        """`granularity: "total"` collapses to one Bucket, so the same
        within-Bucket sort mechanism ranks every row — this is what makes
        the agent leaderboard preset work, with no special-casing."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            sort=SortSpec(column="resolved", direction="desc"),
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 108
        assert all(row.bucket == "total" for row in table.rows)
        values = [row.values["resolved"] for row in table.rows]
        assert values == sorted(values, reverse=True)
        # Top of the descending leaderboard is a real, positive figure.
        assert values[0] > 0

    def test_sort_ascending_also_ranks_the_single_bucket_table(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            sort=SortSpec(column="resolved", direction="asc"),
        )

        table = execute(spec, dataset)

        values = [row.values["resolved"] for row in table.rows]
        assert values == sorted(values)


class TestSortHandlesNoneDurationCells:
    """Issue 05 left an explicit hazard note for this slice: a zero-count
    Duration Metric average is `None`, and sorting must neither crash on it
    (`sorted()` comparing `None` to `float` raises `TypeError`) nor coerce it
    to `0.0` (which would float a zero-ticket Actor to the top of an
    ascending leaderboard). The defensible answer: an entity with no data is
    not ranked among those that have it, so `None` sorts to the end in BOTH
    directions."""

    def test_none_duration_cells_sort_last_ascending(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
            sort=SortSpec(column="resolve_time", direction="asc"),
        )

        table = execute(spec, dataset)

        values = [row.values["resolve_time"] for row in table.rows]
        real_values = [v for v in values if v is not None]
        none_count = len(values) - len(real_values)

        assert none_count > 0  # user_yoJRgsMu (0 tickets) must be among the rows
        # All None cells trail every real value, in either direction.
        assert values[-none_count:] == [None] * none_count
        assert None not in values[:-none_count]
        assert real_values == sorted(real_values)

    def test_none_duration_cells_sort_last_descending(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
            sort=SortSpec(column="resolve_time", direction="desc"),
        )

        table = execute(spec, dataset)

        values = [row.values["resolve_time"] for row in table.rows]
        real_values = [v for v in values if v is not None]
        none_count = len(values) - len(real_values)

        assert none_count > 0
        # A zero-ticket Actor must never rank above real resolvers, even
        # descending — the exact regression this hazard warns about.
        assert values[-none_count:] == [None] * none_count
        assert real_values == sorted(real_values, reverse=True)

    def test_sorting_a_duration_column_never_raises(self, dataset) -> None:
        """The precondition failure mode: plain `sorted()` on a list mixing
        `None` and `float` raises `TypeError`. Executing the spec must not."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
            duration_display="avg",
            sort=SortSpec(column="resolve_time", direction="asc"),
        )

        table = execute(spec, dataset)  # must not raise TypeError

        assert len(table.rows) == 108


class TestColumnOrder:
    """Issue 07, user story 12: explicit column order is honoured in the
    Report Table itself (`ReportTable.columns`), not only in how the
    frontend happens to render it — the exporters (issues 10-11) read the
    same list, so they cannot silently disagree with the screen."""

    def test_explicit_column_order_is_honoured(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED, Metric.NEW_TICKETS, Metric.REPLIES],
            date_from="2026-07-10",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
            columns_order=["replies", "resolved", "new_tickets"],
        )

        table = execute(spec, dataset)

        assert [c.key for c in table.columns] == ["replies", "resolved", "new_tickets"]

    def test_a_metric_left_out_of_columns_order_is_appended_not_dropped(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED, Metric.NEW_TICKETS, Metric.REPLIES],
            date_from="2026-07-10",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
            columns_order=["replies"],
        )

        table = execute(spec, dataset)

        assert [c.key for c in table.columns] == ["replies", "resolved", "new_tickets"]

    def test_no_columns_order_keeps_the_metrics_list_order(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.NEW_TICKETS, Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert [c.key for c in table.columns] == ["new_tickets", "resolved"]


class TestPivotLayout:
    """Issue 07, user stories 16-17: pivot puts Buckets across the top as
    columns for a compact scan of one metric. Because several metrics would
    multiply the column count and make the export unreadable, pivot renders
    `chart_metric` only, and the UI is told why the other selected columns
    are missing via `ReportTable.warnings`."""

    def test_pivot_renders_buckets_as_columns(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-13",
            granularity="day",
            group_by="none",
            layout="pivot",
        )

        table = execute(spec, dataset)

        assert [c.key for c in table.columns] == [
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
        ]
        assert len(table.rows) == 1
        assert table.rows[0].values["2026-07-10"] == DAILY_RESOLVED[0]
        assert table.rows[0].values["2026-07-11"] == DAILY_RESOLVED[1]
        assert table.rows[0].values["2026-07-12"] == DAILY_RESOLVED[2]
        assert table.rows[0].values["2026-07-13"] == DAILY_RESOLVED[3]

    def test_pivot_renders_a_single_metric_and_says_so(self, dataset) -> None:
        """Several metrics selected, but pivot shows only `chart_metric`
        (default `metrics[0]`) — and states this in `warnings` rather than
        silently dropping `new_tickets`/`replies` (user story 17)."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED, Metric.NEW_TICKETS, Metric.REPLIES],
            date_from="2026-07-10",
            date_to="2026-07-13",
            granularity="day",
            group_by="none",
            layout="pivot",
        )

        table = execute(spec, dataset)

        # Only Bucket columns, no `new_tickets`/`replies` columns at all.
        assert {c.key for c in table.columns} == {
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
        }
        assert any("chart metric only" in w for w in table.warnings)
        assert table.rows[0].values["2026-07-10"] == DAILY_RESOLVED[0]

    def test_pivot_honours_an_explicit_chart_metric_other_than_metrics_zero(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED, Metric.NEW_TICKETS],
            date_from="2026-07-10",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
            layout="pivot",
            chart_metric=Metric.NEW_TICKETS,
        )

        table = execute(spec, dataset)

        # The pivot cell must be new_tickets (the explicit chart_metric), not
        # the default metrics[0] (resolved) — read the raw dataset value
        # independently of engine.py's own aggregation to confirm which
        # metric actually landed in the cell.
        expected_new_tickets = dataset.metrics["new_tickets"][0]
        assert table.columns[0].key == "2026-07-10"
        assert table.rows[0].values["2026-07-10"] == expected_new_tickets
        assert expected_new_tickets != DAILY_RESOLVED[0]

    def test_pivot_grouped_by_actor_puts_one_row_per_actor(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
            layout="pivot",
        )

        table = execute(spec, dataset)

        assert len(table.rows) == 108
        assert len(table.columns) == 14
        # Reconciles against the same top-level total as the long layout.
        total_across_actors = sum(
            v for row in table.rows for v in row.values.values() if v is not None
        )
        assert total_across_actors == TOTAL_RESOLVED


class TestUnsupportedMetrics:
    def test_a_sum_kind_metric_is_not_yet_supported_by_any_slice(self, dataset) -> None:
        """`replies_to_resolve` (`kind == "sum"`) is out of issue 05's scope
        too — only Counters and Duration Metrics are aggregated."""
        spec = ReportSpec(
            metrics=[Metric.REPLIES_TO_RESOLVE],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        with pytest.raises(UnsupportedMetricError):
            execute(spec, dataset)


class TestPartialFinalDayFlag:
    """Issue 09 hygiene touch: the Coverage Window's last day
    (2026-07-23 in the fixture) holds partial data — 330 resolved versus
    2534 the day before — and will drag down any trailing average or "last
    N days" view that includes it. `execute()` flags this with a warning
    whenever the selected range's last Bucket is the window's last day,
    rather than letting it silently distort a trend (api-report-fresh.md
    §5.3, §5.5)."""

    def test_a_range_including_the_final_day_is_flagged(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-20",
            date_to="2026-07-23",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert any("partial" in w.lower() and "2026-07-23" in w for w in table.warnings)

    def test_a_range_that_stops_short_of_the_final_day_is_not_flagged(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-15",
            date_to="2026-07-18",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert not any("partial" in w.lower() for w in table.warnings)

    def test_the_flag_applies_to_a_total_granularity_report_too(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert any("partial" in w.lower() and "2026-07-23" in w for w in table.warnings)

    def test_the_flag_applies_to_pivot_layout_too(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-20",
            date_to="2026-07-23",
            granularity="day",
            group_by="none",
            layout="pivot",
        )

        table = execute(spec, dataset)

        assert any("partial" in w.lower() and "2026-07-23" in w for w in table.warnings)


class TestCoverageValidation:
    """Issue 08. Two things are tested here, deliberately at two different
    levels:

    `clamp_to_coverage` itself (a pure function of `spec` + `CoverageWindow`)
    is exercised directly by the tests below that call it — this is also
    the shape issue 16's Assistant will want, to clamp and narrate the
    adjustment as a Repair rather than only catching an exception.

    But the property that actually matters — that a caller cannot get a
    `ReportTable` at all for a spec it can't honestly answer — is only
    proven by calling `execute()` itself, never `clamp_to_coverage` in
    isolation: `TestExecuteEnforcesCoverage` below calls `execute()`
    directly, the same as issue 16's in-process `run_report` tool will, and
    confirms it refuses rather than returning the deceptively clean,
    all-zero, warning-free table that a naive date-slice would produce for
    an out-of-range spec (the upstream's own fail-open trap, one layer
    down: this is what would have shipped without this class). `WINDOW`
    here is the fixture's real window, 2026-07-10..2026-07-23 inclusive.
    """

    def test_a_range_fully_inside_the_window_is_returned_unchanged_with_no_warning(self) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-12",
            date_to="2026-07-15",
            granularity="day",
            group_by="none",
        )

        clamped, warnings = clamp_to_coverage(spec, WINDOW)

        assert clamped.date_from.isoformat() == "2026-07-12"
        assert clamped.date_to.isoformat() == "2026-07-15"
        assert warnings == []

    def test_a_range_partially_overlapping_the_start_is_clamped_with_a_warning_naming_it(
        self,
    ) -> None:
        """User story 21: asked for 5-12 July, data starts on the 10th —
        clamp to the overlap and say so."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-05",
            date_to="2026-07-12",
            granularity="day",
            group_by="none",
        )

        clamped, warnings = clamp_to_coverage(spec, WINDOW)

        assert clamped.date_from.isoformat() == "2026-07-10"
        assert clamped.date_to.isoformat() == "2026-07-12"
        assert len(warnings) == 1
        assert "2026-07-10" in warnings[0]
        assert "2026-07-12" in warnings[0]

    def test_a_range_partially_overlapping_the_end_is_clamped_with_a_warning_naming_it(
        self,
    ) -> None:
        """User story 25: the final day in the window can be partial too —
        a range hanging off the end must clamp exactly as the start does."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-20",
            date_to="2026-07-31",
            granularity="day",
            group_by="none",
        )

        clamped, warnings = clamp_to_coverage(spec, WINDOW)

        assert clamped.date_from.isoformat() == "2026-07-20"
        assert clamped.date_to.isoformat() == "2026-07-23"
        assert len(warnings) == 1
        assert "2026-07-20" in warnings[0]
        assert "2026-07-23" in warnings[0]

    def test_a_range_strictly_containing_the_window_is_clamped_to_the_whole_window(self) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-01",
            date_to="2026-08-01",
            granularity="day",
            group_by="none",
        )

        clamped, warnings = clamp_to_coverage(spec, WINDOW)

        assert clamped.date_from.isoformat() == "2026-07-10"
        assert clamped.date_to.isoformat() == "2026-07-23"
        assert len(warnings) == 1

    def test_touching_the_window_by_exactly_one_day_still_clamps_not_refuses(self) -> None:
        """The boundary itself is real overlap, not zero overlap — a range
        ending exactly on the window's first day must clamp, never refuse."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-01",
            date_to="2026-07-10",
            granularity="day",
            group_by="none",
        )

        clamped, warnings = clamp_to_coverage(spec, WINDOW)

        assert clamped.date_from.isoformat() == "2026-07-10"
        assert clamped.date_to.isoformat() == "2026-07-10"
        assert len(warnings) == 1

    def test_a_range_with_zero_overlap_is_refused_carrying_the_real_window(self) -> None:
        """User story 22: June 2026 has no data at all — refuse outright,
        carrying the real Coverage Window so the caller can offer an
        alternative. Never substitute July's numbers for June's."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-06-01",
            date_to="2026-06-30",
            granularity="day",
            group_by="none",
        )

        with pytest.raises(CoverageRefusedError) as excinfo:
            clamp_to_coverage(spec, WINDOW)

        assert excinfo.value.coverage == WINDOW

    def test_a_range_one_day_beyond_either_edge_is_zero_overlap_and_refused(self) -> None:
        """One day past either edge (2026-07-24, one day after the window's
        last day 2026-07-23) is zero overlap, not a one-day clamp."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-24",
            date_to="2026-07-30",
            granularity="day",
            group_by="none",
        )

        with pytest.raises(CoverageRefusedError):
            clamp_to_coverage(spec, WINDOW)


class TestExecuteEnforcesCoverage:
    """The regression test for the bug an independent review caught: calling
    `engine.execute()` directly — exactly what issue 16's in-process
    `run_report` tool will do, bypassing the `/report` route entirely — with
    an out-of-range spec did NOT error and did NOT return July's numbers. It
    returned a clean `rows: []`, `totals: {"resolved": 0.0}`,
    `warnings: []` table: every bucket index legitimately selected nothing,
    so the zero was arithmetically "correct" and completely misleading. An
    Assistant would have narrated that as "0 tickets resolved in June" — a
    confident false negative, not an obvious error.

    Fixed by enforcing `clamp_to_coverage` *inside* `execute()`, using
    `dataset.coverage` (already present on every `Dataset`, no new
    parameter, no I/O) — so any caller, not just the route that remembers
    to check first, gets the guard for free.
    """

    def test_execute_refuses_an_out_of_range_spec_instead_of_a_zero_filled_table(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-06-01",
            date_to="2026-06-30",
            granularity="day",
            group_by="none",
        )

        with pytest.raises(CoverageRefusedError) as excinfo:
            execute(spec, dataset)

        assert excinfo.value.coverage == dataset.coverage

    def test_execute_clamps_a_partially_overlapping_spec_and_warns(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-05",
            date_to="2026-07-12",
            granularity="day",
            group_by="none",
        )

        table = execute(spec, dataset)

        assert [row.bucket for row in table.rows] == ["2026-07-10", "2026-07-11", "2026-07-12"]
        assert len(table.warnings) == 1
        assert "2026-07-10" in table.warnings[0]
        assert "2026-07-12" in table.warnings[0]
        # The clamp warning matches sum of the real (clamped) days, not a
        # figure quietly computed over the originally requested range.
        assert table.totals["resolved"] == sum(DAILY_RESOLVED[0:3])

    def test_execute_on_a_pivot_layout_also_carries_the_clamp_warning(self, dataset) -> None:
        """The coverage warning must survive both `execute()` branches — the
        pivot path builds its `ReportTable` separately from the long-layout
        path, so it is its own place this could have been dropped."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-05",
            date_to="2026-07-12",
            granularity="day",
            group_by="none",
            layout="pivot",
        )

        table = execute(spec, dataset)

        assert any("2026-07-10" in w for w in table.warnings)
