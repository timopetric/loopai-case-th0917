"""Export routes (issue 10 CSV; structured so issue 11 adds an XLSX route
alongside it without disturbing this one).

Same shape as `report.py`'s `/report` route — a `ReportSpec` in, a file out
— and deliberately reuses `report.resolve_report_table` rather than
re-running `execute()` down a second path: the file this route returns and
the table the preview renders come from the identical function call, so
they structurally cannot disagree (issue 10, PRD "Exports", user story 34).
"""

from fastapi import APIRouter, Depends, Response

from app.api.v1.routers.report import resolve_report_table
from app.exporters import to_csv
from app.models import ReportSpec
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()


@router.post("/export/csv")
async def post_export_csv(
    spec: ReportSpec,
    client: UpstreamClient = Depends(get_upstream_client),
) -> Response:
    table = await resolve_report_table(spec, client)
    body = to_csv(spec, table)
    filename = f"report_{spec.date_from.isoformat()}_{spec.date_to.isoformat()}.csv"
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
