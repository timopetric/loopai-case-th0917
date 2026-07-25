# Fetch the full coverage window on every miss, memoised for 5 minutes

The upstream reporting endpoint ignores `event_types`, `time_unit`, `time_period`,
`time_type`, `timezone`, `community_id`, and `filters` entirely — only `from_date`/`to_date`
narrow the response, and a range outside the data window silently returns the *whole* window
instead of nothing. Measured, a full 14-day fetch is 362 KB / p50 0.289 s against 169 KB /
p50 0.252 s for a single day, so narrowing the request saves roughly 40 ms and 190 KB.

We therefore always request the **entire coverage window**, cache that one normalised dataset
in-process for **5 minutes**, and slice the user's requested date range out of it in the
engine. The cache key is the coverage window itself, read from the undocumented
`GET /health` endpoint (also 5-minute cached, falling back to the hardcoded
`2026-07-10 → 2026-07-23` only if `/health` is unreachable). This supersedes the earlier
"no caching layer, direct live calls" decision in `architecture.md` D2.

## Considered Options

- **Key on `(from_date, to_date)`** — the obvious reading of "cache the request", but every
  date-picker nudge misses and re-fetches substantially the same bytes.
- **Key on the whole spec, caching `ReportTable`** — hit rate collapses, since toggling a
  metric, re-sorting, or reordering a column changes the key without needing new upstream
  data. The re-aggregation it would save is microseconds over a 14×108 dataset.

## Consequences

- Date-range validation becomes **purely local**: we know the coverage window before calling
  upstream, so an out-of-range request is reported honestly instead of silently returning
  data for a different fortnight. This is the main reason for the decision, not the latency.
- Changing dates — including the Assistant doing it mid-conversation — costs zero upstream
  calls.
- Because the key is derived from `/health` rather than hardcoded, a redeployed upstream with
  a different data window is picked up within 5 minutes with no redeploy of this app.
- The app always pulls all 103 mailboxes and 108 actors, even to render one day for one
  actor. Accepted: it is 362 KB and sub-second, and the upstream offers no way to ask for
  less that actually works.
