> **DEPRECATED (2026-07-25).** Superseded by [`plans/decisions/api-report-fresh.md`](../decisions/api-report-fresh.md),
> which independently re-derived this contract and corrects several errors here (required-field
> list, key counts, the `07-24` window edge, `resolve_time_count`). Kept for the audit trail of
> how the contract was originally established. **Do not build against this file.**

# Reporting API — observed contract (empirical map)

`POST https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json`

This document describes what the API **actually does**, determined by empirical probing over three passes (2026-07-24 and 2026-07-25). The published docs (`/spec`, `/reporting-api-guide.pdf` — identical content) are **wrong or misleading in multiple places**; every claim below is evidence-backed, not copied from the docs. Full raw evidence: `scratch/api-probe-findings.md` and `scratch/resp-*.json` fixtures. Canonical test fixture: `scratch/resp-full-unscoped-latest.json` (fresh, unscoped, full-window, all-metrics, fetched 2026-07-25).

## 1. Endpoint & auth

| | |
|---|---|
| URL | `POST /reporting_api/v1/reporting/stats/json` |
| Other verbs | `GET/PUT/DELETE/PATCH/HEAD` → `404`. `OPTIONS` → `200 "OK"` (bare CORS preflight, not a docs endpoint). |
| Sibling paths | None exist. `/stats/csv`, `/stats/xlsx`, `/stats/excel`, `/stats/pdf`, `/reporting/`, `/mailboxes`, `/users`, `/agents`, `/metadata`, `/export` — all `404`. **No server-side export format other than this one JSON endpoint.** |
| Auth header | `Authorization: Bearer <any non-empty string>` → `200`. Token value is never validated (works with `"test"`, a 500-char string, anything). |
| Auth failures | Missing header, empty header, empty `Bearer ` value, `Basic ...`, or a raw token with no `Bearer` scheme → `401 {"error":"No auth provided"}`. |
| Rate limiting | None observed (20 rapid sequential requests all `200`). |
| CORS | Fully open (`*`), `POST, GET, OPTIONS` allowed — note `GET` is advertised in CORS headers but 404s in practice. |

## 2. Request fields — observed behavior

