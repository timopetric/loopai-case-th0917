"""
Scripted fake of the OpenAI chat-completions interface.

Real backend will call OpenRouter with a qwen tool-calling model. For these
tests we never hit a network — `FakeLLM` is handed a fixed script of steps
and plays them back in order each time `chat()` is called, one step per
call, regardless of what's in `messages` (a real model would react to tool
results; the fake just advances a scripted plan — good enough to exercise
the agent loop's plumbing, not the model's reasoning).

Each step is either:
  - a list of tool calls (name + args-as-string, so we can script malformed
    JSON / bad enum values deliberately), or
  - a final assistant text message (no tool calls -> loop stops).

This also models the two malformed-output failure modes we want to test:
  - invalid JSON in a tool call's arguments string
  - valid JSON but an invalid enum value / bad patch (caught by pydantic)
Both should cause the agent loop to feed a validation error back as a
tool-result message, and the fake's *next* scripted step is the "corrected"
retry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FakeToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, deliberately not pre-parsed (can be malformed)


@dataclass
class FakeMessage:
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: list[FakeToolCall] = field(default_factory=list)


class FakeLLM:
    """Plays back a fixed script of FakeMessage steps, one per `chat()` call."""

    def __init__(self, script: list[FakeMessage]):
        self._script = script
        self._i = 0
        self.calls_seen: list[list[dict]] = []  # for assertions on what the loop sent us

    def chat(self, messages: list[dict]) -> FakeMessage:
        self.calls_seen.append(messages)
        if self._i >= len(self._script):
            raise RuntimeError(
                f"FakeLLM script exhausted after {self._i} steps; agent loop made "
                f"an extra call it shouldn't have (check max-iterations / stop condition)."
            )
        step = self._script[self._i]
        self._i += 1
        return step


def tool_call(call_id: str, name: str, arguments: str) -> FakeToolCall:
    return FakeToolCall(id=call_id, name=name, arguments=arguments)


def final(text: str) -> FakeMessage:
    return FakeMessage(role="assistant", content=text, tool_calls=[])


def calling(*calls: FakeToolCall) -> FakeMessage:
    return FakeMessage(role="assistant", content=None, tool_calls=list(calls))
