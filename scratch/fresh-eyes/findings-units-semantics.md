# Units & Semantics Findings — reporting/stats/json

Scope: for each of the 15 metrics, determine unit, mean-vs-sum, `_count` meaning,
business-hours ratio, `handle_time`, `replies_to_resolve`, `open`/`sla_breaches`
always-zero claims, and per-actor consistency. All numbers below were computed by
`analyze-units.py` and `analyze-units2.py` against raw JSON saved in this directory
(`raw-units-daily.json`, `raw-units-weekly.json`, `raw-units-hourly.json`,
`raw-units-timeperiod7.json`). Re-run: `cd /home/timop/work/loopai && uv run
scratch/fresh-eyes/analyze-units.py` (also `analyze-units2.py`).

## 0. Critical precondition: `time_unit`/`time_period` are ignored server-side

Requested `time_unit=day`, `time_unit=week`, `time_unit=hour`, and
`time_unit=day,time_period=7` against the same date range all returned **identical**
per-calendar-day arrays (verified by direct array equality in `analyze-units.py`
Section 0 — `weekly resolve_time array == daily prefix? True`, same for hourly and
time_period=7). The server always buckets by calendar day and ignores the requested
granularity.

**Consequence**: the brief's prescribed decisive test ("compare a 1-day bucket
against a 1-week bucket covering the same 7 days") cannot be executed empirically —
there is no server-computed weekly/hourly aggregate to diff against. This is a
finding in itself, not a methodological shortcut. I substituted two alternative
decisive tests that don't require that comparison (magnitude/count consistency, and
the corrected near-integer fractional test), documented below.

## 1. MEAN vs SUM — per metric

Method: since a real cross-granularity aggregate isn't obtainable, I tested internal
consistency — a metric's single-day value should be the same **order of magnitude**
as a plausible per-ticket duration if it's a MEAN, or should be roughly
`count × per-ticket-duration` (much larger) if it's a SUM.

| metric | day0 value | day0 count/denom | implied per-ticket if SUM | value/denom (=implied mean-of-mean) | verdict |
|---|---|---|---|---|---|
| resolve_time | 9384.08 | 1467 (resolved) | 6.40s (implausibly fast) | 9384s = 2.6h (plausible) | **MEAN** |
| response_time | 17634.15 | 529 (own count) | 33.3s | 17634s = 4.9h (plausible) | **MEAN** |
| time_to_first_reply | 15743.99 | 404 (own count) | 39.0s | 15744s = 4.4h (plausible) | **MEAN** |
| resolve_time_business_hours | 6376.16 | 1467 | 4.3s | 6376s = 1.8h | **MEAN** |
| response_time_business_hours | 11740.13 | 529 | 22.2s | 11740s = 3.3h | **MEAN** |
| time_to_first_reply_business_hours | 10479.58 | 404 | 25.9s | 10480s = 2.9h | **MEAN** |
| handle_time | 7.99 | 569 | 0.014 (trivially implausible as SUM) | 7.99 (plausible as mean, see §2) | **MEAN** |
| replies_to_resolve | 1501 (integer) | 846 | — | 1501/846 = 1.77 replies/ticket (plausible) | **SUM** (see §5) |

Aggregate check across all 14 days (`analyze-units.py` Section 1): for every
time-of-duration metric, `SUM-of-all-14-daily-values` (e.g. resolve_time:
187,974) is roughly the same order of magnitude as the count-weighted mean of
means (20,582) and a single day's value (9,384) — **not** ~14–20× larger as it
would be if daily values were sub-totals of one grand running sum. This confirms
each daily figure is already a per-bucket MEAN, not a SUM, for all 7 duration
metrics. `replies_to_resolve` is the exception: its raw values are all exact
integers (1501, 76, 142, …) and dividing by `replies_to_resolve_count` yields a
plausible small ratio (1.25–1.90), which is the signature of value=SUM,
count=denominator, mean=value/count — see §5.

