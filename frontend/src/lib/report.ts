import { apiFetch } from "./apiClient";

/** Mirrors `app/models.py`'s `SortSpec` (issue 07). `column` must be one of
 * `ReportSpec.metrics` — the engine ranks a metric column, never the bucket
 * or the group label. */
export interface SortSpec {
  column: string;
  direction: "asc" | "desc";
}

/** Mirrors `app/models.py` (issues 04–07). */
export interface ReportSpec {
  metrics: string[];
  date_from: string;
  date_to: string;
  granularity: "day" | "total";
  group_by: "none" | "agent" | "mailbox";
  /** "avg" (default) = per-ticket Σvalue/Σcount ("how fast"); "total" = the
   * raw period sum in hours ("how much work"). Only affects `kind ===
   * "duration"` columns. */
  duration_display?: "avg" | "total";
  /** Ranks rows *within* each Bucket, never globally (architecture.md §2
   * "Table semantics") — a `granularity: "total"` report has one Bucket, so
   * the same mechanism ranks the whole table (issue 07). `null`/omitted =
   * unsorted (engine/dataset order). */
  sort?: SortSpec | null;
  /** Explicit left-to-right metric-column order (issue 07, user story 12).
   * Unknown keys are ignored server-side and any selected metric left
   * unmentioned is appended, so a stale order never drops a column. */
  columns_order?: string[] | null;
  /** "long" (default): rows = Bucket × group. "pivot": Buckets across the
   * top as columns, rendering `chart_metric` only (issue 07). */
  layout?: "long" | "pivot";
  /** The metric `layout: "pivot"` renders. `null`/omitted defaults to
   * `metrics[0]` server-side; must be a member of `metrics`. */
  chart_metric?: string | null;
}

export interface ColumnMeta {
  key: string;
  label: string;
  kind: "counter" | "duration" | "sum";
  unit: "count" | "hours" | "replies";
}

export interface ReportRow {
  bucket: string;
  group_key: string | null;
  group_label: string | null;
  /** `null` marks a Duration Metric cell the engine withholds rather than
   * lies about — a zero-`_count` average is undefined, not `0.0` (issue 05
   * fix: a zero-ticket Actor must never look like the fastest resolver on
   * the board). `duration_display === "total"` never produces `null`. */
  values: Record<string, number | null>;
  /** The Σcount behind each Duration Metric value in `values` — the cell
   * tooltip's data (issue 05, user story 23). Absent for Counter columns. */
  counts: Record<string, number>;
}

export interface ReportTable {
  columns: ColumnMeta[];
  rows: ReportRow[];
  /** `null` marks a cell the engine deliberately withholds — currently only
   * `actioned_emails` totalled across Actors (issue 05, user story 24):
   * it double-counts by ~52% and only across Actors, so the total is a
   * dash, never a number and never a blank. */
  totals: Record<string, number | null>;
  /** The Σcount behind each Duration Metric total, mirroring `ReportRow.counts`. */
  total_counts: Record<string, number>;
  warnings: string[];
}

/**
 * Mirrors `app/engine.py`'s `_label()` exactly (`key.replace("_", " ").capitalize()`)
 * so a metric picker built from the catalogue (`/api/v1/meta`, which carries
 * `key`/`kind`/`unit` but no display label) reads the same as the resulting
 * table's column headers, without hardcoding a metric list anywhere in the
 * frontend (issue 06).
 */
export function formatMetricLabel(key: string): string {
  const withSpaces = key.replace(/_/g, " ");
  return withSpaces.charAt(0).toUpperCase() + withSpaces.slice(1);
}

/**
 * Thrown when the backend refuses a date range with zero overlap with the
 * Coverage Window (issue 08) — a 422 whose `detail.coverage` names the real
 * window, so the caller can tell the user something more useful than "could
 * not load the report" (architecture.md §12 checklist: "a date outside
 * coverage is refused, not silently substituted" must be legible, not a
 * silent empty table). A partially-overlapping range is *not* this error —
 * the backend clamps and returns 200 with a `warnings` entry instead, shown
 * as the usual banner in `ReportTable`.
 */
export class ReportRefusedError extends Error {
  coverage: { from_date: string; to_date: string } | null;

  constructor(message: string, coverage: { from_date: string; to_date: string } | null) {
    super(message);
    this.name = "ReportRefusedError";
    this.coverage = coverage;
  }
}

export async function fetchReport(spec: ReportSpec): Promise<ReportTable> {
  const response = await apiFetch("/api/v1/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!response.ok) {
    if (response.status === 422) {
      // The engine's other 422 (an unsupported metric) has a plain string
      // `detail`; only the coverage refusal carries this shape, so a
      // missing/malformed `coverage` falls through to the generic message.
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      if (detail && typeof detail === "object" && detail.coverage) {
        throw new ReportRefusedError(
          detail.message ?? "That date range has no data.",
          detail.coverage,
        );
      }
    }
    throw new Error(`POST /api/v1/report failed: ${response.status}`);
  }
  return response.json();
}
