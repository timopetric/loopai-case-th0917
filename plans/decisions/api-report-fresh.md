# Reporting API — independent investigation report

**Endpoint under test:** `POST https://ai-homework-production-2423.up.railway.app/reporting_api/v1/reporting/stats/json`
**Investigated:** 2026-07-25. **Method:** ~350 live probes, one variable at a time against a
fixed baseline, all comparisons done programmatically (full-dict equality / MD5 of the raw
body / numeric residuals), never by eye.
**Audience:** an engineer implementing against this API with no other context.
**Standing:** everything below is observed behaviour. Where the official docs (`/spec` and
the identical `reporting-api-guide.pdf`) claim otherwise, the docs are wrong — see
[Gotchas](#gotchas-for-implementers).

Raw evidence and re-runnable probe scripts: `scratch/fresh-eyes/`.

---

## 1. Executive summary

The API is **one canned 14-day dataset behind a near-inert request contract.**

- Of the ten documented request fields, **only `from_date` and `to_date` do anything at
  all.** `community_id`, `event_types`, `time_type`, `time_unit`, `time_period`,
  `timezone`, and `filters` are accepted and completely ignored. `scope` has one narrow
  cosmetic effect.
- **Every response returns all 23 metric arrays and the full 108-actor / 103-mailbox
  breakdown**, regardless of what you asked for. There is no server-side metric
  selection, no server-side grouping, and no server-side filtering.
- **Bucketing is always one calendar day, aligned to UTC midnight.** `time_unit`,
  `time_period`, and `timezone` cannot change it.
- Data exists only for **2026-07-10 → 2026-07-23 inclusive (14 daily buckets)**, which the
  undocumented `/health` endpoint confirms.
- Practical consequence: **the API is a data-dump endpoint, not a query engine.** One
  request retrieves the entire dataset (~362 KB, <1 s). Every product feature —
  filtering, grouping, metric selection, per-agent slicing, aggregation — must be
  implemented client-side (or in your own backend) over that single payload.

The single most important correctness question is metric units and aggregation (§6): the
docs' claim that "time metrics are in seconds" does not survive arithmetic. **Duration
metrics are sums expressed in hours**, and must be aggregated as `Σvalue / Σcount`.

---

## 2. Auth

Enforced on the stats route only. `/`, `/spec`, and the PDF are public.

| Request | Result |
|---|---|
| No `Authorization` header | `401 {"error":"No auth provided"}` |
| `Authorization:` (empty) | 401, same |
| `Authorization: Bearer` (no token) | 401, same |
| `Authorization: Basic xyz` | 401, same — the scheme *is* checked |
| `Authorization: Bearer <any non-empty string>` | **200** |
| `bearer <token>` (lowercase) | 200 — scheme match is case-insensitive |
| `Bearer <5000-char token>` | 200 |
| `?token=...` query param, no header | 401 — query params are never read |

**The token value is never validated.** Five different tokens produced byte-identical
responses. Any non-empty bearer string works; there is no API key to obtain.

*Implementation note:* still read the token from config rather than hardcoding it — the
real InTheLoop API presumably does validate. But do not build a credential-error UX around
upstream 401s; the only way to get a 401 is to omit the header entirely.

---

## 3. Request contract — what actually does something

### 3.1 Required fields

**`from_date` is the only required field.** Omitting any other documented "required" field
returns 200 with unchanged data.

| Omitted | Status |
|---|---|
| `community_id`, `event_types`, `time_type`, `time_unit`, `time_period`, `timezone`, `filters` | 200, response unchanged |
| `to_date` | 200, but the window changes (§3.3) |
| **`from_date`** | **422** |
| `{}` (empty body) | 422, identical error |

Exact 422 body (`text/plain`):

```
Failed to deserialize the JSON body into the target type: missing field `from_date`
```

`from_date: ""` also 422 (treated as absent). This is a deserializer error, not a business
validator — it fires while six other supposedly-required fields are absent.

So the **minimum viable request body** is:

```json
{"from_date": "2026-07-10T00:00:00Z"}
```

…which returns the same data as the elaborate example in the docs.

### 3.2 Fields that are accepted and ignored

Each tested in isolation against the baseline; "no effect" means the full parsed response
was equal to baseline.

| Field | Values tried | Effect |
|---|---|---|
| `community_id` | other strings, `""`, `null`, numeric, UUID, object, array | **None.** No 403/404 for bogus ids — a single hardcoded dataset sits behind every value. |
| `event_types` | one metric, `[]`, unknown names, mixed, bare string, number, `null`, all 15, omitted | **None.** All 23 metric arrays always returned. |
| `time_type` | `today`, `yesterday`, `all`, `custom`, `7d`, `30d`, `1d`, `90d`, garbage, `null`, `123` | **None.** Also never substitutes for `from_date`: with dates omitted, every `time_type` still 422s. |
| `time_unit` | `minute`, `hour`, `day`, `week`, `month`, garbage, `null` | **None.** `minute` and `month` are byte-identical to `day`. Always daily buckets. |
| `time_period` | `1,2,3,7,0,-1,100,"1","abc",null,1.5`, crossed with `time_unit` | **None.** No validation of zero/negative/fractional. |
| `timezone` | `America/New_York`, `UTC`, `Asia/Tokyo`, `Pacific/Kiritimati`, `Not/AZone`, `null`, omitted | **None.** Ticks are always UTC midnight, even for a nonexistent zone. |
| unknown keys | `group_by`, `granularity`, `breakdown`, `limit`, `offset`, `page`, `sort`, `metrics`, `agent_id`, `user_id`, `include` | **None.** Silently accepted; no hidden parameters found. |

### 3.3 `from_date` / `to_date` — the only working controls

The server holds a fixed coverage window **2026-07-10 → 2026-07-23 inclusive**. Requested
ranges are intersected with it.

Observed rule: **buckets = calendar days from `floor(from_date)` to `floor(to_date)`
inclusive, clipped to the coverage window. If the intersection is empty, you silently get
the entire window instead.**

Measured (`verify-range-rule.py`, `verify-range-behavior.py`):

| Requested range | Buckets | First tick | Last tick | Σ resolved |
|---|---|---|---|---|
| 07-10 → 07-24 (full) | 14 | 2026-07-10 | 2026-07-24 | 16372 |
| 07-11 → 07-23 | 13 | 2026-07-11 | 2026-07-24 | 14905 |
| 07-15 → 07-18 | 4 | 2026-07-15 | 2026-07-19 | 4968 |
| 07-20 → 07-21 | 2 | 2026-07-20 | 2026-07-22 | 3650 |
| 07-05 → 07-12 (overlaps left) | 3 | 2026-07-10 | 2026-07-13 | 1662 |
| 07-20 → 08-01 (overlaps right) | 4 | 2026-07-20 | 2026-07-24 | 6514 |
| 07-15 → 07-15 (zero width) | 1 | 2026-07-15 | 2026-07-16 | 1701 |
| 07-18 → 07-12 (inverted) | 1 | 2026-07-18 | 2026-07-19 | 124 |
| `to_date` omitted | 1 | 2026-07-15 | 2026-07-16 | 1701 |
| 07-15T13:00 → 07-17T09:00 (mid-day) | 3 | 2026-07-15 | 2026-07-18 | 4844 |
| **2020-01-01 → 2020-01-05** | **14** | 2026-07-10 | 2026-07-24 | 16372 |
| **2020-01-01 → 2027-01-01** | **14** | 2026-07-10 | 2026-07-24 | 16372 |
| **2030 / 1990 / 07-24 → 07-25** | **14** | 2026-07-10 | 2026-07-24 | 16372 |

Key behaviours:

- **Time-of-day is discarded.** `from_date` is floored to its UTC calendar day; a 13:00
  start still produces a bucket beginning at 00:00Z. There is no partial-bucket support.
- **`to_date` is inclusive of the day it lands on**, which is why the last tick is one day
  past it (ticks are boundaries — §4.2).
- **Out-of-range queries fail open, not closed.** A query for January 2020 returns July
  2026 data with no error and no indication that substitution occurred. *This is the single
  most dangerous behaviour in the API* — a user picking a date range with no data gets a
  full-looking report about a completely different period.
- Invalid `from_date` values (`"yesterday"`, a bare date, an epoch int, a bool, an object)
  are accepted with 200 and silently fall back to the window floor. Only an empty string is
  rejected.
- **Inconsistent `to_date` fallbacks:** omitted/`null`/inverted → a 1-day window; but an
  *unparseable* `to_date` → the full window. Two invalid states, two different results.

### 3.4 `scope` and `filters` — effectively non-functional

This determined the product architecture, so it was tested exhaustively (45 cases,
compared by response hash and element-wise numeric diff).

- **`filters` is a total no-op.** All 22 variants — the 10 documented ids (`user`, `labels`,
  `topics`, `categories`, `allMailboxes`, `mailbox`, `mailboxes`, `privateMailboxes`,
  `customerEmail`, `customerDomain`), 9 plausible undocumented ids, garbage, and a real
  actor id with both `is` and `is_not` — returned **byte-identical** responses to the
  unfiltered baseline (hash `ac082934400d3d71`).
- **`scope` does exactly one thing:** when `scope.id == "mailboxes"` and the values contain
  real mailbox ids, the `mailbox[]` breakdown array is trimmed to those entries. That is
  all. It does **not** change any top-level total, and does **not** touch `actors[]`. The
  surviving mailbox entries are byte-identical to their unscoped counterparts — it is a
  post-hoc list slice, not re-aggregation.
- **`scope.operator` is ignored entirely.** `is`, `is_not`, `or`, `or_not`, `and`,
  `and_not`, a garbage operator, and operator-as-plain-string all yield the identical hash.
  `is` and `is_not` are *not* complements: both return the full total 16372, so
  `is(X) + is_not(X) = 2 × baseline`.
- **All other `scope.id` values do nothing** — `user` with a real actor id, `allMailboxes`,
  `mailbox` (singular), `privateMailboxes`.
- **There is no server-side per-agent filtering of any kind.**

| Case | mailbox[] size | Σ resolved |
|---|---|---|
| no scope | 103 | 16372 |
| scope = 1 real mailbox | 1 | 16372 |
| scope = 3 real mailboxes | 3 | 16372 |
| scope = all 103 mailboxes | 103 | 16372 |
| scope = fabricated id / empty values / names only | 103 | 16372 |
| any operator, any of 22 filter variants | 103 | 16372 |

**Implication:** sending `scope` buys you nothing you couldn't do by slicing the response
locally, and it never reduces payload size meaningfully. Build no feature on `filters`.

---

## 4. Response contract

### 4.1 Top-level keys (29)

Count check: `ticks` (1) + 15 base metrics + 8 `_count` companions + `actors` + `mailbox` +
`labels` + `topics` + `categories` (5) = **29**.

Always present, always the same set, whatever you ask for:

| Key | Type | Notes |
|---|---|---|
| `ticks` | `string[]` | ISO-8601 UTC bucket boundaries. Length = values + 1. |
| 15 base metrics | `number[]` | `actioned_emails`, `resolved`, `new_tickets`, `open`, `replies`, `new_emails`, `replies_to_resolve`, `resolve_time`, `response_time`, `time_to_first_reply`, `resolve_time_business_hours`, `response_time_business_hours`, `time_to_first_reply_business_hours`, `handle_time`, `sla_breaches` |
| 8 `_count` companions | `number[]` | For `replies_to_resolve`, `resolve_time`, `response_time`, `time_to_first_reply`, the three `_business_hours` variants, and `handle_time` |
| `actors` | `object[]` | 108 entries — per-user breakdown |
| `mailbox` | `object[]` | 103 entries — per-inbox breakdown (note: **singular** key) |
| `labels` | `[]` | **Undocumented. Always empty.** |
| `topics` | `[]` | **Undocumented. Always empty.** |
| `categories` | `[]` | **Undocumented. Always empty.** |

There is no `actor` or `mailboxes` alternate key. `sla_breaches` and `open` have no
`_count`.

### 4.2 `ticks` and value alignment

`len(ticks) == len(values) + 1` holds in every observation — the documented claim is
correct. **Value `i` covers `[ticks[i], ticks[i+1])`, i.e. it is anchored to its left
tick** (verified by narrowing a request to a single day and matching the value against the
14-day baseline). Ticks are always UTC midnight and always exactly 24 h apart.

For a bucket-labelled report, use `ticks[i]` as the day label and **discard the final
tick** — it is a boundary, not a bucket.

### 4.3 Breakdown element shape

`actors[]` and `mailbox[]` elements are structurally identical: the same 23 metric arrays
(each the same length as the top-level arrays) plus identity fields.

```jsonc
// actors[i]
{
  "user_id": "user_yoJRgsMu",   // == id
  "id": "user_yoJRgsMu",
  "name": "Elena Kaur",
  "resolved": [0, 0, ...],       // 23 metric arrays, length == len(ticks) - 1
  "resolve_time_count": [0, 0, ...],
  ...
}

// mailbox[i]
{
  "mailbox_id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T",  // == id
  "id": "ACf0kWdEPNiYSou98PwFYiKQfWq9c0T",
  "name": "Returns",
  ...same 23 metric arrays...
}
```

Notably **absent**: email addresses, roles, teams, active/inactive flags, and any link
between an actor and the mailboxes they work in. **You cannot build an agent×inbox
cross-tab** — see §7.

**Breakdowns are never empty**, under any query tried, including out-of-range dates. The
docs' example showing `"actors": []` does not reflect any reachable state.

### 4.4 Entities

- **108 actors**, unique names, ids of the form `user_XXXXXXXX`. The list mixes what look
  like real people (`Elena Kaur`, `Enzo Grant`, `Vera Nash`) with **role/system accounts**
  (`Support`, `Billing`) — worth surfacing but not silently filtering.
- **103 mailboxes**, unique names, ids of the form `AC…0T`. The five sample ids in the docs
  (Returns, Partnerships, Compliance, Fax, Outbound) are **real** and are the first five
  entries. Names are synthetic: **30 base names** (Returns, Partnerships, Compliance, Fax,
  Outbound, Care Team, Front Desk, Dispatch, Records, Intake, Renewals, Disputes, …) each
  repeated up to 4 times with a numeric suffix (`Support 2`, `Billing 2`, …). Actor names
  carry no such suffixes.
- Full lists: `scratch/fresh-eyes/harvested-actors.json`, `harvested-mailboxes.json`.

### 4.5 Reconciliation — breakdowns vs totals

Computed over the full 14-day window, all 108 actors and 103 mailboxes, every metric
(`verify-reconcile-and-tz.py`):

**Every metric reconciles exactly (residual 0.00%) from both breakdowns — with one
exception.**

| Metric | Top-level | Σ actors | Actor residual | Σ mailbox | Mailbox residual |
|---|---|---|---|---|---|
| **`actioned_emails`** | **19024** | **28941** | **+52.13%** | 19024 | 0.00% |
| `resolved` | 16372 | 16372 | 0.00% | 16372 | 0.00% |
| `new_tickets` | 66288 | 66288 | 0.00% | 66288 | 0.00% |
| `replies` | 13679 | 13679 | 0.00% | 13679 | 0.00% |
| `new_emails` | 68711 | 68711 | 0.00% | 68711 | 0.00% |
| `sla_breaches` | 4073 | 4073 | 0.00% | 4073 | 0.00% |
| all time metrics + all `_count` | — | — | 0.00% | — | 0.00% |

`actioned_emails` is the **only** non-additive metric, and only across `actors`. The
natural reading: an email actioned by two agents is credited to both agents but to only one
mailbox. It is a legitimate metric per-agent, but **summing it across agents produces a
number 52% larger than the true total** — never present an "all agents" total for it.

---

## 5. Data reality

### 5.1 The window

**2026-07-10 → 2026-07-23 inclusive, 14 UTC calendar days.** Confirmed three ways:
sweeping 2015→2030 at every granularity, edge-probing at day resolution, and the
undocumented `/health` endpoint, which states it outright:

```json
{"ok":true,"service":"reporting-stats-api",
 "endpoint":"POST /reporting_api/v1/reporting/stats/json",
 "coverage":{"from":"2026-07-10","to":"2026-07-23"}}
```

The window is **fixed to absolute dates, not relative to now**. Today is 2026-07-25, so the
data ends two days ago — it does not track "yesterday". No request shifts it.

### 5.2 The data is static

Three identical requests at t=0 s, +23 s, +153 s returned **byte-identical** JSON (compared
as sorted-key strings). No bucket grew. Response size is constant (362,109 B for the full
window) and latency is flat regardless of range or granularity. This is a pre-baked
fixture, so it is safe to snapshot as test data.

### 5.3 The full daily series

| day | dow | new_tickets | resolved | replies | actioned | sla_breaches | resolve h/tkt | first-reply h/tkt |
|---|---|---|---|---|---|---|---|---|
| 2026-07-10 | Fri | 5594 | 1467 | 1144 | 1638 | 349 | 6.40 | 38.97 |
| 2026-07-11 | Sat | 834 | 84 | 104 | 138 | 17 | 7.98 | 7.14 |
| 2026-07-12 | Sun | 736 | 111 | 113 | 144 | 12 | 12.35 | 14.52 |
| 2026-07-13 | Mon | 5962 | 1478 | 1292 | 1841 | 286 | 11.11 | 38.38 |
| 2026-07-14 | Tue | 6525 | 1675 | 1477 | 1950 | 503 | 10.37 | 46.87 |
| 2026-07-15 | Wed | 6110 | 1701 | 1445 | 1898 | 443 | 6.79 | 35.76 |
| 2026-07-16 | Thu | 5907 | 1586 | 1373 | 1808 | 397 | 11.30 | 61.05 |
| 2026-07-17 | Fri | 6107 | 1557 | 1168 | 1729 | 284 | 10.37 | 35.79 |
| 2026-07-18 | Sat | 978 | 124 | 104 | 150 | 24 | 4.86 | 5.88 |
| 2026-07-19 | Sun | 552 | 75 | 82 | 87 | 7 | 3.13 | 2.76 |
| 2026-07-20 | Mon | 7374 | 1767 | 1282 | 2118 | 319 | 25.27 | 63.14 |
| 2026-07-21 | Tue | 8518 | 1883 | 1644 | 2295 | 589 | 5.64 | 35.88 |
| 2026-07-22 | Wed | 9469 | 2534 | 2197 | 2824 | 707 | 15.02 | 29.84 |
| 2026-07-23 | Thu | 1622 | 330 | 254 | 404 | 136 | 9.02 | 4.55 |

Shape notes:

- A clean **weekday/weekend cycle** — weekends run 5–8 % of weekday volume. Good for demoing
  day-of-week analysis; it means any "last 7 days vs previous 7" comparison must be
  week-aligned or it will mislead.
- **2026-07-23 is a partial day** (1622 new tickets vs ~9000 on the preceding Wednesday).
  Treat the last bucket as incomplete; it will drag down any trailing average and should
  probably be flagged or excluded by default.

### 5.4 Live vs dead metrics

| Status | Metrics |
|---|---|
| **Live** | `actioned_emails`, `resolved`, `new_tickets`, `replies`, `new_emails`, `replies_to_resolve`, `sla_breaches` (total 4073), and all 7 duration metrics with their `_count`s |
| **Always zero** | `open` — 0 in every bucket and in all 108 actor breakdowns (1512 values checked) |
| **Always empty** | `labels`, `topics`, `categories` |

Note `sla_breaches` **is** populated (4073 over the window) and reconciles exactly across
both breakdowns — only `open` is truly dead.

### 5.5 Coverage of entities

104 of 108 actors and 103 of 103 mailboxes have non-zero activity in the window. Grand
totals: `new_tickets` 66,288 · `new_emails` 68,711 · `actioned_emails` 19,024 ·
`resolved` 16,372 · `replies` 13,679 · `replies_to_resolve` 17,965 · `sla_breaches` 4,073 ·
`open` 0.

---

## 6. Metric semantics and units

**This section overrides the documentation.** The docs say: *"Counts are whole numbers;
time metrics are in seconds."* The second half is wrong.

### 6.1 Values are SUMS, not averages

Verified to the last bit: for every duration metric, `Σ over all 108 actors == top-level
value`, **per bucket**, with max residual `0.000000000`. The `_count` arrays are additive in
the same way. A per-bucket *average* could not possibly be reproduced by summing 100+
per-actor numbers.

So the contract is:

```
value[i]  = Σ of the per-ticket durations that completed in bucket i
count[i]  = number of tickets contributing to value[i]
mean[i]   = value[i] / count[i]
```

**Correct aggregation across buckets or agents is therefore `Σvalue / Σcount` — a
count-weighted mean. Never average the per-bucket averages.** That is precisely what the
`_count` companions are for, and the docs are right about their purpose if not their
arithmetic.

### 6.2 The unit is HOURS, not seconds

The decisive experiment: find actor-days where `_count == 1`, so the reported value **is one
single ticket's duration**, free of any averaging.

| metric | singleton samples | median value | as seconds | as minutes | as hours |
|---|---|---|---|---|---|
| `resolve_time` | 40 | 1.060 | 1.1 s | 64 s | **1.06 h** |
| `response_time` | 87 | 1.591 | 1.6 s | 95 s | **1.59 h** |
| `time_to_first_reply` | 90 | 1.420 | 1.4 s | 85 s | **1.42 h** |
| `handle_time` | 89 | 0.014 | 0.014 s | 0.84 s | **50 s** |

- **Seconds is impossible**: a support ticket does not get resolved in 1.06 seconds, and a
  handle time of 0.014 s is not a physical quantity.
- **Minutes is impossible**: it puts handle time at 0.84 seconds per ticket.
- **Hours is the only reading under which every metric is plausible simultaneously**: median
  single-ticket resolve 1.06 h, first reply 1.42 h, agent handle time ~50 s. The full
  singleton range for `resolve_time` is 0.012 → 648 (43 seconds → 27 days), exactly the
  heavy-tailed shape a real helpdesk produces.

Window-level count-weighted means, in hours: `resolve_time` 11.48 h, `response_time`
35.04 h, `time_to_first_reply` 40.20 h, `handle_time` 0.0133 h (48 s).

**Practical rule: multiply by 3600 to get seconds, or just format hours directly. Getting
this wrong understates every duration by 3600×.** This is almost certainly the trap the
brief means by "infer the units, don't wait for perfect info."

### 6.3 Caveat: the data is synthetic and not internally consistent

Stated plainly because it affects how much weight to put on any single number:

- Window-mean `time_to_first_reply` (40.2 h) **exceeds** window-mean `resolve_time`
  (11.5 h), which is semantically impossible — you cannot reply for the first time after
  the ticket is already closed. The two metrics have different denominators (4540 vs
  16371) and were evidently generated independently.
- Each `_business_hours` variant is a near-constant **0.666 ×** its plain counterpart
  (median 0.666, range 0.62–0.83 across all buckets). A genuine business-calendar
  computation would vary wildly per ticket — an overnight ticket would collapse to near
  zero. This is a flat scale factor, not a calendar.

So: trust the units and the aggregation rules, but do not build product logic that depends
on cross-metric consistency (e.g. "% of resolve time spent waiting for first reply").

### 6.4 What `_count` counts

| `_count` array | matches | interpretation |
|---|---|---|
| `resolve_time_count` | `resolved` almost exactly (13/14 days identical, one off by 1) | tickets resolved in the bucket |
| `response_time_count` | 35–55 % of `replies` | replies that qualified as a measurable response |
| `time_to_first_reply_count` | 7–18 % of `new_tickets` | tickets that received their first reply in the bucket |
| `replies_to_resolve_count` | — | resolved tickets with a reply count recorded |
| `*_business_hours_count` | identical to their plain counterparts | same denominators |
| `handle_time_count` | — | tickets with recorded handle time |

`open` and `sla_breaches` have no `_count` — they are plain counters.

### 6.5 Per-metric reference

| metric | kind | unit | aggregate across buckets/agents by | notes |
|---|---|---|---|---|
| `new_tickets` | counter | tickets | sum | highest-volume metric |
| `new_emails` | counter | emails | sum | |
| `actioned_emails` | counter | emails | sum — **but never across agents** | +52.13 % double-attribution in `actors` (§4.5) |
| `resolved` | counter | tickets | sum | |
| `replies` | counter | replies | sum | |
| `open` | counter | tickets | sum | **always 0** — do not expose |
| `sla_breaches` | counter | breaches | sum | live, 4073 in window |
| `replies_to_resolve` | sum | replies | `Σvalue / Σcount` → ~1.8 replies per resolved ticket | integer-valued |
| `resolve_time` | sum | **hours** | `Σvalue / Σcount` | ticket created → resolved |
| `response_time` | sum | **hours** | `Σvalue / Σcount` | inbound → agent reply |
| `time_to_first_reply` | sum | **hours** | `Σvalue / Σcount` | ticket created → first reply |
| `handle_time` | sum | **hours** | `Σvalue / Σcount` | agent touch time; ~50 s/ticket |
| `*_business_hours` (3) | sum | **hours** | `Σvalue / Σcount` | flat 0.666× their plain twin |

Confidence: unit (hours) and sum-vs-mean — **high**, both rest on direct arithmetic.
The plain-English definitions of `response_time` vs `time_to_first_reply` vs `handle_time`
are **inferred from names and magnitudes**, not observable — label them as assumptions.

---

## 7. What report shapes this API can and cannot support

**Can support (single request, client-side slicing):**

- Metric × day (the top-level arrays).
- Metric × day × agent (`actors[i][metric][day]`).
- Metric × day × mailbox (`mailbox[i][metric][day]`).
- Any aggregation *over days* of the above (totals, averages, ranking, trends).
- Agent leaderboards, inbox comparisons, day-of-week patterns.
- The literal ask in the brief — per-day / per-agent / per-inbox CSV — as **two** tables
  (day×agent and day×mailbox), not one.

**Cannot support, at any cost:**

- **Agent × mailbox cross-tabs** ("how many tickets did Elena resolve in Returns?"). The
  two breakdowns are independent marginals; the joint distribution is simply not in the
  payload, and no filter can retrieve it. This is the single biggest product constraint and
  must be stated as an explicit assumption in the README.
- Any breakdown by label, topic, category, customer, or domain — those keys exist but are
  always empty, and the corresponding filters are inert.
- Granularity finer or coarser than one day (no hourly, weekly, or monthly buckets).
- Timezone-aligned days for non-UTC teams.
- Any date range outside 2026-07-10 → 2026-07-23.
- Server-side pagination, sorting, or metric selection.

---

## Gotchas for implementers

Every place observed behaviour contradicts the official documentation:

0. **"Time metrics are in seconds" — wrong by a factor of 3600. They are in HOURS**, and
   each value is a **sum** over the bucket, not an average (§6). This is the highest-impact
   error in the docs: take it literally and every duration in your product is 3600× too
   small, and every cross-bucket average is computed the wrong way.
1. **"All fields required unless marked optional" — false.** Only `from_date` is enforced.
2. **`event_types` does nothing.** You always receive all 23 metric arrays. Metric
   selection is a client-side concern.
3. **`time_unit` does nothing.** `minute`/`hour`/`week`/`month` return byte-identical
   daily-bucketed data. Do not offer a granularity control that claims to work.
4. **`time_period` does nothing.** Not even validated.
5. **`timezone` does nothing.** Documented as controlling bucket alignment; ticks are always
   UTC midnight, even for `Not/AZone`. Days are UTC days, full stop.
6. **`time_type` does nothing**, and does not let you omit `from_date` — so the documented
   presets (`today`, `7d`, `all`) are unusable as written.
7. **`community_id` does nothing.** Any value returns the same dataset; bogus ids do not 404.
8. **`filters` does nothing** — all ten documented filter ids and all six operators.
9. **`scope` only trims the `mailbox[]` breakdown list**, never totals, never `actors[]`,
   and ignores its own `operator`.
10. **Out-of-range date queries silently return the full in-range dataset** instead of empty
    results. Guard this in your own layer or users will read July 2026 numbers as January
    2020 numbers.
11. **Invalid `from_date` values are silently accepted** and clamped, rather than rejected.
12. **`to_date` has two different invalid-input fallbacks** (omitted → 1 day; unparseable →
    full range).
13. **Undocumented response keys** `labels`, `topics`, `categories` are always present and
    always empty.
14. **The `"actors": []` example in the docs is misleading** — breakdowns are never empty.
15. **`actioned_emails` does not sum across actors** (+52.13%), though it does across
    mailboxes. The docs never mention that any breakdown is non-additive.
16. **Auth is not real** — any non-empty bearer token works; the docs describe an API key.
17. **Undocumented `/health` route** exists, unauthenticated, and reports the true coverage
    window: `{"coverage":{"from":"2026-07-10","to":"2026-07-23"}}`.
18. **The response key is `mailbox`, singular**, while the scope/filter id is `mailboxes`,
    plural. Easy to typo.
19. **CORS is wide open** (`Access-Control-Allow-Origin: *`) — the docs never say so, and it
    means a browser could call this API directly.

---

## Infrastructure notes

- **Stack:** `server: railway-hikari`, `x-powered-by: Express`, gzip, weak ETags. But the
  422 body (`Failed to deserialize the JSON body into the target type`) is the signature of
  Rust `serde` extractors, not Express — a mixed or deliberately disguised stack. No
  `/openapi.json`, `/docs`, `/redoc`, or `/swagger` exists.
- **Routes:** only `POST …/stats/json` (200) and `GET /health` (200) are live, plus the
  public `/`, `/spec`, `/reporting-api-guide.pdf`. Everything else 404s with a stock Express
  `Cannot GET …` page — including `/stats/csv`, `/stats/xlsx`, `/mailboxes`, `/users`,
  `/agents`. **There is no server-side export endpoint; CSV/Excel is entirely your job.**
- **Methods:** POST only; GET/PUT/PATCH/DELETE/HEAD/TRACE all 404. `OPTIONS` returns 200.
- **CORS:** `Access-Control-Allow-Origin: *`,
  `Access-Control-Allow-Methods: POST, GET, OPTIONS`,
  `Access-Control-Allow-Headers: authorization, content-type`, no credentials, no max-age.
  Present on every response including 401s.
- **Rate limiting:** none detected. 80-request burst → 0×429, ~4 req/s, no `Retry-After`,
  no latency degradation.
- **Latency and size:** full window 362,109 B, p50 0.289 s, p90 0.306 s; 1-day request
  169,176 B, p50 0.252 s. **Latency and payload size do not scale with the requested range
  or granularity** — further evidence of a pre-baked fixture. No `Cache-Control`.
- **Limits:** request body cap between ~3.5 MB (accepted) and 4 MB (413). Filters nested
  5000 deep are accepted in 0.42 s — they are not walked. No timeouts observed; slowest
  response 0.54 s.
- **Doc fidelity:** the PDF and `/spec` HTML are word-for-word identical on every
  substantive claim. No HTML comments, hidden text, or scripts — no planted clues.
- **Malformed JSON** → Express `400 Bad Request` HTML page (a different error layer from the
  422). Form-encoded bodies → 422 missing `from_date` (body not parsed as JSON).

---

## Practical recommendations

1. **Fetch once, slice locally.** One request with `from_date`/`to_date` at the window
   bounds returns everything in ~0.3 s and ~362 KB. Treat it as "download the dataset",
   then implement filtering/grouping/metric-selection over it.
2. **Send only what matters** (`from_date`, `to_date`), but keep the other fields in the
   request body as documented — they are harmless, and if the real API ever honours them
   you want the shape to be right.
3. **Validate date ranges yourself against 2026-07-10 → 2026-07-23** *before* calling, and
   tell the user plainly when their range is out of coverage. Do not let the fail-open
   behaviour reach the UI.
4. **Never sum `actioned_emails` across agents.**
5. **Do not build UI affordances for granularity, timezone, or server-side filters** — or if
   you do, implement them in your own layer and label them as such.
6. Treat the fixed 14-day window as demo-data scaffolding: keep the date range
   user-controllable, just bounded and clearly communicated.

---

## Divergences

Written after completing the investigation above, then reading the previous session's
conclusions (`plans/old_decision_depricated/api-map.md`, `plans/decisions/idea.md`,
`plans/decisions/architecture.md`, `scratch/api-probe-findings.md`). The two investigations were independent.

**Headline: we agree on every load-bearing conclusion.** Both independently concluded that
`event_types` / `time_unit` / `time_period` / `time_type` / `timezone` / `community_id` /
`filters` are inert; that `scope` only prunes the `mailbox[]` list; that bucketing is always
daily UTC; that the dataset is a static 14-day window with a silent full-window fallback for
out-of-range queries; that **time metrics are in hours, not the documented seconds**; that
`actioned_emails` over-counts ~52 % across actors only; that `open` is always zero; that
`_business_hours` is a flat ⅔ multiplier; that there are no sibling/export endpoints; and
that agent × mailbox cross-tabs are impossible. Two independent probes reaching the same
answers is the strongest evidence available that these are real.

What follows is only where we differ.

### A. Where my findings contradict theirs

**A1. `api-map.md` §2 marks seven fields as server-enforced-required. Only `from_date` is.**
Their table's column is literally headed "Required (server-enforced)" and marks `Yes` for
`community_id`, `event_types`, `time_type`, `time_unit`, `time_period`, `timezone`, and
`from_date`/`to_date`. Omitting each of those individually returns **200 with byte-identical
data**; omitting `to_date` returns 200 with a 1-day window. This also contradicts their own
§4, which correctly lists only `from_date` as the 422 trigger. The minimum viable body is
`{"from_date": "..."}`. *Impact: low for correctness (sending extra fields is harmless), but
it misdescribes the contract and would mislead anyone hardening the client.*

**A2. Key counts are off by one in several places.** There are **29** top-level keys, not 28,
and **8** `_count` companions, not 7 (`replies_to_resolve_count` is the one dropped from the
tally — their own Q1 enumeration lists all eight, but the prose and the reconciliation
sections both say seven). Breakdown elements carry **23** metric arrays, not the stated
"15 metrics + 7 `_count`" = 22. *I made the same 28-key error in my own first draft and
corrected it; the arithmetic is `1 + 15 + 8 + 5 = 29`.*

**A3. The data window's right edge is a boundary tick, not a day with data.** They state the
window as "`2026-07-10T00:00:00Z` through `2026-07-24T00:00:00Z`", and `idea.md` A4 carries
that through as `2026-07-10 → 07-24`. The 14 buckets cover **2026-07-10 through 2026-07-23
inclusive**; `07-24` is the closing boundary of the last bucket and contains nothing. The
undocumented `/health` endpoint (see B1) says so explicitly:
`"coverage":{"from":"2026-07-10","to":"2026-07-23"}`. *Impact: a date picker built on their
phrasing offers users 2026-07-24 as a selectable day that will always come back empty.*

**A4. `resolve_time_count` is not exactly `resolved`.** Their §6 table reports
`resolve_time` count 16,371 alongside `resolved` 16,372 without comment. The difference is
real and localised: the two arrays are identical on 13 of 14 days and differ by exactly 1 on
2026-07-17 (`resolved` 1557, `resolve_time_count` 1556). *Impact: small but concrete — use
the metric's own `_count` as the denominator, never `resolved`.*

**A5. Mailbox base-name count.** They report "~26 base names × up to 4 generations";
stripping numeric suffixes programmatically gives **30** distinct bases, max 4 generations.
Actor names carry no generational suffixes at all. Cosmetic.

**A6. `open` is described with an unevidenced explanation.** They write that it is "likely
intended as a point-in-time 'currently open' snapshot metric, not a period-delta". That is a
plausible guess, but nothing observable supports it — the only fact available is that the
array is zero in all 1,512 top-level-plus-actor positions. Worth keeping the observation and
dropping the mechanism.

### B. Things I found that they missed

**B1. `GET /health` exists — unauthenticated, undocumented, and it states the coverage
window.** Their §1 asserts "Sibling paths: None exist" after probing ~18 paths; `/health` was
not among them (`/healthz` was, and 404s).

```
{"ok":true,"service":"reporting-stats-api",
 "endpoint":"POST /reporting_api/v1/reporting/stats/json",
 "coverage":{"from":"2026-07-10","to":"2026-07-23"}}
```

*This directly improves their design.* `idea.md` A4 proposes detecting the data window
"dynamically (fetch a wide range, trust the ticks that come back)". That heuristic works, but
it is built on the same fail-open behaviour it is trying to defend against — and see B2.
`/health` gives the window authoritatively in one cheap unauthenticated call.

**B2. Their dynamic-window heuristic cannot validate a user's requested range.** Fetching a
wide range and trusting the returned ticks correctly discovers the window. But a *narrow
out-of-range* request (e.g. 2020-01-01 → 2020-01-05) returns the **identical full 14-day
window**, so returned ticks can never tell you "your range had no data". Range validation
must be done client-side against known bounds (ideally `/health`), before the call. Their
`api-map.md` §5 does warn "sanity-check that returned ticks fall inside the requested range",
which is the right instinct — but A4's dynamic-detection mechanism and that check must not be
the same code path.

**B3. Invalid date values are silently swallowed, with two different fallbacks.** Untested by
them. `from_date` set to `"yesterday"`, a bare date, an epoch int, a bool, an object, or an
array → **200**, silently clamped to the window floor; only `from_date: ""` is rejected (422).
`to_date` omitted/`null`/inverted → a **1-day** window, but `to_date` set to an *unparseable*
value → the **full** window. *Impact: material for the AI agent, which is the component most
likely to emit a malformed date — it will get a confident-looking report rather than an
error.*

**B4. `from_date`'s time-of-day is discarded.** A request starting at 13:00 still produces a
bucket beginning 00:00Z. There is no partial-bucket support, so "last 24 hours" cannot be
expressed. They probed boundaries only at midnight.

**B5. No hidden request parameters exist.** I probed `group_by`, `granularity`, `breakdown`,
`limit`, `offset`, `page`, `sort`, `metrics`, `agent_id`, `user_id`, `include` — all silently
accepted, all inert. A negative result, but it closes the question of whether server-side
grouping was merely undocumented.

**B6. The filter sweep was substantially wider.** 22 filter-id variants including 9 plausible
undocumented ones (`agent`, `agents`, `team`, `teams`, `tags`, `status`, `channel`, `inbox`,
`inboxes`) — all byte-identical to baseline. Additionally: `scope.operator` is ignored
entirely, and `is`/`is_not` are **not complements** — both return the full total, so
`is(X) + is_not(X) = 2 × baseline`. Their probing covered the documented ids and four
operators.

**B7. Much stronger evidence for the hours conclusion.** We agree on the answer, but their
reasoning rests on `handle_time`'s plausibility, and their own scratch notes show the
argument wobbling for the other metrics ("still plausible as seconds too: 18667s ≈ 5.2h —
check both readings"). I isolated **actor-days where `_count == 1`**, so the reported value
*is a single ticket's duration* with no averaging:

| metric | singleton samples | median | as seconds | as minutes | as hours |
|---|---|---|---|---|---|
| `resolve_time` | 40 | 1.060 | 1.1 s | 64 s | **1.06 h** |
| `response_time` | 87 | 1.591 | 1.6 s | 95 s | **1.59 h** |
| `time_to_first_reply` | 90 | 1.420 | 1.4 s | 85 s | **1.42 h** |
| `handle_time` | 89 | 0.014 | 0.014 s | 0.84 s | **50 s** |

Hours is the only reading under which all four are simultaneously physical. Since A1 is
their highest-risk assumption and the one most likely to be challenged by a reviewer, it is
worth having evidence that doesn't depend on a plausibility judgement about one metric.

**B8. Sum-vs-mean is now proven, not asserted.** They describe time metrics as "raw totals".
Correct — and demonstrable: for every duration metric, `Σ over all 108 actors == top-level
value` **per bucket**, with max residual `0.000000000`. A per-bucket average could not be
reconstructed by summing 100+ per-actor numbers. This is the formal justification for the
engine's Σ/Σ weighting rule in `architecture.md` §3.

**B9. The metrics are mutually incoherent, which they computed but didn't flag.** Their §6
table contains both window-mean `time_to_first_reply` = 40.20 h and window-mean
`resolve_time` = 11.48 h. A ticket cannot receive its first reply 40 hours in and be resolved
11 hours in. The denominators differ (4,540 vs 16,371) and the generator evidently produced
them independently. *Impact: don't build derived or ratio metrics across these two, and don't
let the AI agent volunteer comparisons between them.*

**B10. The last bucket is a partial day.** 2026-07-23 has 1,622 new tickets against 9,469 the
previous day (~17 %). Not flagged anywhere in their docs. It will silently drag down any
trailing average, any "last N days" default, and any trend line ending at the window edge.

**B11. Strong weekday/weekend seasonality.** Weekends run 5–8 % of weekday volume. Any
"last 7 days vs previous 7" comparison must be week-aligned or it will mislead — relevant to
both the preset design and the agent's date handling.

**B12. Infrastructure measurements they didn't take.** Request body cap between ~3.5 MB
(accepted) and 4 MB (413). Full-window payload exactly 362,109 B, p50 0.289 s / p90 0.306 s;
1-day payload 169,176 B, p50 0.252 s — **latency does not scale with requested range or
granularity**, which is the quantitative case for their fetch-per-request design being fine.
Rate limiting re-tested at 80 requests (vs their 20): still none.

**B13. Auth edge cases.** Lowercase `bearer` is accepted (scheme match is case-insensitive);
a token passed as a `?token=` query param is ignored → 401. Also, auth is enforced *only* on
the stats route — `/`, `/spec`, and the PDF are public.

**B14. Stack fingerprint is self-contradictory.** They noted the serde-style 422 message. The
sharper observation is that it sits behind `x-powered-by: Express` with textbook Express
404/400 handling — a Rust-style validator inside a Node front door. Suggests a deliberately
disguised or mixed harness, and is a reason not to over-infer real-API behaviour from this
one's quirks.

### C. Things they found that I did not

**C1. Cross-calendar-day proof that the window is fixed, not rolling — their strongest
finding, and one I could not reproduce.** They probed on both 2026-07-24 and 2026-07-25;
critically, on 07-24 the window's right edge (`07-24`) *equalled the server's "today"*, which
made a rolling "last 14 days" window the natural hypothesis — and their pass 2 adopted it.
Re-probing the next day, the window had **not** moved, and replaying pass 1's exact body
returned byte-identical JSON. I only ever observed 2026-07-25, where the window already
trailed "today" by two days, so I could show intra-session determinism (153 s) but could
never have distinguished fixed from rolling. **I adopt their conclusion.** It also matters
practically: it is what makes committed fixtures safe from staleness.

**C2. The 5-example-mailboxes trap.** Their pass 1 concluded the `mailbox` breakdown was
"broken/near-empty" because they scoped to the five mailboxes from the docs' example, all of
which happen to have `resolved = 0`; pass 2 overturned it against the full 103-mailbox
universe. I never hit this because I harvested all 103 entities before doing any
reconciliation. Worth recording as a warning: **the documented sample mailboxes are
unrepresentative low-volume outliers**, and anyone re-probing with the docs' example body
will draw the wrong conclusion about the mailbox breakdown.

**C3. Prompt/spec engineering already validated offline.** `scratch/agent-spec-lab/` (63
offline tests) establishes patch-vs-replacement semantics, merged-spec validation, and a
`CrossBreakdownNotSupported` error path. That is outside the API-investigation scope I was
given, and it independently reaches the same conclusion I argue for in `second-opinion.md`
§4.1 — partial, field-scoped edits over whole-spec replacement.

### D. Design implications where I'd push back

Detail in `second-opinion.md`; listed here only where the API evidence is what drives it.

**D1. Replace A4's dynamic window detection with `/health`** (B1), and keep range validation
strictly separate from window detection (B2).

**D2. `architecture.md` §2's `ReportSpec` already makes the impossible report
unrepresentable** — `group_by: Literal["agent","mailbox","none"]` cannot express an
agent × mailbox cross. That is the right call and worth calling out as such rather than
leaving it implicit; it is the single best structural decision in the design.

**D3. Guard the AI agent against B3.** A malformed date from the model currently yields a
plausible-looking full-window report rather than an error. Validate dates in `SpecPatch`
before they reach `upstream.py`.

**D4. `handle_time`'s open question in `idea.md` §5 is answerable.** "Per-agent-day capacity
or per-ticket effort?" — it is a **sum of per-ticket durations in hours**, with
`handle_time_count` tickets contributing, giving ~48 s/ticket (B8 proves the sum semantics).
Exposing both the total and the per-ticket average, as they propose, is right.

**D5. Flag, not override — the "no cache" decision.** `architecture.md` D2's risk row already
anticipates this ("if latency ever bites, add a per-process memo"). B12 quantifies it: every
call returns the same 362 KB in ~0.3 s regardless of parameters, and the payload is provably
static across days (C1). The measurements support the decision being low-risk; my only ask is
that a single report render issues **one** upstream call, not one per metric or grouping.
