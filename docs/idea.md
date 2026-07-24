# idea.md — What we're building and why

Case TH-0917 (InTheLoop take-home). Research phase output. Companion doc: [architecture.md](architecture.md).
Raw evidence: `scratch/spec-research.md` (brief + docs verbatim), `scratch/api-probe-findings.md` (empirical probing), `scratch/resp-*.json` (saved responses).

## 1. The ask, decoded

The client's email (Exhibit A) literally asks for:

1. A **CSV** with, per **day**, how much each **agent** did in each **inbox** — replies, resolved, handle time, "all of it".
2. Not one frozen file — an **interface where they decide how the report looks**.
3. **Excel** export too.
4. View / prepare / download reports **in the browser**.

Plus a hard requirement added by the brief itself:

5. An **AI agent**: describe the report in plain English → it builds the report.

The meta-ask (what they're actually grading): how we handle unreliable docs, state assumptions, prioritize under a one-night deadline, and ship something that actually helps.

## 2. What the endpoint actually knows (probed, not assumed)

One endpoint exists: `POST /reporting_api/v1/reporting/stats/json`, bearer auth (any token), CORS open. Empirical truth diverges from the docs badly:

| Docs say | Reality (probed) |
|---|---|
| `event_types` selects metrics | Ignored — every response contains all ~15 metrics |
| `scope`/`filters` narrow by mailbox/user | Ignored — byte-identical data with/without/fake scope |
| `time_unit` minute…month | Ignored — always daily buckets |
| `timezone` shifts buckets | Ignored |
| `community_id` selects workspace | Ignored |
| time metrics in **seconds** | Best-supported read: totals in **hours**, with `_count` companions (avg handle time ≈ 51 s/ticket under hours; absurd under seconds) |
| any date range | Data exists only for a fixed ~14-day window (2026-07-10 → 2026-07-24); out-of-range requests **silently return the full window** |
| — | Response is **deterministic** (byte-identical across calls) |
| `mailbox` breakdown per inbox | Present but **broken** — sums ≈ 0 vs. top-level totals in the tens of thousands |
| — | `actors` breakdown (108 actors) **reconciles** with totals (except `actioned_emails`, which over-counts) |
| — | Undocumented always-empty arrays: `labels`, `topics`, `categories` |
| strict validation | Only missing required fields → 422; all other garbage → 200 with same data |

**The single most consequential gap:** there is **no agent×inbox cross-breakdown**. Actors and mailboxes are two independent flat breakdowns, scope filtering doesn't work, and the mailbox one doesn't reconcile. The literal "per day, per agent, per inbox" CSV is **not derivable from this data**.

## 3. Assumptions we'll state in the README

- **A1 — Units:** time metrics are totals in **hours**; `metric / metric_count` = average per ticket. (Docs say seconds; the arithmetic says otherwise.)
- **A2 — Grouping:** report by day × agent, **or** day × inbox — not both at once. The mailbox breakdown is surfaced but visibly flagged as "does not reconcile with totals; treat as unreliable" (honesty beats silently shipping wrong numbers).
- **A3 — All server-side filtering is ours to do:** we fetch the full canned dataset and do metric selection, date slicing, re-bucketing (day→week/full-range), grouping and filtering **ourselves**.
- **A4 — Date range:** we clamp the UI to the window where data exists, and detect the window dynamically (fetch a wide range, trust the ticks that come back) rather than hardcoding 2026-07-10/24.
- **A5 — Determinism:** responses are stable, so caching one full fetch is safe; a short TTL guards against the backend changing.
- **A6 — `actioned_emails`:** actor-sum ≠ total; we display top-level totals as truth and flag the discrepancy.

## 4. Product concept

**One core abstraction: the `ReportSpec`.** A small declarative object — metrics, date range, granularity, group-by dimension, filters, sort, pivot orientation. Everything produces or consumes it:

- The **builder UI** edits a ReportSpec with controls.
- The **AI agent** turns plain English into a ReportSpec (and can explain/refine it).
- The **report engine** turns ReportSpec + cached dataset into a table.
- The **exporters** turn that table into CSV / XLSX.
- A **share/save** feature is just persisting the ReportSpec.

This makes the AI agent honest by construction: it can only emit specs the engine can execute, so it can't hallucinate numbers — it manipulates the same levers the human does, visibly.

### Scope variations

**V0 — Floor (bail-out point).** Backend fetches + caches the dataset; one report page: pick metrics, date range, group by agent or day; HTML table preview; CSV + XLSX download. AI agent as a single LLM call → ReportSpec (no chat history). README with assumptions.

**V1 — Target (the one-night sprint aim).** V0 plus: re-bucketing (day/week/whole-range), per-agent and per-mailbox views with the mailbox-quality warning banner, weighted-average time metrics done correctly (Σmetric/Σcount, not avg-of-avgs), sortable preview table with totals row, a small chart of the selected metric over time, AI agent as a chat side-panel that fills the builder controls live ("show me who resolved the most last week" → controls visibly change), spec-in-URL for shareable report links.

**V2 — Stretch (explicitly "what's next" in README, not built).** Saved named reports (Postgres), scheduled email/export, multi-metric pivot layouts, data-quality page that *shows* the doc-vs-reality diffs (turn the investigation into a feature), agent memory/refinement over conversation, auth.

**Cut list (deliberate, documented):** real auth (API accepts any token; ours can too), timezone handling (server ignores it; we present UTC days as-is), minute/hour granularity (no sub-day data exists), the literal agent×inbox pivot (data can't support it — we say so rather than fake it).

### Why this wins the "lean forward" test

The client's underlying need is *visibility into team performance*, not a CSV. The interface answers "who did what, how fast, trend over the period" at a glance; exports satisfy the literal ask; the AI agent removes the learning curve; and the data-quality honesty (units assumption, mailbox warning) is exactly the "own your calls" behavior the brief asks for.

## 5. Open questions (would ask the PM if we could)

- Is the broken `mailbox` breakdown a known backend bug or intentional trap? (We proceed per A2 either way.)
- Is `handle_time` per-hour meant per-agent-day capacity or per-ticket effort? (We expose both total and per-ticket average.)
- Which LLM/key is acceptable for the AI agent in their eval environment? (We make it env-var config with a graceful no-key fallback — see architecture.md.)
