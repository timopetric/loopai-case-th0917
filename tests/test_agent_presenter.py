"""`app/agent/presenter.py` — the security chokepoint (issue 15, AGENTS.md).

`present()` is pure: no server, no fake model, no network needed to exercise
every rule in architecture.md §6. The negative-leak test below is the load-
bearing one — see its own docstring for how it's built to survive issue 16
adding nine real tools.
"""

import pytest
from pydantic import ValidationError

from app.agent.events import (
    ChipsEvent,
    ContentDelta,
    DoneEvent,
    ErrorEvent,
    ReasoningDelta,
    Repair,
    RepairCode,
    SpecEvent,
    StatusEvent,
    ThinkingEvent,
    ThinkingTextEvent,
    TokenEvent,
    ToolCallFinished,
    ToolCallStarted,
    TurnDone,
    TurnError,
)
from app.agent.presenter import present
from app.models import Metric, ReportSpec, SortSpec

BASE_SPEC = ReportSpec(
    metrics=[Metric.RESOLVED],
    date_from="2026-07-10",
    date_to="2026-07-16",
    group_by="none",
)


def _clock(*, start: float = 0.0, step: float = 0.0):
    """A deterministic `now()` for tests that care about `ms` — each call
    advances by `step`."""
    state = {"t": start}

    def now() -> float:
        value = state["t"]
        state["t"] += step
        return value

    return now


class TestThinkingIndicator:
    def test_reasoning_delta_emits_thinking_start_once(self):
        events = list(
            present([ReasoningDelta("a"), ReasoningDelta("b"), ReasoningDelta("c")])
        )
        thinking_starts = [e for e in events if isinstance(e, ThinkingEvent) and e.state == "start"]
        assert len(thinking_starts) == 1

    def test_thinking_ends_on_first_tool_call(self):
        events = list(
            present(
                [
                    ReasoningDelta("thinking about it"),
                    ToolCallStarted(name="set_metrics", args={"metrics": ["resolved"]}),
                ]
            )
        )
        kinds = [type(e).__name__ for e in events]
        assert kinds == ["ThinkingEvent", "ThinkingEvent", "StatusEvent"]
        assert events[0].state == "start"
        assert events[1].state == "end"

    def test_thinking_ends_on_first_content_delta_when_no_tool_call(self):
        events = list(present([ReasoningDelta("hmm"), ContentDelta("Here's")]))
        kinds = [type(e).__name__ for e in events]
        assert kinds == ["ThinkingEvent", "ThinkingEvent", "TokenEvent"]
        assert events[1].state == "end"

    def test_thinking_end_carries_elapsed_ms(self):
        now = _clock(start=0.0, step=0.25)  # 250ms between each now() call
        events = list(
            present(
                [ReasoningDelta("x"), ToolCallStarted(name="set_metrics", args={})],
                now=now,
            )
        )
        end_event = events[1]
        assert isinstance(end_event, ThinkingEvent)
        assert end_event.state == "end"
        assert end_event.ms == 250

    def test_thinking_fires_once_per_tool_step_in_a_multi_step_turn(self):
        spec2 = BASE_SPEC.model_copy(update={"group_by": "agent"})
        events = list(
            present(
                [
                    ReasoningDelta("step one"),
                    ToolCallStarted(name="set_grouping", args={"by": "agent"}),
                    ToolCallFinished(
                        name="set_grouping",
                        args={"by": "agent"},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    ),
                    ReasoningDelta("step two"),
                    ContentDelta("Done."),
                ]
            )
        )
        starts = [e for e in events if isinstance(e, ThinkingEvent) and e.state == "start"]
        ends = [e for e in events if isinstance(e, ThinkingEvent) and e.state == "end"]
        assert len(starts) == 2
        assert len(ends) == 2


