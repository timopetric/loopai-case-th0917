import { Chart } from "../Chart";
import { ReportTable } from "../ReportTable";
import type { Meta } from "../lib/meta";
import type { ReportTable as ReportTableData } from "../lib/report";
import { useReportSpecStore } from "../store/reportSpecStore";

/**
 * The centre "report" zone (issue 02: frontend-rework) — the chart and the
 * table (architecture.md §7, panel 2). Docking the Assistant permanently on
 * the right is the whole point of this slice, so this pane must stay
 * visible and legible next to it rather than assuming the full viewport
 * width the old single-column `App.tsx` gave it.
 *
 * `table`/`reportError`/`presetsReady` are fetch-derived state owned by
 * `WorkspaceShell` (a report request, not Report Spec state) and handed
 * down as props — this pane holds no state of its own beyond what's needed
 * to render what it's given. Sort, column order, layout and chart-metric
 * selection are read from and written back to the shared Report Spec store,
 * the same one `BuilderPane` edits and `AssistantPane` applies to
 * wholesale.
 */
export function ReportPane({
  table,
  reportError,
  presetsReady,
  loading,
  meta,
}: {
  table: ReportTableData | null;
  reportError: string | null;
  presetsReady: boolean;
  /** True for the duration of any report round trip after the first —
   * sorting a column, changing the date range, moving a column. Rendered
   * as `aria-busy` plus a small status line ON TOP of the previous,
   * still-good table (issue 08: frontend-rework accessibility polish;
   * `WorkspaceShell.tsx`'s `reportLoading` docstring has the full
   * reasoning). Never swaps the table out for a spinner — that would be
   * the "disturb a good result" mistake this issue also calls out for
   * export failures. */
  loading: boolean;
  meta: Meta | null;
}) {
  const {
    metrics,
    groupBy,
    layout,
    sort,
    toggleSort,
    moveColumn,
    chartMetric,
    setChartMetric,
  } = useReportSpecStore();

  return (
    // `flex-col` + `overflow-hidden` (not `overflow-y-auto`) is the change
    // this slice makes here: the Report Table now owns its own bounded
    // scroll container so its rows can be virtualised (issue 04) — a pane
    // that scrolls itself as well would give the table unbounded height and
    // defeat the point of windowing the rows into the DOM. The chart stays
    // a fixed-height sibling above it; only the table area is `flex-1
    // min-h-0`, the flexbox idiom for "take the rest of the space, but
    // don't grow past it."
    <section
      // Scrolls itself rather than the document. With the table holding a
      // min-height floor, a short viewport would otherwise push the whole
      // page taller than the screen — which scrolls the docked Assistant and
      // the builder rail out of view, undoing the point of the shell.
      className="flex min-w-0 flex-1 flex-col overflow-y-auto bg-canvas p-4"
      aria-busy={loading}
    >
      {reportError && (
        <p role="alert" className="mb-3 rounded-md bg-danger-soft px-4 py-3 text-body-sm text-danger">
          {reportError}
        </p>
      )}
      {!presetsReady && !reportError && (
        // Before the day-by-Actor preset lands (`/api/v1/meta`'s `presets`),
        // no report has been requested at all — a labelled loading state
        // here, not a blank gap, is what stands in for the table until then.
        <p role="status">Loading report…</p>
      )}
      {/* Every SUBSEQUENT round trip (a sort click, a date change) — the
          previous table stays on screen underneath this, so a slow
          upstream response never reads as "nothing happened" (issue 08). */}
      {table && loading && (
        <p role="status" className="mb-3 text-body-sm text-steel">
          Updating report…
        </p>
      )}
      {table && (
        <Chart
          chart={table.chart}
          metricUnit={
            (meta?.metrics.find((m) => m.key === table.chart?.metric)?.unit as
              | "count"
              | "hours"
              | "replies"
              | undefined) ?? null
          }
          metrics={metrics}
          chartMetric={chartMetric}
          onChartMetricChange={setChartMetric}
        />
      )}
      {/* The table carries a min-height floor, so the chart and the Warnings
          banner can never squeeze it down to a couple of rows on a short
          viewport — past this the pane scrolls instead of crushing the
          report. */}
      {table && (
        // `min-h-0` is load-bearing: without it a flex item's min-height is
        // `auto`, so this wrapper refuses to shrink below its content, grows
        // to the table's full 67,000px and hands the virtualiser an unbounded
        // viewport — putting every row back in the DOM. The row floor lives
        // on the scrolling grid inside ReportTable, not here.
        <div className="mt-4 flex min-h-0 min-w-0 flex-1 flex-col">
          <ReportTable
            table={table}
            groupBy={groupBy}
            layout={layout}
            sort={sort}
            onSort={toggleSort}
            onMoveColumn={(columnKey, direction) =>
              moveColumn(columnKey, direction, table.columns.map((c) => c.key))
            }
          />
        </div>
      )}
    </section>
  );
}
