"""`POST /api/v1/agent/stream` (issue 15, architecture.md §6; live model
wired in issue 17).

A POST, not `GET` + native `EventSource`: the request carries a message and
the current Report Spec, and auth uses the same `X-API-Key` header as every
other route (`EventSource` cannot set headers) — so the frontend streams via
`fetch`-based SSE instead (`frontend/src/lib/agentStream.ts`). Auth itself is
inherited for free: this router is included on `api_router`, which attaches
`require_api_key` once at the aggregate-router level (`api/v1/router.py`).

Three backends, in priority order:

1. `DEV_FAKE_LLM` set (refused outside development by `Settings`'s own
   validator — ADR-0003): `app/agent/fake_model.run_fake_turn` drives a
   scripted two-Tool-Step conversation. Unchanged from issue 15/16.
2. No `OPENROUTER_API_KEY` configured: the endpoint still streams valid,
   well-formed SSE — a single sanitised `error` event saying the assistant
   isn't available, never a 501 or a hang (architecture.md's "graceful
   agent unavailable" mitigation).
3. Otherwise: `app/agent/llm.run_llm_turn` — the live model, bounded by the
   Tool Step budget (issue 17).

Both raw-event sources and `present_async` are `async` because the live
path awaits the provider between events; the fake path is wrapped in a
trivial async generator (`_sync_to_async`) so both share the one
`present_async` chokepoint rather than forking the translation logic.
"""

import json
from collections.abc import AsyncIterator, Iterable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent.events import RawEvent, TurnError
from app.agent.fake_model import run_fake_turn
from app.agent.llm import run_llm_turn
from app.agent.presenter import present_async
from app.config import Settings, get_settings
from app.models import ReportSpec
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


class AgentStreamRequest(BaseModel):
    message: str
    spec: ReportSpec


async def _sync_to_async(events: Iterable[RawEvent]) -> AsyncIterator[RawEvent]:
    """Wrap the fake model's plain (synchronous, no I/O) generator so it can
    be consumed through the same `present_async` chokepoint the live loop
    uses, instead of keeping two translation code paths."""
    for event in events:
        yield event


async def _raw_events(
    body: AgentStreamRequest, settings: Settings, upstream_client: UpstreamClient
) -> AsyncIterator[RawEvent]:
    if settings.dev_fake_llm:
        async for event in _sync_to_async(run_fake_turn(body.message, body.spec)):
            yield event
        return

    if not settings.openrouter_api_key:
        yield TurnError(category="unavailable", detail="OPENROUTER_API_KEY not configured")
        return

    try:
        dataset = await upstream_client.get_dataset()
    except Exception as exc:  # noqa: BLE001 - sanitised for the browser, logged server-side
        yield TurnError(category="internal", detail=str(exc))
        return

    async for event in run_llm_turn(body.message, body.spec, dataset, settings):
        yield event


@router.post("/agent/stream")
async def post_agent_stream(
    body: AgentStreamRequest,
    settings: Settings = Depends(get_settings),
    upstream_client: UpstreamClient = Depends(get_upstream_client),
) -> EventSourceResponse:
    async def event_stream() -> AsyncIterator[dict]:
        raw = _raw_events(body, settings, upstream_client)
        async for ui_event in present_async(raw, include_reasoning_text=True):
            yield {"event": ui_event.event_name, "data": json.dumps(ui_event.to_data())}

    return EventSourceResponse(event_stream())
