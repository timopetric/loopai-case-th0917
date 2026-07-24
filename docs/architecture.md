# architecture.md — Technical design & variations

Companion doc: [idea.md](idea.md) (problem, findings, product scope). This doc: how to build it under the stated constraints.

## 0. Constraints (from Timo)

- FastAPI + Python backend, `uv` for Python tooling.
- Frontend: CodeMirror experience; comfortable with React or Preact (prefers smaller).
- Single microservice: multi-stage Docker build, frontend built and served through FastAPI.
- Deploy target: Railway (Postgres available there if needed).
- One-night-sprint economics: minimize moving parts.

## 1. High-level shape (recommended)

```
                        ┌────────────────────────────────────────────┐
                        │  One container (Railway)                   │
 browser ── static ──▶  │  FastAPI                                   │
   │                    │   ├─ /            → built frontend (SPA)   │
   ├── /api/report ───▶ │   ├─ /api/*       → report engine          │──▶ upstream stats API
   ├── /api/export ───▶ │   ├─ CSV/XLSX exporters                    │    (fetched once, cached)
   └── /api/agent ────▶ │   └─ LLM call → ReportSpec                 │──▶ Anthropic API
                        └────────────────────────────────────────────┘
```

Everything flows through one typed core object:

```python
class ReportSpec(BaseModel):
    metrics: list[Metric]                 # validated enum of the 15 metrics
    date_from: date; date_to: date        # clamped to detected data window
    granularity: Literal["day","week","total"]
    group_by: Literal["agent","mailbox","none"]
    agent_ids: list[str] = []             # optional filter (client-side)
    mailbox_ids: list[str] = []
    sort: SortSpec | None = None
    layout: Literal["long","pivot"] = "long"   # rows=day×group vs days-as-columns
```

`ReportSpec` is the contract between UI, AI agent, engine, exporters, and shareable URLs. One schema, validated once by Pydantic, no divergence.

### Backend components

| Component | Design |
|---|---|
| **Upstream client** | One `httpx` call fetching the *widest* range with all metrics (upstream ignores most params anyway — see idea.md §2). Detects the real data window from returned `ticks`. |
| **Dataset cache** | In-process: parsed response → tidy structure, cached with short TTL (~5 min) + startup warmup. Data is deterministic, so this is safe and makes every user interaction instant and resilient to upstream flapping. |
| **Report engine** | Pure functions: slice dates → re-bucket (day→week/total by summing counts; time metrics summed then divided by summed `_count` for correct weighted averages) → group by agent/mailbox → filter → sort → `ReportTable` (columns + rows + totals + warnings). |
| **Exporters** | CSV via stdlib `csv`; XLSX via `openpyxl` (header styling, column widths, totals row — nothing fancier). Both consume `ReportTable`, so preview and files can never disagree. |
| **AI agent endpoint** | `POST /api/agent {message, current_spec}` → Claude with `ReportSpec` JSON schema as a forced tool call → validated spec + one-sentence summary of what it changed. Errors/no-key → clear message, UI still fully usable manually. |

**Engine library choice:** plain Python dicts/lists. The dataset is ~14 buckets × ~108 actors × ~24 arrays — trivially small. `pandas`/`polars` would only add image weight and hide the (simple) aggregation logic we want to be legible. `openpyxl` is the only data dependency beyond FastAPI/httpx.

### Frontend

**Preact + Vite + TypeScript** (matches "prefers smaller"; identical dev model to React, ~4 kB runtime). Single page, three zones:

1. **Builder panel** — metric multi-select, date range (clamped to data window), granularity, group-by, filters, layout toggle.
2. **Preview** — sortable table + totals row; small time-series chart (`uPlot` or hand-rolled SVG — no heavy chart lib); warning banners (mailbox reliability, units assumption) rendered from engine-provided `warnings`.
3. **Agent chat panel** — messages + "applied changes" chips; each agent reply visibly updates the builder controls (the agent drives the same state the human does).

State: single `ReportSpec` in a store (`@preact/signals`), serialized into the URL query string → shareable links for free. Downloads are plain `<a href="/api/export?...">` — the browser does the rest.

CodeMirror is **not needed** for V1 (no code editing in the product). Optional stretch: a "raw spec" CodeMirror JSON tab for power users — nice nod, zero priority.

## 2. Decision log with variations

### D1 — Where aggregation lives
- **(a) Backend engine (chosen).** Exports and preview share one code path; agent-generated specs are validated server-side; frontend stays thin.
- (b) Frontend calls upstream directly (CORS is open) and aggregates in JS. Fewer server hops, but exports would need duplicate logic (or client-generated files), and the units/reconciliation logic would live in the least testable place.
- (c) Hybrid: backend proxies raw, frontend aggregates. Worst of both — two places to get it wrong.