**Client aggregation rule**: to correctly combine any of the 6 duration metrics (or
handle_time) across multiple days/buckets, a client MUST NOT sum the daily values.
It must recompute a count-weighted mean:
`weighted_mean = Σ(value_i × count_i) / Σ(count_i)`.
Summing daily means directly (as if they were sums) silently overstates any derived
weekly/monthly total by ~14×–20× in this dataset.

## 2. Unit determination

### 2a. Magnitude/plausibility (7 duration metrics)

Distribution over the 14-day window (`analyze-units.py`/`2.py` Section on
distribution stats), values interpreted as **seconds**:

| metric | min | max | median | median as hours |
|---|---|---|---|---|
| resolve_time | 234.45 | 44654.59 | 11082.23 | 3.08h |
| response_time | 138.82 | 35891.14 | 16848.97 | 4.68h |
| time_to_first_reply | 60.79 | 27466.78 | 15241.07 | 4.23h |
| resolve_time_business_hours | 160.96 | 29603.56 | 7375.03 | 2.05h |
| response_time_business_hours | 90.55 | 23861.58 | 11225.13 | 3.12h |
| time_to_first_reply_business_hours | 44.52 | 18322.66 | 10167.57 | 2.82h |
| handle_time | 0.39 | 11.97 | 7.90 | 0.002h = 7.2s |

Interpreting the first six as **seconds** gives median durations of 2–5 hours,
squarely in the plausible range for helpdesk resolve/response/first-reply times.
Interpreting them as **minutes** would put medians at ~3–5 **days** (implausibly
slow for a first reply/response) and as **hours** would put medians at 60–190
**days** (absurd). → **resolve_time, response_time, time_to_first_reply and their
business_hours variants are in SECONDS. High confidence.**

`handle_time` breaks the pattern: as seconds its median is 7.2 **seconds** of agent
touch time per handled item — implausibly fast for genuine handle time. As
**minutes**, median ≈ 7.9 minutes, which matches textbook helpdesk "Average Handle
Time" (typically 3–10 minutes). → **handle_time is most plausibly in MINUTES, not
seconds — moderate confidence** (it is the one metric that doesn't share the
seconds convention of the other six; flagged as an inference, not directly proven).

### 2b. Near-integer fractional-tail test (corrected)

The brief's suggested test ("multiply by 3600/60/1000 and see what's near-integer")
was run first naively and produced a misleading signal: many actor-level values are
small (e.g. handle_time ~0.01–12), and dividing a small number by 3600 trivially
rounds to 0, which looks "near-integer" but is a numeric artifact, not evidence.
**Corrected test** excludes any candidate that would round to 0 (`analyze-units2.py`,
requires `|round(x·mult)| ≥ 1`):

| hypothesis | bucket-level n_valid | frac<0.01 | actor-level n_valid | frac<0.01 | combined frac<0.01 |
|---|---|---|---|---|---|
| ×1 (as-is) | 95 | 4.2% | 2587 | 2.7% | 2.7% |
| ×60 | 98 | 2.0% | 3179 | 2.1% | 2.1% |
| ×3600 | 98 | 2.0% | 3230 | 3.3% | 3.2% |
| ×1000 | 98 | 4.1% | 3228 | 1.6% | 1.7% |
| ÷60 | 84 | 1.2% | 1302 | 2.5% | 2.4% |
| ÷3600 | 56 | 0.0% | 71 | 0.0% | 0.0% |

**No hypothesis dominates** — all multipliers land near-integer only ~0–4% of the
time, indistinguishable from chance. This is the expected result once the metric is
understood to be a MEAN: dividing an integer sum-of-seconds by an arbitrary integer
ticket-count produces a generic, non-repeating decimal regardless of what unit the
result is subsequently reported in. **Conclusion: the long fractional tails
(`.084580277779`, `.736881388889`, …) are simply artifacts of `sum_seconds / count`
division, not evidence of a hidden unit-conversion factor.** The near-integer test is
not decisive here (unlike it would be for a single raw un-averaged timestamp delta);
the magnitude/plausibility argument in §2a is the stronger evidence.

