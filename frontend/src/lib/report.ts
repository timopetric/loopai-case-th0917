import { apiFetch } from "./apiClient";

/** Mirrors `app/models.py` (issue 04). */
export interface ReportSpec {
  metrics: string[];
  date_from: string;
  date_to: string;
  granularity: "day" | "total";
  group_by: "none" | "agent" | "mailbox";
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
  values: Record<string, number>;
}

export interface ReportTable {
  columns: ColumnMeta[];
  rows: ReportRow[];
  totals: Record<string, number>;
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
