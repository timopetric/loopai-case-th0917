"""`DEV_FAKE_LLM` — a scripted raw-event sequence (issue 15, ADR-0003).

Stands in for the real LangGraph/OpenRouter loop (issue 17) so the whole SSE
path — presenter, endpoint, frontend chat panel — is demoable and testable
without spending tokens or wiring any of the nine tools (issue 16). It
produces the exact same `RawEvent` shapes the real loop will, including the
reasoning-delta preamble each Tool Step has (architecture.md §5 guard 2), two
Tool Steps that each edit one field and emit their own `ToolCallFinished`
(so the frontend can be seen moving the controls one step at a time — the
whole point of field-scoped tools, ADR-0002), and a final prose Tool Step.

The two edits are deliberately unconditional on `message`: real intent-
parsing is the live model's job (issue 17). This only has to prove the
CHANNEL works end to end, per the issue brief ("the scripted fake drives the
report end to end for now").
"""

from __future__ import annotations

from collections.abc import Iterator

from app.agent.events import (
    ContentDelta,
    RawEvent,
    ReasoningDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnDone,
)
from app.models import Metric, ReportSpec

_PROSE = (
    "Done",
    " — grouped by agent",
    " with resolved and handle time",
    " for the selected period.",
)


def run_fake_turn(message: str, spec: ReportSpec) -> Iterator[RawEvent]:
    """Yield a fixed, two-Tool-Step conversation turn.

    Step 1 groups by Actor (a `set_grouping`-shaped tool call). Step 2 adds
    `resolved` and `handle_time` to the metric list (a `set_metrics`-shaped
    tool call) — `resolved` may already be selected, so it uses "add if
    missing" rather than duplicating (mirrors the real `set_metrics` tool's
    replace-the-whole-list contract, without needing that tool to exist
    yet). A final prose Tool Step closes the turn.
    """
    # Tool Step 1: reasoning preamble, then set_grouping.
    yield ReasoningDelta("The user wants a per-agent breakdown.")
    yield ReasoningDelta("I'll switch the grouping to agent first.")

    step1_before = spec
    step1_after = ReportSpec.model_validate({**spec.model_dump(mode="json"), "group_by": "agent"})
    yield ToolCallStarted(name="set_grouping", args={"by": "agent"})
    yield ToolCallFinished(
        name="set_grouping",
        args={"by": "agent"},
        ok=True,
        adjusted=[],
        spec_before=step1_before,
        spec_after=step1_after,
    )

    # Tool Step 2: reasoning preamble, then set_metrics.
    yield ReasoningDelta("Now I'll make sure resolved and handle_time are on the report.")

    wanted = [Metric.RESOLVED, Metric.HANDLE_TIME]
    merged_metrics = list(step1_after.metrics) + [m for m in wanted if m not in step1_after.metrics]
    step2_before = step1_after
    step2_after = ReportSpec.model_validate(
        {**step1_after.model_dump(mode="json"), "metrics": [m.value for m in merged_metrics]}
    )
    yield ToolCallStarted(name="set_metrics", args={"metrics": [m.value for m in merged_metrics]})
    yield ToolCallFinished(
        name="set_metrics",
        args={"metrics": [m.value for m in merged_metrics]},
        ok=True,
        adjusted=[],
        spec_before=step2_before,
        spec_after=step2_after,
    )

    # Final Tool Step: prose only (architecture.md §5 guard 1 — the last
    # step never offers tools, so there is nothing for the model to invent a
    # fenced-JSON tool call in place of; not applicable to a scripted fake,
    # but the shape mirrors what the real loop will do).
    yield ReasoningDelta("I'll summarise what I changed.")
    summary_parts = []
    for chunk in _PROSE:
        summary_parts.append(chunk)
        yield ContentDelta(chunk)
    yield TurnDone(summary="".join(summary_parts))
