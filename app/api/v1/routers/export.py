"""Export routes: CSV (issue 10) and XLSX (issue 11), side by side.

Same shape as `report.py`'s `/report` route — a `ReportSpec` in, a file out
— and deliberately reuses `report.resolve_report_table` rather than
re-running `execute()` down a second path: the file this route returns and
the table the preview renders come from the identical function call, so
they structurally cannot disagree (issue 10, PRD "Exports", user story 34).

The XLSX route additionally reads the Coverage Window via
`client.get_coverage_window()` for the "Report info" sheet. That is a
second call on the `UpstreamClient`, but ADR-0001's 5-minute memo means it
costs no extra upstream request in practice — the same reasoning
`assumptions.py`'s route already relies on.
"""

from fastapi import APIRouter, Depends, Response

from app.api.v1.routers.report import resolve_report_table
from app.exporters import to_csv, to_xlsx
from app.models import ReportSpec
from app.upstream import UpstreamClient, get_upstream_client

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


@router.post("/export/xlsx")
async def post_export_xlsx(
    spec: ReportSpec,
    client: UpstreamClient = Depends(get_upstream_client),
) -> Response:
    table = await resolve_report_table(spec, client)
    coverage = await client.get_coverage_window()
    body = to_xlsx(spec, table, coverage)
    filename = f"report_{spec.date_from.isoformat()}_{spec.date_to.isoformat()}.xlsx"
    return Response(
        content=body,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
