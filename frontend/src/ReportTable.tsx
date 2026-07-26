import { useEffect, useMemo, useRef, useState } from "react";

import { useVirtualizer } from "@tanstack/react-virtual";

import type { ReportTable as ReportTableData, ReportRow, SortSpec } from "./lib/report";
import { SegmentedControl } from "./ui/SegmentedControl";

/**
 * The group column header must follow the selected grouping (issue 06) —
 * this used to be hardcoded to "Actor" from when `group_by` could only ever
 * be "agent" (issue 04). The wire value stays `"agent"` (CONTEXT.md — the
 * upstream/spec spelling is correct and not renamed); only the label
 * shown to the user is "Actor".
 */
function groupColumnLabel(groupBy: "none" | "agent" | "mailbox"): string | null {
  if (groupBy === "agent") return "Actor";
  if (groupBy === "mailbox") return "Mailbox";
  return null;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * `"2026-07-10"` -> `"10 Jul"` — the grouping label (issue 04: "Bucket
 * becomes a grouping, not a repeated cell"). Plain string slicing rather
 * than `Date` parsing, matching `BuilderPane.tsx`'s `formatShortDate`: a
 * Bucket has no time component, and round-tripping through `Date` risks a
 * timezone-driven off-by-one (CLAUDE.md's general caution about date
 * handling). `granularity: "total"` collapses every row onto the single
 * `bucket === "total"` (`app/engine.py`), which reads as "Total" instead.
 */
function formatBucketLabel(bucket: string): string {
  if (bucket === "total" || bucket === "pivot") return "Total";
  const parts = bucket.split("-");
  if (parts.length !== 3) return bucket;
  const day = Number.parseInt(parts[2], 10);
  const month = MONTHS[Number.parseInt(parts[1], 10) - 1];
  if (Number.isNaN(day) || !month) return bucket;
  return `${day} ${month}`;
}

/** A withheld Duration Metric average or `actioned_emails`-across-Actors
 * total (issue 05/PRD's withheld-value rule): visibly distinct from a real
 * figure (muted colour, no numeral) AND from an empty cell (a real glyph is
 * always painted here, never nothing) — never mistakable for `0`. */
function WithheldValue() {
  return (
    <span className="text-stone">
      <span aria-hidden="true">—</span>
      <span className="sr-only">not available</span>
    </span>
  );
}

/**
 * A Duration Metric arrives as a number of HOURS (`api-report-fresh.md` — the
 * documented seconds are wrong) already rounded to two decimals by
 * `engine._display_value`. `11.48` reads as a decimal nobody converts in
 * their head, so the table shows `11h 29m`.
 *
 * This is the one place the screen and the exported file deliberately
 * disagree: the CSV and the workbook keep the number, so a spreadsheet can
 * still sum and chart the column. Decided explicitly with the owner; recorded
 * in `plans/issues/frontend-rework/09-verification-record.md`.
 */
function formatHours(value: number): string {
  const totalMinutes = Math.round(value * 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${String(minutes).padStart(2, "0")}m`;
}

type Density = "comfortable" | "compact";

const DENSITY_OPTIONS = [
  { value: "comfortable" as const, label: "Comfortable" },
  { value: "compact" as const, label: "Compact" },
];

/** Fixed row-height classes keyed to `Density`, and the pixel value the
 * virtualizer must use for the SAME rows — these two constants are read
 * together everywhere a row height matters (`ROW_HEIGHT_CLASS[density]` for
 * the rendered `<td>`, `ROW_HEIGHT_PX[density]` for `estimateSize`) so they
 * cannot drift apart into a rendered row that doesn't match the space the
 * virtualizer reserved for it. */
/** How many rows the grid shows at once — a VIEWPORT size, not a page size.
 * Every row stays in the Report Table and in both exports; the rest are
 * reached by scrolling the grid, exactly as before. Nothing here slices,
 * fetches or paginates. Pinned at 10 rather than offered as a control: it
 * leaves the chart and the Warnings visible on a laptop without the middle
 * column needing to be scrolled first. */
const VISIBLE_ROWS = 10;

const ROW_HEIGHT_CLASS: Record<Density, string> = { comfortable: "h-11", compact: "h-8" };
const ROW_HEIGHT_PX: Record<Density, number> = { comfortable: 44, compact: 32 };

/** The column header row and every Bucket group-header row share this exact
 * height (`h-11` = 44px — bumped from 40px in issue 08: frontend-rework so
 * the sortable header buttons and column-order controls that live inside
 * it clear the design reference's 44px touch-target floor, not just their
 * own padding), which is also why a group header's sticky offset can be
 * the static Tailwind class `top-11` instead of a computed value — the
 * header never changes height with density, only body rows do. */
const HEADER_ROW_PX = 44;

type FlatItem =
  | { kind: "group"; bucket: string; label: string }
  | { kind: "row"; row: ReportRow; rowIndex: number };

/**
 * A virtualised table of the executed report (issue 04), extended in issue
 * 05 for Duration Metrics, and in issue 07 for the three table-presentation
 * controls — sort, column order, and the pivot layout:
 *
 * - **Sort** is a click on a column header, in the "long" layout only —
 *   pivot's columns are Buckets (dates), not metrics, and `spec.sort` names
 *   a metric, so it has nothing to bind to there (`app/engine.py`'s
 *   `_execute_pivot` docstring). The header shows an arrow for the sorted
 *   column and its direction; the *semantics* (within-Bucket, global only
 *   when the report has collapsed to one Bucket) live entirely in the
 *   engine — this component only reflects state, it never reorders rows
 *   itself, so the table and the exports (issues 10-11, which read the same
 *   `ReportTable.columns`/`rows` the engine already sorted) cannot disagree.
 * - **Column order**: `<`/`>` buttons per header move a column one slot;
 *   `App.tsx` recomputes the order from `table.columns` (the engine's own
 *   output) and resends it as `columns_order`, so the button always acts on
 *   what's actually on screen.
 * - **Pivot**: `layout === "pivot"` means `table.columns` are Buckets, not
 *   metrics, and `table.rows` are keyed by group only — `row.values` is
 *   indexed by Bucket date instead of by metric key. Rendering this through
 *   the *same* `table.columns.map(...)` as the long layout is deliberate:
 *   the column/value contract (`row.values[column.key]`) doesn't change
 *   between layouts, only what a "column" represents does. There is no
 *   Bucket *grouping* in this layout (there is nothing left to group — a
 *   pivot row already is one Bucket-independent group), so `flatItems`
 *   below only ever produces `"group"` items for the long layout.
 *
 * Otherwise renders exactly the raw numbers and column metadata the backend
 * sends — no client-side re-aggregation, so preview and exports cannot
 * disagree with what is on screen. The pivot "chart metric only" statement
 * (user story 17) is *not* re-derived here — it arrives as one of
 * `table.warnings` from `engine._execute_pivot`, the same banner every
 * other Warning already renders through, so there is exactly one place that
 * decides what the message says.
 *
 * issue 04 (frontend-rework) rewrites the rendering strategy on top of all
 * of the above, unchanged: only `table.rows` (still every row the engine
 * returned — nothing sliced, nothing paginated) is ever windowed into the
 * DOM. `@tanstack/react-virtual` was added for this — a small (~5KB),
 * headless row virtualizer with no opinion on markup, which matters here
 * because the table stays a real `<table>` (sticky `<th>`/`<td>`,
 * `colSpan` group-header rows, native column-width negotiation) rather than
 * a `<div>` grid a heavier "virtual table" component would force. The
 * technique is the same top/bottom "spacer row" recipe used in the
 * library's own table example: only the rows inside `getVirtualItems()`
 * become real `<tr>`s; the two spacer `<tr>`s stand in for the collapsed
 * space above and below them so the scrollbar still represents the full
 * `flatItems.length`, not a page of it. This is also the one place in this
 * file `style={{ height }}` legitimately appears: virtualization is
 * dynamic scroll-position arithmetic (a pixel offset computed per render),
 * not a design value, so it is not a Tailwind/token-layer regression — the
 * token layer covers colour, spacing and type, none of which this
 * computed number touches.
 */
export function ReportTable({
  table,
  groupBy,
  layout,
  sort,
  onSort,
  onMoveColumn,
}: {
  table: ReportTableData;
  groupBy: "none" | "agent" | "mailbox";
  layout: "long" | "pivot";
  sort: SortSpec | null;
  onSort: (columnKey: string) => void;
  onMoveColumn: (columnKey: string, direction: "left" | "right") => void;
}) {
  const [density, setDensity] = useState<Density>("comfortable");
  const groupLabel = groupColumnLabel(groupBy);
  const hasGroups = groupLabel !== null && table.rows.some((row) => row.group_label !== null);
  const isPivot = layout === "pivot";
  const showLeadColumn = hasGroups || isPivot;
  const totalColumnCount = (showLeadColumn ? 1 : 0) + table.columns.length;

  // The engine already returns `table.rows` grouped into contiguous
  // same-Bucket runs (`app/engine.py`'s `_sort_rows_within_bucket` docstring
  // — sort only ever reorders *within* a run) — this only detects the run
  // boundaries the engine already produced, it never re-groups anything
  // itself. `isPivot` rows have nothing to group: each row already IS one
  // Bucket-independent group.
  const flatItems = useMemo<FlatItem[]>(() => {
    if (isPivot) {
      return table.rows.map((row, rowIndex) => ({ kind: "row" as const, row, rowIndex }));
    }
    const items: FlatItem[] = [];
    let lastBucket: string | null = null;
    table.rows.forEach((row, rowIndex) => {
      if (row.bucket !== lastBucket) {
        items.push({ kind: "group", bucket: row.bucket, label: formatBucketLabel(row.bucket) });
        lastBucket = row.bucket;
      }
      items.push({ kind: "row", row, rowIndex });
    });
    return items;
  }, [table.rows, isPivot]);

  const scrollParentRef = useRef<HTMLDivElement>(null);
  const rowHeightPx = ROW_HEIGHT_PX[density];

  const rowVirtualizer = useVirtualizer({
    count: flatItems.length,
    getScrollElement: () => scrollParentRef.current,
    // Every size here is exact, not truly "estimated" — a group-header row
    // is always `HEADER_ROW_PX` and a data row is always `ROW_HEIGHT_PX
    // [density]` (real fixed-height Tailwind classes below, `h-10`/`h-11`/
    // `h-8`), so there is nothing left for the virtualizer to reconcile
    // against a measured DOM size.
    estimateSize: (index) => (flatItems[index]?.kind === "group" ? HEADER_ROW_PX : rowHeightPx),
    overscan: 10,
  });

  // `estimateSize`'s closure captures `density`/`flatItems` but the
  // virtualizer only re-reads it for indices it hasn't sized yet — a
  // density change (or a fresh `table`, which rebuilds `flatItems`) must
  // force it to throw away that cache and re-measure everything, per the
  // library's own guidance for "the sizing logic itself changed".
  useEffect(() => {
    rowVirtualizer.measure();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [density, flatItems]);

  const virtualRows = rowVirtualizer.getVirtualItems();
  const totalSizePx = rowVirtualizer.getTotalSize();
  const paddingTop = virtualRows.length > 0 ? virtualRows[0].start : 0;
  const paddingBottom =
    virtualRows.length > 0 ? totalSizePx - virtualRows[virtualRows.length - 1].end : 0;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {table.warnings.length > 0 && (
        <div
          // `status` (polite), not `alert`: these Warnings are a standing
          // property of the report, not an interruption, and every control
          // change rebuilds the report — an assertive region would cut across
          // whatever the user was reading each time.
          role="status"
          className="mb-3 rounded-lg border border-beige-deep bg-cream px-4 py-3 text-body-sm
            text-ink-tint"
        >
          <p className="mb-1 text-micro-uppercase font-semibold text-steel">Warnings</p>
          <ul className="list-disc space-y-1 pl-5">
            {table.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-2 flex flex-wrap items-center justify-end gap-2">
        <span className="text-micro font-medium uppercase tracking-wide text-muted">Density</span>
        <div className="max-w-full">
          <SegmentedControl name="Row density" options={DENSITY_OPTIONS} value={density} onChange={setDensity} />
        </div>
      </div>

      <div
        ref={scrollParentRef}
        // The height is chosen by the user, in rows, rather than left to
        // flex: inside the pane's own scroll container `flex-1` never
        // reclaims the spare room, so the grid sat at whatever floor it was
        // given no matter how tall the window was. Rows x row height plus
        // the column header and the totals row is exact and predictable —
        // ask for 25 rows and you get 25. Past the pane's height the pane
        // scrolls (ReportPane is `overflow-y-auto`); the rows beyond the
        // chosen count are reached by scrolling the grid, as before.
        style={{ height: VISIBLE_ROWS * rowHeightPx + HEADER_ROW_PX * 2 }}
        // `shrink-0` is load-bearing: a flex item shrinks below its own
        // height by default, so the chosen row count collapsed back to a
        // single row whenever the pane was tight. Holding the height makes
        // the pane overflow instead, which is what gives the middle column
        // its scrollbar.
        className="shrink-0 overflow-auto rounded-lg border border-hairline bg-canvas"
      >
        {/* `border-separate` + zero spacing, not `border-collapse`: sticky
            positioning on `<th>`/`<td>` is unreliable under
            `border-collapse` in some engines (notably Safari drops the
            sticky offset entirely), which would silently break the header
            and leading-column stickiness this issue exists to add. */}
        {/*
          Virtualisation (issue 04) means only a slice of `flatItems` is
          ever a real `<tr>` at once — the constraint issue 08 exists to
          protect is that this must not read as a SMALLER table to
          assistive technology than it visually is. `aria-rowcount` states
          the true total (every Bucket-group row, every data row, the
          column header and the totals footer) and every `<tr>` below
          carries an explicit `aria-rowindex` computed from its position in
          the FULL row set — never from where it happens to land in the
          currently-mounted window. `@tanstack/react-virtual`'s
          `getVirtualItems()` already hands back `.index` as an index into
          the full `count` passed to `useVirtualizer` (not a 0..N index
          over just what's rendered), so `virtualRow.index` is already the
          right number; it only needs the `+2` offset for the header row
          (index 1) and 1-based counting. See
          `tests/test_frontend_accessibility.py::TestVirtualizedTableSemantics`.
        */}
        <table
          className="w-full border-separate border-spacing-0 text-body-sm"
          aria-rowcount={flatItems.length + 2}
          aria-colcount={totalColumnCount}
        >
          <thead>
            <tr className="h-11" aria-rowindex={1}>
              {showLeadColumn && (
                <th
                  scope="col"
                  className="sticky left-0 top-0 z-30 h-11 border-b border-hairline-strong bg-canvas
                    px-3 text-left align-middle text-body-sm-medium font-semibold text-ink-tint"
                >
                  {hasGroups ? groupLabel : ""}
                </th>
              )}
              {table.columns.map((column, index) => (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    isPivot
                      ? undefined
                      : sort?.column === column.key
                        ? sort.direction === "desc"
                          ? "descending"
                          : "ascending"
                        : "none"
                  }
                  className="sticky top-0 z-20 h-11 border-b border-hairline-strong bg-canvas
                    px-3 text-right align-middle text-body-sm-medium font-semibold text-ink-tint"
                >
                  {isPivot ? (
                    <>
                      {column.label}
                      {column.unit === "hours" ? " (h)" : ""}
                    </>
                  ) : (
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => onSort(column.key)}
                        className="cursor-pointer border-none bg-transparent p-0 text-right
                          [font:inherit] font-semibold text-ink-tint hover:text-ink"
                      >
                        {column.label}
                        {column.unit === "hours" ? " (h)" : ""}
                        {sort?.column === column.key ? (sort.direction === "desc" ? " ▼" : " ▲") : ""}
                      </button>
                      <span className="inline-flex gap-0.5">
                        <button
                          type="button"
                          disabled={index === 0}
                          onClick={() => onMoveColumn(column.key, "left")}
                          aria-label={`Move ${column.label} left`}
                          className="inline-flex h-6 w-6 items-center justify-center rounded border
                            border-hairline-strong bg-canvas text-micro leading-none text-steel
                            hover:bg-cream-soft disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {"<"}
                        </button>
                        <button
                          type="button"
                          disabled={index === table.columns.length - 1}
                          onClick={() => onMoveColumn(column.key, "right")}
                          aria-label={`Move ${column.label} right`}
                          className="inline-flex h-6 w-6 items-center justify-center rounded border
                            border-hairline-strong bg-canvas text-micro leading-none text-steel
                            hover:bg-cream-soft disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {">"}
                        </button>
                      </span>
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paddingTop > 0 && (
              <tr aria-hidden="true" style={{ height: paddingTop }}>
                <td colSpan={totalColumnCount} />
              </tr>
            )}
            {virtualRows.map((virtualRow) => {
              const item = flatItems[virtualRow.index];
              if (!item) return null;

              if (item.kind === "group") {
                return (
                  <tr
                    key={`group-${item.bucket}-${virtualRow.index}`}
                    aria-rowindex={virtualRow.index + 2}
                  >
                    <td
                      colSpan={totalColumnCount}
                      // Not sticky. It used to be `sticky top-11`, which
                      // detached it and painted it over the first row of its
                      // own Bucket, and the `sticky left-3` span inside
                      // squeezed the label into a narrow floating box. A
                      // Bucket header is a divider; it reads fine scrolling
                      // with its rows.
                      className="h-11 border-b border-hairline-strong bg-cream px-3 align-middle
                        text-body-sm-medium font-semibold text-ink-tint whitespace-nowrap"
                    >
                      {item.label}
                    </td>
                  </tr>
                );
              }

              const { row, rowIndex } = item;
              const zebraBg = rowIndex % 2 === 1 ? "bg-surface" : "bg-canvas";
              return (
                <tr
                  key={`row-${rowIndex}`}
                  className="group"
                  aria-rowindex={virtualRow.index + 2}
                >
                  {showLeadColumn && (
                    <td
                      className={`sticky left-0 z-10 ${ROW_HEIGHT_CLASS[density]} ${zebraBg}
                        border-b border-hairline-soft px-3 align-middle text-body-sm text-ink-tint
                        whitespace-nowrap group-hover:bg-cream-soft`}
                    >
                      {hasGroups ? row.group_label : ""}
                    </td>
                  )}
                  {table.columns.map((column) => {
                    const value = row.values[column.key];
                    const count = row.counts[column.key];
                    return (
                      <td
                        key={column.key}
                        title={count !== undefined ? `${count} ticket${count === 1 ? "" : "s"}` : undefined}
                        className={`${ROW_HEIGHT_CLASS[density]} ${zebraBg} border-b
                          border-hairline-soft px-3 text-right align-middle font-mono
                          tabular-nums whitespace-nowrap text-ink group-hover:bg-cream-soft`}
                      >
                        {value === null ? (
                          <WithheldValue />
                        ) : column.unit === "hours" ? (
                          formatHours(value)
                        ) : (
                          value
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {paddingBottom > 0 && (
              <tr aria-hidden="true" style={{ height: paddingBottom }}>
                <td colSpan={totalColumnCount} />
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr aria-rowindex={flatItems.length + 2}>
              {showLeadColumn && (
                <td
                  className="sticky bottom-0 left-0 z-30 h-11 border-t-2 border-hairline-strong
                    bg-canvas px-3 align-middle text-body-sm-medium font-semibold text-ink-tint"
                >
                  Total
                </td>
              )}
              {table.columns.map((column) => {
                const value = table.totals[column.key];
                const count = table.total_counts[column.key];
                return (
                  <td
                    key={column.key}
                    title={count !== undefined ? `${count} ticket${count === 1 ? "" : "s"}` : undefined}
                    className="sticky bottom-0 z-20 h-11 border-t-2 border-hairline-strong bg-canvas
                      px-3 text-right align-middle font-mono tabular-nums font-semibold text-ink"
                  >
                    {value === null ? (
                      <WithheldValue />
                    ) : column.unit === "hours" ? (
                      formatHours(value)
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
