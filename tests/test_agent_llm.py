"""`app/agent/llm.py` — the live model loop and its Tool Step budget (issue
17).

Offline throughout: `run_llm_turn`'s `client` parameter is an injection seam
(`ChatCompletionsClient`), so every test here drives it with `FakeClient`
below — a scripted stand-in for `AsyncOpenAI(...).chat.completions` — never
the network. This is what Step 5 of the issue calls "drive the budget with
the fake model."

`FakeClient.calls` records the exact keyword arguments sent to `.create()`
on every step, which is what makes `TestFinalStepOmitsToolsEntirely` an
assertion about *what was sent to the provider*, not just what came back.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent.events import (
    ContentDelta,
    RawEvent,
    ToolCallFinished,
    ToolCallStarted,
    TurnDone,
    TurnError,
)
from app.agent.llm import run_llm_turn
from app.agent.presenter import present
from app.agent.tools import TOOL_NAMES
from app.config import Settings
from app.models import Metric, ReportSpec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


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


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        environment="local",
        openrouter_api_key="test-key-not-real",
        **overrides,
    )


# ── Chunk builders — mirror the real streamed-chunk shape (scratch/fresh-eyes
# /llm-smoke-results.json: `delta.reasoning`, `delta.content`,
# `delta.tool_calls[i].{index,id,function.name,function.arguments}`) ────────


def _chunk(*, content: str | None = None, reasoning: str | None = None, tool_calls=None):
    delta = SimpleNamespace(content=content, reasoning=reasoning, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)])


def _tool_call_chunk(*, index: int, call_id: str, name: str, arguments: str):
    fn = SimpleNamespace(name=name, arguments=arguments)
    tc = SimpleNamespace(index=index, id=call_id, function=fn)
    return _chunk(tool_calls=[tc])


def _prose_chunks(text: str) -> list:
    return [_chunk(content=text)]


class _FakeStream:
    def __init__(self, chunks: list) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator:
        return self._agen()

    async def _agen(self):
        for chunk in self._chunks:
            yield chunk


class FakeClient:
    """Scripted `ChatCompletionsClient`: `scripts[i]` is the chunk list
    returned on the i-th call to `.create()`; the last script repeats if the
    loop calls more times than scripted (defensive against a test typo, not
    load-bearing for any assertion)."""

    def __init__(self, scripts: list[list]) -> None:
        self._scripts = scripts
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any):
        # `messages` is mutated in place by the loop after this call
        # returns (the assistant/tool-result turns get appended for the
        # next step) — snapshot it so `calls[i]["messages"]` reflects what
        # was actually SENT on call i, not the final accumulated state.
        snapshot = {**kwargs, "messages": [dict(m) for m in kwargs["messages"]]}
        self.calls.append(snapshot)
        idx = min(len(self.calls) - 1, len(self._scripts) - 1)
        return _FakeStream(self._scripts[idx])


def _set_metrics_call(call_id: str = "call_1") -> Any:
    args = json.dumps({"metrics": ["resolved", "handle_time"]})
    return _tool_call_chunk(index=0, call_id=call_id, name="set_metrics", arguments=args)


async def _run(
    client: FakeClient, *, message: str, spec: ReportSpec, dataset, settings: Settings
) -> list[RawEvent]:
    return [event async for event in run_llm_turn(message, spec, dataset, settings, client=client)]


class TestLoopStopsAfterConfiguredToolSteps:
    async def test_stops_calling_the_model_at_the_configured_step_count(self, dataset):
        settings = _settings(agent_max_iterations=3)
        # Steps 1 and 2 (not final): keep calling a tool forever if allowed.
        # Step 3 (final, tools omitted): a prose-only response.
        client = FakeClient(
            scripts=[
                [_set_metrics_call(call_id="call_1")],
                [_set_metrics_call(call_id="call_2")],
                _prose_chunks("Grouped by nothing and added handle_time."),
            ]
        )
        events = await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        assert len(client.calls) == 3

        tool_finished = [e for e in events if isinstance(e, ToolCallFinished)]
        assert len(tool_finished) == 2  # steps 1 and 2 each dispatched one tool call

        # The turn ends via the budget path, not a natural TurnDone.
        assert isinstance(events[-1], TurnError)
        assert events[-1].category == "budget"
        assert not any(isinstance(e, TurnDone) for e in events)

    @pytest.mark.parametrize("configured_steps", [1, 2, 4])
    async def test_step_limit_is_read_from_configuration(self, dataset, configured_steps):
        settings = _settings(agent_max_iterations=configured_steps)
        # Every non-final step keeps calling a tool; the final step (tools
        # omitted) can never emit a tool call regardless of the script, so
        # scripting a tool call for every slot and a prose fallback covers
        # both cases without needing to special-case the last index.
        scripts = [[_set_metrics_call(call_id=f"call_{i}")] for i in range(configured_steps - 1)]
        scripts.append(_prose_chunks("Done."))
        client = FakeClient(scripts=scripts)

        await _run(client, message="hi", spec=base_spec(), dataset=dataset, settings=settings)

        assert len(client.calls) == configured_steps


class TestFinalStepOmitsToolsEntirely:
    async def test_final_request_sends_no_tools_parameter(self, dataset):
        settings = _settings(agent_max_iterations=2)
        client = FakeClient(
            scripts=[
                [_set_metrics_call()],
                _prose_chunks("Added handle_time to the report."),
            ]
        )
        await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        assert len(client.calls) == 2
        first_call, final_call = client.calls

        # Earlier steps DO get a tools array.
        assert first_call["tools"] is not None
        assert len(first_call["tools"]) == 9

        # The final call omits `tools` entirely — not merely `tool_choice`.
        assert final_call["tools"] is None
        assert final_call["tool_choice"] is None

    async def test_final_response_is_prose_never_json(self, dataset):
        settings = _settings(agent_max_iterations=2)
        summary_text = "I grouped by nothing and added handle_time to the metrics."
        client = FakeClient(
            scripts=[
                [_set_metrics_call()],
                _prose_chunks(summary_text),
            ]
        )
        events = await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        tokens = "".join(e.text for e in events if isinstance(e, ContentDelta))
        assert tokens == summary_text
        assert not tokens.strip().startswith("{")
        assert not tokens.strip().startswith("[")


class TestPenultimateStepWarning:
    async def test_the_model_is_told_it_has_one_step_left_before_penultimate_call(self, dataset):
        settings = _settings(agent_max_iterations=3)
        client = FakeClient(
            scripts=[
                [_set_metrics_call(call_id="call_1")],
                [_set_metrics_call(call_id="call_2")],
                _prose_chunks("Done."),
            ]
        )
        await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        assert len(client.calls) == 3
        step1_messages, step2_messages, step3_messages = (c["messages"] for c in client.calls)

        def has_warning(messages: list[dict]) -> bool:
            return any(
                m.get("role") == "system" and "Tool Step left" in (m.get("content") or "")
                for m in messages
            )

        assert not has_warning(step1_messages)
        assert has_warning(step2_messages)  # step 2 of 3 is the penultimate step


class TestOutOfBudgetMessage:
    async def test_budget_error_is_presented_with_a_recovery_message(self, dataset):
        settings = _settings(agent_max_iterations=2)
        client = FakeClient(
            scripts=[
                [_set_metrics_call()],
                _prose_chunks("I added handle_time to the metrics."),
            ]
        )
        events = await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        ui_events = list(present(events, include_reasoning_text=False))
        error_texts = [e.to_data()["text"] for e in ui_events if e.event_name == "error"]

        assert len(error_texts) == 1
        assert "used up this turn's work allowance" in error_texts[0]
        assert "send another message to continue" in error_texts[0]

        # No fabricated tool-call JSON or internal names leaked into the
        # sanitised event stream.
        for internal in ("set_metrics", "TurnError", "budget"):
            assert internal not in error_texts[0]


class TestProseIsNeverParsedAsToolCalls:
    """The hard rule (AGENTS.md, architecture.md §5 guard 1): only
    structured `tool_calls` may ever be dispatched. This feeds the loop a
    response with well-formed, plausible tool-call JSON sitting in
    `content`, with `tool_calls` empty/absent — exactly the shape the real
    model was verified to produce under a denied-tools condition — and
    proves no tool is ever dispatched from it."""

    async def test_json_shaped_prose_naming_a_real_tool_is_never_dispatched(self, dataset):
        fabricated = json.dumps(
            {
                "tool_calls": [
                    {"name": "set_metrics", "arguments": {"metrics": ["resolved", "handle_time"]}}
                ]
            }
        )
        assert "set_metrics" in TOOL_NAMES  # the fabrication names a REAL tool

        # budget never binds — the model "chooses" to stop on its own
        settings = _settings(agent_max_iterations=5)
        client = FakeClient(scripts=[_prose_chunks(fabricated)])

        events = await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        # Only one model call happened: the loop read this as a natural
        # finish (no structured tool_calls), not as a request to act.
        assert len(client.calls) == 1

        assert not any(isinstance(e, ToolCallStarted) for e in events)
        assert not any(isinstance(e, ToolCallFinished) for e in events)

        # The fabricated text was streamed verbatim as prose, unparsed.
        tokens = "".join(e.text for e in events if isinstance(e, ContentDelta))
        assert tokens == fabricated

        done = next(e for e in events if isinstance(e, TurnDone))
        assert done.summary == fabricated


class TestToolDispatchIntegratesEndToEnd:
    """One sanity check that a genuine structured tool call really is
    applied through `app/agent/tools.py` and produces the spec-changing
    events the presenter needs — the budget/omission tests above script
    tool calls too, but never inspect the resulting spec."""

    async def test_a_structured_tool_call_updates_the_spec_then_finishes_naturally(self, dataset):
        settings = _settings(agent_max_iterations=5)
        # First step: a reasoning chunk, then a structured tool call.
        # Second step: a natural prose finish (no more tool calls).
        client = FakeClient(
            scripts=[
                [_chunk(reasoning="Adding handle_time."), _set_metrics_call()],
                _prose_chunks("Added handle_time to the report."),
            ]
        )

        events = await _run(
            client, message="add handle time", spec=base_spec(), dataset=dataset, settings=settings
        )

        assert len(client.calls) == 2
        finished = next(e for e in events if isinstance(e, ToolCallFinished))
        assert finished.ok
        assert finished.spec_after.metrics == [Metric.RESOLVED, Metric.HANDLE_TIME]

        done = next(e for e in events if isinstance(e, TurnDone))
        assert done.summary == "Added handle_time to the report."
