"""
The agent loop under test: messages in -> (fake) LLM -> execute tool calls
-> emit events -> until a final assistant message (or max-iterations).

This is intentionally decoupled from any real OpenAI/OpenRouter SDK object
shapes — `fake_llm.FakeLLM` stands in for "call the model", and this module
only depends on the small `FakeMessage`/`FakeToolCall` shapes so swapping in
a real client later is a matter of adapting its response into the same
shape (or vice versa).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pydantic

from engine import compact_summary, run_report as engine_run_report
from events import (
    AssistantSays,
    Error,
    InternalEvent,
    SpecUpdated,
    ToolCallFinished,
    ToolCallStarted,
    Warning as WarningEvent,
    to_ui_event,
)
from fake_llm import FakeLLM
from models import ReportSpec, SpecPatch

MAX_ITERATIONS = 6


@dataclass
class LoopResult:
    final_spec: ReportSpec
    assistant_text: str | None
    events: list[InternalEvent] = field(default_factory=list)
    ui_events: list = field(default_factory=list)
    iterations_used: int = 0
    hit_max_iterations: bool = False


class MaxIterationsExceeded(RuntimeError):
    pass


def run_agent_turn(
    spec: ReportSpec,
    user_message: str,
    llm: FakeLLM,
    fixture: dict | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> LoopResult:
    current_spec = spec
    events: list[InternalEvent] = []
    ui_events = []

    def emit(ev: InternalEvent) -> None:
        events.append(ev)
        ui = to_ui_event(ev)
        if ui is not None:
            ui_events.append(ui)

    messages: list[dict] = [{"role": "user", "content": user_message}]

    for iteration in range(1, max_iterations + 1):
        response = llm.chat(messages)

        if not response.tool_calls:
            text = response.content or ""
            emit(AssistantSays(text))
            return LoopResult(
                final_spec=current_spec,
                assistant_text=text,
                events=events,
                ui_events=ui_events,
                iterations_used=iteration,
            )

        messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in response.tool_calls
                ],
            }
        )

        for tc in response.tool_calls:
            emit(ToolCallStarted(call_id=tc.id, tool_name=tc.name, raw_args={"raw": tc.arguments}))

            try:
                args = json.loads(tc.arguments) if tc.arguments.strip() else {}
            except json.JSONDecodeError as e:
                err_msg = f"Invalid JSON in tool call arguments: {e}"
                emit(Error(err_msg, retriable=True))
                emit(ToolCallFinished(call_id=tc.id, tool_name=tc.name, ok=False, error=err_msg))
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": f"ERROR: {err_msg}"}
                )
                continue

            try:
                result_content, spec_after = _execute_tool(tc.name, args, current_spec, fixture)
            except (pydantic.ValidationError, ValueError) as e:
                err_msg = f"Validation error: {e}"
                emit(Error(err_msg, retriable=True))
                emit(ToolCallFinished(call_id=tc.id, tool_name=tc.name, ok=False, error=err_msg))
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": f"ERROR: {err_msg}"}
                )
                continue
            except KeyError:
                err_msg = f"Unknown tool: {tc.name}"
                emit(Error(err_msg, retriable=False))
                emit(ToolCallFinished(call_id=tc.id, tool_name=tc.name, ok=False, error=err_msg))
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": f"ERROR: {err_msg}"}
                )
                continue

            if spec_after is not None and spec_after != current_spec:
                emit(SpecUpdated(old_spec=current_spec, new_spec=spec_after))
                current_spec = spec_after

            for w in result_content.get("warnings", []):
                emit(WarningEvent(w))

            emit(
                ToolCallFinished(
                    call_id=tc.id, tool_name=tc.name, ok=True, raw_result=result_content
                )
            )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result_content["text"]}
            )

    raise MaxIterationsExceeded(
        f"Agent loop did not reach a final assistant message within {max_iterations} iterations"
    )


def _execute_tool(
    name: str, args: dict, current_spec: ReportSpec, fixture: dict | None
) -> tuple[dict, ReportSpec | None]:
    """Returns (result_dict_with_text_and_warnings, new_spec_or_None)."""
    if name == "get_spec":
        return {"text": current_spec.model_dump_json(), "warnings": []}, None

    if name == "update_spec":
        patch = SpecPatch.model_validate(args)  # raises pydantic.ValidationError on bad enum etc
        new_spec = patch.apply(current_spec)  # raises ValueError on cross-field failure (dates)
        return {"text": new_spec.model_dump_json(), "warnings": []}, new_spec

    if name == "run_report":
        table = engine_run_report(current_spec, fixture)
        return {"text": compact_summary(table), "warnings": table.warnings}, None

    raise KeyError(name)
