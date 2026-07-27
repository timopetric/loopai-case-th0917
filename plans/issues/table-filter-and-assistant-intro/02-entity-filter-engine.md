Status: done

# 02 — `entity_filter` on ReportSpec + engine filtering

## Parent

[`PRD.md`](PRD.md)

## What to build

Add `ReportSpec.entity_filter: str | None = None` — a free-text, case-insensitive substring
filter matched against Actor or Mailbox names, depending on the report's current `group_by`.

A pydantic field validator normalizes empty and whitespace-only input to `None`, and trims
surrounding whitespace on any non-empty value, so "filter is set" and "filter has a real value"
can never disagree anywhere downstream (chips, exports, the `group_by == "none"` repair all need
to answer that as one clean boolean).

Wire the field into `engine.execute()`: before building grouped rows, filter the entity list
(Actors or Mailboxes, whichever `group_by` selects) by substring match on `.name`
(`query.lower() in name.lower()`, no diacritic folding — the real fixture data is all ASCII).
Three previously-undecided behaviors are now settled and must be implemented exactly as follows:

- **Totals reflect only the filtered rows.** This is a deliberate, noted exception to the
  engine's existing "totals are recomputed from the top-level dataset, never from summed rows"
  rule — that rule exists to avoid averaging averages, which is orthogonal to filtering (which
  changes which rows are included, not how a row's own average is computed).
- **A filter matching nothing produces an empty row set plus a Warning** that echoes the exact
  typed query, e.g. `No Actor/Mailbox name matched "theo mancinni" — showing an empty report.`
- **A filter set while `group_by == "none"` is a Repair, not an error**: add a new `RepairCode`
  member (e.g. `ENTITY_FILTER_IGNORED`) with the fixed phrase "entity filter has no effect
  without grouping by Actor or Mailbox" — the filter is ignored, the report renders normally
  ungrouped, and the Repair is reported. This matches ADR-0002's "cross-field drift is repaired
  and reported, never rejected" pattern already used for every other cross-field case in this
  engine.

## Acceptance criteria

- [ ] `ReportSpec(entity_filter="")`, `ReportSpec(entity_filter="   ")`, and
      `ReportSpec(entity_filter=None)` all produce `entity_filter is None`
- [ ] `ReportSpec(entity_filter="  theo  ")` produces `entity_filter == "theo"` (trimmed)
- [ ] A report grouped by Actor with `entity_filter` set to a partial name returns only matching
      rows, case-insensitively
- [ ] The Total row, when filtered, sums only the filtered rows — not the full dataset
- [ ] A filter matching zero entities returns an empty row set plus the exact warning text
      specified above, with the real typed query interpolated
- [ ] `group_by == "none"` with `entity_filter` set produces the new `RepairCode` in
      `execute()`'s output/warnings, the report renders as if ungrouped, and no exception is
      raised
- [ ] Unit tests in the style of `tests/test_engine.py` (same fixture, same assertion patterns
      used for the non-additive-metric and zero-count-average cases) cover all of the above
- [ ] `make check` passes

## Blocked by

None - can start immediately
