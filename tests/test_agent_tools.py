"""`app/agent/tools.py` — the nine Assistant tools and the repair taxonomy
(issue 16, architecture.md §5, the issue's "heaviest test slice").

Pure, offline, no model: `apply_batch`/`apply_one` take a `ReportSpec` and
the real fixture `Dataset` and return `ToolOutcome`s. Structured to mirror
architecture.md §5's taxonomy table row for row — the class names below
follow the table so a reviewer can check off each row directly, per the
issue's ask for "a row-by-row mapping".
"""

import json

import pytest
from pydantic import ValidationError

from app.agent.events import Repair, RepairCode
from app.agent.tools import (
    TOOL_NAMES,
    ToolCall,
    apply_batch,
    apply_one,
)
from app.models import Metric, ReportSpec, SortSpec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")
TOTAL_RESOLVED = 16372


@pytest.fixture
def dataset():
    return _normalise_dataset(FIXTURE_RAW, WINDOW)


def base_spec(**overrides) -> ReportSpec:
    data = {
        "metrics": [Metric.RESOLVED],
        "date_from": "2026-07-10",
        "date_to": "2026-07-16",
        "group_by": "none",
    }
    data.update(overrides)
    return ReportSpec.model_validate(data)


def call(name: str, **args) -> ToolCall:
    return ToolCall(name=name, args=args)


# ── Nine tools, strict schema, applies to the spec ──────────────────────


class TestNineToolsExistAndApply:
    def test_exactly_ten_tool_names(self):
        assert len(TOOL_NAMES) == 10

    def test_set_date_range_applies_both_bounds_together(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-11", date_to="2026-07-15")
        )
        assert outcome.ok
        assert outcome.spec_after.date_from.isoformat() == "2026-07-11"
        assert outcome.spec_after.date_to.isoformat() == "2026-07-15"

    def test_set_metrics_replaces_the_metric_list(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=["resolved", "handle_time"]))
        assert outcome.ok
        assert outcome.spec_after.metrics == [Metric.RESOLVED, Metric.HANDLE_TIME]

    def test_set_grouping_applies(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("set_grouping", by="agent"))
        assert outcome.ok
        assert outcome.spec_after.group_by == "agent"

    def test_set_sort_applies(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("set_sort", column="resolved", direction="asc"))
        assert outcome.ok
        assert outcome.spec_after.sort == SortSpec(column="resolved", direction="asc")

    def test_set_columns_applies(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcome = apply_one(spec, dataset, call("set_columns", order=["handle_time", "resolved"]))
        assert outcome.ok
        assert outcome.spec_after.columns_order == ["handle_time", "resolved"]

    def test_set_chart_applies(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcome = apply_one(spec, dataset, call("set_chart", metric="handle_time"))
        assert outcome.ok
        assert outcome.spec_after.chart_metric == Metric.HANDLE_TIME

    def test_set_layout_applies_both_fields_together(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("set_layout", granularity="total", layout="long"))
        assert outcome.ok
        assert outcome.spec_after.granularity == "total"
        assert outcome.spec_after.layout == "long"

    def test_set_filter_sets_the_entity_filter(self, dataset):
        spec = base_spec(group_by="agent")
        outcome = apply_one(spec, dataset, call("set_filter", query="theo"))
        assert outcome.ok
        assert outcome.spec_after.entity_filter == "theo"

    def test_set_filter_with_empty_string_clears_an_existing_filter(self, dataset):
        spec = base_spec(group_by="agent", entity_filter="theo")
        outcome = apply_one(spec, dataset, call("set_filter", query=""))
        assert outcome.ok
        assert outcome.spec_after.entity_filter is None

    def test_run_report_executes_the_current_spec(self, dataset):
        spec = base_spec(date_from="2026-07-10", date_to="2026-07-23", granularity="total")
        outcome = apply_one(spec, dataset, call("run_report"))
        assert outcome.ok
        assert outcome.result["totals"]["resolved"] == TOTAL_RESOLVED
        # a read tool never changes the spec
        assert outcome.spec_after == spec

    def test_get_meta_returns_actors_mailboxes_metrics_coverage(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("get_meta"))
        assert outcome.ok
        assert outcome.result["coverage"] == {"from": "2026-07-10", "to": "2026-07-23"}
        assert len(outcome.result["actors"]) == 108
        assert len(outcome.result["mailboxes"]) == 103
        assert {m["key"] for m in outcome.result["metrics"]} == {m.value for m in Metric}
        assert outcome.spec_after == spec

    @pytest.mark.parametrize(
        ("name", "bad_args"),
        [
            ("set_date_range", {"date_from": "not-a-date", "date_to": "2026-07-11"}),
            ("set_metrics", {"metrics": "resolved"}),  # not a list
            ("set_grouping", {"by": "mailbox_and_agent"}),
            ("set_sort", {"column": "resolved", "direction": "sideways"}),
            ("set_chart", {"metric": "customer_satisfaction"}),
            ("set_layout", {"granularity": "week", "layout": "long"}),
        ],
    )
    def test_malformed_args_are_rejected_by_the_strict_schema(self, dataset, name, bad_args):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call(name, **bad_args))
        assert outcome.ok is False
        assert outcome.error_category == "validation"
        assert outcome.spec_after is None


# ── Date range is a single, pair-scoped call ────────────────────────────


class TestDateRangeIsAPairNeverTwoBounds:
    def test_setting_a_date_range_is_one_call_and_produces_a_valid_ordered_range(self, dataset):
        spec = base_spec(date_from="2026-07-10", date_to="2026-07-11")
        # Moving the window "later" in one call — a two-tool version that set
        # date_from first would momentarily invert against the old date_to.
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-20", date_to="2026-07-22")
        )
        assert outcome.ok
        assert outcome.spec_after.date_from <= outcome.spec_after.date_to

    def test_an_inverted_pair_is_rejected_as_a_genuine_input_error(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-15", date_to="2026-07-10")
        )
        assert outcome.ok is False
        assert outcome.error_category == "validation"


