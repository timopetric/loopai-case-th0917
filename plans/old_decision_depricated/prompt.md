> **DEPRECATED (2026-07-25).** Spent process artifact — the fresh-eyes prompt that produced
> [`plans/decisions/api-report-fresh.md`](../decisions/api-report-fresh.md). Kept only to show how the
> independent verification was set up. **Not a specification.**

# Fresh-eyes prompt

Copy-paste everything below the line into a new Claude Code session. It intentionally does NOT contain our API findings or design conclusions — the point is an independent re-derivation. (For the curious: our own results live in `docs/idea.md`, `docs/architecture.md`, `docs/api-map.md`, `scratch/` — the prompt tells the agent to compare against them only at the very end.)

---

You are getting fresh eyes on a take-home assignment. A previous session has already researched this; you must NOT read its conclusions until the final step (explicitly listed below), because the whole point is to independently verify. Form your own conclusions from primary evidence first.

## The assignment

This is a take-home ("Case No. TH-0917") from InTheLoop, a helpdesk/support-inbox analytics company. Read the brief yourself at:

- https://ai-homework-production-2423.up.railway.app/ (the assignment brief)
- https://ai-homework-production-2423.up.railway.app/spec (the API quick-start guide)
- https://ai-homework-production-2423.up.railway.app/reporting-api-guide.pdf (PDF of the guide)

Short version: a client with many support agents and many shared inboxes wants visibility into who did what, where, and how fast. The literal ask is a per-day/per-agent/per-inbox CSV, but the deliverable is: a configurable in-browser report builder, CSV + Excel export, and an AI agent that builds reports from plain-English requests. There is exactly one data source: `POST https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json` (bearer auth). The brief warns the docs may be unreliable and says candidates are graded on judgment, stated assumptions, and prioritization under a one-night deadline — not polish.

## Fixed decisions (made by the project owner — do not relitigate, do build on)

- Backend: FastAPI + Python, `uv` tooling, config via pydantic-settings reading `.env` (`.env.example` committed).
- Frontend: React + Vite + TS, built and served through FastAPI; one container, multi-stage Docker; deployed on Railway.
- No database, no caching layer, no mock mode: the backend calls the upstream API live, directly. Saved response snapshots are test fixtures only.
- Auth: single shared key (X-API-Key) from settings, entered on a login screen — the backend hosts the AI agent and spends LLM tokens, so it can't be open.
- AI agent: OpenRouter (OpenAI-compatible), target model family qwen, orchestrated minimally (LangGraph-style tool loop). Tool calls execute on the backend. The frontend receives Server-Sent Events translated server-side into user-friendly messages/tags — internal tool names/args/prompts never reach the browser. Prompt templates are `*.jinja` files.
- Core abstraction: a single pydantic `ReportSpec` model (metrics, date range, granularity, group-by, filters, sort, column order, layout) is the one contract shared by the builder UI, the AI agent (which edits it via validated tool calls), the report engine, the exporters, and shareable URLs.

## Your working rules

- Use **Sonnet subagents for all research legwork** — this matters for cost. You orchestrate and synthesize; subagents fetch, probe, and grind.
- Do NOT build the app or create its directory structure. Research and documents only.
- Put scripts and raw evidence in `scratch/fresh-eyes/` (create it), scripts with slug-like names, run via `uv run` (a uv venv exists at repo root).
- Trust only what you observe. The official docs are suspected to be wrong in places — treat every documented claim as a hypothesis to test against the live endpoint.

## Task 1 — independent API investigation → `docs/api-report-fresh.md`

Probe the reporting endpoint exhaustively and produce a clean, standalone API report (audience: an engineer implementing against this API with no other context). Answer at minimum, with evidence:

- Request contract: which request fields actually do anything? (`community_id`, `event_types`, `time_type`, `time_unit`, `time_period`, `from_date`/`to_date`, `timezone`, `scope`, `filters` — test each in isolation.) What does validation accept/reject, with what errors?
- Response contract: every key, its shape and meaning; the ticks/buckets relationship; breakdown arrays and their structure; undocumented keys.
- Semantics: what does each metric appear to measure? What UNITS are the time metrics really in (the docs' claim vs what the numbers support — do the arithmetic)? What are the `_count` companions for?
- Data reality: what date range actually has data, and how does the API behave for ranges outside it? Is the data static or changing? Do breakdowns reconcile with totals (check per metric, on the full dataset, not a sample)? How many agents/mailboxes exist?
- Auth specifics, other endpoints/methods (probe for siblings), rate limiting, CORS.
- A "gotchas for implementers" section: every place where observed behavior contradicts the documentation.

## Task 2 — product & architecture perspective → `docs/second-opinion.md`

With Task 1's evidence in hand (and the fixed decisions above as constraints), write your independent take: what should this product be, what's the smartest one-night-sprint scope, what would you build first/cut, what risks do you see, and anything about the fixed decisions that the evidence makes you want to flag (flag, don't override). Pay special attention to: what report shapes the data can and cannot support, and how the AI agent should be allowed to interact with the report definition.

## Final step — only after both docs are written

Read the previous session's conclusions (`docs/api-map.md`, `docs/idea.md`, `docs/architecture.md`, `scratch/api-probe-findings.md`) and append a `## Divergences` section to `docs/api-report-fresh.md`: every point where your findings disagree with theirs (or where you found something they missed, or they found something you missed). Be specific — these divergences are the most valuable output of this whole exercise.
