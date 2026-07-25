"""Report route (issue 04): `ReportSpec` in, `ReportTable` out.

The single request/response pair the builder UI, and later the Assistant's
`run_report` tool, both drive. Backed by `upstream.get_dataset()` (the same
5-minute memo `meta.py` shares) and `engine.execute()`, which is pure and
does no I/O of its own.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.engine import UnsupportedMetricError, execute
from app.models import ReportSpec, ReportTable
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


@router.post("/report")
async def post_report(
    spec: ReportSpec,
    client: UpstreamClient = Depends(get_upstream_client),
) -> ReportTable:
    dataset = await client.get_dataset()
    try:
        return execute(spec, dataset)
    except UnsupportedMetricError as exc:
        # `replies_to_resolve` (`kind == "sum"`) is still unsupported (issue
        # 05 covers Counters and Duration Metrics only). A clear 422 beats a
        # silently wrong number.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
