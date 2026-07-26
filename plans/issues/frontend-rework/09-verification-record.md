# Slice 09 — browser verification record

Run 2026-07-26 against the **built image** (`docker run` of `timopetric/caseth0917:latest`) with
`DEV_FAKE_UPSTREAM=1 DEV_FAKE_LLM=1`, driven through Chrome DevTools MCP. The MCP server became
available after the owner reloaded plugins mid-session; every earlier session reported it missing.

The container ran with `APP_API_KEY` set to a throwaway value rather than the real one from `.env`,
so the shared key never entered the session transcript.

## Confirmed working

| Check | Result |
|---|---|
| Fonts load, no request leaves the origin | **13/13 requests same-origin or `data:`**; all three families fingerprinted from `/assets/` |
| Export matches the screen at full row count | **CSV had 1,514 lines while 16 rows were in the DOM** — virtualisation does not truncate the export |
| Withheld value in CSV | empty field, as specified; a muted dash with an `sr-only` label on screen |
| Duration headers name their unit | `Resolve time (h)`, `Handle time (h)` |
| Table semantics after virtualisation | `display: table/table-row/table-cell`, `scope="col"`, `aria-rowindex` from the **full** set, `aria-rowcount=1528` |
| Sort | `aria-sort="descending"`, arrow glyph, rows re-ranked, URL round-trips |
| Assistant moves the controls | sent a request; metrics went 4 → 5 and `handle_time` appeared in the URL and the table, with the report still on screen |
| Repair chips | render as badges |
| Dark mode | whole workspace, no light surface leaking, dark chart palette in use |
| Narrow viewport (390px) | panes stack, everything wraps, **no horizontal page scroll** |
| Console | clean apart from one autofill hint (see below) |

## Fixed during this pass

1. **Virtualisation was not working at all.** The shell root used `min-h-screen`, which is a
   *minimum* and never capped the flex chain. Every `min-h-0 flex-1 overflow-auto` below it grew to
   its content, the table's scroll parent reported a **67,232px** client height, and the virtualiser
   correctly concluded all 1,512 rows were visible — **all 1,526 rows were in the DOM.** Every
   source-level test passed throughout, because the code *is* virtualised; the layout never let it
   bind. Fixed with `lg:h-screen`. Now 16 rows in the DOM.
2. **Disabled buttons became unreadable.** Slice 07's border-contrast fix darkened
   `--border-hairline-strong`, which four buttons also used as a *disabled fill* — label contrast
   fell to **1.43:1**. A border colour should not be a surface; the fills now use `bg-hairline`.
3. **The Warnings banner was `role="alert"`** (assertive), so it interrupted on every report
   rebuild — and every control change rebuilds the report. Now `role="status"`.
4. **The report was the smallest thing on screen** — the chart at 320px plus two stacked dev-fake
   banners left the table ~130px. The chart is 240px, the banners are one compact row, and the
   table has a min-height floor.
5. **Horizontal overflow at 390px** — missing `min-w-0` on two flex wrappers plus a fixed-width
   density control 6px too narrow for its own labels.

## Found and deliberately not fixed

Both need a decision that is not this rework's to make.

1. **Duration values render as raw floats** — `11.482139109909799` in the Total row,
   `31.910186825396828` in body rows. This defeats the tabular alignment slice 04 exists for, and it
   is **pre-existing**, not a regression: the old table rendered the same raw value.

   It cannot be fixed on screen alone. `app/exporters.py:110` prints the full float *deliberately*,
   to match what JS renders, so rounding only the display would break the graded "the exported file
   matches exactly what is on screen" story. The correct fix rounds in the engine or in both
   exporters — and the PRD puts *"the engine, the exporters or the API"* out of scope for this
   rework. Worth doing next, as one change spanning engine and screen together.

2. **A Repair chip shows a wire enum** — "Added metric: handle_time", where the rail calls the same
   thing "Handle time (h)". Slice 09's own regression list says no enum value should appear in the
   conversation. The string is built at **`app/agent/presenter.py:243`** (`f"Added metric: {m.value}"`),
   which this rework may not touch and which carries the negative leak assertions.

   Mapping keys to labels in the frontend instead would mean parsing presenter prose, which is the
   brittle path the repo warns against elsewhere. One line in the presenter is the right fix; it
   just needs to be made where the presenter's tests can move with it.

## Not covered

- **Level 3 (live upstream, live model) is slice 10** and has not been run.
- A real screen reader was not driven — the ARIA is verified structurally and in the a11y tree, but
  NVDA/VoiceOver announcement behaviour is unverified.
- The clamped and refused date ranges, the assumptions modal's focus restore, and column reordering
  were verified structurally rather than clicked through.
