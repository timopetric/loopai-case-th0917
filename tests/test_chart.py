"""`engine.execute` chart derivation (issue 14).

Exercises the real fixture dataset (same fixture and window as
`test_engine.py`) via `execute()` — the chart is a field on the same
`ReportTable` the table renders, never a second data path. Two behaviours
are pure enough to test directly against the committed fixture (issue 14
"How to verify", Level 1):

- **Top-eight selection by total**: with `group_by="agent"` (108 Actors),
  the chart keeps only the 8 largest by raw `Σvalue` of the chart metric
  and reports the rest as `chart.dropped`.
- **Colour is entity-stable, not rank-stable**: narrowing the date range
  changes which Actors make the top 8 and in what order (verified below
  against real per-Actor sums), but any Actor present in both windows
  keeps the same `color_slot`.
"""

import json

import pytest

from app.engine import execute
from app.models import Metric, ReportSpec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


@pytest.fixture
def dataset():
    return _normalise_dataset(FIXTURE_RAW, WINDOW)


class TestTopEightSelection:
    def test_chart_keeps_only_the_eight_largest_series_by_total_and_reports_the_rest(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
        )

        table = execute(spec, dataset)

        assert table.chart is not None
        assert len(table.chart.series) == 8
        # 108 Actors in the fixture (tests/test_engine.py docstring) minus the 8 shown.
        assert table.chart.dropped == 108 - 8

    def test_chart_is_hidden_when_the_report_is_collapsed_to_a_single_bucket(
        self, dataset
    ) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="agent",
        )

        table = execute(spec, dataset)

        assert table.chart is None


class TestChartHonoursEntityFilter:
    """table-filter-and-assistant-intro issue 02/07: the chart must agree
    with the (long-layout) table it sits next to — a filtered table with an
    unfiltered chart would contradict the PRD's stated reason for putting
    the filter in the engine at all ("preview, exports, and the Assistant's
    run_report all agree by construction"). "kaur" matches exactly three
    Actors in the fixture (Elena/Rosa/Ivan Kaur — `tests/test_engine.py`'s
    `TestEntityFilter` docstring)."""

    def test_chart_series_are_narrowed_to_the_filtered_entities(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
            entity_filter="kaur",
        )

        table = execute(spec, dataset)

        assert table.chart is not None
        assert {s.label for s in table.chart.series} == {"Elena Kaur", "Rosa Kaur", "Ivan Kaur"}
        assert table.chart.dropped == 0

    def test_the_eight_largest_cap_ranks_within_the_filtered_set_not_the_full_population(
        self, dataset
    ) -> None:
        """A filter matching fewer than eight entities must show all of
        them, never dropped as though ranked against the unfiltered 108."""
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
            entity_filter="kaur",
        )

        table = execute(spec, dataset)

        assert len(table.chart.series) == 3
        assert table.chart.dropped == 0


class TestColourFollowsEntityNotRank:
    def test_an_actor_kept_in_two_date_ranges_keeps_its_colour_even_though_ranking_changes(
        self, dataset
    ) -> None:
        # Real per-Actor `resolved` sums (verified against the fixture): the
        # first-week and second-week top-8 lists share six Actors but in a
        # different order — user_nN5brDNG is 2nd in the first week and 1st
        # in the second, so this is a genuine ranking change, not a no-op.
        first_week = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-16",
            granularity="day",
            group_by="agent",
        )
        second_week = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-17",
            date_to="2026-07-23",
            granularity="day",
            group_by="agent",
        )

        table_first = execute(first_week, dataset)
        table_second = execute(second_week, dataset)

        by_key_first = {s.key: s for s in table_first.chart.series}
        by_key_second = {s.key: s for s in table_second.chart.series}

        # Ranking genuinely changed between the two windows.
        assert [s.key for s in table_first.chart.series] != [
            s.key for s in table_second.chart.series
        ]

        common_keys = set(by_key_first) & set(by_key_second)
        assert len(common_keys) >= 4  # sanity: the overlap this test relies on is real
        for key in common_keys:
            assert by_key_first[key].color_slot == by_key_second[key].color_slot

    def test_colour_slot_never_exceeds_the_eight_slot_palette(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="day",
            group_by="mailbox",
        )

        table = execute(spec, dataset)

        assert all(0 <= s.color_slot <= 7 for s in table.chart.series)
