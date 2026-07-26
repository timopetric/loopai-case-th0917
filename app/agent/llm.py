"""The real model loop (issue 17): OpenAI-compatible provider (OpenRouter),
bounded by a Tool Step budget.

**One Tool Step is one model call**, regardless of how many tool calls that
call's response carries (architecture.md §5's "Budget"; a batch of parallel
tool calls — verified live, up to three at once — is still one step). The
loop is a plain `async for` over provider stream chunks; `app/agent/tools.py`
does the actual spec editing (pure, already tested), this module only wires
the provider, the prompt, and the step count together and turns what comes
back into the same `RawEvent` shapes `app/agent/fake_model.py` emits, so
`app/agent/presenter.py` (via `present_async`) doesn't know or care which
one produced them.

**The hard rule (AGENTS.md, architecture.md §5 guard 1): no code path here
may ever parse assistant prose as tool calls.** The only place a `ToolCall`
is ever constructed is `_ordered_tool_calls`, and it reads exclusively from
the provider's structured `delta.tool_calls` field — never from
`delta.content` / the accumulated prose. Denied real tools on the final
step, this exact model was verified to answer with a fenced JSON blob
impersonating a tool call, using a schema that does not exist
(`edit_report_spec`, `resolved_tickets`); nothing in this module ever
inspects `content` for anything JSON-shaped, so there is no code path left
that *could* act on it even if a future edit added a bug that tried — the
only structural knob that would need to change is a new caller reading
`content` (see `tests/test_agent_llm.py`'s
`TestProseIsNeverParsedAsToolCalls`, which proves this by handing the loop
a response with well-formed, plausible tool-call JSON in prose and no
structured `tool_calls`, and asserting nothing dispatches).

**Never logged**: the OpenRouter key (never touches a log call in this
module — it only ever goes into the `AsyncOpenAI` client constructor) or any
full prompt (`_log_step` below logs the step index, tool names dispatched,
and elapsed ms — never `messages`, never `content`).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol

import jinja2
from loguru import logger
from openai import AsyncOpenAI

from app.agent.events import (
    ContentDelta,
    RawEvent,
    ReasoningDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnDone,
    TurnError,
)
from app.agent.tools import ToolCall, ToolOutcome, apply_batch, build_tool_definitions
from app.config import Settings
from app.models import ReportSpec
from app.upstream import METRIC_CATALOGUE, Dataset

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_PROMPTS_DIR),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


class ChatCompletionsClient(Protocol):
    """The one method this module calls on the provider client — narrow on
    purpose so a test double only has to implement this, not the whole
    `AsyncOpenAI` surface (see `tests/test_agent_llm.py`'s `FakeClient`)."""

    async def create(self, **kwargs: Any) -> Any: ...


def _render(template_name: str, **context: Any) -> str:
    return _JINJA_ENV.get_template(template_name).render(**context)


def _system_prompt(spec: ReportSpec, dataset: Dataset) -> str:
    return _render(
        "report_agent_system.jinja",
        coverage=dataset.coverage,
        metrics=METRIC_CATALOGUE,
        spec_json=json.dumps(spec.model_dump(mode="json"), indent=2),
    )


_BUDGET_PENULTIMATE_TEXT = _render("budget_penultimate.jinja").strip()
_BUDGET_FINAL_TEXT = _render("budget_final.jinja").strip()


def _safe_json_object(raw: str) -> dict:
    """Tool call arguments, parsed defensively — a malformed or empty
    argument string becomes `{}` (the tool's own pydantic schema then
    reports a validation error, same as any other bad input) rather than
    raising out of the loop."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_result_payload(outcome: ToolOutcome) -> dict:
    """What goes back to the model as the `tool` role message content — the
    same information `ToolOutcome` already carries, JSON-shaped. Internal
    only (never reaches the browser; the presenter never sees this)."""
    if not outcome.ok:
        return {"ok": False, "error_category": outcome.error_category}
    payload: dict[str, Any] = {"ok": True}
    if outcome.adjusted:
        payload["adjusted"] = [repair.model_dump(mode="json") for repair in outcome.adjusted]
    if outcome.result is not None:
        payload["result"] = outcome.result
    return payload


class _StepResult:
    """What one streamed model call produced, decoded into plain data — the
    boundary between "talk to the provider" and "decide what to do next"."""

    __slots__ = ("content", "tool_calls")

    def __init__(self, content: str, tool_calls: list[dict]) -> None:
        self.content = content
        self.tool_calls = tool_calls


async def _run_step(
    client: ChatCompletionsClient,
    *,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    temperature: float,
    emit: list[RawEvent],
) -> _StepResult:
    """One Tool Step: one streamed model call. Appends `RawEvent`s to `emit`
    as chunks arrive (reasoning -> `ReasoningDelta`, prose -> `ContentDelta`)
    and returns the accumulated prose plus the **structured** tool calls —
    `delta.tool_calls`, never `content` — for the caller to act on.
    `tools=None` (the final step) is passed straight through to the
    provider: the parameter is omitted from the request entirely, not sent
    as an empty list or with `tool_choice="none"` (architecture.md §5 guard
    1 — the latter was verified to make this model emit fabricated
    tool-call JSON as prose instead)."""
    stream = await client.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto" if tools else None,
        temperature=temperature,
        stream=True,
    )

    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict] = {}

    async for chunk in stream:
        choices = getattr(chunk, "choices", None)
        if not choices:
            continue
        delta = choices[0].delta

        reasoning = getattr(delta, "reasoning", None)
        if reasoning:
            emit.append(ReasoningDelta(text=reasoning))

        content = getattr(delta, "content", None)
        if content:
            emit.append(ContentDelta(text=content))
            content_parts.append(content)

        for tc in getattr(delta, "tool_calls", None) or []:
            idx = getattr(tc, "index", 0)
            acc = tool_calls_acc.setdefault(idx, {"id": None, "name": None, "arguments": ""})
            if getattr(tc, "id", None):
                acc["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    acc["name"] = fn.name
                if getattr(fn, "arguments", None):
                    acc["arguments"] += fn.arguments

    ordered_tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
    return _StepResult(content="".join(content_parts), tool_calls=ordered_tool_calls)


def _log_step(step: int, *, tool_names: list[str], elapsed_ms: float, final: bool) -> None:
    """architecture.md §4: log Tool Steps with tool names and durations —
    never the messages/prompt that produced them, never the API key (this
    function doesn't even receive either)."""
    logger.info(
        "assistant Tool Step {step} ({kind}): tools={tools} elapsed_ms={ms:.0f}",
        step=step,
        kind="final/prose-only" if final else "normal",
        tools=tool_names or "none",
        ms=elapsed_ms,
    )


async def run_llm_turn(
    message: str,
    spec: ReportSpec,
    dataset: Dataset,
    settings: Settings,
    *,
    client: ChatCompletionsClient | None = None,
) -> AsyncIterator[RawEvent]:
    """Run one Assistant turn against the live model, bounded by
    `settings.agent_max_iterations` Tool Steps.

    `client` is an injection seam (`ChatCompletionsClient` above) — tests
    drive this with a scripted fake instead of `AsyncOpenAI` so the budget,
    the tool-omission guard and the prose-vs-tool-call rule are all provable
    offline (issue 17's Level 1 requirement). Real callers get a live
    `AsyncOpenAI(...).chat.completions` pointed at OpenRouter.
    """
    active_client: ChatCompletionsClient = client or AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    ).chat.completions

    max_steps = max(1, settings.agent_max_iterations)
    tool_defs = build_tool_definitions()

    messages: list[dict] = [
        {"role": "system", "content": _system_prompt(spec, dataset)},
        {"role": "user", "content": message},
    ]

    current_spec = spec

    for step in range(1, max_steps + 1):
        is_final = step == max_steps
        is_penultimate = (not is_final) and step == max_steps - 1

        if is_penultimate:
            messages.append({"role": "system", "content": _BUDGET_PENULTIMATE_TEXT})
        if is_final:
            messages.append({"role": "system", "content": _BUDGET_FINAL_TEXT})

        step_tools = None if is_final else tool_defs
        emitted: list[RawEvent] = []
        started = time.monotonic()
        result = await _run_step(
            active_client,
            model=settings.llm_model,
            messages=messages,
            tools=step_tools,
            temperature=settings.llm_temperature,
            emit=emitted,
        )
        elapsed_ms = (time.monotonic() - started) * 1000

        for event in emitted:
            yield event

        if is_final or not result.tool_calls:
            _log_step(step, tool_names=[], elapsed_ms=elapsed_ms, final=is_final)
            if is_final:
                # The budget ran out — architecture.md §5/PRD "Budget": name
                # the real constraint plainly and invite another message.
                # `presenter.py`'s fixed `_ERROR_TEXT["budget"]` carries that
                # copy; the model's own forced prose (already streamed as
                # `ContentDelta`s above) is "where it got to".
                yield TurnError(category="budget", detail=f"exhausted {max_steps} Tool Steps")
            else:
                # Natural completion: the model chose to answer in prose
                # instead of calling another tool, before the budget ran out.
                yield TurnDone(summary=result.content)
            return

        # Structured tool_calls present (never `result.content`) — dispatch.
        tool_names = [tc["name"] for tc in result.tool_calls]
        _log_step(step, tool_names=tool_names, elapsed_ms=elapsed_ms, final=False)

        messages.append(
            {
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in result.tool_calls
                ],
            }
        )

        calls = [
            ToolCall(name=tc["name"], args=_safe_json_object(tc["arguments"]))
            for tc in result.tool_calls
        ]
        outcomes = apply_batch(current_spec, dataset, calls)

        for tc, call, outcome in zip(result.tool_calls, calls, outcomes, strict=True):
            yield ToolCallStarted(name=call.name, args=call.args)
            yield ToolCallFinished(
                name=outcome.name,
                args=outcome.args,
                ok=outcome.ok,
                adjusted=outcome.adjusted,
                spec_before=outcome.spec_before,
                spec_after=outcome.spec_after,
            )
            if outcome.ok and outcome.spec_after is not None:
                current_spec = outcome.spec_after
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(_tool_result_payload(outcome)),
                }
            )
