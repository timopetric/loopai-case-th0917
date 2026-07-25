# Sub-agent report (verbatim relay): auth, infrastructure, surface area, doc fidelity

Relayed by the orchestrator (agent was blocked from writing the file itself).
Evidence: `evidence-auth-infra/{auth_matrix.txt, routes.txt, cors_preflight.txt,
cors_preflight_headers.txt, latency.txt, rate_limit_burst.txt, robustness.txt,
reporting-api-guide.pdf, pdf_text.txt, spec.html, index.html}`; scripts
`probe-auth-infra.py`, `probe-routes.py`, `probe-rate-latency.py`, `probe-robustness.py`.

## 1. Auth — what is actually enforced

Any non-empty `Bearer <token>` is accepted; the value is never checked and never changes
the response.

| Case | Status | Body |
|---|---|---|
| No `Authorization` header | 401 | `{"error":"No auth provided"}` |
| `Authorization: ""` | 401 | same |
| `Authorization: Bearer` (no token) | 401 | same |
| `Bearer <20 random chars>` | 200 | full data |
| `Basic xyz` | 401 | same (scheme is checked) |
| `Bearer <punctuation junk>` | 200 | full data |
| `Bearer <5000-char token>` | 200 | full data |
| `bearer sometoken123` (lowercase scheme) | 200 | case-insensitive scheme match |
| `?token=...` query param, no header | 401 | query param never read |
| 5 different tokens | 200 | byte-identical bodies |

Auth is enforced **only** on the stats POST route; `/`, `/spec`, and the PDF are public.

## 2. Route / method surface

| Path | Method | Status |
|---|---|---|
| `/reporting_api/v1/reporting/stats/json` | POST | 200 (only working combo) |
| same | GET/HEAD/PUT/PATCH/DELETE/TRACE | 404 |
| same | OPTIONS | 200 `OK` (CORS preflight) |
| `/stats/{csv,xlsx,excel}`, `/stats`, `/reporting`, `/v1`, `/reporting_api` | GET | 404 |
| `/reporting_api/v1/reporting/mailboxes` | GET | 404 |
| `/openapi.json`, `/docs`, `/redoc`, `/swagger*` | GET | 404 |
| **`/health`** | GET | **200 — undocumented, only extra live route** |
| `/healthz`, `/api`, `/users`, `/actors`, `/agents`, `/communities`, `/metrics`, `/reporting_api/v2/*`, `/.well-known/*` | GET | 404 |
| `/`, `/spec`, `/reporting-api-guide.pdf` | GET | 200, public |

`/health` body:
`{"ok":true,"service":"reporting-stats-api","endpoint":"POST /reporting_api/v1/reporting/stats/json","coverage":{"from":"2026-07-10","to":"2026-07-23"}}`
— no auth, undocumented, and it states the fixed data-coverage window.

## 3. Framework fingerprint

`server: railway-hikari` (Railway edge), `x-powered-by: Express`, weak ETags, gzip.
Routing/404/400 behavior is textbook Express. But the 422 is **not** Express-native:
`422 text/plain`, ``Failed to deserialize the JSON body into the target type: missing
field `from_date` `` — the signature of Rust `serde` extractors (Axum/Actix). Suggests a
mixed or deliberately disguised stack. No OpenAPI surface exists.

## 4. CORS

Preflight: `access-control-allow-origin: *`,
`access-control-allow-methods: POST, GET, OPTIONS`,
`access-control-allow-headers: authorization, content-type`, no `Allow-Credentials`,
no `Max-Age`. Every response (including 401s) carries `Access-Control-Allow-Origin: *`.
**A browser can call this API directly from any origin — no proxy needed for CORS.**

## 5. Rate limiting

80-request burst: 0 x 429, 80 x 200, 19.82 s (~4 req/s, client-bound). No `Retry-After`,
no degradation. No rate limit detected.

## 6. Latency & caching

1-day request: 169176 B constant across 8 repeats, p50 0.252 s / p90 0.540 s.
30-day hourly: 362109 B constant, p50 0.289 s / p90 0.306 s. Sizes identical across
repeats; latency does not scale with requested range or granularity — consistent with a
pre-baked fixture. No `Cache-Control`/`Last-Modified`; weak ETag stable across repeats.

## 7. Robustness

- Huge body (~50k junk filter objects) → 413. Cap between ~3.5 MB (accepted) and 4 MB.
- Filters nested 5000 deep → 200 in 0.42 s (filters not meaningfully parsed).
- Date range 1900–2100 → 200, same constant 362109 B, ~0.3 s.
- No timeouts observed; slowest response 0.54 s.

## 8. Doc fidelity: PDF vs `/spec` vs reality

PDF (530705 B, 5 pages) and `/spec` HTML are **word-for-word identical** on every
substantive claim — same source. No HTML comments, hidden text, or `<script>` tags in
either page; no planted clues.

Doc vs reality (infra layer):
- Doc frames auth as an API key; no key validation exists at all.
- `/health` exists, undocumented.
- No rate limit, body-size cap, or CORS policy is documented; all found empirically.

## 9. Mock/simulator signals

Byte-identical responses across tokens; constant sizes and latency regardless of range or
granularity; `/health` bakes in a fixed coverage window; junk/deeply-nested filters
accepted rather than validated. All consistent with a deterministic canned-fixture
backend.
