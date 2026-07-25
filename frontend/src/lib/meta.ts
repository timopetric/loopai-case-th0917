import { apiFetch } from "./apiClient";

/** Mirrors `app/api/v1/routers/meta.py`'s `MetaResponse` (issue 03). */
export interface Meta {
  coverage_window: { from_date: string; to_date: string };
  actors: { id: string; name: string }[];
  mailboxes: { id: string; name: string }[];
  metrics: { key: string; kind: string; unit: string }[];
  dev_fake_upstream: boolean;
}

export async function fetchMeta(): Promise<Meta> {
  const response = await apiFetch("/api/v1/meta");
  if (!response.ok) {
    throw new Error(`GET /api/v1/meta failed: ${response.status}`);
  }
  return response.json();
}
