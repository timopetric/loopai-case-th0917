"""
"Almost unit tests" for the report-spec-editing agent design, PLUS an
assumption-test suite: every capability ReportSpec promises gets a test that
verifies the assumption against REAL API data (the fixture pulled unscoped,
full-window, all-metrics -- resp-full-unscoped-latest.json, ~103 mailboxes /
108 actors).

Offline by default (`pytest scratch/agent-spec-lab/ -q`). Tests that hit a
live network endpoint are marked `@pytest.mark.live` and excluded by
pytest.ini's `addopts = -m "not live"`; run them explicitly with `-m live`.

Run: uv run --with pydantic,pytest,jinja2,openai python -m pytest scratch/agent-spec-lab/ -q
Live: uv run --with pydantic,pytest,jinja2,openai,requests python -m pytest scratch/agent-spec-lab/ -q -m live
"""
from __future__ import annotations

import itertools
import json
import os
from datetime import date

import pytest

from agent_loop import MaxIterationsExceeded, run_agent_turn
from engine import (
    CrossBreakdownNotSupported,
    _bucket_indices,
    _period_groups,
    _tick_dates,
    data_window,
    load_fixture,
    run_report,
)
from events import UiEvent
from fake_llm import FakeLLM, calling, final, tool_call
from models import METRIC_DESCRIPTIONS, TIME_METRICS, Metric, ReportSpec, SortSpec, SpecPatch
from prompts import render_system_prompt

FIXTURE = load_fixture()
WIN_FROM, WIN_TO = data_window(FIXTURE)  # 2026-07-10 .. 2026-07-23


def _agent_by_name(name: str) -> dict:
    return next(a for a in FIXTURE["actors"] if a["name"] == name)


def _mailbox_by_name(name: str) -> dict:
    return next(m for m in FIXTURE["mailbox"] if m["name"] == name)


def _top_agents(metric: str = "resolved", n: int = 3) -> list[dict]:
    return sorted(FIXTURE["actors"], key=lambda a: sum(a[metric]), reverse=True)[:n]


def _top_mailboxes(metric: str = "resolved", n: int = 3) -> list[dict]:
    return sorted(FIXTURE["mailbox"], key=lambda m: sum(m[metric]), reverse=True)[:n]


RETURNS_MAILBOX = _mailbox_by_name("Returns")


def base_spec(**overrides) -> ReportSpec:
    defaults = dict(
        metrics=[Metric.RESOLVED, Metric.HANDLE_TIME],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="total",
        group_by="agent",
        columns_order=["group", "resolved", "handle_time", "handle_time_avg"],
    )
    defaults.update(overrides)
    return ReportSpec(**defaults)


# ===========================================================================
# Part 1: agent-loop scenarios (fake LLM)
# ===========================================================================


def test_switch_columns_around():
    spec = base_spec()
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps(
                        {"columns_order": ["group", "handle_time", "handle_time_avg", "resolved"]}
                    ),
                )
            ),
            final("Swapped the last two columns with resolved."),
        ]
    )
    result = run_agent_turn(spec, "switch the columns around", llm, FIXTURE)

    assert result.final_spec.columns_order == ["group", "handle_time", "handle_time_avg", "resolved"]
    spec_change_events = [e for e in result.ui_events if e.kind == "spec_change"]
    assert len(spec_change_events) == 1
    assert "Swapped columns" in spec_change_events[0].chips
    for e in result.ui_events:
        assert "columns_order" not in e.text
        assert "update_spec" not in e.text


def test_who_resolved_the_most():
    spec = base_spec(group_by="none", granularity="day", columns_order=[])
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps(
                        {
                            "group_by": "agent",
                            "granularity": "total",
                            "sort": {"field": "resolved", "direction": "desc"},
                        }
                    ),
                )
            ),
            calling(tool_call("2", "run_report", "{}")),
            final("Providers resolved the most tickets in this window."),
        ]
    )
    result = run_agent_turn(spec, "show me who resolved the most", llm, FIXTURE)

    assert result.final_spec.group_by == "agent"
    assert result.final_spec.sort == SortSpec(field="resolved", direction="desc")

    table = run_report(result.final_spec, FIXTURE)
    assert not table.is_empty()
    resolved_values = [row["resolved"] for row in table.rows]
    assert resolved_values == sorted(resolved_values, reverse=True)
    assert table.rows[0]["group"] == "Providers"
    assert table.rows[0]["resolved"] == pytest.approx(sum(_agent_by_name("Providers")["resolved"]))

    status_events = [e for e in result.ui_events if e.kind == "status"]
    assert any("Running the report" in e.text or "Report updated" in e.text for e in status_events)


