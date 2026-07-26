"""Metadata route (issue 03): everything the frontend needs before it can even
draw the report builder — the Coverage Window, the Actor and Mailbox lists,
the metric catalogue, and (issue 12) the preset list. Backed by
`upstream.get_dataset()`, so it shares the same 5-minute memo as the report
route added in a later slice.

Presets are deliberately not built into the frontend (a lesson learned mid-
issue-12): a hand-mirrored TS copy of `app/presets.py` would let the button a
user actually clicks drift from the `ReportSpec`s `tests/test_presets.py`
proves the shape of, silently, with every test still green. This route is
the single translation of `app.presets.build_presets` to JSON — see
`app/assumptions.py` and `routers/assumptions.py` for the identical pattern
and its own drift-proofing sentinel test
(`test_assumptions_route_has_no_hardcoded_second_copy`), mirrored here as
`test_meta_route_has_no_hardcoded_second_copy_of_presets`
(`tests/test_api_meta.py`). The frontend renders one button per entry in
`presets` and applies `spec` verbatim — it holds no preset definitions of
its own.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.models import ReportSpec
from app.presets import build_presets
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


class PresetResponse(BaseModel):
    id: str
    label: str
    spec: ReportSpec
    """The fully-built Report Spec, real Coverage Window dates already
    baked in by `build_presets` — the frontend applies this verbatim
    (`App.tsx`'s `applyPreset`), never re-deriving it from a coverage
    window of its own."""


class MetaResponse(BaseModel):
    coverage_window: CoverageWindowResponse
    actors: list[EntityResponse]
    mailboxes: list[EntityResponse]
    metrics: list[MetricResponse]
    presets: list[PresetResponse]
    dev_fake_upstream: bool
    dev_fake_llm: bool


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
        presets=[
            PresetResponse(id=p.id, label=p.label, spec=p.spec)
            for p in build_presets(dataset.coverage)
        ],
        dev_fake_upstream=settings.dev_fake_upstream,
        dev_fake_llm=settings.dev_fake_llm,
    )
