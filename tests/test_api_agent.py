"""API-level test for `POST /api/v1/agent/stream` (issue 15).

Drives the real route in-process via `TestClient`, exactly like every other
API-level test in this suite — `DEV_FAKE_LLM` swaps in the scripted fake
model (`app/agent/fake_model.py`) via a `Settings` dependency override, same
pattern `test_upstream.py`'s `DEV_FAKE_UPSTREAM` tests use, so this is
offline, free, and deterministic (ADR-0003). Asserts:

- the route requires the same `X-API-Key` header as every other route
  (covered generically by `test_auth.py`'s route-enumeration test too, but
  a dedicated check here documents the reasoning: SSE via `fetch`, not
  `EventSource`, exists BECAUSE of this)
- the SSE frames are well-formed (`event: ...` / `data: <json>` pairs)
- the event order matches architecture.md §6's flow, repeated per Tool Step
- with `DEV_FAKE_LLM` unset, the stream still returns well-formed SSE with a
  single sanitised `error` event, never a 500 or a hang
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, environment="local", **overrides)


def _app(settings: Settings):
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    return application


def _client(settings: Settings) -> TestClient:
    return TestClient(_app(settings))


def _auth_headers(settings: Settings) -> dict[str, str]:
    return {"X-API-Key": settings.app_api_key}


def _spec(**overrides) -> dict:
    body = dict(
        metrics=["resolved"],
        date_from="2026-07-10",
        date_to="2026-07-16",
        granularity="day",
        group_by="none",
    )
    body.update(overrides)
    return body


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse `event: X\\r\\ndata: Y\\r\\n\\r\\n` frames (sse-starlette's wire
    format) into `(event, data)` pairs, asserting each frame is well-formed
    along the way (a malformed frame — missing `event:` line, non-JSON
    `data:` — raises here rather than being silently skipped)."""
    normalised = text.replace("\r\n", "\n")
    frames = [block for block in normalised.split("\n\n") if block.strip()]
    parsed: list[tuple[str, dict]] = []
    for block in frames:
        lines = block.splitlines()
        event_lines = [line for line in lines if line.startswith("event:")]
        data_lines = [line for line in lines if line.startswith("data:")]
        assert event_lines, f"SSE frame missing 'event:' line: {block!r}"
        assert data_lines, f"SSE frame missing 'data:' line: {block!r}"
        event_name = event_lines[0].removeprefix("event:").strip()
        data_raw = "".join(line.removeprefix("data:").strip() for line in data_lines)
        data = json.loads(data_raw)  # raises if not well-formed JSON
        parsed.append((event_name, data))
    return parsed


class TestAuth:
    def test_stream_rejects_a_request_with_no_key(self):
        settings = _settings(dev_fake_llm=True)
        client = _client(settings)

        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "hi", "spec": _spec()},
        )

        assert response.status_code == 401

    def test_stream_accepts_the_correct_key(self):
        settings = _settings(dev_fake_llm=True)
        client = _client(settings)

        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "hi", "spec": _spec()},
            headers=_auth_headers(settings),
        )

        assert response.status_code == 200