def test_mailbox_filter_is_trusted_when_grouped_by_mailbox():
    """CORRECTED behavior (second probing pass): the mailbox breakdown fully
    reconciles with totals once you look past the 5 low-volume spec-example
    mailboxes -- it is NOT unreliable. Filtering to one mailbox via
    group_by='mailbox' + mailbox_ids should just work, with no data-quality
    warning, and the returned row should match the fixture exactly."""
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps(
                        {
                            "group_by": "mailbox",
                            "mailbox_ids": [RETURNS_MAILBOX["id"]],
                            "metrics": ["new_tickets"],
                        }
                    ),
                )
            ),
            calling(tool_call("2", "run_report", "{}")),
            final("Filtered to the Returns mailbox."),
        ]
    )
    result = run_agent_turn(spec, "only the Returns inbox", llm, FIXTURE)

    assert result.final_spec.mailbox_ids == [RETURNS_MAILBOX["id"]]
    assert result.final_spec.group_by == "mailbox"

    warnings = [e for e in result.ui_events if e.kind == "warning"]
    assert warnings == [], f"expected no data-quality warnings, got: {warnings}"

    table = run_report(result.final_spec, FIXTURE)
    assert len(table.rows) == 1
    assert table.rows[0]["group"] == "Returns"
    assert table.rows[0]["new_tickets"] == pytest.approx(sum(RETURNS_MAILBOX["new_tickets"]))


def test_mailbox_filter_without_matching_group_by_warns_no_effect():
    """A mailbox filter set while group_by isn't 'mailbox' can't change the
    top-level totals (matches the real API: scope/filters never touch
    top-level totals) -- the engine should warn that the filter is a no-op,
    not silently ignore it or claim the data is unreliable."""
    spec = base_spec(group_by="none", granularity="total", columns_order=[], metrics=[Metric.RESOLVED])
    patched = SpecPatch(mailbox_ids=[RETURNS_MAILBOX["id"]]).apply(spec)
    table = run_report(patched, FIXTURE)
    assert any("no effect" in w for w in table.warnings)


def test_narrow_date_range_within_window_no_warning():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    narrow_from = date(2026, 7, 17)
    narrow_to = date(2026, 7, 23)
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps({"date_from": narrow_from.isoformat(), "date_to": narrow_to.isoformat()}),
                )
            ),
            calling(tool_call("2", "run_report", "{}")),
            final("Narrowed to the last week."),
        ]
    )
    result = run_agent_turn(spec, "last week only", llm, FIXTURE)

    assert result.final_spec.date_from == narrow_from
    assert result.final_spec.date_to == narrow_to
    warnings = [e for e in result.ui_events if e.kind == "warning"]
    assert warnings == []


def test_out_of_window_date_range_clamped_with_warning():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps({"date_from": "2026-08-01", "date_to": "2026-08-07"}),
                )
            ),
            calling(tool_call("2", "run_report", "{}")),
            final("That range is outside the available data, so I used the full available window."),
        ]
    )
    result = run_agent_turn(spec, "show me last week of August", llm, FIXTURE)

    assert result.final_spec.date_from == date(2026, 8, 1)
    warnings = [e for e in result.ui_events if e.kind == "warning"]
    assert any("no overlap" in e.text or "clamped" in e.text for e in warnings)