| Field | Required (server-enforced) | Observed effect |
|---|---|---|
| `community_id` | Yes (any string accepted) | **Ignored.** Different `community_id` values return byte-identical responses. |
| `event_types` | Yes | **Ignored.** Response always contains all 15 metrics + their `_count` companions regardless of what's requested, including nonsense values like `["not_a_real_event_type"]` (still `200`, still full response). |
| `time_type` | Yes | **Ignored** as a preset. `today`/`yesterday`/`all`/`7d`/`custom`/garbage string all produce identical output — actual output is driven only by `from_date`/`to_date`. `7d` without `from_date`/`to_date` present → `422` (dates are required regardless of preset, contradicting the docs' implication that presets compute the range). |
| `time_unit` | Yes | **Ignored.** `minute`/`hour`/`week`/`month`, or a valid `day`, all return the same **daily** buckets. There is no way to get non-daily granularity. |
| `time_period` | Yes | **Ignored.** `1`, `3`, `-1` all produce identical daily buckets. |
| `from_date` / `to_date` | Yes (missing → `422` serde error) | **Partially respected** — see §5 Date-window semantics. Genuinely clips the response window when it overlaps the fixed data window; falls back to the full window when there's no overlap at all. |
| `timezone` | Yes | **Ignored.** `America/New_York` vs `Asia/Tokyo` → byte-identical `ticks` and values; no bucket realignment. |
| `scope` | No | **Partially respected** — filters which entries appear in the `mailbox` breakdown array (see §7). Does NOT affect top-level totals, `actors`, or values inside surviving mailbox entries. Only the exact key `id: "mailboxes"` (plural) with recognized real mailbox IDs has an effect; `id: "mailbox"` (singular), `id: "allMailboxes"`, a scope containing only a fake ID, or no `scope` at all → falls back to **all 103 mailboxes**. `id: "user"` scope: no observed effect on `actors` (still returns all 108). |
| `filters` | No | **No effect in any shape tested** — `labels`, `topics`, `categories`, `user`, `customerEmail`, all operators (`is`, `is_not`, `or`, `and_not`) — identical output whether present, absent, or combined with `scope`. |

## 3. Response — full schema

Top-level keys (28 total), always present regardless of `event_types`:

```
ticks                                            — array[string], ISO8601, N+1 for N buckets
actioned_emails, resolved, new_tickets, open,
replies, new_emails, replies_to_resolve,
sla_breaches                                     — array[number], length N (whole numbers)
resolve_time, response_time, time_to_first_reply,
resolve_time_business_hours,
response_time_business_hours,
time_to_first_reply_business_hours, handle_time  — array[number], length N (float, see §6 units)
<same 7 metrics>_count                           — array[int], length N — ticket count backing each bucket's time-metric value
actors                                           — array[object], per-user breakdown (§7)
mailbox                                          — array[object], per-mailbox breakdown (§7)
labels, topics, categories                       — array, always [] in every response observed — undocumented, unpopulated placeholders
```

- **N+1 ticks rule confirmed**: 14 daily buckets → 15 ticks.
- Every metric array and its `_count` companion are the same length as `resolved` etc. (N, one fewer than `ticks`).
- `actors[i]` and `mailbox[i]` each repeat **all** the same metric + `_count` arrays as the top level, plus identity fields:
  - `actors[i]`: `{user_id, id, name, <24 metric/_count arrays>}` — `id` and `user_id` are identical.
  - `mailbox[i]`: `{name, id, mailbox_id, <24 metric/_count arrays>}` — `id` and `mailbox_id` are identical.
- Neither breakdown nests the other; they are two independent flat, parallel breakdowns of the same totals.

## 4. Validation & error behavior

| Condition | Result |
|---|---|
| Missing required field (e.g. `from_date`) | `422`, body: `Failed to deserialize the JSON body into the target type: missing field \`from_date\`` (serde-style) |
| Invalid enum values (`time_type`, `event_types`) | `200`, silently ignored, no validation |
| Negative/nonsensical `time_period` | `200`, ignored |
| `from_date > to_date` | `200`, degenerates to a small (e.g. 1-bucket) result rather than erroring |
| Huge date range + `minute` bucket | `200`, no explosion — still just the fixed 14 daily buckets |
| Missing auth | `401 {"error":"No auth provided"}` |

**No 5xx observed anywhere.** The server essentially never rejects a syntactically valid JSON body except for missing required top-level fields.

## 5. Date-window semantics (settled — see §8 for roll verdict)

- The mock dataset has data for exactly **`2026-07-10T00:00:00Z` through `2026-07-24T00:00:00Z`** (14 daily buckets, 15 ticks) — confirmed via binary search on both edges.
- **Left edge**: `from_date` values `<= 2026-07-10T00:00:00.000Z` clip to the window start (ticks begin `07-10`). `from_date = 2026-07-11T00:00:00.000Z` correctly drops the first bucket (ticks begin `07-11`, 14 ticks). Boundary is exact.
- **Right edge**: `to_date = 2026-07-22T00:00:00.000Z` correctly truncates to end `07-23` (14 ticks). Any `to_date >= 2026-07-23T00:00:00.000Z` (including far-future dates) → ticks end `07-24` (can't extend past available data). Boundary is exact.
- **Zero-overlap fallback**: any request range with **no overlap** at all with `[2026-07-10, 2026-07-24]` (tested: 1 day before/after, all of 2020/2024/2030) returns the **full 15-tick window** instead of an empty or error result. A client must sanity-check that returned `ticks` actually fall inside the requested range.
- **`from_date == to_date`**: returns a 1-day bucket (not zero-width/empty).
- **`from_date > to_date`** (inverted): returns a degenerate small result rather than erroring — not proper clamp-then-render logic for this case, exact behavior is implementation-specific edge case, avoid sending it.

## 6. Metric-by-metric semantics (computed on `scratch/resp-full-unscoped-latest.json`, full 103-mailbox / 108-actor unscoped dataset)

Units conclusion for all time metrics: **hours**, not seconds as the docs claim (§3a of `/spec`). Evidence: `handle_time` totals of ~85 across ~6400 tickets only make sense as hours (→ ~48s/ticket average); reading as seconds implies an absurd ~0.013s average handle time per ticket.

| Metric | Type | Top total | actor-sum match | mailbox-sum match | Notes |
|---|---|---:|:---:|:---:|---|
| `actioned_emails` | count | 19,024 | **NO** (28,941) | yes | Only metric with actor/total mismatch — actor breakdown over-counts by ~52%, likely double-attribution (e.g. multiple actors credited per action). Treat actor-level `actioned_emails` as unreliable; use top-level or mailbox-level instead. |
| `resolved` | count | 16,372 | yes | yes | Reconciles exactly. |
| `new_tickets` | count | 66,288 | yes | yes | Reconciles exactly. |
| `open` | count | 0 | yes (0) | yes (0) | **Always zero everywhere** — top, every actor, every mailbox. Not a data quality issue confined to a subset; genuinely unpopulated in this mock. Likely intended as a point-in-time "currently open" snapshot metric, not a period-delta — don't rely on it for time-series reporting. |
| `replies` | count | 13,679 | yes | yes | Reconciles exactly. |
| `new_emails` | count | 68,711 | yes | yes | Reconciles exactly. |
| `replies_to_resolve` | count (+`_count`) | 17,965 | yes | yes | Reconciles; `_count` companion also reconciles (16,371 both breakdowns match top). |
| `sla_breaches` | count | 4,073 | yes | yes | Reconciles exactly. |
| `resolve_time` (+`_count`) | time, hours | 187,974.10 (count 16,371) | yes | yes | Avg ≈ 187974.10/16371 ≈ **11.48 h** to resolve. |
| `response_time` (+`_count`) | time, hours | 209,110.77 (count 5,968) | yes | yes | Avg ≈ **35.04 h**. |
| `time_to_first_reply` (+`_count`) | time, hours | 182,526.74 (count 4,540) | yes | yes | Avg ≈ **40.20 h**. |
| `resolve_time_business_hours` (+`_count`) | time, hours | 125,344.54 (count 16,371, same count as base) | yes | yes | ≈ 66.68% of `resolve_time` total. Avg ≈ **7.66 h** (business hours < calendar hours, as expected). |
| `response_time_business_hours` (+`_count`) | time, hours | 139,410.74 (count 5,968) | yes | yes | ≈ 66.67% of base. Avg ≈ **23.36 h**. |
| `time_to_first_reply_business_hours` (+`_count`) | time, hours | 121,831.72 (count 4,540) | yes | yes | ≈ 66.75% of base. Avg ≈ **26.84 h**. |
| `handle_time` (+`_count`) | time, hours | 85.0669 (count 6,407) | yes | yes | Avg ≈ 85.0669/6407 ≈ **0.0133 h ≈ 48 s** per ticket — a plausible per-ticket handle time, confirming the hours-unit conclusion (reading as seconds gives an absurd ~0.013s). |

**Business-hours ratio is remarkably consistent (~66.7%) across all three pairs** — resolve_time, response_time, time_to_first_reply — suggesting the mock data generator applies a fixed ~2/3 multiplier rather than genuinely simulating business-hour calendars. The `_count` values for a base metric and its `_business_hours` variant are identical (same ticket population), only the aggregated hours differ.

**Bottom line: 14 of 15 metrics (all except `actioned_emails`) reconcile exactly between top-level totals, `sum(actors[*])`, and `sum(mailbox[*])` when using the full unscoped 103-mailbox / 108-actor dataset.** All 7 `_count` companions also reconcile exactly. Only `actioned_emails` diverges (actor-sum is high), and only for the actor breakdown — its mailbox breakdown is accurate.

## 7. Breakdowns

### `actors`
- **108 actors**, always returned in full regardless of `scope`/`filters` (tested against 1-mailbox scope, fake-mailbox scope, and `id:"user"` scope with a real user_id — count stayed 108 in every case).
- Names mix real-looking people (e.g. "Elena Kaur") and shared/team-style names (e.g. "Support", "Billing", "Accounting", "Scheduling") — treat as a flat actor list, not guaranteed to be "1 person = 1 entry."
- Structure: `{user_id, id, name, <15 metrics + 7 _count arrays, each length N>}`. `id == user_id` always.
- Full list dumped to `scratch/actors-list.json` (id + name pairs) from the canonical fixture.

### `mailbox`
- **103 real mailboxes** in the mock dataset when unscoped (or when `scope` doesn't contain a recognized `"mailboxes"` list) — not just the 5 from the spec's example request.
- Mailbox names follow a repeating pattern: ~26 base names (Returns, Partnerships, Compliance, Fax, Outbound, Care Team, Front Desk, Dispatch, Records, Intake, Renewals, Disputes, Wholesale, Logistics, Concierge, Support, Billing, Scheduling, Providers, Vendors, Accounting, Customer Care, Quality, Notifications, Receivables, Payables, Escalations, Travel, Onboarding, Claims) each appearing up to 4 times suffixed `" 2"`, `" 3"`, `" 4"` — likely synthetic multi-generation naming.
- **`scope.id: "mailboxes"` (exact key, plural) with a list of recognized real mailbox IDs prunes this array** to exactly the requested mailboxes (1 mailbox in scope → 1 entry back; 3 → 3 back). Any other scope shape (no scope, fake ID, singular `"mailbox"`, `"allMailboxes"`) returns all 103.
- Scope does **not** change the values inside surviving entries — each mailbox's own per-metric arrays are fixed regardless of what else is/isn't in scope.
- Structure: `{name, id, mailbox_id, <15 metrics + 7 _count arrays>}`. `id == mailbox_id` always.
- Full list dumped to `scratch/mailboxes-list.json` (id + name pairs) from the canonical fixture.
- **Both breakdowns reconcile with top-level totals** (see §6) when using the full/unscoped sets — earlier suspicion that `mailbox` was "broken" was an artifact of testing only 5 low-volume example mailboxes.

## 8. Window roll verdict (settled 2026-07-25, one day after initial probing)

**The window is FIXED, not rolling.** On 2026-07-25 (one calendar day after the initial probe), a fresh unscoped request with a deliberately wide range (`2026-07-01`→`2026-08-10`) still returned exactly the same 15 ticks, `2026-07-10T00:00:00Z` through `2026-07-24T00:00:00Z` — **not** shifted to end `07-25`. A request replaying pass-1's exact original body also returned a response **byte-identical in full JSON dict comparison** to the response saved the previous day (`scratch/resp-q1-full-14day.json` vs `scratch/resp-q1-rerun-day2.json`).

This **overturns the pass-2 hypothesis** that the window was "rolling, anchored to wall-clock now" (which had only coincidentally lined up with the probe date at the time). **Conclusion: the dataset is a static, hardcoded mock fixed permanently at `2026-07-10`–`2026-07-24`**, independent of the actual calendar date the request is made on. Any UI/report built on "today"/"yesterday"/"last N days" semantics needs to be aware this backend will not reflect real elapsed time — it is not live data.

## 9. Quirks list (quick reference)

1. No sibling endpoints, no export formats server-side (CSV/XLSX/PDF) — must build client-side.
2. `event_types`, `time_unit`, `time_period`, `time_type`, `timezone`, `community_id`, `filters` are all effectively no-ops.
3. `scope` only prunes the `mailbox` breakdown array; doesn't touch totals, `actors`, or non-pruned mailbox values.
4. Fixed static dataset, calendar-anchored to `2026-07-10`–`2026-07-24`, does not roll with real time.
5. Out-of-range date requests silently fall back to the full window instead of erroring or returning empty.
6. Docs claim time metrics are in "seconds" — actual data strongly implies **hours**.
7. `actioned_emails` actor-level breakdown over-counts vs. the true total by ~52%; don't trust actor-level `actioned_emails`.
8. `open` metric is always zero everywhere in this dataset — don't build a live "open tickets" view on it.
9. `_business_hours` variants are a near-constant ~66.7% of their base metric across all three time-metric pairs — looks like a fixed synthetic multiplier, not genuine business-calendar simulation.
10. `labels`, `topics`, `categories` top-level arrays exist but are always empty — reserved/unimplemented.
11. Auth accepts any non-empty Bearer token; no real API-key validation.
12. No rate limiting observed.