class TestToolCallTranslation:
    def test_tool_call_started_emits_a_fixed_status_phrase(self):
        raw = [ToolCallStarted(name="set_metrics", args={"metrics": ["resolved"]})]
        events = list(present(raw))
        assert len(events) == 1
        assert isinstance(events[0], StatusEvent)
        assert events[0].text == "Updating the metrics…"

    def test_unrecognised_tool_name_falls_back_to_a_generic_status_phrase(self):
        events = list(present([ToolCallStarted(name="totally_unknown_tool", args={})]))
        assert events[0].text == "Updating the report…"

    def test_successful_tool_call_emits_chips_then_spec(self):
        spec2 = BASE_SPEC.model_copy(update={"group_by": "agent"})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_grouping",
                        args={"by": "agent"},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        assert [type(e).__name__ for e in events] == ["ChipsEvent", "SpecEvent"]
        # "Actor", not the wire value "agent" — CONTEXT.md bans unqualified
        # "agent" in UI copy.
        assert "Grouping: by Actor" in events[0].chips
        assert events[1].spec == spec2

    def test_failed_tool_call_emits_a_sanitised_error_not_the_args(self):
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_date_range",
                        args={"from": "not-a-date"},
                        ok=False,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=None,
                    )
                ]
            )
        )
        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert "not-a-date" not in events[0].text

    def test_repair_adjustment_surfaces_as_a_chip(self):
        spec2 = BASE_SPEC.model_copy(update={"metrics": [Metric.HANDLE_TIME]})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_metrics",
                        args={"metrics": ["handle_time"]},
                        ok=True,
                        adjusted=[Repair(code=RepairCode.CHART_METRIC_RESET)],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Adjusted: chart metric reset to the first selected metric" in chips_event.chips

    def test_metric_auto_added_repair_names_the_metric_via_the_closed_enum(self):
        spec2 = BASE_SPEC.model_copy(update={"metrics": [Metric.RESOLVED, Metric.HANDLE_TIME]})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_chart",
                        args={"metric": "handle_time"},
                        ok=True,
                        adjusted=[
                            Repair(code=RepairCode.METRIC_AUTO_ADDED, metric=Metric.HANDLE_TIME)
                        ],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Adjusted: added Handle time to the report" in chips_event.chips

    def test_repair_code_is_a_closed_enum_a_free_string_cannot_be_constructed(self):
        """The type-level guarantee the coordinator's leak probe demanded:
        `Repair.code` rejects anything outside `RepairCode`'s five members
        at CONSTRUCTION time — there is no way to get a free string (a
        sentinel, a tool-argument value, model-generated prose) into this
        field for the presenter to later interpolate. Compare with the old
        `adjusted: list[str]` design, where any string was accepted and the
        presenter's discipline about not interpolating it was a convention,
        not a property."""
        with pytest.raises(ValidationError):
            Repair(code="SENTINEL_NOT_A_REAL_REPAIR_CODE")

    def test_repair_metric_is_a_closed_enum_too(self):
        with pytest.raises(ValidationError):
            Repair(code=RepairCode.METRIC_AUTO_ADDED, metric="SENTINEL_NOT_A_REAL_METRIC")

    def test_entity_filter_set_emits_filter_chip(self):
        spec2 = BASE_SPEC.model_copy(update={"entity_filter": "smith"})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_filter",
                        args={"query": "smith"},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Filter: smith" in chips_event.chips

    def test_entity_filter_cleared_emits_filter_cleared_chip(self):
        spec_with_filter = BASE_SPEC.model_copy(update={"entity_filter": "smith"})
        spec_cleared = BASE_SPEC.model_copy(update={"entity_filter": None})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_filter",
                        args={"query": None},
                        ok=True,
                        adjusted=[],
                        spec_before=spec_with_filter,
                        spec_after=spec_cleared,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Filter cleared" in chips_event.chips

    def test_entity_filter_ignored_repair_surfaces_as_a_chip(self):
        spec2 = BASE_SPEC.model_copy(update={"entity_filter": "smith"})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_filter",
                        args={"query": "smith"},
                        ok=True,
                        adjusted=[Repair(code=RepairCode.ENTITY_FILTER_IGNORED)],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert (
            "Adjusted: entity filter has no effect without grouping by Actor or Mailbox"
            in chips_event.chips
        )

    def test_added_metric_chip_uses_label_not_wire_value(self):
        spec2 = BASE_SPEC.model_copy(update={"metrics": [Metric.RESOLVED, Metric.HANDLE_TIME]})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_metrics",
                        args={"metrics": ["resolved", "handle_time"]},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Added metric: Handle time" in chips_event.chips
        assert "Added metric: handle_time" not in chips_event.chips
        for chip in chips_event.chips:
            assert "handle_time" not in chip

    def test_chart_metric_chip_uses_label_not_wire_value(self):
        spec2 = BASE_SPEC.model_copy(update={"chart_metric": Metric.HANDLE_TIME})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_chart",
                        args={"metric": "handle_time"},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Chart: Handle time" in chips_event.chips
        for chip in chips_event.chips:
            assert "handle_time" not in chip

    def test_sort_chip_uses_metric_label_and_spelled_out_direction(self):
        spec_with_metric = BASE_SPEC.model_copy(
            update={"metrics": [Metric.RESOLVED, Metric.HANDLE_TIME]}
        )
        spec2 = spec_with_metric.model_copy(
            update={"sort": SortSpec(column="handle_time", direction="desc")}
        )
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_sort",
                        args={"column": "handle_time", "direction": "desc"},
                        ok=True,
                        adjusted=[],
                        spec_before=spec_with_metric,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        assert "Sort: Handle time (descending)" in chips_event.chips
        for chip in chips_event.chips:
            assert "handle_time" not in chip
            assert "desc" not in chip.replace("descending", "")

    def test_no_metric_key_leaks_when_metrics_chart_and_sort_all_change_together(self):
        """Closes the coordinator's follow-up finding: fixing only the
        metric-added/removed chips left `Chart:` and `Sort:` printing the
        same wire enum shape a few lines below. A single turn that touches
        all three at once is the regression that would have caught it."""
        spec2 = BASE_SPEC.model_copy(
            update={
                "metrics": [Metric.RESOLVED, Metric.HANDLE_TIME],
                "chart_metric": Metric.HANDLE_TIME,
                "sort": SortSpec(column="handle_time", direction="asc"),
            }
        )
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_metrics",
                        args={"metrics": ["resolved", "handle_time"]},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    )
                ]
            )
        )
        chips_event = events[0]
        assert isinstance(chips_event, ChipsEvent)
        for chip in chips_event.chips:
            assert "handle_time" not in chip, f"raw metric key leaked into chip: {chip!r}"


