# idea.md — What we're building and why

Case TH-0917 (InTheLoop take-home). Research phase output. Companion doc: [architecture.md](architecture.md).
Raw evidence: `scratch/spec-research.md` (brief + docs verbatim), `scratch/api-probe-findings.md` (three probing passes), `scratch/resp-*.json` (saved responses). The distilled, definitive observed contract lives in [api-map.md](../old_decision_depricated/api-map.md) *(deprecated — superseded by [api-report-fresh.md](api-report-fresh.md))* — build against that, not the official /spec.

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

Two probing passes were run (the second specifically to challenge the first — it overturned two conclusions, marked ⚠ below).

| Docs say | Reality (probed, 2 passes) |
|---|---|
| `event_types` selects metrics | Ignored — every response contains all ~15 metrics |
| `scope` narrows the report | ⚠ Partially real: `scope` selects **which entries appear in the `mailbox` breakdown** (1 scoped → 1 entry; none/fake → all 103 mailboxes). It never affects top-level totals or `actors`. |
| `filters` narrow further | Ignored in every shape tried (all filter ids, all operators); `labels`/`topics`/`categories` arrays never populate |
| `time_unit` minute…month | Ignored — always daily buckets |
| `timezone` / `community_id` | Ignored |
| time metrics in **seconds** | Best-supported read: totals in **hours**, with `_count` companions (avg handle time ≈ 51 s/ticket under hours; absurd under seconds). The PDF guide is textually identical to /spec — same wrong units claim. |
| any date range | Data exists only in `2026-07-10T00:00Z → 2026-07-24T00:00Z` — a **fixed** window (confirmed across calendar days; the right edge matching "today" during pass 2 was coincidence). Overlapping requests are clamped; zero-overlap requests **silently return the full window** |
| — | Fully deterministic across days (byte-identical replay); no rate limiting observed; auth needs literal `Bearer <nonempty>` (any value) |
| `mailbox` breakdown per inbox | ⚠ **Trustworthy** — pass 1 called it broken from a 5-mailbox sample that happened to be low-volume; across the full 103-mailbox universe it reconciles exactly with totals |
| — | `actors` breakdown (108 actors) reconciles with totals — full reconciliation of all 15 metrics shows exactly one inconsistency: `actioned_emails` actor-sum over-counts the total by ~52% (its mailbox-sum matches) |
| — | `open` is genuinely zero everywhere (totals, all actors, all mailboxes) — don't offer an "open tickets" view |
| — | `*_business_hours` variants ≈ ⅔ of their base metric — a synthetic multiplier, not real business-hours math; fine to display, worth a tooltip |
| — | No sibling endpoints (no /stats/csv|xlsx, no /mailboxes, /users …) — `/stats/json` POST is the entire API |
| strict validation | Only missing required fields → 422; all other garbage → 200 |

**The single most consequential gap stands:** there is **no agent×inbox cross-breakdown**. `actors` and `mailbox` are two independent flat breakdowns of the same totals. Per-day×per-agent and per-day×per-inbox reports are both fully supported; the literal three-way "per day, per agent, per inbox" cross is **not derivable from this data** — we say so rather than fake it.

## 3. Assumptions we'll state in the README

