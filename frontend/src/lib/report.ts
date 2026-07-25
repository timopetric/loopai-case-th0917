import { apiFetch } from "./apiClient";

/** Mirrors `app/models.py` (issues 04–05). */
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

export async function fetchReport(spec: ReportSpec): Promise<ReportTable> {
  const response = await apiFetch("/api/v1/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!response.ok) {
    throw new Error(`POST /api/v1/report failed: ${response.status}`);
  }
  return response.json();
}
