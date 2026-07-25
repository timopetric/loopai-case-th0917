"""`engine.execute` unit tests (issue 04).

Exercises the real fixture dataset via `upstream._normalise_dataset` — no
network, no FastAPI. This slice covers Counters only (Duration Metric
aggregation is issue 05's scope), so every assertion here works with plain
sums. Real fixture figures pinned in the issue brief: 16372 resolved across
the window, 108 Actors, 103 Mailboxes, and the daily `resolved` series
[1467, 84, 111, 1478, 1675, 1701, 1586, 1557, 124, 75, 1767, 1883, 2534, 330].
"""

import json

import pytest

from app.engine import UnsupportedMetricError, execute
from app.models import Metric, ReportSpec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")

DAILY_RESOLVED = [1467, 84, 111, 1478, 1675, 1701, 1586, 1557, 124, 75, 1767, 1883, 2534, 330]
TOTAL_RESOLVED = 16372


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


class TestUnsupportedMetrics:
    def test_a_duration_metric_is_not_yet_supported_by_this_slice(self, dataset) -> None:
        spec = ReportSpec(
            metrics=[Metric.RESOLVE_TIME],
            date_from="2026-07-10",
            date_to="2026-07-23",
            granularity="total",
            group_by="none",
        )

        with pytest.raises(UnsupportedMetricError):
            execute(spec, dataset)
