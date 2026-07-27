Status: done

# 04 — Exporters: XLSX records the active filter, CSV stays untouched

## Parent

[`PRD.md`](PRD.md)

## What to build

The XLSX "Report info" sheet's "Report definition" section already prints one row per spec
dimension, unconditionally, every time (Metrics, Date range, Granularity, Grouped by, Duration
display, Layout — none of these are ever omitted just because they're at a default value). Add
one more row in the same style, directly after "Grouped by":

```
["Entity filter", spec.entity_filter or "None"]
```

No separate "matched N of M" row — this sheet doesn't report row/entity counts for any other
dimension today, so adding one only for the filter would be new scope, not filling a gap. The
empty-match case is already covered for free: `table.warnings` (which will include the
empty-match warning from slice 02) already flows unconditionally into this sheet's existing
"Warnings" section.

CSV gets no changes. Its "pure data, no preamble" rule (architecture.md §3) is a settled,
deliberate constraint — a filtered CSV simply has fewer rows, exactly like a filtered CSV already
doesn't self-describe date range or grouping either. The export filename also stays unchanged
(it currently encodes only the date range) — a filter-only filename marker would be inconsistent
special-casing relative to every other spec field that equally affects row count and gets no
filename treatment.

## Acceptance criteria

- [ ] XLSX "Report info" sheet contains an "Entity filter" row with the real value when set
- [ ] XLSX "Report info" sheet contains an "Entity filter" row reading "None" when unset (row is
      always present, never conditionally omitted)
- [ ] A CSV export with `entity_filter` set is byte-for-byte identical in structure to one without
      it, aside from the (correctly filtered) row count — no preamble, no new columns
- [ ] Export filenames are unchanged (still date-range-only)
- [ ] Unit tests added for both the XLSX row and the CSV non-change
- [ ] `make check` passes

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
