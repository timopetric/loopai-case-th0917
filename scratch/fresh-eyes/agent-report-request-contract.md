# Sub-agent report (verbatim relay): request contract & validation

Relayed by the orchestrator (agent was blocked from writing the file itself).
Evidence: `evidence/` (122 raw request/response files), `evidence/_summary.json`,
`probe-request-contract.py`, `probe-followup.py`, `probe-to-date.py`,
`probe-from-date2.py`, `analyze.py`.

~120 requests, no 429s. All "identical" claims are full-dict programmatic equality on
parsed JSON.

## 1. Required fields — only `from_date`

| Omitted | Status |
|---|---|
| `community_id`, `event_types`, `time_type`, `time_unit`, `time_period`, `timezone`, `filters` | 200, data unchanged |
| `to_date` | 200, data changes (see §9) |
| **`from_date`** | **422** |
| `{}` empty body | **422**, identical error |

Exact 422 body: ``Failed to deserialize the JSON body into the target type: missing field `from_date` `` —
a generic deserializer error, not a business validator. **7 of the doc's 8 "required"
fields are not enforced.** `from_date: ""` also 422 (treated as absent); `to_date: ""` → 200.

## 2. `event_types` — no observable effect

Single metric, `[]`, unknown name, mixed, non-array string, non-array number, `null`, all
15, omitted — all 9 variants byte-identical to baseline. No type or value validation.

## 3. `community_id` — no effect on data

Alternate string, `""`, `null`, numeric, UUID, plausible-nonexistent id, object, array —
all 200, identical to baseline. No 404/403 for bogus ids. Single hardcoded dataset.

## 4. `time_type` — no effect, and never substitutes for `from_date`

`today, yesterday, all, custom, 7d, 30d, 1d, 90d`, garbage, `null`, `123` — all 11
identical. With dates omitted, all still 422 missing `from_date`.

## 5. `time_unit` — no effect on tick spacing

`minute, hour, day, week, month`, garbage, `null` — all 7 produce the same daily ticks;
`minute` and `month` byte-identical to `day`.

## 6. `time_period` — no effect on bucket width

`1,2,3,7,0,-1,100,"1","abc",null,1.5`, combined with varied `time_unit` — every
combination returns the same daily ticks. No validation of negative/zero/fractional.

## 7. `timezone` — no effect on tick alignment

`America/New_York, UTC, Asia/Tokyo, Pacific/Kiritimati`, garbage, `null`, omitted — all 7
byte-identical; ticks always UTC midnight.

## 8. Unknown/extra fields — silently accepted, no effect

`group_by, granularity, breakdown, limit, offset, page, sort, metrics, agent_id,
user_id, include`, plus a combined junk payload — all 200, identical. Deserializer is not
`deny_unknown_fields`. No plausible undocumented param does anything.

## 9. Date handling — the only field family that works

**`from_date`:**
- Valid in-range ISO date sets the start tick correctly.
- Valid date before the data floor (`2026-06-01`, `2026-01-01`) is **clamped to 2026-07-10**.
- Any unparseable/wrong-type value ("yesterday", date without time, epoch int, bool,
  object, array) is accepted (200) and silently falls back to the floor-clamped result.
- Empty string is the sole rejected value (422, as if absent).

**`to_date`** — asymmetric:
- Valid in-range date sets the end tick correctly.
- Valid date beyond the ceiling clamps to `2026-07-24`.
- `to_date` before `from_date`, equal to `from_date`, or omitted/null → **1-day window**
  anchored at `from_date`.
- `to_date` present but unparseable (bad string, integer, empty string) → **full
  ceiling-clamped range**, NOT the 1-day window.

  Genuine inconsistency: two different "invalid" states produce two different fallbacks.
  (Speculation: `to_date ?? from_date+1day` vs a garbage string becoming `Invalid Date`
  that a `min(parsed, ceiling)` comparison resolves to the ceiling. Unconfirmed.)

No date variant ever produced a 4xx — only field absence or empty-string `from_date`.

## 10. Method / content-type

| Request | Status | Notes |
|---|---|---|
| GET / PUT / DELETE | 404 | Express `Cannot GET /...` |
| form-urlencoded body | 422 | same missing-`from_date` error; body not parsed as JSON |
| malformed JSON | 400 | generic Express HTML `Bad Request` |

Two distinct error layers: raw JSON parse failure → Express 400 HTML; structurally valid
but incomplete → plain-text 422 with serde/Rust-style wording, despite
`x-powered-by: Express`. (Speculation: Rust validation layer behind an Express gateway.)

## Contradictions vs documented contract

1. Only `from_date` is required; doc claims 8 fields are.
2. `event_types` has zero effect — full metric set always returned.
3. `community_id` has zero effect on data.
4. `time_type` has zero effect and never removes the `from_date` requirement.
5. `time_unit` / `time_period` have zero effect — always daily bucketing.
6. `timezone` has zero effect — ticks always UTC midnight.
7. No undocumented params show any effect.
8. Date clamping/fallback logic is real but internally inconsistent.