def test_invalid_enum_then_retry_succeeds():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM(
        [
            calling(tool_call("1", "update_spec", json.dumps({"granularity": "hourly"}))),
            calling(tool_call("2", "update_spec", json.dumps({"granularity": "week"}))),
            final("Switched to weekly."),
        ]
    )
    result = run_agent_turn(spec, "show weekly", llm, FIXTURE)

    assert result.final_spec.granularity == "week"
    from events import Error as ErrorEvent

    error_events = [e for e in result.events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].retriable is True
    assert all(e.kind != "error" for e in result.ui_events)


def test_invalid_json_args_then_retry_succeeds():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM(
        [
            calling(tool_call("1", "update_spec", "{not valid json")),
            calling(tool_call("2", "update_spec", json.dumps({"group_by": "mailbox"}))),
            final("Grouped by mailbox."),
        ]
    )
    result = run_agent_turn(spec, "group by mailbox", llm, FIXTURE)
    assert result.final_spec.group_by == "mailbox"


def test_invalid_date_range_patch_then_retry_succeeds():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM(
        [
            calling(
                tool_call(
                    "1",
                    "update_spec",
                    json.dumps({"date_from": "2026-07-23", "date_to": "2026-07-10"}),
                )
            ),
            calling(
                tool_call(
                    "2",
                    "update_spec",
                    json.dumps({"date_from": "2026-07-10", "date_to": "2026-07-23"}),
                )
            ),
            final("Fixed the date range."),
        ]
    )
    result = run_agent_turn(spec, "set the range", llm, FIXTURE)
    assert result.final_spec.date_from <= result.final_spec.date_to


def test_max_iterations_guard():
    spec = base_spec(group_by="none", granularity="total", columns_order=[])
    llm = FakeLLM([calling(tool_call(str(i), "get_spec", "{}")) for i in range(10)])
    with pytest.raises(MaxIterationsExceeded):
        run_agent_turn(spec, "loop forever", llm, FIXTURE, max_iterations=3)


def test_full_replacement_loses_fields_patch_does_not():
    customized = base_spec(
        group_by="agent",
        layout="pivot",
        agent_ids=["user_abc"],
        sort=SortSpec(field="resolved", direction="desc"),
        columns_order=[],
    )

    llm_full_output = {
        "metrics": ["resolved"],
        "date_from": "2026-07-15",
        "date_to": "2026-07-20",
    }
    replaced = ReportSpec.model_validate(llm_full_output)

    assert replaced.layout == "long"
    assert replaced.agent_ids == []
    assert replaced.sort is None
    assert replaced.group_by == "none"
    assert replaced != customized

    patch = SpecPatch(metrics=[Metric.RESOLVED], date_from=date(2026, 7, 15), date_to=date(2026, 7, 20))
    patched = patch.apply(customized)

    assert patched.layout == "pivot"
    assert patched.agent_ids == ["user_abc"]
    assert patched.sort == SortSpec(field="resolved", direction="desc")
    assert patched.group_by == "agent"
    assert patched.metrics == [Metric.RESOLVED]
    assert patched.date_from == date(2026, 7, 15)


def test_system_prompt_renders_and_contains_units_warning():
    spec = base_spec()
    rendered = render_system_prompt(spec, (WIN_FROM, WIN_TO))

    assert "HOURS" in rendered
    assert "handle_time" in rendered
    assert "metric_count" in rendered or "_count" in rendered
    assert str(WIN_FROM) in rendered
    assert str(WIN_TO) in rendered
    assert '"metrics"' in rendered
    assert "update_spec" in rendered and "run_report" in rendered


# ===========================================================================
# Part 2: assumption tests against REAL fixture data
# ===========================================================================


@pytest.mark.parametrize("metric", list(Metric))
def test_agent_breakdown_reconciles_or_warns(metric: Metric):
    """Every metric's per-agent breakdown must sum to the top-level total --
    EXCEPT actioned_emails, which is a known upstream inconsistency (actor
    sums to more than the total). The engine must catch that dynamically,
    not just for this one hardcoded metric."""
    spec = ReportSpec(
        metrics=[metric], date_from=WIN_FROM, date_to=WIN_TO, granularity="total", group_by="agent"
    )
    table = run_report(spec, FIXTURE)
    top_total = sum(FIXTURE[metric.value])
    breakdown_total = sum(row[metric.value] for row in table.rows)

    if metric == Metric.ACTIONED_EMAILS:
        assert any("does not match" in w for w in table.warnings)
        assert breakdown_total != pytest.approx(top_total)
    else:
        assert table.warnings == []
        assert breakdown_total == pytest.approx(top_total, abs=1e-3)


