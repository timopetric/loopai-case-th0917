# architecture.md — Technical design & variations

Companion docs: [idea.md](idea.md) (problem, findings, product scope) and [api-map.md](../old_decision_depricated/api-map.md) *(deprecated — superseded by [api-report-fresh.md](api-report-fresh.md))* (the definitive observed upstream contract — implement against it, not the official /spec). This doc: how to build it under the stated constraints. Structural patterns borrowed selectively from [PLAYBOOK.md](PLAYBOOK.md) (pobude playbook) — noted per section as "playbook:" with what we take and what we deliberately skip for one-night-sprint speed.

## 0. Constraints (from Timo)

- FastAPI + Python backend, `uv` tooling; config via **pydantic-settings** reading `.env` (playbook §3). `.env.example` committed.
- Frontend: **React** (+ Vite + TS) — chosen over Preact for execution speed with well-trodden patterns.
- Single microservice: multi-stage Docker, frontend built and served through FastAPI. Deploy: Railway.
- **No database, no mock mode; a 5-minute in-process memo of one dataset** (revised — see ADR-0001). The backend fetches the full Coverage Window from the real upstream and memoises that single normalised dataset for 5 minutes, slicing requested ranges locally. Saved response snapshots exist only as test fixtures and scratch evidence, never as a shipped runtime data path. *(Narrow exception: `DEV_FAKE_UPSTREAM` / `DEV_FAKE_LLM` serve fixtures for the verification loop and are refused outside development — ADR-0003.)*
- AI agent: **OpenRouter** (OpenAI-compatible), model **`qwen/qwen3.6-plus`** — slug confirmed live 2026-07-25, see §5. Orchestrated with **LangGraph** (kept minimal — see D4). Prompt templates as **`*.jinja`** files.
- Tool calls run **on the backend**; the frontend receives **SSE** events that are translated server-side into user-friendly messages/tags — internal tool names/args never leak.
- Backend is auth-gated (shared key/password in Settings) since it now hosts the agent chat (and pays for LLM tokens).

## 1. High-level shape

```
 browser (React SPA served from FastAPI)
   │  X-API-Key on every call (login screen stores it)
   ├── GET  /api/v1/meta          ── data window, agents, mailboxes, metric catalog
   ├── POST /api/v1/report        ── ReportSpec → ReportTable (preview)
   ├── GET  /api/v1/export        ── ReportSpec (query) → CSV / XLSX
   └── POST /api/v1/agent/stream  ── chat msg + current spec → SSE event stream
                 │
        ┌────────┴─────────────────────────────────────┐
        │ FastAPI (one container)                      │
        │  config.py   pydantic-settings (.env)        │
        │  upstream.py thin live client ───────────────┼──▶ real reporting API
        │  engine.py   slice/re-bucket/group/sort      │
        │  exporters   CSV / XLSX from ReportTable     │
        │  agent/      LangGraph loop, jinja prompts ──┼──▶ OpenRouter (qwen)
        │  api/v1/     routers; auth dependency ONCE   │
        └──────────────────────────────────────────────┘
```

One typed core object flows through everything — see §2.

## 2. ReportSpec — the contract

```python
class ReportSpec(BaseModel):
    metrics: list[Metric]                      # StrEnum of the 15 upstream metrics
    date_from: date; date_to: date             # validated against the Coverage Window:
                                               #   partial overlap → clamp + report adjustment
                                               #   zero overlap    → refuse, return the window
    granularity: Literal["day","total"]        # "week" dropped: the 14-day window starts on a
                                               # Friday, so week buckets are two ragged partials
    group_by: Literal["agent","mailbox","none"]
    agent_ids: list[str] = []                  # client-side filters (upstream ignores scope)
    mailbox_ids: list[str] = []
    sort: SortSpec | None = None
    columns_order: list[str] | None = None     # explicit column order ("switch the columns")
    layout: Literal["long","pivot"] = "long"   # rows=bucket×group  vs  buckets-as-columns.
                                               # pivot renders chart_metric ONLY — with several
                                               # metrics the column count multiplies and the CSV
                                               # becomes unreadable. The UI states this.
    chart_metric: Metric | None = None         # None → metrics[0]; validated ∈ metrics
    duration_display: Literal["avg","total"] = "avg"   # avg = Σvalue/Σcount per ticket
```

Produced/consumed by: builder UI (edits it), agent (edits it via tools), engine (executes it → `ReportTable`), exporters (CSV/XLSX from the same `ReportTable`), URL (serialized → shareable links). Pydantic validates it once, everywhere: agent output and UI input hit the identical validator, so the agent can never push the UI into a state a human couldn't reach. `ReportTable` (columns, rows, totals, `warnings[]`) is the second, derived object — warnings (clamped dates, units assumption, "agent×inbox cross not available upstream") originate in the engine and render as banners in the UI and as a notes row in exports.