# ── Repair taxonomy — architecture.md §5, row by row ────────────────────


class TestRepairSetMetricsDropsChartMetric:
    """Row: `set_metrics` drops the metric `chart_metric` pointed at |
    Repair — reset to `metrics[0]`."""

    def test_dropping_the_charted_metric_resets_chart_metric(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME], chart_metric=Metric.HANDLE_TIME
        )
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=["resolved"]))
        assert outcome.ok
        assert outcome.spec_after.chart_metric is None
        assert outcome.spec_after.effective_chart_metric == Metric.RESOLVED
        assert outcome.adjusted == [Repair(code=RepairCode.CHART_METRIC_RESET)]

    def test_dropping_an_unrelated_metric_does_not_repair_the_chart(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME], chart_metric=Metric.RESOLVED
        )
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=["resolved"]))
        assert outcome.ok
        assert outcome.spec_after.chart_metric == Metric.RESOLVED
        assert outcome.adjusted == []


class TestRepairSetMetricsDropsSortColumn:
    """Row: `set_metrics` drops the metric `sort` pointed at | Repair —
    clear sort."""

    def test_dropping_the_sorted_metric_clears_sort(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME],
            sort=SortSpec(column="handle_time", direction="desc"),
        )
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=["resolved"]))
        assert outcome.ok
        assert outcome.spec_after.sort is None
        assert outcome.adjusted == [Repair(code=RepairCode.SORT_CLEARED)]

    def test_both_chart_and_sort_can_be_repaired_by_one_call(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME],
            chart_metric=Metric.HANDLE_TIME,
            sort=SortSpec(column="handle_time", direction="desc"),
        )
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=["resolved"]))
        assert outcome.ok
        assert outcome.spec_after.chart_metric is None
        assert outcome.spec_after.sort is None
        codes = {r.code for r in outcome.adjusted}
        assert codes == {RepairCode.CHART_METRIC_RESET, RepairCode.SORT_CLEARED}


