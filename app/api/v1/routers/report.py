"""Report route (issue 04): `ReportSpec` in, `ReportTable` out.

The single request/response pair the builder UI, and later the Assistant's
`run_report` tool, both drive. Backed by `upstream.get_dataset()` (the same
5-minute memo `meta.py` shares) and `engine.execute()`, which is pure and
does no I/O of its own.

Coverage validation (issue 08) is enforced *inside* `engine.execute()`, not
here — this route is a thin translation of `CoverageRefusedError` into a 422
carrying the real Coverage Window, not the place the rule is decided. That
placement matters: `client.get_dataset()` always fetches the whole window
regardless of the requested dates (ADR-0001), so there is nothing this route
could usefully skip by checking first, and issue 16's Assistant calls
`execute()` directly, in-process, without ever going through this route at
all. Enforcing the guard in `execute()` is what makes it apply to every
caller rather than to whichever caller remembered to ask for it.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.engine import CoverageRefusedError, UnsupportedMetricError, execute
from app.models import ReportSpec, ReportTable
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


async def resolve_report_table(spec: ReportSpec, client: UpstreamClient) -> ReportTable:
    """`ReportSpec` -> `ReportTable`, translating the engine's domain errors
    into the same 422s every caller of a Report Spec needs (issue 04, issue
    08). Shared by `/report` (preview) and `/export/csv` (issue 10, and
    issue 11's XLSX route) so the error handling — and the guarantee that an
    export can never disagree with the preview because it runs the identical
    `execute()` call — lives in exactly one place.
    """
    dataset = await client.get_dataset()
    try:
        return execute(spec, dataset)
    except CoverageRefusedError as exc:
        # The requested date range has zero overlap with the Coverage
        # Window (issue 08) — refuse outright and hand back the real
        # window so the caller can offer an alternative, rather than ever
        # showing a table that looks like it answered the question asked.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "date range outside Coverage Window",
                "message": str(exc),
                "coverage": {
                    "from_date": exc.coverage.from_date,
                    "to_date": exc.coverage.to_date,
                },
            },
        ) from exc
    except UnsupportedMetricError as exc:
        # `replies_to_resolve` (`kind == "sum"`) is still unsupported (issue
        # 05 covers Counters and Duration Metrics only). A clear 422 beats a
        # silently wrong number.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post("/report")
async def post_report(
    spec: ReportSpec,
    client: UpstreamClient = Depends(get_upstream_client),
) -> ReportTable:
    return await resolve_report_table(spec, client)
