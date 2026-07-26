import { apiFetch } from "./apiClient";

/** Mirrors `app.assumptions.AssumptionNote` / `app/api/v1/routers/assumptions.py`'s
 * `AssumptionItem` (issue 09) — the single source shared with the future
 * Excel "Report info" sheet (issue 11). Nothing here restates the text; it
 * only shapes what the backend already sends. */
export interface AssumptionNote {
  id: string;
  title: string;
  body: string;
}

export async function fetchAssumptions(): Promise<AssumptionNote[]> {
  const response = await apiFetch("/api/v1/assumptions");
  if (!response.ok) {
    throw new Error(`GET /api/v1/assumptions failed: ${response.status}`);
  }
  const body: { items: AssumptionNote[] } = await response.json();
  return body.items;
}
