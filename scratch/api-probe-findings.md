# Reporting API — empirical probe findings

## Third pass

Final pass, run 2026-07-25 (one calendar day after passes 1 and 2). Script: `scratch/probe-third-pass.py`, output `scratch/probe-third-pass-output.txt`. Deliverable: `docs/api-map.md` (definitive observed-contract reference). Canonical fixture: `scratch/resp-full-unscoped-latest.json` (fresh, unscoped — no `scope` key — full-window, all-`event_types` request, wide requested range `2026-07-01`→`2026-08-10` to specifically probe for window roll). Supporting dumps: `scratch/actors-list.json` (108 entries), `scratch/mailboxes-list.json` (103 entries), `scratch/z3-reconciliation.json` (raw per-metric reconciliation numbers), `scratch/resp-q1-rerun-day2.json` (today's response to yesterday's exact pass-1 request body, for direct diffing).

### Window roll verdict: FIXED, not rolling

A wide-range unscoped request today (`from_date=2026-07-01`, `to_date=2026-08-10`) still returned exactly 15 ticks spanning `2026-07-10T00:00:00Z`→`2026-07-24T00:00:00Z` — identical to yesterday, **not** shifted to end `2026-07-25`. Additionally, replaying pass-1's exact original request body today produced a response that is **byte-identical (full JSON dict equality)** to yesterday's saved `resp-q1-full-14day.json`. This overturns the pass-2 speculation that the window was "rolling, anchored to wall-clock now" — that was a coincidence of the window's right edge matching the probe date at the time. **The dataset is static and hardcoded at `2026-07-10`–`2026-07-24` regardless of the real calendar date of the request.**

### Full per-metric reconciliation (all 15 metrics + 7 `_count` companions, full unscoped 103-mailbox/108-actor dataset)

| metric | top total | actor-sum | mailbox-sum | actor match | mailbox match |
|---|---:|---:|---:|:---:|:---:|
| actioned_emails | 19,024 | 28,941 | 19,024 | **NO** | yes |
| resolved | 16,372 | 16,372 | 16,372 | yes | yes |
| new_tickets | 66,288 | 66,288 | 66,288 | yes | yes |
| open | 0 | 0 | 0 | yes | yes |
| replies | 13,679 | 13,679 | 13,679 | yes | yes |
| new_emails | 68,711 | 68,711 | 68,711 | yes | yes |
| replies_to_resolve | 17,965 | 17,965 | 17,965 | yes | yes |
| sla_breaches | 4,073 | 4,073 | 4,073 | yes | yes |
| resolve_time | 187,974.10 | 187,974.10 | 187,974.10 | yes | yes |
| response_time | 209,110.77 | 209,110.77 | 209,110.77 | yes | yes |
| time_to_first_reply | 182,526.74 | 182,526.74 | 182,526.74 | yes | yes |
| resolve_time_business_hours | 125,344.54 | 125,344.54 | 125,344.54 | yes | yes |
| response_time_business_hours | 139,410.74 | 139,410.74 | 139,410.74 | yes | yes |
| time_to_first_reply_business_hours | 121,831.72 | 121,831.72 | 121,831.72 | yes | yes |
| handle_time | 85.0669 | 85.0669 | 85.0669 | yes | yes |

All 7 `_count` companions (`resolve_time_count`, `response_time_count`, `time_to_first_reply_count`, and their `_business_hours` variants, `handle_time_count`) reconcile exactly on both actor-sum and mailbox-sum. **`actioned_emails` is the sole outlier** — its actor-level breakdown over-counts the true total by ~52% (28,941 vs 19,024), while its mailbox-level breakdown is exact. Likely cause: an action gets attributed to more than one actor in the mock generator (e.g. a shared-mailbox action credited to both a team alias and an individual), or `actioned_emails` at actor granularity double-counts something the mailbox aggregation doesn't. Not fixable from the client side — just don't sum actor-level `actioned_emails` and expect it to match the total.

### `open` metric: confirmed always zero

`open` is `[0, 0, 0, ..., 0]` at the top level, and zero for **every single one of the 108 actors and 103 mailboxes** (not just the top level, not just a subset) in the canonical fixture. This is a fully unpopulated metric in this mock dataset, not a partial/sparse data issue. Likely intended as a "currently open ticket count" snapshot metric rather than a period-delta metric, and the mock simply never generates a nonzero value for it.

