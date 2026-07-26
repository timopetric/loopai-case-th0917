"""Assumptions route (issue 09): backs the coverage banner's modal.

Deliberately thin — every word of the response comes from
`app.assumptions.build_assumptions`, the single source shared with the
future Excel "Report info" sheet (issue 11). This route must never grow its
own copy of the text; if it needs to change, it changes in
`app/assumptions.py` and both consumers pick it up automatically.

Backed by `upstream.get_dataset()` so the partial-final-day note names the
Coverage Window's real last day, not a hardcoded one — the same memoised
call `meta.py` and `report.py` already share (ADR-0001), so this costs no
extra upstream request in practice.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.assumptions import build_assumptions
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


class AssumptionItem(BaseModel):
    id: str
    title: str
    body: str


class AssumptionsResponse(BaseModel):
    items: list[AssumptionItem]


@router.get("/assumptions")
async def get_assumptions(
    client: UpstreamClient = Depends(get_upstream_client),
) -> AssumptionsResponse:
    dataset = await client.get_dataset()
    notes = build_assumptions(dataset.coverage)
    return AssumptionsResponse(items=[AssumptionItem(**asdict(n)) for n in notes])
