"""Report Spec <-> URL query parameters, over real HTTP (issue 13).

Proves the property `tests/test_spec_url.py` proves in-process — every
`ReportSpec` field survives serialise/deserialise — also survives an actual
round trip through Starlette's query-string parsing (PRD's API-level test
list: "a Report Spec survives a round-trip through URL query parameters").
`app.spec_url` does all the work; this route is a thin translation of
`request.query_params` to `spec_from_query_or_default`, using the real
day-by-Actor preset (`app/presets.py`, the same one `/api/v1/meta` serves
first) as the fallback default — the same "restore, or fall back to the
default report with a Warning" contract the frontend implements client-side
in `frontend/src/lib/specUrl.ts` for the actual sharing feature (there is no
network hop on the real restore path: the browser reads its own URL).
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.models import ReportSpec
from app.presets import DEFAULT_PRESET_ID, build_presets
from app.spec_url import spec_from_query_or_default
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


class SpecFromQueryResponse(BaseModel):
    spec: ReportSpec
    warnings: list[str]


@router.get("/spec")
async def get_spec_from_query(
    request: Request,
    client: UpstreamClient = Depends(get_upstream_client),
) -> SpecFromQueryResponse:
    dataset = await client.get_dataset()
    default = next(
        preset.spec for preset in build_presets(dataset.coverage) if preset.id == DEFAULT_PRESET_ID
    )

    spec, warnings = spec_from_query_or_default(dict(request.query_params), default)
    return SpecFromQueryResponse(spec=spec, warnings=warnings)