## 3. business_hours vs plain — ratio and violations

`analyze-units.py` Section 3, over all 14 days:

| pair | violations (biz > plain) | ratio min | ratio max | ratio mean |
|---|---|---|---|---|
| resolve_time vs resolve_time_business_hours | 0/14 | 0.651 | 0.790 | 0.678 |
| response_time vs response_time_business_hours | 0/14 | 0.622 | 0.812 | 0.679 |
| time_to_first_reply vs time_to_first_reply_business_hours | 0/14 | 0.616 | 0.833 | 0.685 |

**business_hours ≤ plain always holds** (0 violations across 42 comparisons) —
consistent with a "business calendar" clock that only accumulates during
business hours and therefore is never larger than wall-clock elapsed time.

The mean ratio (~0.68) does **not** match an 8h/24h business day (0.333). It's
closer to a ~16h/24h window (16/24 = 0.667) or reflects that non-business time
(nights/weekends) is a minority contributor to these particular tickets' elapsed
time. **Inferred, moderate confidence**: business-hours calendar is wider than a
strict 9-to-5 (roughly 16h/day equivalent, or the ticket mix skews toward
same-business-day resolutions where the discount is small). Exact calendar
definition (which hours, weekend handling) is not recoverable from aggregate ratios
alone — flagged as shaky.

## 4. handle_time

- **Present**: yes, non-zero every day (0.39–11.97 raw units).
- **Has `_count`**: yes, `handle_time_count` (569, 35, 31, 551, 706, 746, 674, 575,
  46, 26, 624, 739, 936, 149).
- **Relation to resolved/actioned_emails**: `handle_time_count / resolved` ranges
  0.28–0.45 (mean ~0.39); `handle_time_count / actioned_emails` ranges 0.22–0.39
  (mean ~0.32). Neither ratio is 1.0, so `handle_time_count` is **not** simply
  counting resolved tickets or actioned emails — it counts some other, smaller
  subset (e.g. distinct "handling" touches/sessions).
- **Interpretation**: plausibly an **agent-touch/active-work-time metric** — the
  MEAN active handling duration per handling event, most likely in **minutes**
  (median ≈ 7.9, matching industry-standard AHT), distinct in unit from the
  other six (seconds) metrics. This is the one genuinely shaky unit call in this
  report — flagged explicitly.

## 5. replies_to_resolve / replies_to_resolve_count

Raw `replies_to_resolve` values are exact integers (1501, 76, 142, 1410, 2066, …) —
confirmed via `float(v).is_integer()` check, all 14/14 true. Dividing by
`replies_to_resolve_count` gives:

```
day0: 1501/846 = 1.774
day1: 76/61   = 1.246
day2: 142/95  = 1.495
day3: 1410/889= 1.586
...
day12: 3024/1597 = 1.894
day13: 358/194   = 1.845
```

All values land in **1.25–1.90 replies per resolved ticket** — a sensible small
number, consistent with the hypothesis: **`replies_to_resolve` is a SUM (total
reply-count across resolved tickets in the bucket) and `replies_to_resolve_count` is
the number of resolved tickets that had at least one reply counted**; their ratio is
the true "mean replies to resolve a ticket" statistic a client would want. Note
`replies_to_resolve_count` (846 on day0) is smaller than `resolved` (1467) — so the
count is scoped to a subset of resolved tickets (those with tracked replies), not
all resolved tickets; cross-checked against `replies` (1144) and `resolved` (1467),
neither of which equals `replies_to_resolve_count` exactly, confirming it's its own
denominator, not a proxy for `replies` or `resolved`.

**Client aggregation rule**: unlike the duration metrics, `replies_to_resolve` sums
correctly (`Σ replies_to_resolve_i` is valid across buckets), and so does
`replies_to_resolve_count`; the derived mean-replies-per-ticket must be recomputed
as `Σreplies_to_resolve / Σreplies_to_resolve_count` for any multi-bucket rollup.

## 6. `_count` companions

