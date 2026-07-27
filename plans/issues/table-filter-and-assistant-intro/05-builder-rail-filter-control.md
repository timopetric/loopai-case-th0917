Status: done

# 05 — Builder-rail filter control

## Parent

[`PRD.md`](PRD.md)

## What to build

Add a filter text input to the builder rail (`BuilderPane.tsx`), in a new "Filter" section placed
directly below "Grouping", using the existing `TextInput` primitive:

- **Always rendered**, never appears/disappears as grouping changes (avoids rail reflow). When
  `groupBy === "none"`, the input is `disabled` with an explanatory placeholder (e.g. "Group by
  Actor or Mailbox to filter").
- Label reads "Filter by Actor name" or "Filter by Mailbox name", dynamically following the
  current `groupBy`.
- The store gains an `entityFilter: string | null` field and a setter, wired into `buildSpec`/
  `applySpec` exactly like every other field.
- **The store keeps `entityFilter`'s value even while the control is disabled** — toggling
  grouping to "None" does not clear it; switching back to Actor/Mailbox restores exactly what the
  user last typed. This is what makes the `group_by == "none"` + filter-set Repair (built in
  slice 02) a real, reachable path rather than dead code the UI happens to prevent.
- The rail input itself debounces (~300-400ms after typing stops) before writing to the store — a
  bare `onChange` writing straight through would fire a network request and a chart re-render on
  every keystroke. Once the debounced write lands in the store, `entityFilter` needs no special
  handling anywhere downstream: it slots into the existing report-fetch effect and the existing
  URL-sync effect in `WorkspaceShell.tsx` exactly like every other field already does (both are
  already un-debounced, `history.replaceState`-based — confirmed, not assumed).
- The rail control **never emits a chip** — chips remain exclusively an Assistant-conversation
  concept; no other rail control produces one either.

## Acceptance criteria

- [ ] Typing a name into the filter field, when grouped by Actor, narrows the visible table to
      matching rows after the debounce settles
- [ ] Switching `groupBy` to "None" disables the filter input (with placeholder text) but does not
      clear its typed value; switching back to Actor/Mailbox immediately restores the filter's
      effect with no re-typing
- [ ] The filter input never produces a chip anywhere in the UI
- [ ] The report's URL updates to reflect the filter (via slice 03's round-trip), same cadence as
      every other field
- [ ] Verified in a real browser (Chrome DevTools MCP) against `make run` with `DEV_FAKE_UPSTREAM`
      — this is UI wiring, not source-level-tested per this project's existing convention

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
- [03 — `entity_filter` round-trips through the shareable URL](03-spec-url-entity-filter.md)