### Table semantics (settled 2026-07-25)

- **Sort is applied *within* the bucket**, never globally. On a day × agent report, days stay in
  chronological order and rows are ordered inside each day. A global sort would silently destroy
  the time series the report exists to show. With `granularity: "total"` there is one bucket, so
  sorting is global by definition — which is what makes the leaderboard preset work.
- **`actioned_emails` renders `—` in the Total row** when grouped by Actor, with the existing
  warning explaining why. Not blank (reads as a bug) and not a number (wrong by 52%, §4.5 of the
  API report).
- **The `_count` behind an average is shown in the cell tooltip**, not as its own column. A cell
  reading `0.014 h` is untrustworthy without knowing whether it rests on one ticket or four
  hundred; a full column per Duration Metric is scope creep, an invisible denominator is a trap.

## 3. Backend components

| Component | Design |
|---|---|
| **`config.py`** | Playbook §3 verbatim: one flat `Settings` class, `.env` + env vars, `@lru_cache get_settings()` as DI seam, `environment` literal with `is_development`/`is_production`. Fields: see `.env.example`. |
| **`upstream.py`** | Thin live client + a 5-minute in-process memo (ADR-0001), no mock: one `httpx.AsyncClient`. Always requests **unscoped** and **full-window** — probing showed `scope` only selects mailbox-breakdown entries, and the full window costs ~40 ms more than one day. The Coverage Window comes from `GET /health` (also 5-minute memoised, hardcoded `2026-07-10 → 2026-07-23` only as an unreachable-fallback) and is the cache key, so an upstream redeployed with new dates is picked up without redeploying us. Unit normalization (hours assumption, `_count` handling) lives HERE, in one place. In unit tests this module is faked with the committed fixture via dependency override — fixtures are a test asset, never a runtime path. |
| **`engine.py`** | Pure functions: `ReportSpec` + normalized dataset → `ReportTable`. Date slice → re-bucket (sum counts; time metrics = Σtotal/Σcount weighted averages) → group by agent/mailbox → filter → sort → order columns → layout. No pandas — dataset is ~14×108, plain Python stays legible and testable. |
| **`exporters.py`** | CSV via stdlib, XLSX via `openpyxl`, both from `ReportTable` — preview and files can't disagree. **CSV is pure data**: units baked into column headers (`Avg resolve time (h)`), totals row, no preamble (anything above the header breaks naive parsing). **XLSX adds a second "Report info" sheet** carrying the spec summary, coverage window, the hours-not-seconds note, and `ReportTable.warnings` — the format people open by hand carries the caveats. |
| **`agent/`** | See §5. |
| **`api/v1/`** | Playbook §4: aggregate router with `Depends(require_api_key)` applied once; unauthenticated `/healthz`; error envelope handlers (trimmed: `ServiceError` + validation + catch-all, no request-id middleware for V1). |

**Auth.** `APIKeyHeader(name="X-API-Key", auto_error=False)` dependency (playbook §4), compared against `settings.app_api_key`. Frontend: a login screen that stores the key (sessionStorage) and attaches it to every request. This is a shared-secret gate, not user management — right-sized for a take-home whose backend spends LLM tokens. SSE caveat: native `EventSource` can't send headers — solved by using `fetch()`-based streaming for the agent (see §6), so the same header auth covers the stream; no tokens in URLs.

## 4. Configuration & files

- `.env.example` (committed, exhaustive, commented) ↔ `Settings` fields 1:1. `.env` gitignored.
- `.gitignore` covers `.env`, venv/node/dist/pycache. **Test fixtures are committed, never gitignored** (playbook §15: tests must pin fixtures).
- Prompt templates: `app/agent/prompts/*.jinja`, rendered with jinja2 (`report_agent_system.jinja`, `spec_diff_summary.jinja`, …). Templates get: current spec JSON, metric catalog with units gotchas, data window, tool guidance.

### Makefile — the single UX surface

```make
make backend    # uvicorn --reload on :8000        ← own terminal, live reload output
make frontend   # vite dev server on :5173         ← own terminal, live HMR output
make dev        # both together (convenience only; prefer the two above when debugging)
make test       # pytest — offline, no network, no LLM
make lint       # ruff + tsc --noEmit
make check      # lint + test in one command: the single green signal
make build      # docker build -t timopetric/caseth0917:$(TAG)
make run        # run the built image on :8000     ← the §12 browser-checklist target
make push       # push :$(TAG) and :latest to Docker Hub
```

