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

Needs a decision that is not this rework's to make.

1. **A Repair chip shows a wire enum** — "Added metric: handle_time", where the rail calls the same
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

## Follow-up, same day — the table collapsed to one row

Reported from a real window: the table showed only its header and the Total row, with nothing
scrollable to reach.

The min-height floor from fix (4) was on the *outer wrapper*, but the Warnings banner and the
density row are siblings **inside** `ReportTable`. With two warnings (selecting `actioned_emails`
adds the non-additivity Warning) the banner alone spent ~120px of the 256px floor, leaving about
one row.

Three corrections, verified at 620px and 1000px viewport heights:

- the floor moved onto the **scrolling grid itself**, so it guarantees rows rather than whatever is
  left after the banners
- the wrapper regained **`min-h-0`** — removing it left `min-height: auto`, which refused to shrink
  and put all 1,526 rows back in the DOM, reintroducing the original virtualisation bug within
  minutes of fixing it
- the floor is **`40vh`, not a fixed rem**: inside the pane's own scroll container `flex-1` does not
  reclaim spare room, so a fixed floor gave a tall window the same few rows as a short one

Now ~5 rows at 620px and ~9 at 1000px, with 21 rows in the DOM and the report column scrolling for
the rest.


## Follow-up — durations, and the row count

**Durations now read as `31h 55m` on screen and stay numeric in the exports.**
`engine._display_value` rounds every Duration Metric to two decimals at the single place one is
produced, so `11.482139109909799` is now `11.48` in the CSV and the workbook, and the browser
renders that as `11h 29m`.

**Screen and file deliberately disagree here, and that was decided explicitly with the owner.**
The alternative — formatting hours and minutes in the exporters too, to preserve "the file matches
the screen" literally — would make the duration column *text* in Excel, so nobody could sum,
average or chart it. Keeping the number is what an export is for. `test_frontend_report_table.py`
guards the split in both directions: the formatter must exist in the browser and must NOT appear in
`app/exporters.py`.

The engine tests that pinned unrounded means now compare to `DURATION_TOLERANCE` (0.005, half a
rounding step). The assertion contrasting the weighted mean against the naive mean-of-daily-averages
is deliberately left tight — those differ by orders of magnitude, which is its whole point.

**The grid is pinned at 10 visible rows.** It was briefly a 10–100 picker; pinning keeps the chart
and the Warnings on screen without scrolling the middle column first. Still a viewport size, never a
page size — every row stays in the Report Table and both exports, verified again after the change:
1,514 CSV lines against 23 rows in the DOM.
