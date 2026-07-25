# Sub-agent report (verbatim relay): response shape & breakdowns

Written by the orchestrator from the sub-agent's returned text (the agent was blocked
from writing this file itself). Raw evidence: `raw-*.json`, `actors.json`,
`mailboxes.json`, `reconcile.py`, `probe-response-shape.py`, `probe-anchoring*.py`.

**Caveat added by orchestrator:** this agent's claim 0 ("the response is effectively
canned / query-independent") is only partly right. Independent verification
(`verify-range-behavior.py`, `verify-range-rule.py`) shows sub-ranges *inside* the data
window DO slice correctly; the canned full-window response is a *fallback* for ranges
that do not intersect the window. See the main report.

## 0. Query-independence (partly overstated — see caveat)

`time_unit` day/week/month, `time_type: all`, a 2020-2027 wide range, an out-of-range
2020-01-01..2020-01-05 window, bogus `event_types`, and a nonexistent `community_id` all
returned **byte-identical** 362,109-byte payloads covering a fixed window
`2026-07-10..2026-07-24` (14 daily buckets, 108 actors, 103 mailboxes).

## 1. Top-level keys (28)

`ticks` + 23 metric arrays (`actioned_emails`, `resolved`, `new_tickets`, `open`,
`replies`, `new_emails`, `replies_to_resolve(+_count)`, `resolve_time(+_count)`,
`response_time(+_count)`, `time_to_first_reply(+_count)`, the `_business_hours` variants
of the last three (each +`_count`), `handle_time(+_count)`, `sla_breaches`) + `actors` +
`mailbox` + three **undocumented, always-empty** keys: `labels`, `topics`, `categories`.
No `actor` / `mailboxes` alternate keys exist.

## 2. ticks / values

`len(ticks) == len(values) + 1` holds everywhere. Value `i` anchors to the **left/start**
tick (confirmed by comparing a narrowed single-day request against the 14-day baseline:
value 6110 landed at `ticks[0]`). `time_unit` week/month has **zero effect** — bucketing
is always daily.

## 3/4. `actors` / `mailbox` element shape

Identical 23 metric arrays (len 14) plus `name` + `id`; actors additionally carry
`user_id` (== `id`), mailboxes `mailbox_id` (== `id`). No email, no role/team, no
mailbox affiliation on actors. 108 actors, 103 mailboxes, no duplicate names, all array
lengths match the top level across all 211 elements.

## 5. Reconciliation (numeric, full dataset)

Every metric sums correctly from both `actors` and `mailbox` to the top-level total
(float noise ~1e-11) — **except `actioned_emails` summed across actors**: top-level
19024 vs actors-sum 28941, a **+52.13% overstatement** (residual 9917, max per-bucket
residual 1623). The same metric reconciles exactly (0 residual) across `mailbox`.
Interpretation: `actioned_emails` is credited to every actor who touched a ticket
(multi-attribution) but to only one mailbox.

## 6. Breakdown emptiness

Breakdowns were never empty in ~10 query variants, including out-of-range dates and
bogus params — contradicting the doc example's implication (`"actors": []`) that empty
is a normal state.

## 7. `_count` companions

Exactly 8 of 23 metrics have them: `replies_to_resolve`, `resolve_time`, `response_time`,
`time_to_first_reply`, the three `_business_hours` variants, and `handle_time`.
`resolve_time_count` matches `resolved` almost exactly (13/14 buckets identical, one off
by 1); `resolve_time / resolve_time_count` gives plausible per-ticket durations.

## 8. Headers

`content-type: application/json; charset=utf-8`, `server: railway-hikari`,
`x-powered-by: Express`, gzip, CORS wide open (`*`), weak `etag`, no cache-control, no
rate-limit headers. ~0.9 s response, 362 KB decompressed for the full window.

## 9. Per-entity `_count`

All 8 `_count` companions are present at both breakdown levels, same lengths.

## 10. Extracted lists

`actors.json` (108: id, user_id, name), `mailboxes.json` (103: id, mailbox_id, name).

## Contradictions of the documented contract

1. `"actors": []` implying emptiness is possible — never observed empty.
2. `labels` / `topics` / `categories` exist, undocumented, always empty.
3. Actor-level `actioned_emails` is not additive to the top-level total (+52%), while
   mailbox-level is exact.
4. Bucket count returned is one more than the `[from, to)` window implies.
5. `time_unit` has no effect — always daily.
6. Out-of-window queries return a fixed canned dataset rather than empty results.
