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
  meta,
}: {
  table: ReportTableData | null;
  reportError: string | null;
  presetsReady: boolean;
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
    <section className="min-w-0 flex-1 overflow-y-auto bg-canvas p-4">
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
      {table && (
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
      )}
    </section>
  );
}
