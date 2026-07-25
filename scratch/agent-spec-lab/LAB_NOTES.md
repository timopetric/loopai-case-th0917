# Findings: LLM-edits-report-spec design lab

Status (extension round): 63 passed, 2 deselected (live-marked) by default.
Running with `-m live`: 1 passed (fixture-drift check against the real API),
1 skipped (real-model smoke test - no OPENROUTER_API_KEY in this
environment, so the tool schemas have still not been validated against an
actual qwen model).

Run (offline default): uv run --with pydantic,pytest,jinja2,openai python -m pytest scratch/agent-spec-lab/ -q
Run (live, occasionally): uv run --with pydantic,pytest,jinja2,openai,requests python -m pytest scratch/agent-spec-lab/ -q -m live

## CORRECTION (second probing pass): the mailbox breakdown is NOT unreliable

The original findings (and this lab's first version) concluded the
`mailbox` breakdown was broken because a 5-mailbox sample (the spec's own
example mailboxes: Returns, Partnerships, Compliance, Fax, Outbound) summed
to near-zero against the top-level totals. The second probing pass pulled
an **unscoped** request and got back all ~103 real mailboxes in the mock
dataset -- with no scope filter, `sum(mailbox[i].metric)` reconciles
**exactly** with the top-level total for every metric, including
`actioned_emails` (which is the one metric where the `actors` breakdown
does NOT reconcile -- actor-sum 28,941 vs top-level 19,024, a genuine
upstream inconsistency). The 5 spec-example mailboxes are simply
low-resolved-volume mailboxes in the mock data (all near-zero `resolved`);
that was a sampling artifact, not a data-quality problem with the mailbox
breakdown itself.

Consequences for the lab, now implemented in `engine.py`:
- `group_by="mailbox"` is a first-class, trusted path, symmetric with
  `group_by="agent"` -- both use `_reconciliation_warnings()`, which
  dynamically compares breakdown-sum vs top-level-total per metric rather
  than hardcoding "mailbox bad" or "actors always fine." It correctly
  fires only for `actioned_emails` under `group_by="agent"` and never under
  `group_by="mailbox"` (tested in `test_agent_breakdown_reconciles_or_warns`
  and `test_mailbox_breakdown_reconciles`, parametrized over all 15
  metrics).
- The old "mailbox_ids set -> unreliable data" warning is gone. It's
  replaced by two more precise, corrected behaviors:
  1. A mailbox_ids (or agent_ids) filter set while `group_by` doesn't match
     that dimension now warns that the filter **has no effect** on the
     numbers shown (matches the real API: scope/filters never touch
     top-level totals) -- `test_mailbox_filter_without_matching_group_by_warns_no_effect`.
  2. `group_by="agent"` combined with `mailbox_ids` (or the reverse) now
     raises `CrossBreakdownNotSupported` (`engine.CrossBreakdownNotSupported`,
     a `ValueError` subclass so it flows through the existing agent-loop
     retry path unchanged) rather than silently returning numbers that look
     plausible but aren't actually cross-filtered -- the upstream `actors`
     and `mailbox` arrays are independent, non-nested breakdowns of the same
     totals, there is no way to compute "agent X's activity in mailbox Y"
     from this API. Tested both directions in
     `test_cross_breakdown_not_supported_*`.

## Fixture rebuilt on real, wider data

`resp-full-unscoped-latest.json` (an unscoped, full-window, all-metrics pull,
saved into the lab directory) replaced the original 5-mailbox
`resp-q1-full-14day.json` as the fixture. Same 14-day window
(2026-07-10..2026-07-23, confirmed stable across both probing passes and a
same-day live re-check), but now 103 mailboxes / 108 actors instead of 5/108
-- makes the mailbox-grouping and cross-breakdown tests meaningful instead of
degenerate on near-zero data.

## Assumption-test inventory (new)

Every capability `ReportSpec` promises now has at least one test verifying
it against the real fixture (all in `test_agent_lab.py`, Part 2):

- **Reconciliation**: `test_agent_breakdown_reconciles_or_warns` and
  `test_mailbox_breakdown_reconciles`, parametrized over all 15 `Metric`
  values -- sum-over-group-rows equals the top-level total for every metric
  except `actioned_emails` under agent grouping, which must warn.
- **Weighted averages**: `test_weighted_average_matches_raw_sum_over_sum_count`
  (week and total granularity) checks the engine's `<metric>_avg` against
  `sum(raw metric)/sum(raw metric_count)` computed directly from the fixture
  arrays; `test_weighted_average_diverges_from_mean_of_means_on_real_data`
  confirms the weighted-average and mean-of-daily-averages formulas actually
  differ on this dataset, so the first test isn't vacuously true.
- **Date clamping/slicing**: `test_date_range_fully_inside_window_slices_exactly`
  (bucket count matches `ticks`, values match the raw arrays index-for-index);
  the earlier clamp/no-overlap-warning scenarios in Part 1 cover the
  out-of-window case.
- **Filters**: `test_agent_ids_filter_matches_fixture_exactly` and
  `test_mailbox_ids_filter_matches_fixture_exactly` -- a 3-id subset produces
  exactly 3 rows whose values match the corresponding fixture entries.
- **columns_order**: `test_columns_order_permutations_reorder_only_never_change_values`
  exhaustively permutes the 4 available columns (24 permutations) and checks
  only `Table.columns` order changes, never row values;
  `test_columns_order_unknown_column_is_validation_error` covers the
  reject case.
- **Pivot layout**: `test_pivot_round_trips_every_value_from_long` builds the
  same spec in both `layout="long"` and `layout="pivot"`, and checks every
  long-format value appears at the correct `(period, group::metric)` pivot
  cell (a lossless reshape, not an aggregation) plus a total-sum check;
  `test_pivot_requires_group_and_period_axis` checks the engine rejects
  pivot requests with no group or no period axis to pivot on (this is a new
  constraint introduced while implementing pivot -- see "pitfalls" below).
- **Sort**: `test_sort_correctness_and_tie_stability_on_real_data` checks
  desc/asc ordering on real (tied) values; `test_sort_field_must_be_an_included_metric`
  is a new model-level validator (added this round) rejecting a `sort.field`
  that isn't one of the report's own columns.
- **Spec round-trips**: `test_spec_json_roundtrip_is_identical`
  (ReportSpec -> JSON -> validate -> equal); `test_agent_can_never_brick_the_report`
  runs every representative `SpecPatch` shape the scripted scenarios produce
  through the engine and asserts none of them raise.
- **Live drift check**: `test_live_fixture_still_representative_of_real_api`,
  marked `@pytest.mark.live`, re-fetches an unscoped response and checks the
  frozen fixture still matches its shape (window length, mailbox/actor
  counts >= 100). Excluded from the default run by `pytest.ini`'s
  `addopts = -m "not live"`; run explicitly with `-m live`. Passed when run
  live this round.

## What the spec can / can't promise (given the upstream data)

**Possible, and tested:**
- Per-agent and per-mailbox breakdowns for any metric except `actioned_emails`
  under agent grouping (that one's flagged, not silently wrong).
- Exact date-range slicing for any range that overlaps the fixed 14-day
  window, with clamping + a warning for partial or zero overlap.
- Weighted (not mean-of-means) averages for all time metrics, at day/week/
  total granularity.
- Arbitrary column reordering with no effect on values.
- Lossless long<->pivot reshaping, given both a group axis and a period axis.
- Filtering by agent_ids or mailbox_ids, exactly, as long as `group_by`
  matches the filtered dimension.

**Hard, but handled with an explicit warning/error rather than silently
wrong data:**
- Filtering by a dimension that isn't the active `group_by` (no effect;
  warned).
- Requesting a date range with zero overlap with the fixed window (clamped
  to the full window; warned) -- mirrors the real API's own fallback
  behavior, but surfaced instead of hidden.
- `actioned_emails` per-agent numbers (upstream data inconsistency; warned,
  not hidden).

**Impossible given this upstream API, and the engine now refuses outright
rather than fabricating:**
- Any agent x mailbox cross-breakdown ("this agent's activity in this
  mailbox") -- `actors` and `mailbox` are independent, non-nested arrays of
  the same top-level totals; there is no join key between them in the data.
- True sub-day or true multi-week/month bucketing beyond what the fixed
  14-day daily-bucket dataset supports (the underlying API ignores
  `time_unit`/`time_period` entirely per the probe findings) -- `granularity`
  in this lab is a client-side re-bucketing of the same 14 daily buckets,
  not a request for different upstream granularity.
- Real mailbox/user/event-type *filtering at the upstream API level* --
  everything this engine does with `agent_ids`/`mailbox_ids`/date ranges is
  client-side slicing of one fixed, fully-downloaded dataset, not a
  narrower upstream query. This only works because the dataset is small
  enough to pull in full; it would not scale to a real multi-tenant backend
  without the upstream API actually implementing filtering.

## Verdict: patch, not full replacement

Recommendation: the agent should always edit the spec via a partial
SpecPatch, never by re-emitting the entire ReportSpec.

test_full_replacement_loses_fields_patch_does_not demonstrates the concrete
failure mode: a spec customized with layout="pivot", an agent_ids filter,
and a sort - when "replaced" by an LLM that only outputs the fields it is
actively reasoning about (metrics, date_from, date_to), the omitted fields
do not stay put, they silently fall back to pydantic defaults (layout back
to "long", filter and sort gone, group_by back to "none"). This is not a
hypothetical - it is exactly the kind of partial attention real tool-calling
models show on multi-field objects, especially smaller/faster ones. Patch
semantics make "fields I did not mention" mean "leave them alone" instead of
"reset them," which matches user intent for incremental requests ("switch
the columns," "only Returns," "last week") far better than requiring the
model to restate the whole object correctly every turn.

The cost of patch semantics: validation must happen on the merged result,
not the patch in isolation (date_from alone is meaningless without
date_to) - SpecPatch.apply() does this by dumping the base spec, merging in
only the explicitly-set patch fields (exclude_unset=True), and re-validating
the whole dict through ReportSpec.model_validate. This also sidesteps a
subtle pydantic gotcha found while building it: model_copy(update=...) does
not validate/coerce nested models, so a plain dict for `sort` silently sits
where a SortSpec should be and only surfaces later as a confusing serializer
warning. Round-tripping through model_dump(mode="json") + merge +
model_validate avoids that entirely and was simpler than it sounds.

## Tool surface: 3 tools, not more

get_spec, update_spec, run_report. Deliberately did not expose one tool per
field (set_group_by, set_date_range, ...) - compound requests like "group by
agent and sort by resolved and only last week" are extremely common and a
single-patch tool makes that one atomic, validated merge instead of a
sequence of tool calls where an intermediate state could be invalid or where
a mid-sequence failure leaves the spec half-edited. run_report returning a
compact summary (columns, row count, <=8 sample rows, warnings) rather than
the full table was enough for the fake model to "see" its own work in the
test_who_resolved_the_most scenario without bloating context.

## Spec diff -> UI chips

events.py's _diff_chips() is the single place allowed to turn a
before/after ReportSpec comparison into short human phrases ("Added metric:
handle time", "Grouping: by agent", "Swapped columns"). Two things made this
easier than expected:
- Detecting a reorder vs. a real change in columns_order by comparing the
  two lists as sets first ("Swapped columns") vs. showing a generic
  "Columns changed" otherwise - cheap and reads well.
- Symmetric add/remove diffing on metrics (set difference) instead of a
  generic "metrics changed" chip - users care which metric appeared/left,
  not that the list object changed.

One thing to watch in the real implementation: this function silently
returns no chip for changes it does not recognize a friendly phrasing for
(e.g. if a new spec field is added later without updating _diff_chips, edits
to it become invisible in the UI even though the tool call succeeded). Needs
a fallback path or a test that asserts every ReportSpec field has diff-chip
coverage.

## Event taxonomy

Two layers, one asymmetric mapping (to_ui_event, internal -> UI only, never
the reverse): ToolCallStarted/Finished, SpecUpdated, AssistantSays, Error,
Warning internally; status / spec_change / message / warning / error in the
UI. The important discipline, checked directly in tests
("columns_order" not in e.text, "update_spec" not in e.text): raw tool
names, raw JSON args, and raw pydantic validation error text must never
reach UiEvent.text. Retriable validation errors (Error(retriable=True)) map
to a generic "That didn't quite work, retrying..." status or nothing at all
- the retry loop is backend plumbing, not something to narrate turn-by-turn
to the user. Warning is intentionally separate from Error: nothing failed
(e.g. a date range got clamped, or mailbox data is flagged unreliable), but
the user should still know their literal request was not honored 1:1.

## What the system prompt must contain

Validated by test_system_prompt_renders_and_contains_units_warning. Three
things earned their place after building the engine against the real
fixture, not just in theory:
1. The units gotcha for time metrics is not optional context, it is
   load-bearing. handle_time/resolve_time/etc. are totals in hours with a
   companion _count, not per-ticket averages and not seconds (confirmed
   empirically in api-probe-findings.md Q2 - the "seconds" doc claim
   produces absurd values). An agent that does not know this will describe
   a total as "the average handle time" to the user, which is a
   believable-sounding but wrong number - worse than an obvious bug.
2. The fixed data window, stated explicitly with real dates, because the
   underlying API/engine clamps out-of-window requests rather than erroring
   (mirrors the real reporting API's own silent-clamp behavior per finding
   #1 in the probe notes) - the agent should expect and explain clamps, not
   be surprised by them.
3. The current spec as JSON, so "switch the columns around" can be answered
   with a targeted patch instead of the model needing to infer current
   state from conversation history.

## Pitfalls found while building this

- SUPERSEDED this round: mailbox data was believed untrustworthy based on
  pass-1's 5-mailbox sample. Pass 2's unscoped 103-mailbox pull showed it
  fully reconciles -- the earlier conclusion was a sampling artifact, not a
  real data problem. Lesson for future probing: a "reconciliation" check is
  only as good as the sample it's run against; a 5-of-103 sample that
  happens to be all near-zero-volume entries will look broken even when the
  underlying mechanism is fine. Prefer unscoped/full pulls for this kind of
  cross-check, and re-verify "unreliable data" conclusions before hardcoding
  them into product warnings -- this round replaced a hardcoded
  metric-name check with a dynamic reconciliation comparison specifically
  so the next data surprise doesn't require another hand-edit.
- Combining group_by with granularity used to silently collapse the whole
  date range into one row per group regardless of the requested granularity
  (a gap in the original lab, not a real-API limitation) -- fixed this round
  so group_by="agent"/"mailbox" + granularity="day"/"week" produces one row
  per (source, period), which is also what makes the pivot layout
  meaningful (it needs both a group axis and a period axis to transpose
  on). `layout="pivot"` now explicitly requires `group_by != "none"` and
  `granularity != "total"`, and raises otherwise rather than silently
  returning a degenerate 1-row/1-column pivot.
- Out-of-window vs. inverted date ranges need different handling. The real
  API silently substitutes the full window on zero-overlap ranges and
  produces a degenerate 1-bucket result on from > to - neither is an error
  from its point of view. This lab's ReportSpec validator rejects
  date_from > date_to outright (a real validation error, fed back to the
  LLM for retry - see test_invalid_date_range_patch_then_retry_succeeds),
  but zero-overlap ranges are accepted at the spec level and only clamped
  (with a warning) at run_report time, since "August" is a syntactically
  valid request that just happens to have no data, not a malformed spec.
- model_copy(update=...) skips validation for nested pydantic models - worth
  a code-review checklist item for anyone touching ReportSpec/SpecPatch
  later; always merge via dict + model_validate, not model_copy.
- Untested against a real model. No OPENROUTER_API_KEY was available in this
  environment, so test_real_qwen_model_can_call_update_spec is
  skipif-guarded and has never actually run. The biggest unvalidated risk is
  whether a real qwen model reliably (a) picks update_spec over
  get_spec/run_report for edit requests, (b) omits untouched fields rather
  than restating the whole patch, and (c) recovers cleanly from the
  validation-error-retry path with real (non-scripted) reasoning. The fake
  LLM tests only prove the harness is correct, not that the model will
  behave as scripted.