class TestProseAndCompletion:
    def test_content_delta_becomes_token_event(self):
        events = list(present([ContentDelta("Hello")]))
        assert events == [TokenEvent(text="Hello")]

    def test_turn_done_reports_spec_version_as_count_of_spec_events_this_turn(self):
        spec2 = BASE_SPEC.model_copy(update={"group_by": "agent"})
        spec3 = spec2.model_copy(update={"granularity": "total"})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_grouping",
                        args={},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec2,
                    ),
                    ToolCallFinished(
                        name="set_layout",
                        args={},
                        ok=True,
                        adjusted=[],
                        spec_before=spec2,
                        spec_after=spec3,
                    ),
                    TurnDone(summary="Done — grouped by agent, whole period."),
                ]
            )
        )
        done = events[-1]
        assert isinstance(done, DoneEvent)
        assert done.spec_version == 2
        assert done.summary == "Done — grouped by agent, whole period."

    def test_turn_error_maps_category_to_a_fixed_message(self):
        events = list(present([TurnError(category="coverage", detail="internal stack trace")]))
        assert events == [
            ErrorEvent(text="That date range has no data in the Coverage Window.")
        ]


class TestDevOnlyReasoningPanel:
    def test_reasoning_text_absent_by_default(self):
        events = list(present([ReasoningDelta("the secret sauce")]))
        assert all(not isinstance(e, ThinkingTextEvent) for e in events)

    def test_reasoning_text_included_only_when_flag_set(self):
        events = list(
            present([ReasoningDelta("raw reasoning here")], include_reasoning_text=True)
        )
        text_events = [e for e in events if isinstance(e, ThinkingTextEvent)]
        assert len(text_events) == 1
        assert text_events[0].text == "raw reasoning here"


