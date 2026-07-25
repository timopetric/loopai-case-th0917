"""Metadata route (issue 03): everything the frontend needs before it can even
draw the report builder — the Coverage Window, the Actor and Mailbox lists,
and the metric catalogue. Backed by `upstream.get_dataset()`, so it shares the
same 5-minute memo as the report route added in a later slice.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.upstream import METRIC_CATALOGUE, UpstreamClient, get_upstream_client

router = APIRouter()


class CoverageWindowResponse(BaseModel):
    from_date: str
    to_date: str


class EntityResponse(BaseModel):
    id: str
    name: str


class MetricResponse(BaseModel):
    key: str
    kind: str
    unit: str


class MetaResponse(BaseModel):
    coverage_window: CoverageWindowResponse
    actors: list[EntityResponse]
    mailboxes: list[EntityResponse]
    metrics: list[MetricResponse]
    dev_fake_upstream: bool


@router.get("/meta")
async def get_meta(
    client: UpstreamClient = Depends(get_upstream_client),
    settings: Settings = Depends(get_settings),
) -> MetaResponse:
    dataset = await client.get_dataset()

    return MetaResponse(
        coverage_window=CoverageWindowResponse(
            from_date=dataset.coverage.from_date, to_date=dataset.coverage.to_date
        ),
        actors=[EntityResponse(id=a.id, name=a.name) for a in dataset.actors],
        mailboxes=[EntityResponse(id=m.id, name=m.name) for m in dataset.mailboxes],
        metrics=[
            MetricResponse(key=m.key, kind=m.kind, unit=m.unit) for m in METRIC_CATALOGUE
        ],
        dev_fake_upstream=settings.dev_fake_upstream,
    )