class TestSetGroupingOrphaningSort:
    """Row: `set_grouping` orphans a sort on a group column | Repair — clear
    sort. See `app/agent/tools.py`'s module docstring for the interpretive
    call: a sort ranks rows within a Bucket, and `group_by == "none"` leaves
    exactly one row per Bucket to rank, so grouping away from agent/mailbox
    to none orphans an existing sort."""

    def test_ungrouping_clears_a_pre_existing_sort(self, dataset):
        spec = base_spec(group_by="agent", sort=SortSpec(column="resolved", direction="desc"))
        outcome = apply_one(spec, dataset, call("set_grouping", by="none"))
        assert outcome.ok
        assert outcome.spec_after.sort is None
        assert outcome.adjusted == [Repair(code=RepairCode.SORT_CLEARED)]

    def test_switching_between_two_groupings_does_not_touch_sort(self, dataset):
        spec = base_spec(group_by="agent", sort=SortSpec(column="resolved", direction="desc"))
        outcome = apply_one(spec, dataset, call("set_grouping", by="mailbox"))
        assert outcome.ok
        assert outcome.spec_after.sort == SortSpec(column="resolved", direction="desc")
        assert outcome.adjusted == []

    def test_grouping_with_no_pre_existing_sort_reports_no_repair(self, dataset):
        spec = base_spec(group_by="agent")
        outcome = apply_one(spec, dataset, call("set_grouping", by="none"))
        assert outcome.ok
        assert outcome.adjusted == []


