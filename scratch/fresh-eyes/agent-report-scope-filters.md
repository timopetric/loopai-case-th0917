# Sub-agent report (verbatim relay): scope & filters

Written by the orchestrator from the sub-agent's returned text (the agent was blocked
from writing this file itself). Raw evidence: `evidence-scope/*.json`,
`scope-filters-results-log.json`, `harvested-actors.json`, `harvested-mailboxes.json`.

## Verdict

- **`filters` is a complete no-op.** All 22 filter-id variants tested (10 documented +
  garbage + 9 undocumented + real-actor-id with is/is_not) return a response
  **byte-identical** (hash `ac082934400d3d71`) to the unfiltered baseline.
- **`scope` has exactly one real effect: it trims the `mailbox[]` breakdown array** when
  `scope.id == "mailboxes"` with real mailbox ids. It does NOT change any top-level
  totals and does NOT touch `actors[]`. Kept mailbox entries are byte-identical to their
  baseline counterparts — a post-hoc list slice, not re-aggregation.
- **`scope.operator` is entirely ignored.** `is`, `is_not`, `or`, `or_not`, `and`,
  `and_not`, a garbage operator, and operator-as-plain-string all produce hash
  `a1a77597b4b52001`. `is` and `is_not` are NOT complementary: both return the full
  baseline total (16372), so `is(X) + is_not(X) = 2 x baseline`.
- **`scope.id` values other than `"mailboxes"`** (`user` with a real actor id,
  `allMailboxes`, `mailbox` singular, `privateMailboxes`) have zero effect.
- **No server-side per-agent filtering exists.** Confirmed via `scope.id=user` and
  `filters.id=user` with both `is` and `is_not`. Clients must slice `actors[]` themselves.
- `scope` wrapped in an array is silently ignored (treated as absent). Sending the whole
  request body as a bare array gives HTTP 422 (unrelated structural validation).

## Entity harvest

108 actors, 103 mailboxes. All 5 documented sample mailbox ids
(Returns / Partnerships / Compliance / Fax / Outbound) are real and appear verbatim as
the first 5 entries of the 103-mailbox breakdown.

## Evidence matrix (45 cases; 34 hash-identical to baseline, 11 differ)

Every difference reduces to the single "scope.id=mailboxes narrows mailbox[] regardless
of operator" mechanism, plus one unrelated 422.

| case | hash | mailbox[] size | resolved total |
|---|---|---|---|
| baseline (no scope) | ac082934400d3d71 | 103 | 16372 |
| scope = 1 real mailbox | a1a77597b4b52001 | 1 | 16372 |
| scope = 3 real mailboxes | 97914dd012bc9d22 | 3 | 16372 |
| scope = all 103 mailboxes | ac082934400d3d71 | 103 | 16372 |
| scope = fabricated id / empty values / name-only | ac082934400d3d71 | 103 | 16372 |
| scope operator is/is_not/or/or_not/and/and_not/garbage/plain-string | a1a77597b4b52001 (all) | 1 | 16372 |
| any of 22 `filters[]` variants | ac082934400d3d71 | 103 | 16372 |
| scope as top-level array | 422 | — | — |

All 23 non-breakdown metric arrays were diffed element-by-element between baseline and
the 1-mailbox-scoped response: every value identical.

## Bottom line

1. Treat `filters` as unimplemented server-side; build no UI that depends on it.
2. `scope` only trims the `mailbox[]` list, never totals, never `actors[]` — and since the
   server returns the full breakdown anyway, sending `scope` gains nothing over slicing
   locally.
3. Per-agent filtering must be 100% client-side.
4. `operator` can be dropped or hardcoded.
