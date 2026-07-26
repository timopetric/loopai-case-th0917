import { apiFetch } from "./apiClient";
import type { ReportSpec } from "./report";
import { ReportRefusedError } from "./report";

export type ExportFormat = "csv" | "xlsx";

const CONTENT_DISPOSITION_FILENAME = /filename="([^"]+)"/;

/**
 * POSTs the current `ReportSpec` to `/api/v1/export/{format}` and returns the
 * response body as a `Blob` plus the filename the server chose.
 *
 * Both export routes are POST and sit behind the shared-key auth (issue 02),
 * so a plain `<a href="/api/v1/export/csv" download>` cannot work — it would
 * issue a GET with no `X-API-Key` and 401. This goes through `apiFetch`
 * exactly like `fetchReport`, so the key attaches and a 401 still triggers
 * the same sign-in bounce (`UNAUTHORIZED_EVENT`) as every other call.
 *
 * The filename is read from the `Content-Disposition` header the routes
 * already set (`app/api/v1/routers/export.py`), never reconstructed from the
 * spec here — the server already names the file after the date range, and a
 * second copy of that logic is exactly how the two would drift apart.
 */
export async function exportReport(
  spec: ReportSpec,
  format: ExportFormat,
): Promise<{ blob: Blob; filename: string }> {
  const response = await apiFetch(`/api/v1/export/${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });

  if (!response.ok) {
    if (response.status === 422) {
      // Same shape as `fetchReport`'s coverage-refusal handling: the export
      // routes reuse `resolve_report_table`, so a zero-overlap range 422s
      // here exactly the way it does for the preview.
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      if (detail && typeof detail === "object" && detail.coverage) {
        throw new ReportRefusedError(
          detail.message ?? "That date range has no data.",
          detail.coverage,
        );
      }
    }
    throw new Error(`POST /api/v1/export/${format} failed: ${response.status}`);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const match = CONTENT_DISPOSITION_FILENAME.exec(disposition);
  const filename = match ? match[1] : `report.${format}`;

  const blob = await response.blob();
  return { blob, filename };
}

/**
 * Triggers a browser "Save as" for `blob` named `filename`, via a temporary
 * object URL that is revoked immediately after the click so the blob is not
 * retained by the page.
 */
export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