`backend` and `frontend` are deliberately separate so each runs in its own terminal with its
own live output — reload errors and Vite HMR messages are the fastest debugging signal there is,
and interleaving them into one stream hides both. `make dev` exists for convenience, not for
debugging. `make run` earns its place because §12 requires the browser checklist to run against
the **built image**, where a build-time-config mistake would surface and the dev server cannot.

### Logging — loguru, kept plain

One loguru sink to stderr, level from `LOG_LEVEL`, stdlib and uvicorn loggers intercepted so
everything shares one format. No file sinks, no rotation, no request-id middleware — the
platform captures stderr and that is enough here.

What gets logged: upstream fetches (cache hit/miss, coverage window), Assistant Tool Steps with
tool names and durations, **Repairs** applied, and every error with a stack trace. What must
**never** be logged: the shared API key, the OpenRouter key, or any full prompt. Tool names are
fine server-side — they only must not reach the browser (§6).

## 5. AI agent

**Stack:** LangGraph's prebuilt ReAct agent (`create_react_agent`) + `ChatOpenAI` pointed at OpenRouter (`base_url`, `OPENROUTER_API_KEY`, `model=settings.llm_model`). Rationale vs the alternatives:
- **LangGraph minimal (chosen):** tool loop, retries, and `astream_events` (token + tool lifecycle events) out of the box; the "graph" is one agent node — no custom state machines.
- LangChain classic agents: deprecated in favor of LangGraph — no.
- DeepAgents: planning/sub-agent machinery for long-horizon tasks — overkill for "edit a spec, run a report".
- Hand-rolled openai-sdk loop: fewest deps and totally transparent; the fallback if LangGraph streaming fights us. The tool schemas are generated from pydantic either way, so switching costs little.

**Tool surface (field-scoped, generated from pydantic schemas).** Each write tool covers a
**cohesive unit** whose validation is self-contained, so no single call can leave the spec in
a transiently invalid state (see ADR-0002):
- `set_date_range(from, to)` — both bounds together; a two-tool version would allow an inverted range mid-sequence.
- `set_metrics(list)` · `set_grouping(by)` · `set_sort(column, direction)` · `set_columns(order)` · `set_chart(metric)` · `set_layout(granularity, layout)`
- `run_report()` — executes the current spec, returns a compact table summary (the Assistant reads results to answer questions like "who was slowest?").
- `get_meta()` — actors/mailboxes/metrics/coverage window, so the model can resolve names → ids.

Each write tool applies immediately and emits its own `spec` SSE event, so the builder
controls visibly move one step at a time rather than snapping into place in a single frame —
this progressive rendering is the main reason for field-scoping over one atomic patch.

**Repair, don't reject.** When a call invalidates an earlier field (e.g. `set_metrics` drops
the metric that `chart_metric` or `sort` pointed at), the backend **repairs** the spec —
resets `chart_metric` to `metrics[0]`, clears the dangling sort — rather than returning a
validation error. The tool result reports what changed:
`{"ok": true, "adjusted": ["chart_metric reset to resolved", "sort cleared"]}`, so the model
can say so in its prose, and the same adjustments land in `ReportTable.warnings`. Genuine
input errors (bad enum, bad date) still return a validation error for one retry.

**Repair vs error — the full taxonomy:**

| Situation | Verdict |
|---|---|
| `set_metrics` drops the metric `chart_metric` or `sort` pointed at | Repair — reset to `metrics[0]` / clear sort |
| `set_grouping` orphans a sort on a group column | Repair — clear sort |
| `set_columns` references a column that no longer exists | Repair — drop it from the order |
| `set_chart(m)` where `m ∉ metrics` | Repair — **auto-add `m` to metrics**, then set it |
| `set_date_range` partially overlaps the Coverage Window | Repair — clamp, report |
| `set_date_range` misses the Coverage Window entirely | Error — refuse, return the window |
| `set_metrics([])` | Error — a report with no metrics isn't a report |
| Bad enum, malformed date, unknown actor id | Error — one retry |
| Grouping by Actor with `actioned_emails` selected | Neither — a `Warning` (valid number, non-additive) |