@pytest.mark.parametrize("metric", list(Metric))
def test_mailbox_breakdown_reconciles(metric: Metric):
    """CORRECTED assumption: unlike agents, the mailbox breakdown reconciles
    for every metric including actioned_emails -- pass-1's 'mailbox is
    broken' conclusion was a 5-mailbox sampling artifact."""
    spec = ReportSpec(
        metrics=[metric], date_from=WIN_FROM, date_to=WIN_TO, granularity="total", group_by="mailbox"
    )
    table = run_report(spec, FIXTURE)
    top_total = sum(FIXTURE[metric.value])
    breakdown_total = sum(row[metric.value] for row in table.rows)

    assert table.warnings == []
    assert breakdown_total == pytest.approx(top_total)


def test_cross_breakdown_not_supported_agent_grouped_mailbox_filtered():
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        group_by="agent",
        mailbox_ids=[RETURNS_MAILBOX["id"]],
    )
    with pytest.raises(CrossBreakdownNotSupported):
        run_report(spec, FIXTURE)


def test_cross_breakdown_not_supported_mailbox_grouped_agent_filtered():
    top_agent = _top_agents()[0]
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        group_by="mailbox",
        agent_ids=[top_agent["id"]],
    )
    with pytest.raises(CrossBreakdownNotSupported):
        run_report(spec, FIXTURE)


@pytest.mark.parametrize("granularity", ["week", "total"])
def test_weighted_average_matches_raw_sum_over_sum_count(granularity: str):
    """Averages must be sum(metric)/sum(metric_count) over the raw arrays --
    never a mean of per-day averages (mean-of-means)."""
    spec = ReportSpec(
        metrics=[Metric.HANDLE_TIME],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity=granularity,
        group_by="none",
    )
    table = run_report(spec, FIXTURE)
    dates = _tick_dates(FIXTURE)
    idxs = _bucket_indices(dates, WIN_FROM, WIN_TO)

    if granularity == "total":
        periods = [("total", idxs)]
    else:
        periods = _period_groups(dates, idxs, "week")

    assert len(table.rows) == len(periods)
    for row, (_label, sub_idxs) in zip(table.rows, periods):
        raw_total = sum(FIXTURE["handle_time"][i] for i in sub_idxs)
        raw_count = sum(FIXTURE["handle_time_count"][i] for i in sub_idxs)
        expected_avg = raw_total / raw_count
        assert row["handle_time_avg"] == pytest.approx(expected_avg, abs=1e-4)


def test_weighted_average_diverges_from_mean_of_means_on_real_data():
    """Confirms the two formulas actually diverge on this dataset -- so the
    test above would catch a regression to the wrong (mean-of-means) formula
    rather than passing vacuously because they happen to coincide."""
    dates = _tick_dates(FIXTURE)
    idxs = _bucket_indices(dates, WIN_FROM, WIN_TO)
    weighted_avg = sum(FIXTURE["handle_time"][i] for i in idxs) / sum(
        FIXTURE["handle_time_count"][i] for i in idxs
    )
    per_day_avgs = [
        FIXTURE["handle_time"][i] / FIXTURE["handle_time_count"][i]
        for i in idxs
        if FIXTURE["handle_time_count"][i]
    ]
    mean_of_means = sum(per_day_avgs) / len(per_day_avgs)
    assert weighted_avg != pytest.approx(mean_of_means, rel=1e-6)


def test_date_range_fully_inside_window_slices_exactly():
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=date(2026, 7, 15),
        date_to=date(2026, 7, 18),
        granularity="day",
        group_by="none",
    )
    table = run_report(spec, FIXTURE)
    dates = _tick_dates(FIXTURE)
    idxs = _bucket_indices(dates, date(2026, 7, 15), date(2026, 7, 18))

    assert table.warnings == []
    assert len(idxs) == 4
    assert len(table.rows) == 4
    assert [row["period"] for row in table.rows] == [
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
        "2026-07-18",
    ]
    for row, i in zip(table.rows, idxs):
        assert row["resolved"] == pytest.approx(FIXTURE["resolved"][i])