class TestFakeModelDrivesTheReportEndToEnd:
    @pytest.fixture
    def events(self) -> list[tuple[str, dict]]:
        settings = _settings(dev_fake_llm=True)
        client = _client(settings)
        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "resolved and handle time by agent", "spec": _spec()},
            headers=_auth_headers(settings),
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return _parse_sse(response.text)

    def test_event_order_matches_the_architecture_flow(
        self, events: list[tuple[str, dict]]
    ) -> None:
        # architecture.md §6: thinking(start) -> thinking(end) -> status ->
        # chips -> spec, repeated once per Tool Step, then token* -> done.
        # `thinking_text` is the dev-only reasoning channel (this fixture's
        # settings are always development, since DEV_FAKE_LLM requires it —
        # ADR-0003) and is checked separately below; filtered out here so
        # this test asserts the stable, always-shipped vocabulary's order.
        core_events = {"thinking", "status", "chips", "spec", "token", "done", "error"}
        names = [name for name, _ in events if name in core_events]
        assert names == [
            "thinking",
            "thinking",
            "status",
            "chips",
            "spec",
            "thinking",
            "thinking",
            "status",
            "chips",
            "spec",
            "thinking",
            "thinking",
            "token",
            "token",
            "token",
            "token",
            "done",
        ]

    def test_thinking_events_bracket_start_then_end(
        self, events: list[tuple[str, dict]]
    ) -> None:
        thinking_events = [data for name, data in events if name == "thinking"]
        assert thinking_events[0]["state"] == "start"
        assert thinking_events[1]["state"] == "end"
        assert "ms" in thinking_events[1]

    def test_spec_events_carry_the_full_validated_spec_and_move_the_controls(
        self, events: list[tuple[str, dict]]
    ) -> None:
        spec_events = [data["spec"] for name, data in events if name == "spec"]
        assert len(spec_events) == 2
        assert spec_events[0]["group_by"] == "agent"
        assert spec_events[1]["group_by"] == "agent"
        assert set(spec_events[1]["metrics"]) == {"resolved", "handle_time"}

    def test_chips_describe_what_changed(self, events: list[tuple[str, dict]]) -> None:
        chip_events = [data["chips"] for name, data in events if name == "chips"]
        # "Actor", not the wire value "agent" — CONTEXT.md bans unqualified
        # "agent" in UI copy; the wire value itself is checked unchanged in
        # test_spec_events_carry_the_full_validated_spec_and_move_the_controls.
        assert any("Grouping: by Actor" in chips for chips in chip_events)
        assert any(
            any(chip.startswith("Added metric:") for chip in chips) for chips in chip_events
        )

    def test_done_event_carries_a_summary_and_final_spec_version(
        self, events: list[tuple[str, dict]]
    ) -> None:
        done = next(data for name, data in events if name == "done")
        assert done["spec_version"] == 2
        assert isinstance(done["summary"], str) and done["summary"]

    def test_token_events_concatenate_to_the_done_summary(
        self, events: list[tuple[str, dict]]
    ) -> None:
        tokens = "".join(data["text"] for name, data in events if name == "token")
        done = next(data for name, data in events if name == "done")
        assert tokens == done["summary"]


class TestNoInternalsInTheStream:
    def test_no_tool_name_argument_or_prompt_fragment_appears_in_the_non_reasoning_events(self):
        # ADR-0005: tool names/enum values may now legitimately appear inside
        # `thinking_text` events — that channel is exempted here, on purpose.
        # Every OTHER event type (`token`, `chips`, `status`, `spec`, `error`,
        # plus the content-free `thinking` state markers) must still never
        # carry a tool name, a raw argument, or a prompt fragment; narrowing
        # this to exclude only `thinking_text` (rather than dropping the
        # assertion, or exempting the whole stream) is the point of this test.
        settings = _settings(dev_fake_llm=True)
        client = _client(settings)
        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "resolved and handle time by agent", "spec": _spec()},
            headers=_auth_headers(settings),
        )

        events = _parse_sse(response.text)
        non_reasoning_events = [
            (name, data) for name, data in events if name != "thinking_text"
        ]
        assert non_reasoning_events, "expected non-reasoning events in the stream"
        body = "\n".join(f"{name}:{data!r}" for name, data in non_reasoning_events)
        for internal in ("set_grouping", "set_metrics", '"by": "agent"', "ReasoningDelta"):
            assert internal not in body, f"{internal!r} leaked into a non-reasoning SSE event"

    def test_reasoning_text_streams_even_outside_development(self):
        # ADR-0005: the `settings.is_development` gate on `ThinkingTextEvent`
        # is gone — reasoning streams to every user, in every environment.
        # `dev_fake_llm=True` still requires `environment="local"` (ADR-0003's
        # own validator), so we flip `environment` to something non-local
        # directly on the `Settings` instance after construction to get a
        # genuinely non-development configuration, rather than relying on
        # `_settings`'s default and merely failing to notice the gate is gone.
        settings = _settings(dev_fake_llm=True)
        object.__setattr__(settings, "environment", "prod")
        assert settings.is_development is False
        client = _client(settings)
        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "hi", "spec": _spec()},
            headers=_auth_headers(settings),
        )

        events = _parse_sse(response.text)
        thinking_text_events = [name for name, _ in events if name == "thinking_text"]
        assert len(thinking_text_events) > 0


class TestFakeModelUnavailableWithoutTheFlag:
    def test_stream_returns_a_sanitised_error_when_dev_fake_llm_is_unset(self):
        settings = _settings(dev_fake_llm=False)
        client = _client(settings)

        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "hi", "spec": _spec()},
            headers=_auth_headers(settings),
        )

        assert response.status_code == 200
        events = _parse_sse(response.text)
        assert [name for name, _ in events] == ["error"]
        assert "issue 17" not in events[0][1]["text"]
        assert events[0][1]["text"] == "The assistant isn't available right now."
