import { apiFetch } from "./apiClient";
import type { ReportSpec } from "./report";

/**
 * `ReportSpec` <-> URL query parameters (issue 13, architecture.md §7 "State
 * ... synced to URL query for shareable reports").
 *
 * Decoding a query string is the risky half — parsing untrusted input,
 * validating against the model, deciding what is stale vs malformed,
 * falling back safely — and it must go through the SAME validation as any
 * other input (issue 13 acceptance criteria). `ReportSpec`'s validators
 * only exist in `app/models.py`, checked by pydantic; a second, hand-typed
 * copy of those rules here would drift the moment either side's rules
 * changed, silently, on the one input path that is untrusted by
 * construction (a hand-edited URL). So decoding is NOT done here: `App.tsx`
 * sends the raw query string to `GET /api/v1/spec`
 * (`app/spec_url.py::decode_spec`, going through `ReportSpec` itself) and
 * applies whatever comes back — a validated spec, or the default plus a
 * Warning it can show verbatim. That request already happens inside a
 * loading phase the app has anyway (the same one that fetches
 * `/api/v1/meta`), so it costs nothing perceptible.
 *
 * Encoding is mechanical by contrast — turning a `ReportSpec` the app
 * already built and knows is valid into a query string — so it stays here,
 * client-side, and runs on every control change without a network round
 * trip. Field names and the list separator are kept identical to
 * `app/spec_url.py::encode_spec` by inspection (this project does not
 * unit-test the frontend), so the query strings this function writes are
 * exactly what the server-side decoder above is proven, in
 * `tests/test_spec_url.py`, to accept.
 */

const LIST_SEP = ",";

export function encodeSpecToSearchParams(spec: ReportSpec): URLSearchParams {
  const params = new URLSearchParams();
  params.set("metrics", spec.metrics.join(LIST_SEP));
  params.set("date_from", spec.date_from);
  params.set("date_to", spec.date_to);
  params.set("granularity", spec.granularity);
  params.set("group_by", spec.group_by);
  params.set("duration_display", spec.duration_display ?? "avg");
  params.set("layout", spec.layout ?? "long");
  if (spec.sort) {
    params.set("sort_column", spec.sort.column);
    params.set("sort_direction", spec.sort.direction);
  }
  if (spec.columns_order && spec.columns_order.length > 0) {
    params.set("columns_order", spec.columns_order.join(LIST_SEP));
  }
  if (spec.chart_metric) {
    params.set("chart_metric", spec.chart_metric);
  }
  return params;
}

export interface SpecFromQueryResult {
  spec: ReportSpec;
  /** Non-empty when the query string could not be honoured verbatim — no
   * params at all is NOT a warning (a plain visit), only a present-but-
   * invalid-or-stale link is. Single-sourced from the server
   * (`app/spec_url.py::spec_from_query_or_default`) rather than composed
   * client-side, so the message shown never disagrees with the reason the
   * fallback actually happened. */
  warnings: string[];
}

/**
 * `search` is `window.location.search` verbatim (including a leading `?`,
 * or `""`). Requires auth (routed through `apiFetch`, like every other API
 * call) — `App.tsx` only calls this once signed in, which is also exactly
 * when a restored spec is meaningful to show.
 */
export async function fetchSpecFromQuery(search: string): Promise<SpecFromQueryResult> {
  const response = await apiFetch(`/api/v1/spec${search}`);
  if (!response.ok) {
    throw new Error(`GET /api/v1/spec failed: ${response.status}`);
  }
  return response.json();
}