**Batch reconciliation.** When one model message carries several tool calls, apply them in
order and then **discard any adjustment to a field that a later call in the same batch
explicitly set**. Implementation is a `dict[field, adjustment]` with a delete on explicit
set — no net-diffing. Without this, `set_metrics` followed by `set_sort` reports "sort
cleared" for a sort that exists by the time the Assistant speaks, and it narrates something
untrue. With a single tool call per message the rule is a no-op. (User-facing chips are
already net-correct, being derived from the validated spec diff — §6; this protects the
Assistant's *prose*, which is written from tool results.)

*Open work (post-sprint):* the repair rules deserve a proper state design and a dedicated
test suite before this is production-grade — currently specified, not yet exhaustively tested.
The batch-reconciliation rule in particular needs tests for multi-call messages.

The agent never emits numbers from memory: quantitative answers must come from `run_report` output, and spec changes only through `update_spec` — hallucination-resistant by construction. Chat history per session kept in memory (no DB in V1).

**Patch vs full replacement — decided by the scratch lab** (`scratch/agent-spec-lab/`, 63 offline tests green + a live fixture-drift check, see its `LAB_NOTES.md`): **patch semantics, never full-spec replacement.** Demonstrated failure mode: a spec with `layout="pivot"` + a filter + a sort, "replaced" by an LLM that only restates the fields it's reasoning about, silently loses all three to pydantic defaults. Patch = "field not mentioned means leave it alone", which is what incremental requests ("switch the columns") need. Implementation notes proven in the lab:
- Merge patch into spec via `spec.model_dump()` + dict update + `ReportSpec.model_validate(...)` — not `model_copy(update=...)`, which skips nested validation.
- Validate the **merged spec**, not the patch alone (cross-field rules like `date_from <= date_to` only exist post-merge); on failure, feed the validation error back to the model for one retry (bad-enum, bad-JSON and inverted-dates retry paths all tested).
- The lab proved **patch over full replacement**; it did *not* settle tool granularity. Field-scoped tools are themselves patch semantics ("field not mentioned means leave it alone"), so they satisfy the lab's finding — see ADR-0002 for why granularity went the other way.
- The system prompt **must** spell out the units gotcha (time metrics = totals in hours + `_count` companions), or the agent produces confidently wrong numbers.
- Engine behaviors proven by the extended assumption suite (every spec capability tested against the real unscoped dataset): reconciliation warnings are detected **dynamically** (only `actioned_emails` under agent grouping actually trips it); an agent×mailbox cross request raises a typed `CrossBreakdownNotSupported` instead of returning fabricated numbers; re-bucketed averages are weighted (Σ/Σ) and verified against raw arrays; column reordering and long↔pivot reshaping are proven lossless.
- Caveat: only the harness plumbing is proven — no real model has exercised these schemas yet (no `OPENROUTER_API_KEY` available). First real-model smoke test is a day-one implementation task.

**Verified against the real model — 2026-07-25** (`qwen/qwen3.6-plus` via OpenRouter, 11 calls,
~12.5k tokens; script `scratch/fresh-eyes/llm-smoke-tool-calling.py`, raw results
`llm-smoke-results.json`):

| Assumption | Result |
|---|---|
| Model slug resolves | **Pass** — `qwen/qwen3.6-plus` echoed back exactly |
| Picks the right tool from 9 | **Pass** — `set_date_range` + `set_metrics` with correct args |
| **Parallel tool calls in one message** | **Pass — 3 calls in a single assistant message, stable across runs.** The batch-reconciliation rule is therefore load-bearing, not theoretical |
| Strict enum discipline | **Pass** — asked for "customer satisfaction" it refused in prose and listed the real enum; no invalid enum value in any test |
| Error-feedback retry | **Pass** — corrects, though it asks the user rather than auto-substituting a metric (safe; our Repair happens backend-side anyway) |
| Out-of-coverage dates | **Pass** — asked for June 2026 it called `get_meta()` to check rather than blindly setting the range. Implies `get_meta` must stay cheap |
| `tool_choice="none"` | **Partial — see guard 1** |
| Streaming tool calls | **Pass with caveat — see guard 2** |

**Guard 1 — never parse assistant prose for tool calls.** Under `tool_choice="none"` OpenRouter
does suppress the `tool_calls` array, but the model responds by emitting a *fenced JSON blob
impersonating tool calls*, inventing a schema that does not exist (`edit_report_spec`,
`resolved_tickets`). Two consequences: (a) no code path may ever scan assistant content for
tool-call-shaped JSON and act on it — that is a live execution risk; (b) the forced final answer
would otherwise show the user a JSON code block instead of a sentence. **On the final Tool Step,
omit the `tools` parameter entirely rather than merely setting `tool_choice="none"`**, and word
the injected instruction as "summarise in plain prose, no JSON, no tool calls". Re-test this
specific path once implemented.

**Guard 2 — the SSE presenter must absorb a reasoning preamble, and show it as a `thinking` event (§6).** This is a reasoning model: in a
streamed single-tool-call request, **87 of 103 chunks were `reasoning` deltas** before the first
`tool_calls` delta. The presenter needs a "thinking…" status event covering that gap, or the UI
looks hung. Good news for reassembly: `id` and `function.name` arrive together in one delta, with
`arguments` streamed after — no cross-chunk id/name buffering needed. Reasoning also inflates
completion tokens (~484/call average here), so if latency bites, disabling reasoning via
OpenRouter's per-request option is the first lever to try.

## 6. Agent streaming: SSE design

`POST /api/v1/agent/stream` (fetch-streamed SSE; POST because the request carries message + current spec + history cursor; auth via the normal `X-API-Key` header — this is why we don't use native `EventSource`).

**Two event vocabularies, translated server-side.** Internally the loop produces raw events (tool name, args, model deltas). A backend-only `presenter` maps them to a small, stable, UI-facing event taxonomy — the frontend never sees tool names, arguments, prompts, or model ids:

```
event: thinking    data: {"state": "start"}                        # first reasoning delta arrives
event: thinking    data: {"state": "end", "ms": 3200}              # first tool_call/content delta arrives
event: status      data: {"text": "Updating the report…"}          # from tool_call_started(set_metrics)
event: chips       data: {"chips": ["Grouping: by agent",          # from validated spec diff
                          "Added metric: handle_time"]}
event: spec        data: {"spec": {...full validated ReportSpec}}   # frontend applies → live re-render
event: token       data: {"text": "Here's"}                        # assistant prose, streamed
event: done        data: {"summary": "...", "spec_version": 7}
event: error       data: {"text": "I couldn't build that report."}  # sanitized; details only in logs
```

**The `thinking` event exists because the model reasons before acting** — measured, 87 of 103
stream chunks were `reasoning` deltas before the first actionable one (§5, guard 2). Without it
the UI sits silent for seconds and reads as hung. The presenter emits `thinking: start` on the
first reasoning delta and `thinking: end` when the first `tool_calls` or `content` delta arrives;
it fires once per model call, so a multi-step turn shows the indicator repeatedly — which is
honest, since the Assistant really is thinking again each time.

**The `thinking` event itself carries no reasoning text — only state.** It exists so the UI has
something to show the instant reasoning starts, independent of whatever the content stream ends up
containing.

**Reasoning text streams to every user, in every environment (ADR-0005).** Alongside `thinking`,
the presenter also streams `event: thinking_text` with the model's raw reasoning, unconditionally —
not gated on `settings.is_development` or any other flag. The frontend renders it as markdown in a
collapsible panel, open by default while a turn is in flight. Raw chain-of-thought routinely names
internal tools (`set_metrics`, `get_meta`) and enum values, so this is a deliberate, one-way
reversal of the earlier "internal tool names, arguments and prompts never reach the browser" rule
as applied to reasoning text specifically — that rule is unchanged for `token`/`chips`/`spec`/
`error`, which still never carry a tool name, a raw argument, or a prompt fragment. See ADR-0005
for the rationale, the alternatives considered (keeping the gate; sanitizing the text first), and
the accepted tradeoff (tool internals visible in the reasoning panel, distinct from the Assistant's
actual answer).

Flow for "switch the columns": user sends message → `status` ("Updating the report…") → backend executes `update_spec`, validates, diffs old vs new spec → `chips` (["Reordered columns"]) + `spec` → frontend puts the new spec into its store → builder controls visibly move and the preview refetches `/report` (or re-renders from included table) → `token`s stream the assistant's one-line confirmation → `done`.

Practices: `sse-starlette` `EventSourceResponse`; heartbeat comments every ~15 s (Railway proxy timeouts); client uses `@microsoft/fetch-event-source` (native retry semantics, headers, POST); one stream per message (request-scoped, no long-lived socket to babysit); `spec` events carry the **full validated spec** not a diff — idempotent, resilient to a dropped chip event; the chips are presentation sugar, the spec event is the source of truth.

## 7. Frontend (React + Vite + TS)

Single page, three zones + login gate:
1. **Builder panel** — metric multi-select, date range (clamped to window from `/meta`), granularity, group-by, filters, column order (drag or up/down buttons), layout toggle.
2. **Preview** — sortable table, totals row, warning banners from `ReportTable.warnings`; CSV/XLSX buttons = plain links to `/export` (key attached via fetch → blob download, since headers are needed).
   **Chart** (`recharts`): line chart over ticks of the single `spec.chart_metric`, one series per group row, **top 8 by total descending** with the remainder dropped and the legend noting "+N not shown" (an "Other" aggregate would be wrong for `actioned_emails`, which is non-additive across Actors). Hidden entirely when the spec has no time axis (`granularity: "total"`). Recharts chosen over hand-rolled SVG for the tooltip/axis/legend affordances — the dataset is 14 points × ≤8 series, so bundle size and performance are both irrelevant here.

   Chart rules (from the dataviz skill; these are non-negotiable):
   - **One metric, one y-axis. Never a dual axis** — this is why `chart_metric` is singular. Counts and hours cannot share a scale.
   - **Colour follows the entity, not its rank.** Assign a hue by a stable hash of the Actor/Mailbox `id` into a fixed ordered palette — *not* by position in the top-8 list. Otherwise changing the date range reshuffles the ranking and repaints every surviving series, which reads as the chart changing subject.
   - **Never generate a 9th hue.** The 8-series cap is the categorical palette's length; beyond it we drop and say so.
   - Legend always present for ≥2 series; ≤4 series also get direct labels, so identity is never colour-alone. The report table beneath is the required table view.
   - Crosshair + tooltip on hover by default; 2px lines, recessive grid and axes; values and labels wear text tokens, never the series colour.
   - Dark mode is a **selected** set of steps validated against the dark surface, not an automatic inversion. Run the palette validator rather than eyeballing CVD safety.
3. **Agent chat** — messages, streaming tokens, `chips` rendered as tags on the agent's message; every `spec` event updates the same store the builder edits, so agent actions are visibly "the agent moving the controls".
   **Thinking indicator:** on `thinking: start` render an animated “Thinking…” row with an elapsed-seconds counter; clear it on `thinking: end`. It reappears for each model call in a multi-step turn. Given a measured multi-second reasoning preamble before the first tool call, this is the difference between “working” and “broken” — it is not decoration. No reasoning *text* is shown outside dev mode (§6).

State: one `ReportSpec` store (Zustand — tiny, Claude-familiar), synced to URL query for shareable reports. No CodeMirror in V1 (optional "raw spec JSON" tab later).

**Presets.** Three, seeded as `ReportSpec` literals: **day × agent** (the client's verbatim ask — loads on first paint), **day × inbox**, and **agent leaderboard** (`granularity: "total"`, grouped by Actor, sorted desc).

*Future preset ideas — **not built in this version**, recorded so they aren't re-invented.* Each is expressible as a plain `ReportSpec` (no engine changes), and all respect the data's limits — no agent×inbox cross, no sub-day buckets, inside the Coverage Window:

| Preset idea | Spec shape | Why it's interesting |
|---|---|---|
| Backlog pressure | `new_tickets` + `resolved`, daily, no grouping | The clearest "are we keeping up?" view; the two lines diverging is the whole story |
| Weekday vs weekend | any counter, daily, no grouping | The data has a genuine 5–8% weekend collapse — a striking demo, and a warning against unaligned 7-day comparisons |
| First-response speed | `time_to_first_reply` avg, by Actor, total | "How fast" in the client's own words |
| Inbox workload balance | `new_tickets`, by Mailbox, total, sorted desc | Answers staffing questions the day×inbox table only implies |
| SLA hot-spots | `sla_breaches`, by Mailbox, total, sorted desc | 4 073 breaches in the window; concentration is the useful signal |
| Capacity view | `handle_time` with `duration_display: "total"`, by Actor | The "how much work" counterpart to the avg-based leaderboard |

**Gotcha for any average-based leaderboard:** ranking by a Duration Metric average surfaces Actors with one or two tickets at both extremes (single-ticket `resolve_time` ranges 0.012–648 h). Such a preset needs a minimum `_count` threshold, or it ranks noise. Not solved in this version — another reason these are deferred.

**Assumptions modal.** A persistent coverage banner (`Data: 10–23 Jul 2026`) opens a modal listing the doc-vs-reality assumptions — hours not seconds, daily UTC buckets only, no agent×inbox cross-tab, `actioned_emails` non-additive across Actors, `open` always zero. Same content as the XLSX "Report info" sheet, one source.

**Auth failure.** Any 401 from our API clears the stored key, returns to the login screen, and preserves the current spec in the URL so the user lands back on the same report after re-entering it. Identical handling for a 401 on the SSE stream. The key is a non-expiring shared secret, so a mid-session 401 means the server restarted with a different key — there is no token-refresh path to build.

## 8. Decision log (updated)

- **D1 aggregation on backend** — unchanged (shared path for preview/exports/agent).
- **D2 upstream strategy — revised again, now final: full-window fetch + 5-minute in-process memo (ADR-0001).** No MOCK switch, no boundary ABC, no database — one thin client module, faked in tests via dependency override with committed fixtures. The earlier "no cache at all" position was superseded once probing showed every response is the same 362 KB payload regardless of parameters: memoising one dataset keyed on the `/health` Coverage Window costs nothing and is what lets an out-of-range request be refused locally instead of silently answered.
- **D3 persistence: no database at all** — not even as a V2 path. Spec-in-URL covers sharing; chat history is per-session in memory. If "saved named reports" ever becomes real, revisit — but nothing in this product needs a DB, and Postgres would be pure infrastructure theater here.
- **D4 agent: LangGraph minimal ReAct + OpenRouter/qwen** — replaces "single forced tool call". Structured edits via pydantic-validated tools; streaming via §6. Fallback: hand-rolled loop if framework streaming misbehaves; graceful "agent unavailable" without an API key.
- **D5 frontend: React + Vite** — replaces Preact (speed of execution over bundle size).
- **D6 auth: shared X-API-Key** in Settings + login screen — new.
- **Playbook adoptions (7, all one-file-or-one-rule):** `config.py` pattern, auth-once-on-router, error envelope, `.env.example` discipline, committed-fixtures rule, `.python-version`, thin Makefile, small `conftest.py`, root `AGENTS.md` router (+ `CLAUDE.md` symlink), and the principle that upstream DTO shapes never surface as API models. **Logging: loguru**, single stderr sink, no file/rotation machinery.
- **Playbook skips (deliberate, one-night sprint):** Postgres/alembic/repositories (no DB at all), the boundary ABC+factory+MOCK idiom (a single thin client + test-time dependency override suffices), request-id middleware + loguru contract (std logging OK), CI/release machinery, ADR/issue tracker, integration-test tier (unit tests on engine/exporters/agent-loop with the committed fixture), digest-pinned/rootless Docker hardening (basic multi-stage only).

## 9. Deployment

Dockerfile multi-stage: **`node:24-slim`** builds `frontend/dist` → `python:3.13-slim` + `uv sync --frozen --no-dev`, copy app + dist, `CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

*Node version (checked 2026-07-25):* **24 "Krypton" is Active LTS**; 22 "Jod" has dropped to Maintenance and 26 is Current-but-not-LTS until October. Use 24. This is a build stage only — no Node reaches the runtime image, so the choice carries no production risk and no attack surface.

*Frontend stack, latest at 2026-07-25:* `vite@8.1.5`, `react@19.2.8`, `recharts@3.10.0`, `typescript@7.0.2`, `zustand@5.0.14`. Pin them in `package.json` and commit the lockfile — a local Docker build with a floating range is exactly how "works on my machine" ships. Railway env vars = `.env.example` minus local-only ones.

**Image is built locally and pushed to public Docker Hub `timopetric/caseth0917`**; Railway deploys that image rather than building from source (no registry credentials needed). Tag each push with a version *and* `latest`, so a Railway redeploy is unambiguous about what it pulled. Local arch is x86_64 and Railway runs amd64, so no cross-build flags. This is safe only because the frontend has **zero build-time configuration** — no `VITE_*` variables anywhere, all API calls use relative `/api/v1` paths against the same origin FastAPI serves the SPA from. The Vite dev server proxies `/api` to `localhost:8000` so dev and prod are identical from the frontend's point of view. Never introduce a build-time env var here: it would silently bind the image to the machine that built it, and the failure appears only in the browser, in production, after a green deploy. `docker compose up` = one-command run (single service, nothing else). Local dev: `uv run uvicorn --reload` + Vite dev server proxying `/api`.

## 10. Repo layout (proposed — not created yet)

```
loopai/
├─ pyproject.toml  uv.lock  .env.example  .gitignore
├─ Dockerfile  docker-compose.yml  README.md  Makefile (thin: dev/test/build)
├─ app/
│  ├─ main.py            # create_app(), static mount, healthz, v1 router
│  ├─ config.py          # pydantic-settings (playbook §3)
│  ├─ models.py          # ReportSpec, SpecPatch, ReportTable, Metric
│  ├─ upstream.py        # thin live client + unit normalization
│  ├─ engine.py  exporters.py
│  ├─ agent/             # loop.py, tools.py, events.py, presenter.py, prompts/*.jinja
│  └─ api/v1/            # router.py, routers/{report,export,agent,meta}.py, deps.py (auth)
├─ frontend/             # React + Vite + TS: src/{builder,preview,chat,state,api}
├─ tests/                # engine, exporters, spec validation, agent loop w/ fake LLM
│  └─ fixtures/          # committed upstream snapshots (test-only, never a runtime path)
├─ plans/decisions/      # trusted spec: this file, idea.md, CONTEXT.md, adr/, PLAYBOOK.md
└─ scratch/              # probes, saved responses, agent-spec-lab (evidence trail)
```

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Upstream changes/vanishes during eval | Accepted risk (direct-call decision): no runtime fallback; committed scratch snapshots would let us wire an emergency stub quickly if it ever dies |
| Stale data served from the 5-minute memo | Acceptable: the upstream dataset is provably static across calendar days, so the memo can only be stale about a dataset that does not change. The `/health` Coverage Window is re-read on the same interval, so a redeployed upstream is picked up within 5 minutes (ADR-0001) |
| Units assumption (hours) wrong | Isolated in `upstream/normalize.py`; README + UI tooltip state it |
| qwen tool-calling quality via OpenRouter | **Largely retired 2026-07-25** — smoke-tested live against the 9-tool strict-enum surface (§5): correct tool selection, 3 parallel calls in one message, zero enum hallucination across all tests. Two residual guards remain: never parse assistant prose as tool calls, and absorb the reasoning-delta preamble in the SSE presenter. `LLM_MODEL` stays swappable. |
| LangGraph streaming ↔ SSE impedance | Presenter isolates the mapping; fallback to hand-rolled openai-sdk loop behind the same event taxonomy |
| SSE through Railway proxy | Heartbeats, one-stream-per-message, client auto-retry |
| Excel/chart polish eats the night | Time-capped; table + CSV are the product's core |

## 12. Verification loop — the autonomy ladder

Unit tests cover pure functions; none of them prove the *app* works. This section defines three
levels of verification, cheapest first. **A coding agent should climb only as far as the change
requires, but must reach level 3 before declaring the work done.**

### Level 1 — `make check` (offline, free, after every edit)

Lint, typecheck, unit tests and **API-level tests** in one command. The API-level tests
(`test_api.py`) drive the real routes in-process via FastAPI's `TestClient` with `upstream`
faked from the committed fixture and a **fake LLM** returning scripted tool calls. No network,
no Docker, no tokens. They catch what unit tests structurally cannot — the seams:

- the auth dependency is actually attached (a request without a key is rejected)
- export routes return spreadsheet content-types, and the CSV parses with a standard reader
- a **Report Spec** survives a round-trip through URL query parameters, so shared links work
- the SSE stream emits well-formed frames in the right order (`thinking → status → spec → token → done`)
- the Tool Step budget forces a final prose answer
- **no tool name, argument or prompt fragment appears anywhere in the stream**

This is the loop that makes an agent autonomous: a deterministic full-stack red/green it can run
unattended after every edit.

### Level 2 — browser against dev fakes (free, no tokens, no upstream dependency)

`make run` the built image with `DEV_FAKE_UPSTREAM=1 DEV_FAKE_LLM=1` (ADR-0003), then drive it
with **Chrome DevTools MCP**: open the app, sign in, click through presets, change metrics and
dates, download an export, send the Assistant a request and watch the controls move. Read the
console and network panels — a 401 loop, a CORS surprise, or a build-time value baked to
`localhost` surface here and nowhere else.

Use this level for anything about layout, interaction, wiring or copy. It is fast, repeatable
and costs nothing, so an agent can iterate on the UI, screenshot the result, notice its own
mistakes and fix them without human involvement. The UI shows a fake-mode banner throughout, so
screenshots cannot later be mistaken for live evidence.

### Level 3 — browser against the real thing (costs tokens; required before "done")

Same walkthrough, `make run` with real credentials: live upstream, live OpenRouter key. This is
the only level that proves the units are right against today's data, that the **Coverage
Window** is read correctly from `/health`, and that the real model drives the nine tools as the
smoke test predicted. Run it last, run it once, and read the output rather than assuming it.

### The checklist (levels 2 and 3)

Each row maps to a decision capable of regressing silently:

| Check | Guards |
|---|---|
| Coverage banner shows the window from `/health` | `/health` wiring + fallback (ADR-0001) |
| A date outside coverage is refused, not silently substituted | the upstream fail-open trap |
| Duration column header reads `(h)` and the value is hours | the units finding |
| Hovering a duration cell reveals the underlying count | invisible-denominator trap |
| `actioned_emails` shows `—` in the Total row when grouped by Actor | non-additive metric |
| `set_chart` on an unselected metric adds a column and says so | Repair reporting (ADR-0002) |
| Assistant request updates controls **incrementally**, not in one snap | field-scoped tools |
| "Thinking…" appears within ~1 s of sending, then clears | `thinking` event wiring |
| No tool names or enum values appear anywhere in the chat UI | prose/reasoning containment |
| Chart hides when `granularity: "total"` | chart mode rule |
| A series keeps its colour when the date range changes | entity-stable colour |
| XLSX has a second "Report info" sheet | export split |
| CSV parses with `pandas.read_csv` with no preamble rows | export split |
| A shared URL reproduces the report exactly | spec-in-URL |
| Sign-out then a bad key returns to login with the spec intact | 401 handling |

*Status:* `chrome-devtools-mcp@chrome-devtools-plugins` is configured and available in new
sessions. Levels 2 and 3 must run against the **built image**, not the dev server — that is
where a build-time-configuration mistake would first appear, and the dev server cannot catch it
by construction.