### `_business_hours` variants vs base metrics

Computed on the canonical fixture:

| base | base total (h) | base count | business total (h) | business count | ratio (business/base) | avg base (h) | avg business (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
| resolve_time | 187,974.10 | 16,371 | 125,344.54 | 16,371 | 0.6668 | 11.48 | 7.66 |
| response_time | 209,110.77 | 5,968 | 139,410.74 | 5,968 | 0.6667 | 35.04 | 23.36 |
| time_to_first_reply | 182,526.74 | 4,540 | 121,831.72 | 4,540 | 0.6675 | 40.20 | 26.84 |

Sane on both counts: the `_count` for a base metric and its `_business_hours` variant are always identical (same ticket population — business-hours variant is a different measurement of the same tickets, not a different subset), and business-hours averages are consistently lower than calendar-time averages, as expected. The ratio clusters tightly around **0.667 (2/3)** for all three pairs — too consistent to be organic business-hours-vs-calendar-hours simulation; reads as a fixed multiplier baked into the mock generator rather than a real business-calendar computation.

### Mailbox/actor list census

Canonical fixture has **108 actors** and **103 mailboxes** (dumped verbatim to `scratch/actors-list.json` and `scratch/mailboxes-list.json`). Mailbox names follow a repeating-generation pattern: ~26 distinct base names (Returns, Partnerships, Compliance, Fax, Outbound, Care Team, Front Desk, Dispatch, Records, Intake, Renewals, Disputes, Wholesale, Logistics, Concierge, Support, Billing, Scheduling, Providers, Vendors, Accounting, Customer Care, Quality, Notifications, Receivables, Payables, Escalations, Travel, Onboarding, Claims), each appearing as itself plus suffixed generations `" 2"`, `" 3"`, `" 4"` (up to 4x each) — clearly synthetic/generated rather than a real customer's mailbox list.

## Second pass

Second, deeper probing pass — done same day (2026-07-24) as pass 1, before locking the product design. Scripts: `scratch/probe-sibling-endpoints.py`, `scratch/probe-mailbox-and-filters.py`, `scratch/probe-date-boundary-and-auth.py`, `scratch/probe-determinism-and-pdf.py`. Raw responses: `scratch/resp-y*.json`, `scratch/resp-z1-rerun-q1.json`, PDF text in `scratch/reporting-api-guide-pdf-text.txt`.

### Conclusions & gotchas (second pass) — read this first

1. **CORRECTION to pass-1 finding #7/#4: `scope` DOES do something — it controls which entries appear in the `mailbox` breakdown array.** It does NOT change top-level totals, `actors`, or the values inside the surviving mailbox entries (those stay fixed per-mailbox regardless of what's requested) — but it does filter the *list* of mailboxes returned. 1-mailbox scope → 1 mailbox entry back; 3-mailbox scope → 3 entries back; no scope, a scope with a **fake/nonexistent mailbox ID**, scope `id: "mailbox"` (singular — wrong field name), or `id: "allMailboxes"` all fell back to returning **all 103 real mailboxes** in the mock dataset. So scope only prunes the mailbox list, and only when it contains at least one recognized real mailbox ID under the exact key `"mailboxes"` (plural).
2. **CORRECTION to pass-1 finding #7: the `mailbox` breakdown is NOT broken — it fully reconciles with top-level totals once you look at the full 103-mailbox universe.** Pass 1 tested only the 5 spec-example mailboxes (Returns, Partnerships, Compliance, Fax, Outbound), which happen to have `resolved = 0` for all of them — that's why the "broken" conclusion was drawn. With no scope (all 103 mailboxes returned), `sum(mailbox[i].resolved) == 16372 == top-level resolved sum`, and same exact match for `new_tickets`, `replies`, and `handle_time`. **The 5 spec-example mailboxes are simply low-resolved-volume mailboxes in the mock data — the mailbox breakdown itself is trustworthy.**
3. **The mock dataset has 103 real mailboxes**, not 5 — the spec's 5-mailbox example is just a small subset. Mailbox names follow a repeating pattern (`"Returns"`, `"Returns 2"`, `"Returns 3"`, `"Returns 4"`, `"Partnerships"`, `"Partnerships 2"`, … — looks like ~26 base names × 4 generations).
4. **`filters` still does nothing** — every filter variant tried (labels, topics, categories, user, customerEmail, operator `is_not`/`and_not`/`or`) produced byte-identical `mailbox` lists to the underlying `scope`, i.e. filters neither prune the mailbox list nor change any values. Only `scope` (with the exact key `"mailboxes"`) has any observable effect. `labels`/`topics`/`categories` top-level arrays remain empty `[]` in every case — never observed populated by any filter shape.
5. **No sibling endpoints exist.** `/stats/csv`, `/stats/xlsx`, `/stats/excel`, `/stats/pdf`, `/reporting/`, `/reporting`, `/v1/`, `/mailboxes`, `/users`, `/agents`, `/metadata`, `/export`, `/stats/export` all return `404`. Only `/reporting_api/v1/reporting/stats/json` exists. `OPTIONS` on it returns `200 "OK"` (CORS preflight only, not a real endpoint description). `PUT`/`DELETE`/`PATCH`/`GET`/`HEAD` all `404`. There is no CSV/Excel/PDF export capability server-side — any export format needs to be generated client-side from the JSON.
6. **The exact data window is `2026-07-10T00:00:00Z` through `2026-07-24T00:00:00Z`** (15 ticks, 14 daily buckets), confirmed via binary search: `from_date` values before `2026-07-10T00:00:00Z` all clip to start at `2026-07-10`; `from_date = 2026-07-11T00:00:00.000Z` correctly drops the first bucket (14 ticks starting 07-11). Symmetric behavior on `to_date`: `to_date = 2026-07-22T00:00:00.000Z` correctly truncates to end at `2026-07-23` (14 ticks); anything `>= 2026-07-23T00:00:00.000Z` (or beyond) gives the full window ending `2026-07-24`. **This is genuine intersection/clamping logic, not pure ignoring** — from/to dates truncate the window correctly when they overlap it. The only "weird" behavior is the **zero-overlap fallback**: a request entirely outside `[2026-07-10, 2026-07-24]` (tested: 1 day before, 1 day after, all of 2020/2024/2030) returns the **full 15-tick window** instead of an empty/zero result. Net effect for a client: always sanity-check that the returned `ticks` actually fall within your requested range before trusting the response.
7. **The window's right edge (`2026-07-24T00:00:00Z`) exactly equals "today"** in the server's clock (matches the actual current date at probe time). Combined with the fixed 14-day span, this strongly suggests a **rolling "last 14 days" window anchored to wall-clock "now"**, not a hardcoded calendar range — but this could only be fully confirmed by probing again on a different calendar day. Within this single session (pass 1 and pass 2, several hours apart, same day), the window and all values were **byte-identical on every repeat** — full JSON dict equality confirmed by re-running pass 1's exact request and diffing against the pass-1 saved file (`resp-q1-full-14day.json` vs `resp-z1-rerun-q1.json`). No intra-day drift; static/deterministic within a day, rolling-window hypothesis for day-to-day is plausible but unverified.
8. **Auth**: `Bearer <any non-empty token>` (including a 500-char token) → `200`. Empty bearer (`Bearer ` with nothing after), `Basic ...`, a raw token with no `Bearer` scheme, a missing `Authorization` header, and an empty `Authorization` header all → `401 {"error":"No auth provided"}`. So the scheme keyword `Bearer` plus a non-empty value is required, but the value itself is never validated. No token length limit observed.
9. **No rate limiting observed**: 20 rapid sequential requests all returned `200` with no `429` or slowdown pattern.
10. **The PDF guide is byte-for-byte the same content as `/spec`**, just paginated (5 pages, extracted via `pypdf`) — no extra fields, no extra endpoints, no differing units claims. It repeats the same "time metrics are in seconds" claim from §3a, which pass 1 already flagged as contradicted by the actual data (best-supported reading: hours). The PDF is not a richer source of truth than the HTML page — treat them as identical.

### Second pass — evidence detail

**Q1 sibling endpoints** (`scratch/probe-sibling-endpoints.py`, output in `scratch/probe-sibling-endpoints-output.txt`): all 18 guessed paths 404'd except the known-good one. Verb probe on the real endpoint: `GET/PUT/DELETE/PATCH/HEAD` → `404`; `OPTIONS` → `200 "OK"` (2-byte body, CORS preflight response, not a documented-endpoints listing). `access-control-allow-methods` header consistently reports `POST, GET, OPTIONS` even though `GET` 404s in practice — the CORS header is just a static allow-list, not reflective of real routing.

**Q2/Q3 mailbox & filters** (`scratch/probe-mailbox-and-filters.py`, output in `scratch/probe-mailbox-and-filters-output.txt`, raw responses `resp-y1`…`resp-y15`):
- `scope` 1 mailbox → `mailbox: [1 entry]`; 3 mailboxes → `[3 entries]`; no `scope` key at all → `[103 entries]` (all real mailboxes); fake mailbox ID → `[103 entries]` (fallback, fake ID ignored); `scope.id: "mailbox"` (singular, wrong key) → `[103 entries]` (fallback); `scope.id: "allMailboxes"` → `[103 entries]`.
- Full reconciliation check on the no-scope (103-mailbox) response: `resolved` top=16372 vs `sum(mailbox.resolved)`=16372; `new_tickets` top=66288 vs sum=66288; `replies` top=13679 vs sum=13679; `handle_time` top=85.067 vs sum=85.067 — all exact matches.
- `filters` array tried with `labels`, `topics`, `categories`, `user` (operator `and_not`), `customerEmail`, all layered on top of the default 5-mailbox `scope` — every case returned exactly the same 5 mailbox entries with the same values as scope-alone, i.e. `filters` had zero additional effect in every shape tried.
- `scope` (1 mailbox) + `filters` (exclude a different mailbox) combined → mailbox list still driven purely by `scope` (1 entry, "Returns") — filters exclusion had no observable effect.

**Q4 date boundary search** (`scratch/probe-date-boundary-and-auth.py`, output in `scratch/probe-date-boundary-and-auth-output.txt`):
- Left edge: `from_date` from `2026-07-08` through `2026-07-10T01:00:00.000Z` all → ticks start `2026-07-10` (15 ticks); `from_date = 2026-07-11T00:00:00.000Z` → ticks start `2026-07-11` (14 ticks). Left boundary is exactly `2026-07-10T00:00:00Z`.
- Right edge: `to_date = 2026-07-22T00:00:00.000Z` → ticks end `2026-07-23` (14 ticks, correctly truncated); `to_date >= 2026-07-23T00:00:00.000Z` (including far-future dates like `2026-07-31`) → ticks end `2026-07-24` (15 ticks, can't extend past available data). Right boundary is exactly `2026-07-24T00:00:00Z`.
- 1-day slivers overlapping just the first or last day of the window correctly return a 1-bucket result for that specific day.
- Ranges with **zero overlap** (fully before `2026-07-10` or fully after `2026-07-24`) both fell back to the full 15-tick window rather than an empty result — reconfirms pass-1 finding, now precisely bounded.

**Q5 auth edge / rate limit**: see conclusions #8–9 above; raw statuses captured in the output file.

**Q6 determinism vs pass 1**: `resp-z1-rerun-q1.json` (identical request body to pass-1's `resp-q1-full-14day.json`) is byte-identical in full JSON dict comparison. No drift observed within the session. (True note: pass-1 and pass-2 both ran on 2026-07-24, so this cannot distinguish "fixed calendar window" from "rolling window that hasn't rolled yet" — see conclusion #7.)

**Q7 PDF vs /spec diff**: extracted text (`scratch/reporting-api-guide-pdf-text.txt`, 4462 chars, 5 pages) matches the `/spec` page content verbatim (aside from PDF layout artifacts like a stray `POST https:///reporting_api/...` with a dropped host, clearly a PDF-rendering artifact of the original link, and `community_idYes` for missing whitespace, both formatting-only). No new fields, endpoints, or unit claims found in the PDF.


Endpoint: `POST /reporting_api/v1/reporting/stats/json`
Probed 2026-07-24. All scripts in `scratch/probe-*.py` (run via `uv run --with requests <script>` from repo root). Raw JSON responses saved as `scratch/resp-*.json`.

## Conclusions & gotchas (read this first)

1. **The backend is a fixed/mocked dataset, not a real time-series query engine.** It always has "data" for a hardcoded ~14-day window ending on the server's "today" (2026-07-10 → 2026-07-24 at probe time, i.e. current date minus 14 days through current date). Requests are effectively **clamped/intersected against that fixed window**, not used to select genuinely different data:
   - A request range fully inside the window (e.g. `2026-07-15`→`2026-07-17`) correctly returns the narrower slice with matching values.
   - A request range with **zero overlap** with the fixed window (e.g. all of 2020, 2024, or 2030) silently **falls back to the full 14-day window** instead of returning empty/zero data or an error. This is a serious gotcha: querying "January 2025" silently gives you July 2026 data.
   - `from_date > to_date` (inverted) doesn't error either — it returns a degenerate 1-bucket result. `from_date == to_date` returns a 1-day bucket. Behavior here is clearly clamp-then-render logic with no real validation, not date-range-aware querying.
2. **`time_unit` and `time_period` are ignored.** Requesting `hour`, `week`, `month`, or `minute` buckets, or `time_period: 3` or even `-1`, all produced the exact same **daily** buckets as `time_unit: "day", time_period: 1`. There is no way to get sub-day or multi-day buckets from this API in its current state — confirmed by requesting an explicit hour-bucketed 1-day window and getting back only day-boundary ticks identical to the day-bucketed request.
3. **`event_types` filtering does nothing.** Requesting only `["resolved"]` returns the exact same full set of ~28 keys (all metrics + `_count` companions) as requesting all 15 documented event types, with identical values. There is no way to get a slimmer response.
4. **`scope` and `filters` do nothing.** No-scope, 1-mailbox scope, a scope with a made-up mailbox ID that doesn't exist, and `id: "user"` scope with a real user_id all returned byte-identical `resolved` arrays and the same 108 actors. The backend does not filter by mailbox or user at all — it always returns the same underlying mock dataset.
5. **`community_id` and `timezone` do nothing.** A nonsense `community_id` returns identical data to `demo-community`. `America/New_York` vs `Asia/Tokyo` produce byte-identical `ticks` and values — no timezone-aware bucket shifting occurs.
6. **`time_type` (`today`/`yesterday`/`all`/`7d`/`custom`) does nothing by itself** — output is driven only by `from_date`/`to_date` (subject to the clamping behavior in #1), not by the preset name.
7. **The `mailbox` breakdown array is present but effectively broken/near-empty** — its metric values mostly sum to 0 or to a tiny fraction of the true total (e.g. `resolved` mailbox-sum = 0 vs top-level total 16,372; `handle_time` mailbox-sum ≈ 0.8 vs top-level 85.07). Don't trust it for real per-mailbox reporting.
8. **The `actors` breakdown is the reliable one** — per-actor sums reconcile almost exactly with top-level totals for most metrics (`resolved`, `sla_breaches`, `handle_time`, `new_tickets`, `replies` all reconcile to the total). One exception: `actioned_emails` actor-sum (28,941) is *larger* than the top-level total (19,024) — an internal inconsistency in the mock data, worth flagging rather than trusting blindly.
9. **Time metrics (`handle_time`, `resolve_time`, `response_time`, `time_to_first_reply`, and `_business_hours` variants) are stored as raw totals in an ambiguous unit**, each with a matching `_count` (ticket count) for computing an average. Best-supported read: units are **hours**, not seconds as the doc's section 3a claims — see Q2 below for the arithmetic. Divide `metric / metric_count` to get an average handle/resolve/response time per ticket, in hours.
10. Two extra undocumented top-level arrays exist beyond `ticks`/metrics/`actors`/`mailbox`: `labels`, `topics`, `categories` — all empty `[]` in every response observed, presumably placeholders for scope/filter-type breakdowns that were never populated in the mock.
11. **Determinism**: identical requests return byte-identical JSON (checked twice). Not randomly generated per call — it's a fixed seeded/static dataset.
12. Validation is minimal: missing required fields → `422` with a serde-style message (`Failed to deserialize the JSON body into the target type: missing field \`from_date\``). Everything else (bad `time_type`, bad `event_types` values, negative `time_period`) is silently accepted and returns `200` with the same data — no server-side enum/range validation beyond required-field presence.

**Practical implication for building on top of this API**: treat every response as "the same canned ~14-day, all-metrics, all-actors dataset" regardless of most request parameters. The only request field that has any real effect is `from_date`/`to_date` when the range overlaps the fixed window (and even then only to slice/clamp it). Any product built on this needs to do its own client-side filtering/aggregation (by mailbox, by actor, by event type) since the server won't do it, and should not promise real hour/week/month granularity.

---

## Q1: full response structure

Request: 14-day custom window (`2026-07-10`→`2026-07-24`), day bucket, the 5 mailboxes from the spec example, all 15 event types. Saved: `resp-q1-full-14day.json`.

**Top-level keys** (28 total):
```
ticks, actioned_emails, resolved, new_tickets, open, replies, new_emails,
replies_to_resolve, replies_to_resolve_count, resolve_time, resolve_time_count,
response_time, response_time_count, time_to_first_reply, time_to_first_reply_count,
resolve_time_business_hours, resolve_time_business_hours_count,
response_time_business_hours, response_time_business_hours_count,
time_to_first_reply_business_hours, time_to_first_reply_business_hours_count,
handle_time, handle_time_count, sla_breaches,
actors, mailbox, labels, topics, categories
```
- `ticks`: 15 entries (for 14 daily buckets), confirming the documented "N+1 ticks" rule.
- `labels`, `topics`, `categories`: always `[]` (empty) in all responses tested — undocumented, unused placeholders.
- `actors`: 108 entries, each `{user_id, id, name, <same ~24 metric arrays as top level>}`. Names look like a mix of real people (e.g. "Elena Kaur") and shared/team mailboxes-as-actors (e.g. "Support", "Billing", "Accounting", "Scheduling", "Vendors", "Claims") — 108 is a lot for 5 requested mailboxes, suggesting `actors` is NOT scoped by the request at all (consistent with finding #4 above).
- `mailbox`: 5 entries (matching the 5 scope values sent), each `{name, id, mailbox_id, <same ~24 metric arrays>}`.
- **Nesting**: neither nests the other. `mailbox` entries have no actor-list field; `actors` entries have no mailbox-list field. They are two independent, flat, parallel breakdowns of the same top-level totals — and (per finding #7) the `mailbox` one doesn't actually reconcile to the totals while `actors` does.

## Q2: units mystery

1-day window (`2026-07-15`→`2026-07-16`), requested as `time_unit: day` vs `time_unit: hour`. Saved: `resp-q2-day-bucket.json`, `resp-q2-hour-bucket.json`.

Critical caveat first: **the hour-bucketed request returned the same day-granularity ticks as the day request** (3 ticks either way) — confirming finding #2 that `time_unit` is ignored. So the intended "do hourly buckets sum to the daily bucket" test degenerates to "identical requests give identical output" (trivially true) rather than testing real sub-day bucketing.

Raw values (2 daily buckets, 07-15 and 07-16):
| metric | day 1 value | day 1 count | day 2 value | day 2 count |
|---|---|---|---|---|
| handle_time | 10.537 | 746 | 9.250 | 674 |
| resolve_time | 11548.07 | 1701 | 17920.96 | 1586 |
| response_time | 22758.19 | 704 | 35891.14 | 611 |
| time_to_first_reply | 18667.55 | 522 | 27167.34 | 445 |

Best-supported conclusion on units: `handle_time` is a **total across all tickets in the bucket**, not a per-ticket value — `handle_time / handle_time_count` ≈ 10.537/746 ≈ **0.0141 hours ≈ 50.7 seconds** per ticket, a very plausible average handle time. Treating the raw value as seconds would imply a ~10-second total handle time across 746 tickets, which is absurd; treating it as **hours** gives a sane per-ticket average (~51s) — so time metrics are almost certainly reported as **total hours**, contradicting the doc's claim of "seconds" (§3a). Cross-check with `resolve_time`: 11548.07 / 1701 ≈ 6.79 hours per ticket to resolve — also a plausible support-ticket resolve time. `response_time`: 22758.19/704 ≈ 32.3 hours; `time_to_first_reply`: 18667.55/522 ≈ 35.8 hours — all sane if unit is hours, nonsensical if seconds (would imply first-reply of 5+ hours... wait, still plausible as seconds too: 18667s ≈ 5.2h — check both readings). Given the ambiguity for the response/reply metrics alone, `handle_time`'s sub-minute-if-seconds absurdity is the strongest signal — **conclusion: hours**, note explicitly as an assumption in any deliverable.

(Values do NOT match doc's "totals in seconds" framing directly, but `_count` arrays behave exactly as documented — divide to get a weighted average.)

## Q3: does `event_types` filtering do anything?

Compared `event_types: [...all 15]` vs `event_types: ["resolved"]`. Saved: `resp-q3-all-event-types.json`, `resp-q3-only-resolved.json`.

**No effect.** Both responses have identical key sets (28 keys) and `resolved` arrays are byte-identical. The field is accepted but not applied.

## Q4: does `scope` actually filter?

Compared no `scope`, 1 real mailbox, 1 made-up mailbox id, and `id: "user"` scope with a real `user_id` (`user_yoJRgsMu`, "Support"). Saved: `resp-q4-no-scope.json`, `resp-q4-1-mailbox.json`, `resp-q4-fake-mailbox.json`, `resp-q4-user-scope.json`.

**No effect on anything tested.** `resolved` = `[1467, 84, 111, 1478, 1675, 1701, 1586, 1557, 124, 75, 1767, 1883, 2534, 330]` in all four cases, and actor count stayed at 108 even under a single-user scope. Confirms finding #4.

## Q5: `community_id`, `timezone`, `time_type`

Saved: `resp-q5-community1.json`, `resp-q5-community2.json`, `resp-q5-tz1.json`, `resp-q5-tz2.json`, `resp-q5-7d.json`, `resp-q5-custom.json`, `resp-q5-7d-nodates.json`.

- `community_id`: `"demo-community"` vs `"some-other-community-xyz"` → **identical response** (confirmed with full dict equality).
- `timezone`: `America/New_York` vs `Asia/Tokyo` → **identical `ticks` and identical `resolved`** — no timezone-aware shifting of bucket boundaries.
- `time_type`: `"custom"` vs `"7d"` (both with explicit from/to present) → identical ticks; output tracks `from_date`/`to_date` only. `time_type: "7d"` **without** `from_date`/`to_date` present → `422` (they're required fields regardless of `time_type`, contradicting the doc's implication that presets like `7d`/`today` compute the range for you).

## Q6: actual date coverage & determinism

Wide probe `2025-01-01`→`2026-08-01`, week bucket, `["resolved","new_tickets","replies"]`. Saved: `resp-q6-wide-range.json`.

- Server still returned only **15 ticks** (the same fixed 14-day window `2026-07-10`→`2026-07-24`), confirming the "wide request gets clamped to the fixed window" behavior (finding #1) — the requested week-bucket, 19-month span was entirely ignored in favor of the canned daily 14-day series.
- `resolved` nonzero across all 14 buckets in that window; no evidence of any data outside `2026-07-10`→`2026-07-24` — every out-of-window probe (2019, 2020, 2024, 2030) fell back to this same fixed window rather than returning zeros or a different slice, so it's not possible to tell from this API whether "real" data exists at other dates — most likely there isn't any, and this is the entirety of the mock dataset.
- **Determinism**: two byte-identical requests (`resp-q6-determinism-1.json`, `resp-q6-determinism-2.json`) → **identical JSON**, full dict equality confirmed. Not randomized per call.

## Q7: weird inputs

Saved: `resp-q7-*.json`.

| Input | Result |
|---|---|
| `time_unit: "week"` | `200`, silently ignored, same daily ticks as default |
| `time_unit: "month"` | `200`, silently ignored, same daily ticks |
| `time_unit: "minute"`, huge range (2020→2026) | `200`, still just the fixed 14 daily ticks — no minute buckets, no explosion |
| invalid `event_types: ["not_a_real_event_type"]` | `200`, no error, same full response as always (event_types not validated or applied) |
| `from_date` after `to_date` | `200`, degenerates to a 1-bucket (2-tick) response instead of erroring |
| missing required field (`from_date` deleted) | `422`, serde-style message: `Failed to deserialize the JSON body into the target type: missing field \`from_date\`` |
| invalid `time_type: "banana"` | `200`, no error, ignored (see Q5 — time_type barely matters anyway) |
| `time_period: 3` | `200`, ignored, same daily buckets as `time_period: 1` |
| `time_period: -1` | `200`, ignored, no error, same daily buckets |

No case produced a 5xx or a payload-size blowup; the only way to get a `422` in all of this probing was a genuinely missing required field. The API essentially never rejects a syntactically-valid request body regardless of nonsensical field values.

---

## Files in this probe

- `probe_common.py` — shared request helper (`base_body()`, `call()`), constants (`ALL_EVENT_TYPES`, `MAILBOX_SCOPE`).
- `probe-api-behavior.py` — main script, runs Q1–Q7, prints analysis, saves `resp-q1-*.json` … `resp-q7-*.json`.
- `probe-date-ignoring.py` — follow-up script specifically nailing down the date-clamping/fallback behavior (finding #1), saves `resp-x1-*.json` … `resp-x11-*.json`.
- `probe-run-output.txt`, `probe-date-ignoring-output.txt` — captured stdout from the two runs, for reference.