Keys **with** a `_count` companion: `replies_to_resolve`, `resolve_time`,
`response_time`, `time_to_first_reply`, `resolve_time_business_hours`,
`response_time_business_hours`, `time_to_first_reply_business_hours`,
`handle_time`.

Keys **without**: `actioned_emails`, `resolved`, `new_tickets`, `open`, `replies`,
`new_emails`, `sla_breaches`.

Equality tests against candidate denominators (`analyze-units.py` Section 6, all 14
days):

| count field | candidate denominator | exact matches | diffs |
|---|---|---|---|
| resolve_time_count | resolved | 13/14 | `[0,0,0,0,0,0,0,-1,0,0,0,0,0,0]` |
| resolve_time_business_hours_count | resolved | 13/14 | same pattern |
| response_time_count | replies | 0/14 | always smaller by 51–1326 |
| response_time_business_hours_count | replies | 0/14 | identical diffs to response_time_count |
| time_to_first_reply_count | new_tickets | 0/14 | always smaller by 530–8765 |
| time_to_first_reply_business_hours_count | new_tickets | 0/14 | identical diffs to time_to_first_reply_count |

**Findings**:
- `resolve_time_count` (and its business_hours twin) is essentially identical to
  `resolved` (13/14 exact, off by exactly 1 on one day) — resolve-time is measured
  for virtually every resolved ticket.
- `response_time_count` is **much smaller** than `replies` (roughly 35–55% of it) —
  it does not count every reply, only some qualifying subset (e.g. first
  agent-reply events used for the response-time calc, not every reply message).
- `time_to_first_reply_count` is **much smaller** than `new_tickets` (roughly
  7–18% of it) — only a minority of new tickets have a tracked "time to first
  reply" in this window (consistent with many tickets not yet having received a
  first reply, or first-reply tracking requiring both a ticket and a qualifying
  reply inside the queried window).
- The plain and business_hours variants of a given metric share **exactly the same
  count** in every case — confirms both are computed over the identical
  ticket/event population, differing only in the clock (wall vs business hours)
  used to measure duration.
- **General rule**: `_count` is the denominator of the MEAN reported alongside it —
  confirmed exactly for resolve_time, and structurally consistent (smaller, stable,
  plausible subset) for response_time and time_to_first_reply.

## 7. `open` and `sla_breaches` — always zero?

- **`open`**: bucket-level `[0,0,0,0,0,0,0,0,0,0,0,0,0,0]` — all zero. Checked
  every one of the 108 actors × 14 days (1512 values): **0 nonzero entries**.
  **`open` is always zero, everywhere, definitively, in this data window.**
- **`sla_breaches`**: bucket-level is **NOT** always zero:
  `[349, 17, 12, 286, 503, 443, 397, 284, 24, 7, 319, 589, 707, 136]`. Per-actor: 28
  of 108 actors have at least one nonzero `sla_breaches` day; summing
  `sla_breaches` across all actors × all days gives exactly **4073**, which equals
  the sum of the bucket-level `sla_breaches` array exactly (4073) — the per-actor
  breakdown reconciles perfectly with the aggregate. **`sla_breaches` is a real,
  populated, non-zero counter — the premise that it's always zero is FALSE for this
  metric** (only `open` supports that premise).

## 8. Plain-English definitions (OBSERVED vs INFERRED)