- **A1 — Units:** time metrics are totals in **hours**; `metric / metric_count` = average per ticket. (Docs say seconds; the arithmetic says otherwise.)
- **A2 — Grouping:** report by day × agent, **or** day × inbox — not both at once (no cross-breakdown exists upstream; both individual breakdowns reconcile and are trustworthy). The UI states this limitation instead of faking a three-way pivot.
- **A3 — Nearly all filtering is ours to do:** we fetch the dataset unscoped (empty scope → all 103 mailboxes in the breakdown) and do metric selection, date slicing, re-bucketing (day→week/full-range), grouping and filtering **ourselves**. The one upstream lever that works — `scope` selecting mailbox-breakdown entries — is redundant once we fetch everything, but the live proxy may still use it as an optimization.
- **A4 — Date range (revised 2026-07-25):** the window is read from `GET /health`, which states it outright (`coverage: 2026-07-10 → 2026-07-23`) — not inferred by fetching a wide range and trusting the returned ticks, since a *narrow out-of-range* request returns the identical full window and so the ticks can never tell you a range had no data. The date picker is bounded to the window; for the Assistant, **partial overlap clamps and reports the adjustment**, while **zero overlap refuses** and hands back the real window rather than silently substituting it. Note the last bucket boundary is `07-24`, but the last day *with data* is `07-23`.
- **A5 — Live API, memoised 5 minutes, no mock (revised 2026-07-25, see ADR-0001):** the app fetches the **full coverage window** from upstream and memoises that one normalised dataset in-process for 5 minutes, slicing the requested range locally. The cache key is the coverage window itself, read from the undocumented `GET /health` (also 5-minute cached, hardcoded `2026-07-10 → 2026-07-23` only as an unreachable-fallback), so an upstream redeploy with new dates is picked up without redeploying this app. Still no MOCK mode and no database. Committed snapshots remain **test fixtures only**, never a runtime path.
- **A6 — `actioned_emails`:** actor-sum ≠ total (the only metric×grouping combination that doesn't reconcile, verified across all 15 metrics); we display top-level totals as truth, and the engine detects such mismatches dynamically and attaches a warning rather than hardcoding this one case.

## 4. Product concept

**One core abstraction: the `ReportSpec`.** A small declarative object — metrics, date range, granularity, group-by dimension, filters, sort, pivot orientation. Everything produces or consumes it:

- The **builder UI** edits a ReportSpec with controls.
- The **AI agent** turns plain English into a ReportSpec (and can explain/refine it).
- The **report engine** turns ReportSpec + the live-fetched dataset into a table.
- The **exporters** turn that table into CSV / XLSX.
- A **share/save** feature is just persisting the ReportSpec.

This makes the AI agent honest by construction: it can only emit specs the engine can execute, so it can't hallucinate numbers — it manipulates the same levers the human does, visibly.

### Scope variations

**V0 — Floor (bail-out point).** Backend proxies the live API; one report page: pick metrics, date range, group by agent or day; HTML table preview; CSV + XLSX download. AI agent as a single LLM call → ReportSpec (no chat history, no streaming). README with assumptions.

**V1 — Target (the one-night sprint aim).** V0 plus: re-bucketing (day/week/whole-range), per-agent and per-mailbox views (with the "no agent×inbox cross" limitation stated in-UI), weighted-average time metrics done correctly (Σmetric/Σcount, not avg-of-avgs), sortable preview table with totals row + column reordering, a small chart of the selected metric over time, AI agent as a **streaming chat side-panel** (backend tool calls surfaced as friendly status/tags via SSE; the agent visibly moves the builder controls — see architecture.md §5–6), login gate (shared key — the backend spends LLM tokens), spec-in-URL for shareable report links.

**V2 — Stretch (explicitly "what's next" in README, not built).** Saved named reports (the one feature that would introduce persistence — deliberately absent today), scheduled email/export, multi-metric pivot layouts, data-quality page that *shows* the doc-vs-reality diffs (turn the investigation into a feature), agent memory/refinement over conversation, auth.

**Cut list (deliberate, documented):** real auth (API accepts any token; ours can too), timezone handling (server ignores it; we present UTC days as-is), minute/hour granularity (no sub-day data exists), the literal agent×inbox pivot (data can't support it — we say so rather than fake it).

### Why this wins the "lean forward" test

The client's underlying need is *visibility into team performance*, not a CSV. The interface answers "who did what, how fast, trend over the period" at a glance; exports satisfy the literal ask; the AI agent removes the learning curve; and the data-quality honesty (units assumption, mailbox warning) is exactly the "own your calls" behavior the brief asks for.

## 5. Open questions (would ask the PM if we could)

- ~~Is the broken `mailbox` breakdown a bug?~~ Resolved by pass 2: it isn't broken — pass 1 sampled 5 low-volume mailboxes. Remaining question: is the missing agent×inbox cross-breakdown intentional scope-cutting upstream, or something a real backend would add? (We design so a future upstream cross-breakdown slots into `group_by` without UI changes.)
- ~~Does the data window roll forward daily?~~ Resolved by pass 3 (cross-day re-probe): **fixed** at 2026-07-10→24; responses replay byte-identically across days. Committed test fixtures won't go stale.
- ~~Is `handle_time` per-agent-day capacity or per-ticket effort?~~ Resolved: it is a **sum of per-ticket durations in hours** (proven — per-bucket `Σ over 108 actors == top-level`, residual 0.000000000), with `handle_time_count` contributing tickets, giving ≈48 s/ticket. Both readings are exposed via `duration_display`, defaulting to the per-ticket average.
- Which LLM/key is acceptable for the AI agent in their eval environment? (We make it env-var config with a graceful no-key fallback — see architecture.md.)