class TestRepairSetColumnsDroppedColumn:
    """Row: `set_columns` references a column that no longer exists |
    Repair — drop it from the order."""

    def test_stale_column_name_is_dropped_and_reported(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcome = apply_one(
            spec, dataset, call("set_columns", order=["resolved", "actioned_emails"])
        )
        assert outcome.ok
        assert outcome.spec_after.columns_order == ["resolved"]
        assert outcome.adjusted == [Repair(code=RepairCode.COLUMN_DROPPED)]

    def test_an_order_naming_only_real_columns_reports_no_repair(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcome = apply_one(
            spec, dataset, call("set_columns", order=["handle_time", "resolved"])
        )
        assert outcome.ok
        assert outcome.adjusted == []


class TestRepairSetChartAutoAdds:
    """Row: `set_chart(m)` where `m ∉ metrics` | Repair — auto-add `m` to
    metrics, then set it. The only Repair that names a Metric."""

    def test_charting_an_unselected_metric_adds_it_and_charts_it(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED])
        outcome = apply_one(spec, dataset, call("set_chart", metric="handle_time"))
        assert outcome.ok
        assert Metric.HANDLE_TIME in outcome.spec_after.metrics
        assert outcome.spec_after.chart_metric == Metric.HANDLE_TIME
        assert outcome.adjusted == [
            Repair(code=RepairCode.METRIC_AUTO_ADDED, metric=Metric.HANDLE_TIME)
        ]

    def test_charting_an_already_selected_metric_reports_no_repair(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcome = apply_one(spec, dataset, call("set_chart", metric="handle_time"))
        assert outcome.ok
        assert outcome.adjusted == []


class TestRepairDateRangePartialOverlap:
    """Row: `set_date_range` partially overlaps the Coverage Window |
    Repair — clamp, report."""

    def test_range_hanging_off_the_start_is_clamped(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-01", date_to="2026-07-12")
        )
        assert outcome.ok
        assert outcome.spec_after.date_from.isoformat() == "2026-07-10"
        assert outcome.spec_after.date_to.isoformat() == "2026-07-12"
        assert outcome.adjusted == [Repair(code=RepairCode.DATE_RANGE_CLAMPED)]

    def test_range_hanging_off_the_end_is_clamped(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-20", date_to="2026-08-05")
        )
        assert outcome.ok
        assert outcome.spec_after.date_from.isoformat() == "2026-07-20"
        assert outcome.spec_after.date_to.isoformat() == "2026-07-23"
        assert outcome.adjusted == [Repair(code=RepairCode.DATE_RANGE_CLAMPED)]

    def test_range_fully_inside_the_window_is_not_repaired(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-07-12", date_to="2026-07-14")
        )
        assert outcome.ok
        assert outcome.adjusted == []


class TestErrorDateRangeZeroOverlap:
    """Row: `set_date_range` misses the Coverage Window entirely | Error —
    refuse, return the window."""

    def test_a_range_with_no_overlap_at_all_errors_rather_than_repairs(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="2026-06-01", date_to="2026-06-30")
        )
        assert outcome.ok is False
        assert outcome.error_category == "coverage"
        assert outcome.spec_after is None
        assert outcome.adjusted == []


class TestErrorEmptyMetrics:
    """Row: `set_metrics([])` | Error — a report with no metrics isn't a
    report."""

    def test_empty_metric_list_errors(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("set_metrics", metrics=[]))
        assert outcome.ok is False
        assert outcome.error_category == "validation"


class TestErrorBadEnumOrMalformedDate:
    """Row: bad enum, malformed date, unknown actor id | Error — one retry."""

    def test_unknown_metric_name_errors(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_metrics", metrics=["customer_satisfaction"])
        )
        assert outcome.ok is False
        assert outcome.error_category == "validation"

    def test_malformed_date_errors(self, dataset):
        spec = base_spec()
        outcome = apply_one(
            spec, dataset, call("set_date_range", date_from="not-a-date", date_to="2026-07-11")
        )
        assert outcome.ok is False
        assert outcome.error_category == "validation"

    def test_sort_by_a_real_metric_not_currently_selected_errors(self, dataset):
        # A real Metric enum value, just not one of spec.metrics right now —
        # caught by ReportSpec's own cross-field validator on merge.
        spec = base_spec(metrics=[Metric.RESOLVED])
        outcome = apply_one(spec, dataset, call("set_sort", column="handle_time"))
        assert outcome.ok is False
        assert outcome.error_category == "validation"


class TestNeitherRepairNorErrorActionedEmailsByActor:
    """Row: Grouping by Actor with `actioned_emails` selected | Neither — a
    Warning (valid number, non-additive). Verified two ways: the tool call
    itself succeeds cleanly with no Repair, and the Warning only shows up
    later, at `run_report` time, in `ReportTable.warnings`."""

    def test_grouping_by_actor_with_actioned_emails_is_not_a_repair(self, dataset):
        spec = base_spec(metrics=[Metric.ACTIONED_EMAILS])
        outcome = apply_one(spec, dataset, call("set_grouping", by="agent"))
        assert outcome.ok
        assert outcome.adjusted == []

    def test_the_warning_appears_only_when_the_report_actually_runs(self, dataset):
        spec = base_spec(metrics=[Metric.ACTIONED_EMAILS], group_by="agent")
        outcome = apply_one(spec, dataset, call("run_report"))
        assert outcome.ok
        assert any("actioned_emails is not additive" in w for w in outcome.result["warnings"])


class TestRepairSetFilterIgnoredWhenUngrouped:
    """Row: `set_filter` while `group_by == "none"` | Repair — apply the
    filter and report it as ignored, never error, since there is no Actor/
    Mailbox breakdown to narrow (engine.py's `_entity_filter_warnings`)."""

    def test_filtering_while_ungrouped_applies_and_reports_ignored(self, dataset):
        spec = base_spec(group_by="none")
        outcome = apply_one(spec, dataset, call("set_filter", query="theo"))
        assert outcome.ok
        assert outcome.spec_after.entity_filter == "theo"
        assert outcome.adjusted == [Repair(code=RepairCode.ENTITY_FILTER_IGNORED)]

    def test_filtering_while_grouped_reports_no_repair(self, dataset):
        spec = base_spec(group_by="agent")
        outcome = apply_one(spec, dataset, call("set_filter", query="theo"))
        assert outcome.ok
        assert outcome.adjusted == []

    def test_clearing_the_filter_while_ungrouped_reports_no_repair(self, dataset):
        spec = base_spec(group_by="none")
        outcome = apply_one(spec, dataset, call("set_filter", query=""))
        assert outcome.ok
        assert outcome.spec_after.entity_filter is None
        assert outcome.adjusted == []

    def test_grouping_away_from_none_with_an_existing_filter_reports_no_repair(self, dataset):
        # Reverse direction of the orphaning below: a filter set while
        # ungrouped, then grouping turned on, is now live — no Repair.
        spec = base_spec(group_by="none", entity_filter="theo")
        outcome = apply_one(spec, dataset, call("set_grouping", by="agent"))
        assert outcome.ok
        assert outcome.adjusted == []

    def test_set_grouping_to_none_with_an_existing_filter_reports_ignored(self, dataset):
        """`_set_grouping`'s own analogue of the orphaned-sort repair
        (module docstring): turning grouping off makes an existing filter
        inert, exactly the same verdict `set_filter` reports when applied
        while already ungrouped."""
        spec = base_spec(group_by="agent", entity_filter="theo")
        outcome = apply_one(spec, dataset, call("set_grouping", by="none"))
        assert outcome.ok
        assert outcome.adjusted == [Repair(code=RepairCode.ENTITY_FILTER_IGNORED)]


class TestBatchReconciliationEntityFilterIgnoredVersusGrouping:
    """`ENTITY_FILTER_IGNORED` is caused by the combination of `entity_filter`
    and `group_by`, not by `entity_filter` alone — a later call in the same
    batch that changes *either* field must be able to supersede the verdict
    (ADR-0002's batch reconciliation, module docstring)."""

    def test_filter_then_group_in_one_batch_drops_the_stale_ignored_repair(self, dataset):
        spec = base_spec(group_by="none")
        outcomes = apply_batch(
            spec,
            dataset,
            [call("set_filter", query="theo"), call("set_grouping", by="agent")],
        )
        assert all(o.ok for o in outcomes)
        assert not any(
            Repair(code=RepairCode.ENTITY_FILTER_IGNORED) in o.adjusted for o in outcomes
        )
        final = outcomes[-1].spec_after
        assert final.group_by == "agent"
        assert final.entity_filter == "theo"

    def test_filter_then_ungroup_in_one_batch_reports_ignored_exactly_once(self, dataset):
        spec = base_spec(group_by="agent")
        outcomes = apply_batch(
            spec,
            dataset,
            [call("set_filter", query="theo"), call("set_grouping", by="none")],
        )
        assert all(o.ok for o in outcomes)
        occurrences = sum(
            o.adjusted.count(Repair(code=RepairCode.ENTITY_FILTER_IGNORED)) for o in outcomes
        )
        assert occurrences == 1


class TestSetFilterCaseInsensitivePartialMatchThroughRunReport:
    """The tool does no name-resolution of its own (module docstring / issue
    07) — it relies entirely on the engine's existing loose substring match,
    exercised here end to end via `run_report`."""

    def test_a_lowercase_partial_query_matches_end_to_end(self, dataset):
        spec = base_spec(group_by="agent")
        actor_name = dataset.actors[0].name
        partial = actor_name[: max(3, len(actor_name) // 2)].lower()
        set_outcome = apply_one(spec, dataset, call("set_filter", query=partial))
        assert set_outcome.ok
        run_outcome = apply_one(set_outcome.spec_after, dataset, call("run_report"))
        assert run_outcome.ok
        assert run_outcome.result["row_count"] >= 1


class TestRunReportAlwaysReportsEntityFilter:
    """`run_report`'s result dict is always self-describing (issue 07 /
    `get_meta`'s same pattern) — the model never has to remember an earlier
    `set_filter` call in the same turn."""

    def test_run_report_reports_null_entity_filter_when_unset(self, dataset):
        spec = base_spec()
        outcome = apply_one(spec, dataset, call("run_report"))
        assert outcome.ok
        assert outcome.result["entity_filter"] is None

    def test_run_report_reports_the_active_entity_filter_when_set(self, dataset):
        spec = base_spec(group_by="agent", entity_filter="theo")
        outcome = apply_one(spec, dataset, call("run_report"))
        assert outcome.ok
        assert outcome.result["entity_filter"] == "theo"


# ── run_report inherits the coverage guard from engine.execute ─────────


class TestRunReportInheritsCoverageGuard:
    def test_out_of_coverage_range_errors_rather_than_repairs(self, dataset):
        spec = base_spec(date_from="2026-06-01", date_to="2026-06-30")
        outcome = apply_one(spec, dataset, call("run_report"))
        assert outcome.ok is False
        assert outcome.error_category == "coverage"


# ── Batch reconciliation — the case most likely to be skipped ──────────


class TestBatchReconciliation:
    """architecture.md §5 / ADR-0002: within one model message, discard any
    adjustment to a field a LATER call in the same batch explicitly sets."""

    def test_a_later_set_sort_suppresses_an_earlier_sort_cleared_repair(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME],
            sort=SortSpec(column="handle_time", direction="desc"),
        )
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_metrics", metrics=["resolved"]),  # would clear sort
                call("set_sort", column="resolved", direction="asc"),  # sets a new sort
            ],
        )
        first, second = outcomes
        assert first.ok and second.ok
        # The repair really happened to spec_after — it just isn't reported.
        assert first.adjusted == []
        assert second.spec_after.sort == SortSpec(column="resolved", direction="asc")

    def test_a_later_set_chart_suppresses_an_earlier_chart_metric_reset_repair(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME], chart_metric=Metric.HANDLE_TIME
        )
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_metrics", metrics=["resolved"]),  # would reset chart_metric
                call("set_chart", metric="resolved"),  # explicitly re-sets chart
            ],
        )
        first, second = outcomes
        assert first.adjusted == []
        assert second.ok
        assert second.spec_after.chart_metric == Metric.RESOLVED

    def test_a_later_set_columns_suppresses_an_earlier_column_dropped_repair(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED, Metric.HANDLE_TIME])
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_columns", order=["resolved", "gone_metric"]),  # drops "gone_metric"
                call("set_columns", order=["handle_time", "resolved"]),  # re-sets columns_order
            ],
        )
        first, second = outcomes
        assert first.adjusted == []
        assert second.ok
        assert second.spec_after.columns_order == ["handle_time", "resolved"]

    def test_a_later_set_metrics_suppresses_an_earlier_metric_auto_added_repair(self, dataset):
        spec = base_spec(metrics=[Metric.RESOLVED])
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_chart", metric="handle_time"),  # auto-adds handle_time
                call("set_metrics", metrics=["resolved", "new_tickets"]),  # replaces the list
            ],
        )
        first, second = outcomes
        assert first.adjusted == []
        assert second.ok
        assert Metric.HANDLE_TIME not in second.spec_after.metrics

    def test_a_repair_with_no_superseding_call_still_survives_the_batch(self, dataset):
        spec = base_spec(
            metrics=[Metric.RESOLVED, Metric.HANDLE_TIME], chart_metric=Metric.HANDLE_TIME
        )
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_metrics", metrics=["resolved"]),  # resets chart_metric
                call("set_grouping", by="agent"),  # unrelated field
            ],
        )
        first, second = outcomes
        assert first.adjusted == [Repair(code=RepairCode.CHART_METRIC_RESET)]
        assert second.ok

    def test_three_call_batch_applies_sequentially_like_the_live_smoke_test(self, dataset):
        """architecture.md §5's live-model verification saw exactly this
        shape: three tool calls in one assistant message."""
        spec = base_spec()
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_date_range", date_from="2026-07-10", date_to="2026-07-16"),
                call("set_metrics", metrics=["resolved", "handle_time"]),
                call("set_grouping", by="agent"),
            ],
        )
        assert all(o.ok for o in outcomes)
        final = outcomes[-1].spec_after
        assert final.metrics == [Metric.RESOLVED, Metric.HANDLE_TIME]
        assert final.group_by == "agent"
        assert final.date_from.isoformat() == "2026-07-10"

    def test_an_earlier_failed_call_does_not_block_later_calls_in_the_batch(self, dataset):
        spec = base_spec()
        outcomes = apply_batch(
            spec,
            dataset,
            [
                call("set_metrics", metrics=["not_a_real_metric"]),  # errors
                call("set_grouping", by="agent"),  # still applies
            ],
        )
        first, second = outcomes
        assert first.ok is False
        assert second.ok
        assert second.spec_after.group_by == "agent"
        # The failed call's own spec_before is the pre-batch spec, since
        # nothing before it changed anything.
        assert first.spec_before == spec


class TestReportCodeStaysAClosedEnum:
    """Constraint carried over from issue 15: no free-text Repair code can
    ever be constructed, so nothing this module builds can smuggle model-
    supplied prose into a Repair."""

    def test_repair_construction_rejects_anything_outside_the_enum(self):
        with pytest.raises(ValidationError):
            Repair(code="not_a_real_repair_code")