| metric | unit | mean/sum | has _count | definition | confidence |
|---|---|---|---|---|---|
| resolved | count | n/a (raw count) | no | OBSERVED: number of tickets resolved in the bucket | high |
| new_tickets | count | n/a | no | OBSERVED: number of tickets created in the bucket | high |
| actioned_emails | count | n/a | no | OBSERVED: number of emails an agent took action on | high (name is descriptive) |
| replies | count | n/a | no | OBSERVED: number of reply messages sent in the bucket | high |
| new_emails | count | n/a | no | OBSERVED: number of inbound emails received | high |
| open | count | n/a | no | OBSERVED: always 0 in this dataset — INFERRED: count of currently-open tickets, but this canned dataset/window never produces a nonzero value | shaky (never observed nonzero, so its true semantics is unverified) |
| sla_breaches | count | n/a | no | OBSERVED: number of SLA breach events in the bucket (real, non-zero, reconciles exactly with per-actor sum) | high |
| resolve_time | seconds | MEAN per resolved ticket | yes (=resolved) | INFERRED: average wall-clock time to resolve a ticket, in seconds | high |
| response_time | seconds | MEAN | yes (< replies) | INFERRED: average wall-clock time to respond (subset of reply events), in seconds | medium-high (unit high, exact denominator semantics inferred) |
| time_to_first_reply | seconds | MEAN | yes (< new_tickets) | INFERRED: average wall-clock time from ticket creation to first reply, in seconds | medium-high |
| resolve_time_business_hours | seconds | MEAN | yes (=resolved) | INFERRED: same as resolve_time but clock only accrues during business hours | high (unit/mean), medium (exact calendar) |
| response_time_business_hours | seconds | MEAN | yes | INFERRED: business-hours version of response_time | same as above |
| time_to_first_reply_business_hours | seconds | MEAN | yes | INFERRED: business-hours version of time_to_first_reply | same as above |
| handle_time | **minutes** (best guess) | MEAN per handling event | yes | INFERRED: average agent active-handling duration per touch/session; unit inferred from plausibility (median ≈7.9 = plausible AHT in minutes, implausible in seconds) | **shaky** — unit is the least certain call in this report |
| replies_to_resolve | count (integer) | **SUM** | yes | OBSERVED integer values; INFERRED: total number of replies sent across tickets resolved in the bucket; divide by replies_to_resolve_count for mean replies/ticket (1.25–1.90 observed) | high |

## 9. Per-actor consistency

- Per-actor arrays exist for all 15 base metrics (and their `_count` companions);
  same 14-day length as bucket-level arrays.
- Re-ran the corrected near-integer test restricted to per-actor values only
  (3230 nonzero samples): no multiplier hypothesis dominates (0–3.3% near-integer
  under any of ×1/×60/×3600/×1000/÷60/÷3600), matching the bucket-level result —
  same "mean of integers, no hidden conversion factor" pattern holds per-actor.
- Spot-checked the busiest actor (`user_nN5brDNG`, up to 192 resolves/day):
  `resolve_time` values (e.g. 363.53 with count 123, 2529.00 with count 129) are the
  same order of magnitude as the bucket-level per-ticket means (hundreds to low
  thousands of seconds) — consistent with each actor's value also being a MEAN in
  seconds, not a sum.
- `open` is 0 for every one of the 108 actors on every day (see §7) —
  actor-level data doesn't contradict the bucket-level always-zero finding.
- `sla_breaches` sums exactly across actors to the bucket-level total (4073),
  confirming actor and bucket data are drawn from the same consistent underlying
  dataset (not independently randomized).

## Client aggregation cheat-sheet

| metric | to combine across multiple days/buckets |
|---|---|
| resolved, new_tickets, actioned_emails, replies, new_emails, open, sla_breaches | **sum** the raw values |
| resolve_time, response_time, time_to_first_reply, and their *_business_hours variants | **count-weighted mean**: `Σ(value_i·count_i) / Σ(count_i)` using the matching `_count` array — never sum the daily values directly |
| handle_time | same as above, weighted by `handle_time_count` |
| replies_to_resolve | **sum** both `replies_to_resolve` and `replies_to_resolve_count`; derive the mean as `Σvalue/Σcount` only for display |

## Evidence files (this directory)

- `probe-units-semantics.py`, `probe-timeperiod.py` — request scripts
- `raw-units-daily.json`, `raw-units-weekly.json`, `raw-units-hourly.json`,
  `raw-units-timeperiod7.json` — raw API responses proving time_unit/time_period
  are ignored
- `analyze-units.py`, `analyze-units2.py` — all arithmetic in this report, runnable
  and re-printable
- `analyze-units-output.txt` — captured stdout of the first analysis pass