class TestNegativeLeakAssertion:
    """The hard-to-defeat test the issue requires.

    Rather than grepping the output for today's known tool names, every
    internal position (tool name, every argument key AND value, reasoning
    text, and — per the coordinator's review — the Repair `adjusted` field
    too) is seeded with its own distinctive sentinel string. Those sentinels
    are then asserted absent from the serialised form of EVERY emitted
    event — not just the ones we expect to carry them. A presenter change
    that starts leaking through a field nobody thought to check (e.g. a
    future `StatusEvent` built by string-formatting the tool name in) fails
    this test even though the sentinel names don't exist yet when issue 16
    adds real tools.

    `adjusted` is the one position where "seed it with a sentinel string" is
    no longer even expressible: `Repair.code`/`Repair.metric` are closed
    enums enforced at pydantic construction (see
    `test_repair_code_is_a_closed_enum_a_free_string_cannot_be_constructed`
    above), so attempting to build a poisoned `Repair` is asserted to raise
    right here, inline with the rest of the sweep, rather than the leak
    guarantee resting on a separate test someone could delete.
    """

    def test_no_internal_value_leaks_into_any_emitted_event(self):
        sentinel_tool_name = "SENTINEL_TOOL_NAME_9f3c2a"
        sentinel_arg_key = "SENTINEL_ARG_KEY_7b1e44"
        sentinel_arg_value = "SENTINEL_ARG_VALUE_d05b6c"
        sentinel_reasoning = "SENTINEL_REASONING_TEXT_e281af naming set_metrics and get_meta"
        sentinel_error_detail = "SENTINEL_ERROR_DETAIL_119ac0 Traceback (most recent call last)"
        sentinel_repair_code = "SENTINEL_REPAIR_CODE_c4a710"

        # `adjusted` can no longer carry a sentinel string at all — proven
        # here, inline, as part of the same sweep (see class docstring).
        with pytest.raises(ValidationError):
            Repair(code=sentinel_repair_code)

        raw_events = [
            ReasoningDelta(sentinel_reasoning),
            ToolCallStarted(name=sentinel_tool_name, args={sentinel_arg_key: sentinel_arg_value}),
            ToolCallFinished(
                name=sentinel_tool_name,
                args={sentinel_arg_key: sentinel_arg_value},
                ok=False,
                adjusted=[],
                spec_before=BASE_SPEC,
                spec_after=None,
            ),
            ReasoningDelta(sentinel_reasoning),
            ToolCallFinished(
                name=sentinel_tool_name,
                args={sentinel_arg_key: sentinel_arg_value},
                ok=True,
                # The only `adjusted` content that can exist post-fix: a real
                # `Repair` built from the closed `RepairCode` enum.
                adjusted=[Repair(code=RepairCode.SORT_CLEARED)],
                spec_before=BASE_SPEC,
                spec_after=BASE_SPEC.model_copy(update={"group_by": "agent"}),
            ),
            ContentDelta("ordinary prose is fine"),
            TurnError(category="internal", detail=sentinel_error_detail),
            TurnDone(summary="ordinary summary is fine"),
        ]

        sentinels = [
            sentinel_tool_name,
            sentinel_arg_key,
            sentinel_arg_value,
            sentinel_reasoning,
            sentinel_error_detail,
            sentinel_repair_code,
        ]

        # Presenter called WITHOUT the dev flag — the default, production
        # path — is the one that must never leak any of the above.
        events = list(present(raw_events, include_reasoning_text=False))
        serialised = "\n".join(f"{e.event_name}:{e.to_data()!r}" for e in events)

        for sentinel in sentinels:
            assert sentinel not in serialised, f"{sentinel!r} leaked into: {serialised!r}"

        # And no raw event type itself is smuggled into the output either.
        assert not any(isinstance(e, ThinkingTextEvent) for e in events)

    def test_group_by_never_reaches_a_chip_as_the_unqualified_wire_word(self):
        """CONTEXT.md bans unqualified "agent" in prose/UI copy — a support
        person is an Actor, the LLM is the Assistant. `ReportSpec.group_by`'s
        wire value `"agent"` is correct and unchanged (asserted present in
        the `spec` event below, which mirrors the real Report Spec verbatim
        by design), but no `chips` text may say bare "agent" — it must say
        "Actor"."""
        spec_after = BASE_SPEC.model_copy(update={"group_by": "agent"})
        events = list(
            present(
                [
                    ToolCallFinished(
                        name="set_grouping",
                        args={"by": "agent"},
                        ok=True,
                        adjusted=[],
                        spec_before=BASE_SPEC,
                        spec_after=spec_after,
                    )
                ]
            )
        )
        chips_event = next(e for e in events if isinstance(e, ChipsEvent))
        spec_event = next(e for e in events if isinstance(e, SpecEvent))

        assert spec_event.spec.group_by == "agent"  # the wire value: unchanged, correct
        assert any("Actor" in chip for chip in chips_event.chips)
        for chip in chips_event.chips:
            words = chip.replace(":", " ").split()
            assert "agent" not in words, f"unqualified 'agent' leaked into chip: {chip!r}"

    def test_dev_mode_reasoning_panel_still_never_leaks_tool_names_or_args(self):
        """Even the one channel that IS allowed to carry raw reasoning
        (`ThinkingTextEvent`, dev-only) must not leak tool names or
        arguments — only `ReasoningDelta.text` ever reaches it, and this
        confirms tool internals from OTHER events in the same stream don't
        bleed across."""
        sentinel_tool_name = "SENTINEL_TOOL_NAME_dev_9f3c2a"
        sentinel_arg_value = "SENTINEL_ARG_VALUE_dev_d05b6c"

        raw_events = [
            ToolCallStarted(name=sentinel_tool_name, args={"x": sentinel_arg_value}),
            ReasoningDelta("legitimate reasoning text, allowed in dev mode"),
        ]

        events = list(present(raw_events, include_reasoning_text=True))
        serialised = "\n".join(f"{e.event_name}:{e.to_data()!r}" for e in events)

        assert sentinel_tool_name not in serialised
        assert sentinel_arg_value not in serialised