def test_agent_ids_filter_matches_fixture_exactly():
    top3 = _top_agents(n=3)
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="total",
        group_by="agent",
        agent_ids=[a["id"] for a in top3],
    )
    table = run_report(spec, FIXTURE)
    assert len(table.rows) == 3
    by_name = {r["group"]: r for r in table.rows}
    for a in top3:
        assert by_name[a["name"]]["resolved"] == pytest.approx(sum(a["resolved"]))


def test_mailbox_ids_filter_matches_fixture_exactly():
    top3 = _top_mailboxes(n=3)
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="total",
        group_by="mailbox",
        mailbox_ids=[m["id"] for m in top3],
    )
    table = run_report(spec, FIXTURE)
    assert len(table.rows) == 3
    by_name = {r["group"]: r for r in table.rows}
    for m in top3:
        assert by_name[m["name"]]["resolved"] == pytest.approx(sum(m["resolved"]))


def test_columns_order_permutations_reorder_only_never_change_values():
    top2 = _top_agents(n=2)
    base = ReportSpec(
        metrics=[Metric.RESOLVED, Metric.HANDLE_TIME],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="total",
        group_by="agent",
        agent_ids=[a["id"] for a in top2],
    )
    baseline_table = run_report(base, FIXTURE)
    baseline_by_group = {r["group"]: r for r in baseline_table.rows}
    available = sorted(base.available_columns())

    for perm in itertools.permutations(available):
        spec = SpecPatch(columns_order=list(perm)).apply(base)
        table = run_report(spec, FIXTURE)
        assert table.columns == list(perm)
        assert {r["group"]: r for r in table.rows} == baseline_by_group


def test_columns_order_unknown_column_is_validation_error():
    with pytest.raises(Exception):
        ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from=WIN_FROM,
            date_to=WIN_TO,
            group_by="none",
            columns_order=["not_a_real_column"],
        )


def test_pivot_round_trips_every_value_from_long():
    top3 = _top_agents(n=3)
    common = dict(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="week",
        group_by="agent",
        agent_ids=[a["id"] for a in top3],
    )
    long_spec = ReportSpec(layout="long", **common)
    pivot_spec = ReportSpec(layout="pivot", **common)

    long_table = run_report(long_spec, FIXTURE)
    pivot_table = run_report(pivot_spec, FIXTURE)

    pivot_by_period = {row["period"]: row for row in pivot_table.rows}
    assert set(pivot_by_period) == {row["period"] for row in long_table.rows}

    for row in long_table.rows:
        prow = pivot_by_period[row["period"]]
        col = f"{row['group']}::resolved"
        assert col in prow
        assert prow[col] == pytest.approx(row["resolved"])

    long_sum = sum(row["resolved"] for row in long_table.rows)
    pivot_sum = sum(
        v for row in pivot_table.rows for k, v in row.items() if k != "period" and v is not None
    )
    assert long_sum == pytest.approx(pivot_sum)


def test_pivot_requires_group_and_period_axis():
    with pytest.raises(ValueError):
        run_report(
            ReportSpec(
                metrics=[Metric.RESOLVED],
                date_from=WIN_FROM,
                date_to=WIN_TO,
                granularity="total",  # no period axis
                group_by="agent",
                layout="pivot",
            ),
            FIXTURE,
        )
    with pytest.raises(ValueError):
        run_report(
            ReportSpec(
                metrics=[Metric.RESOLVED],
                date_from=WIN_FROM,
                date_to=WIN_TO,
                granularity="week",
                group_by="none",  # no group axis
                layout="pivot",
            ),
            FIXTURE,
        )


