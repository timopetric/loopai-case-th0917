"""`POST /api/v1/agent/stream` (issue 15, architecture.md §6).

A POST, not `GET` + native `EventSource`: the request carries a message and
the current Report Spec, and auth uses the same `X-API-Key` header as every
other route (`EventSource` cannot set headers) — so the frontend streams via
`fetch`-based SSE instead (`frontend/src/lib/agentStream.ts`). Auth itself is
inherited for free: this router is included on `api_router`, which attaches
`require_api_key` once at the aggregate-router level (`api/v1/router.py`).

This slice ships no real tools and no live model (issues 16/17) — with
`DEV_FAKE_LLM` unset, the endpoint still streams valid, well-formed SSE, just
a single sanitised `error` event saying the assistant isn't available yet,
rather than 501ing or hanging (architecture.md's "graceful agent unavailable"
risk mitigation). With `DEV_FAKE_LLM` set (refused outside development by
`Settings`'s own validator — ADR-0003, verified in `test_config.py`, not
re-verified here), `app/agent/fake_model.run_fake_turn` drives a scripted
two-Tool-Step conversation through the same `present()` chokepoint the real
loop will use.
"""

import json
from collections.abc import AsyncIterator, Iterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent.events import RawEvent, TurnError
from app.agent.fake_model import run_fake_turn
from app.agent.presenter import present
from app.config import Settings, get_settings
from app.models import ReportSpec

router = APIRouter()


class AgentStreamRequest(BaseModel):
    message: str
    spec: ReportSpec


def _raw_events(body: AgentStreamRequest, settings: Settings) -> Iterator[RawEvent]:
    if not settings.dev_fake_llm:
        # Issue 17 wires the live model; until then there is nothing to run.
        yield TurnError(category="unavailable", detail="no model backend configured (issue 17)")
        return
    yield from run_fake_turn(body.message, body.spec)


@router.post("/agent/stream")
async def post_agent_stream(
    body: AgentStreamRequest,
    settings: Settings = Depends(get_settings),
) -> EventSourceResponse:
    async def event_stream() -> AsyncIterator[dict]:
        raw = _raw_events(body, settings)
        for ui_event in present(raw, include_reasoning_text=settings.is_development):
            yield {"event": ui_event.event_name, "data": json.dumps(ui_event.to_data())}

    return EventSourceResponse(event_stream())
