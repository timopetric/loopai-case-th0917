Status: ready-for-agent

# 12 — Full Chrome DevTools MCP verification pass (final gate)

## Parent

[`PRD.md`](PRD.md)

## What to build

Not a feature slice — the explicit final verification gate for this entire body of work, run only
after every other slice (02-11) is complete and `make check` is green. This is deliberately
ordered last, per the product owner's own instruction during design: browser verification via
Chrome DevTools MCP is one of the *last* steps, used to catch and correct anything the individual
slices' own narrower checks missed, matching architecture.md §12's existing "Level 3 last, once"
rule.

Walk through, against `make run` first with `DEV_FAKE_UPSTREAM`/`DEV_FAKE_LLM` (Level 2, free)
and then against the real thing (Level 3, required before declaring done):

- Sign in; confirm the new hard-coded Assistant introduction renders correctly on first load
- Exercise the builder-rail filter control: type a partial name while grouped by Actor, confirm
  the table narrows; switch grouping to Mailbox, confirm the label/behavior follows; switch
  grouping to "None," confirm the input disables with its placeholder but the typed value is
  preserved when grouping is restored
- Trigger the empty-match case (a filter matching nobody) and confirm the Warning banner appears
  with the typed query echoed
- Ask the Assistant to filter by a loosely-typed name ("filter to just theo's numbers") and
  confirm `set_filter` fires, the chip appears, and the table narrows correctly
- Ask the Assistant to filter while grouping is "None" and confirm the Repair chip appears with
  the correct wording, without an error
- Watch the reasoning indicator live through all three states (waiting → thinking, expanded →
  collapsed) across a multi-Tool-Step turn; manually collapse mid-turn and confirm it isn't
  snapped back open
- Confirm past turns' reasoning remains visible/re-expandable after sending a new message
- Download a filtered CSV and a filtered XLSX; confirm the XLSX "Report info" sheet states the
  active filter and the CSV contains no preamble, just the (correctly filtered) rows
- Confirm a shared URL with a filter applied restores the identical filtered report on reload
- Read the browser console and network panel throughout for anything a source-level test
  structurally cannot catch (per architecture.md §12) — a 401 loop, a CORS surprise, a build-time
  value baked in, an unhandled exception during the new reasoning-panel state transitions

Fix anything found directly, in the smallest slice it belongs to, rather than accumulating fixes
here — this issue's job is to find problems and route them, not to become a dumping ground of
unrelated patches.

## Acceptance criteria

- [ ] Every checklist item above passes against `make run` with dev fakes (Level 2)
- [ ] Every checklist item above passes against the real upstream/LLM (Level 3), run last, once
- [ ] Any defect found is fixed in the appropriate earlier slice (or a new small follow-up issue is
      opened for it) rather than patched ad hoc in this issue
- [ ] `make check` is green after any fixes made during this pass

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
- [03 — `entity_filter` round-trips through the shareable URL](03-spec-url-entity-filter.md)
- [04 — Exporters: XLSX records the active filter, CSV stays untouched](04-exporters-entity-filter.md)
- [05 — Builder-rail filter control](05-builder-rail-filter-control.md)
- [06 — Presenter: filter chips/repair text, plus the bundled enum-leak fix](06-presenter-filter-chips-and-enum-fix.md)
- [07 — The `set_filter` Assistant tool](07-set-filter-tool.md)
- [08 — System prompt rewrite and tool-schema description overhaul](08-system-prompt-and-tool-descriptions.md)
- [09 — ADR-0005 backend wiring: stream raw reasoning to all users](09-reasoning-default-on-backend.md)
- [10 — Frontend: per-message reasoning trace, three-state indicator](10-frontend-reasoning-ui.md)
- [11 — Hard-coded Assistant introduction](11-assistant-introduction.md)