def test_sort_correctness_and_tie_stability_on_real_data():
    spec = ReportSpec(
        metrics=[Metric.RESOLVED],
        date_from=WIN_FROM,
        date_to=WIN_TO,
        granularity="total",
        group_by="mailbox",
        sort=SortSpec(field="resolved", direction="desc"),
    )
    table = run_report(spec, FIXTURE)
    values = [row["resolved"] for row in table.rows]
    assert values == sorted(values, reverse=True)
    # confirm there really are ties in this dataset, so the test is meaningful
    assert len(values) != len(set(values))

    spec_asc = ReportSpec.model_validate(
        {**spec.model_dump(mode="json"), "sort": {"field": "resolved", "direction": "asc"}}
    )
    table_asc = run_report(spec_asc, FIXTURE)
    values_asc = [row["resolved"] for row in table_asc.rows]
    assert values_asc == sorted(values_asc)


def test_sort_field_must_be_an_included_metric():
    with pytest.raises(Exception):
        ReportSpec(
            metrics=[Metric.RESOLVED],
            date_from=WIN_FROM,
            date_to=WIN_TO,
            group_by="none",
            sort=SortSpec(field="handle_time", direction="desc"),
        )


def test_spec_json_roundtrip_is_identical():
    spec = base_spec()
    roundtripped = ReportSpec.model_validate_json(spec.model_dump_json())
    assert roundtripped == spec


REPRESENTATIVE_PATCHES = [
    {"columns_order": ["group", "resolved"]},
    {"group_by": "agent", "sort": {"field": "resolved", "direction": "desc"}},
    {"group_by": "mailbox", "mailbox_ids": [RETURNS_MAILBOX["id"]], "metrics": ["new_tickets"]},
    {"date_from": "2026-07-17", "date_to": "2026-07-23"},
    {"granularity": "week"},
    {"layout": "long"},
]


@pytest.mark.parametrize("patch_dict", REPRESENTATIVE_PATCHES)
def test_agent_can_never_brick_the_report(patch_dict):
    """Every SpecPatch shape the scripted scenarios above actually produce
    must yield a spec the engine can execute without raising -- the agent
    should never be able to leave the UI stuck on a broken report."""
    current = base_spec(group_by="agent", granularity="total", columns_order=[])
    patched = SpecPatch.model_validate(patch_dict).apply(current)
    table = run_report(patched, FIXTURE)  # must not raise
    assert table is not None


# ===========================================================================
# Part 3: live tests (skipped by default; run with `-m live`)
# ===========================================================================


@pytest.mark.live
def test_live_fixture_still_representative_of_real_api():
    """Sanity-check that the frozen fixture still looks like what the live
    API returns today (same window shape, same mailbox/actor counts). Not
    run by default -- the whole point of the fixture is to avoid a live call
    on every test run -- but useful to re-run occasionally to catch drift."""
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from probe_common import base_body, call  # type: ignore

    body = base_body()
    body.pop("scope", None)
    _resp, result = call(body, label="live-check")
    live = result["response_json"]

    assert len(live["ticks"]) == len(FIXTURE["ticks"])
    assert len(live["mailbox"]) >= 100
    assert len(live["actors"]) >= 100


@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set; skipping real-model call (this path is otherwise untested)",
)
def test_real_qwen_model_can_call_update_spec():
    """One live sanity check: does a real OpenRouter qwen model actually emit
    a valid update_spec tool call for a simple request?"""
    import openai

    from tools import TOOLS

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    spec = base_spec(group_by="none", columns_order=[])
    response = client.chat.completions.create(
        model="qwen/qwen-2.5-72b-instruct",
        messages=[
            {"role": "system", "content": render_system_prompt(spec, (WIN_FROM, WIN_TO))},
            {"role": "user", "content": "group the report by agent and sort by resolved descending"},
        ],
        tools=TOOLS,
    )
    message = response.choices[0].message
    assert message.tool_calls, "expected the model to call a tool, got plain text instead"
    call_ = message.tool_calls[0]
    assert call_.function.name in {"update_spec", "get_spec", "run_report"}
    if call_.function.name == "update_spec":
        args = json.loads(call_.function.arguments)
        patch = SpecPatch.model_validate(args)
        result = patch.apply(spec)
        assert result.group_by == "agent"
