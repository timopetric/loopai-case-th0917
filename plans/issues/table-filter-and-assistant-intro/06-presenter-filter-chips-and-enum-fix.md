Status: done

# 06 — Presenter: filter chips/repair text, plus the bundled enum-leak fix

## Parent

[`PRD.md`](PRD.md)

## What to build

Two changes to `app/agent/presenter.py`, both small and both scoped to this one file:

1. **New chip text for the filter**: `_diff_chips` gains a case for `entity_filter` changing —
   `f"Filter: {after.entity_filter}"` when set, `"Filter cleared"` when it goes from set to
   unset. Plus a `_repair_chip` entry for the new `ENTITY_FILTER_IGNORED` `RepairCode` (built in
   slice 02), rendering as `"Adjusted: entity filter has no effect without grouping by Actor or
   Mailbox"`.

2. **The previously-flagged, unrelated enum leak**: `_diff_chips`'s `"Added metric: {m.value}"` /
   `"Removed metric: {m.value}"` currently print the wire enum value (e.g. `handle_time`) instead
   of the label the rail already shows. Fix by reusing `_metric_label(m)`, already defined in this
   same file, so both chips read e.g. `"Added metric: Handle time"`. This was flagged as an
   outstanding, unfixed finding in the original handoff and is in scope now because this file is
   already being touched for the filter chips above — the handoff explicitly asked for it to be
   bundled in whenever this file was next modified.

## Acceptance criteria

- [ ] A `set_filter` change produces the correct chip text (`"Filter: <query>"` / `"Filter
      cleared"`)
- [ ] A filter-ignored Repair produces the correct chip text via `_repair_chip`
- [ ] `_diff_chips` now emits `"Added metric: Handle time"` (label), never `"Added metric:
      handle_time"` (wire value) — a regression test asserts this explicitly, closing the
      handoff's outstanding finding
- [ ] Existing presenter tests (`tests/test_agent_presenter.py`) still pass, moved/extended as
      needed to cover the new cases
- [ ] `make check` passes

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