### D2 — Upstream data strategy
- **(a) Fetch-full + cache + TTL (chosen).** Justified by proven determinism; instant UX; one place to normalize units.
- (b) Pass-through per request. Honest to "live API" framing, but slower, N× upstream load, and pointless since params are ignored upstream.
- (c) Snapshot into Postgres at startup. Real DB queries, but adds a service for zero functional gain at this data size.

### D3 — Persistence
- **(a) None for V1 (chosen).** Spec-in-URL covers sharing; Railway Postgres listed as the V2 path for saved/named reports + agent conversation history. Keeps compose/deploy single-service.
- (b) SQLite volume for saved reports. Cheap, but Railway volumes + one-night sprint = avoidable risk.
- (c) Postgres now. Only if saved reports get promoted into V1.

### D4 — AI agent shape
- **(a) Single forced-tool call emitting `ReportSpec` (chosen for V1).** Deterministic surface, cheap, impossible to fabricate numbers; conversation history passed for refinement ("now only the Returns inbox").
- (b) Agentic loop with tools (`get_schema`, `run_report`, `inspect_result`) so the agent can *look at* results and iterate ("who was the slowest?" → runs report, reads it, answers). Much stronger demo; ~2–3× the work. **Promote if time allows** — the brief explicitly spotlights the agent.
- (c) Text-to-answer (agent replies with numbers in prose). Rejected: unverifiable, hallucination-prone, doesn't produce a reusable report.
- Fallback without an API key: endpoint returns "agent unavailable, here's the manual builder" — the product never bricks on a missing secret.

### D5 — Frontend delivery
- **(a) Vite build in Docker stage 1, static files served by FastAPI (chosen).** Matches Timo's usual pattern; TS + JSX + HMR in dev.
- (b) Preact + `htm` from CDN, no build step. Fastest to start, but no TS and CDN dependency at runtime.
- (c) Jinja + htmx server-rendered. Fine for forms, awkward for a live interactive builder + chat.

## 3. Deployment

**Dockerfile (multi-stage):**
1. `node:22-slim` — `npm ci && npm run build` → `frontend/dist`.
2. `python:3.13-slim` + `uv` — `uv sync --frozen --no-dev`; copy backend + `dist`; `CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

**Railway:** deploy from repo (Railway auto-builds the Dockerfile), respect `$PORT`, env vars: `ANTHROPIC_API_KEY`, `UPSTREAM_BASE_URL` (override for tests), `UPSTREAM_TOKEN` (any string). Postgres = one click later if V2 needs it.

**docker-compose:** single service for parity with prod (`docker compose up` = the "one command" submission requirement); a commented-out `postgres` service ready for V2.

**Local dev:** `uv run uvicorn --reload` + `npm run dev` with Vite proxying `/api`.

## 4. Repo layout (proposed — not created yet)

```
loopai/
├─ pyproject.toml            # uv-managed
├─ Dockerfile                # multi-stage: frontend build → FastAPI runtime
├─ docker-compose.yml
├─ README.md                 # run / built / assumed / next (the graded artifact)
├─ app/
│  ├─ main.py                # FastAPI app, static mount, routes
│  ├─ models.py              # ReportSpec, ReportTable, Metric enum
│  ├─ upstream.py            # httpx client, cache, window detection, unit normalization
│  ├─ engine.py              # slice/re-bucket/group/sort → ReportTable (pure, tested)
│  ├─ exporters.py           # CSV / XLSX from ReportTable
│  └─ agent.py               # Claude → ReportSpec
├─ frontend/                 # Preact + Vite + TS
│  └─ src/{app.tsx, builder/, preview/, chat/, state.ts}
├─ tests/                    # engine + exporter tests on a fixture response
├─ docs/                     # this file, idea.md, problem statement
└─ scratch/                  # probes & saved responses (evidence trail — keep in repo)
```

`scratch/` stays in the repo deliberately: the probe scripts and saved responses *are* the investigation the brief asks to see, and `resp-q1-full-14day.json` doubles as the test fixture.

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Upstream changes/disappears during eval | Cache + bundled fixture fallback (`DEMO_MODE=1` serves the saved response) |
| Units assumption (hours) is wrong | Isolated in `upstream.py` normalization, one constant to flip; assumption stated in README and in-UI tooltip |
| Agent emits invalid spec | Pydantic-validated tool schema; on failure, one retry with the validation error, then graceful "couldn't build that" |
| Excel niceties eat the night | `ReportTable` → openpyxl is mechanical; styling capped at 30 min |
| Scope creep on the chart | One metric, one line/bars, or drop it — table is the product |
