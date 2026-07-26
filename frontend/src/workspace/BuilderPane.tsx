import type { Meta } from "../lib/meta";
import { formatMetricLabel } from "../lib/report";
import { useReportSpecStore } from "../store/reportSpecStore";

/**
 * The left "builder" zone (issue 02: frontend-rework) — metric multi-select,
 * date range (clamped to the Coverage Window from `/api/v1/meta`),
 * granularity, group-by, duration display and the pivot layout toggle
 * (architecture.md §7, panel 1).
 *
 * This is the shell/store slice: the controls themselves are carried over
 * unchanged from the old `App.tsx` (restyling is slices 03-06) but now read
 * and write the single Report Spec store directly instead of fourteen
 * prop-drilled `useState`s — the same store `AssistantPane`/`Chat` applies a
 * whole spec to, which is what makes a control edit and an Assistant spec
 * event "the same path" (this issue's acceptance criteria).
 *
 * `meta` (the metric catalogue and the Coverage Window bounds) is fetched
 * once by `WorkspaceShell` and handed down — it is not Report Spec state,
 * it's the menu of what a spec is allowed to contain.
 */
export function BuilderPane({
  meta,
  collapsed,
  onToggleCollapse,
}: {
  meta: Meta | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const {
    metrics,
    toggleMetric,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    granularity,
    setGranularity,
    groupBy,
    setGroupBy,
    durationDisplay,
    setDurationDisplay,
    layout,
    setLayout,
    chartMetric,
    setChartMetric,
  } = useReportSpecStore();

  if (collapsed) {
    return (
      <aside className="flex w-11 shrink-0 flex-col items-center border-r border-hairline bg-surface py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand the report builder"
          className="rounded-md p-2 text-body-sm text-steel hover:bg-cream-soft hover:text-ink"
        >
          »
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-full shrink-0 overflow-y-auto border-hairline bg-surface p-4 lg:w-72 lg:border-r">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-heading-5 font-semibold text-ink">Report builder</h2>
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Collapse the report builder"
          className="rounded-md px-2 py-1 text-body-sm text-steel hover:bg-cream-soft hover:text-ink"
        >
          «
        </button>
      </div>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Date range</legend>
        <label style={{ display: "block", marginBottom: "0.35rem" }}>
          From{" "}
          <input
            type="date"
            value={dateFrom}
            min={meta?.coverage_window.from_date}
            max={meta?.coverage_window.to_date}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label style={{ display: "block" }}>
          To{" "}
          <input
            type="date"
            value={dateTo}
            min={meta?.coverage_window.from_date}
            max={meta?.coverage_window.to_date}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </label>
      </fieldset>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Grouping</legend>
        <label>
          <select
            value={groupBy}
            onChange={(event) =>
              setGroupBy(event.target.value as "none" | "agent" | "mailbox")
            }
          >
            <option value="none">No grouping</option>
            <option value="agent">By Actor</option>
            <option value="mailbox">By Mailbox</option>
          </select>
        </label>
      </fieldset>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Granularity</legend>
        <label style={{ display: "block", marginBottom: "0.25rem" }}>
          <input
            type="radio"
            name="granularity"
            value="day"
            checked={granularity === "day"}
            onChange={() => setGranularity("day")}
          />{" "}
          Per day
        </label>
        <label style={{ display: "block" }}>
          <input
            type="radio"
            name="granularity"
            value="total"
            checked={granularity === "total"}
            onChange={() => setGranularity("total")}
          />{" "}
          Whole period (one Bucket)
        </label>
      </fieldset>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Metrics</legend>
        {meta?.metrics.map((metric) => (
          <label key={metric.key} style={{ display: "block", marginBottom: "0.15rem" }}>
            <input
              type="checkbox"
              checked={metrics.includes(metric.key)}
              onChange={() => toggleMetric(metric.key)}
            />{" "}
            {formatMetricLabel(metric.key)}
            {metric.unit === "hours" ? " (h)" : ""}
          </label>
        ))}
      </fieldset>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Duration display</legend>
        <label style={{ display: "block", marginBottom: "0.25rem" }}>
          <input
            type="radio"
            name="duration_display"
            value="avg"
            checked={durationDisplay === "avg"}
            onChange={() => setDurationDisplay("avg")}
          />{" "}
          Per-ticket average (how fast)
        </label>
        <label style={{ display: "block" }}>
          <input
            type="radio"
            name="duration_display"
            value="total"
            checked={durationDisplay === "total"}
            onChange={() => setDurationDisplay("total")}
          />{" "}
          Period total (how much work)
        </label>
      </fieldset>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Layout</legend>
        <label style={{ display: "block", marginBottom: "0.25rem" }}>
          <input
            type="radio"
            name="layout"
            value="long"
            checked={layout === "long"}
            onChange={() => setLayout("long")}
          />{" "}
          Table (rows = Bucket × group)
        </label>
        <label style={{ display: "block" }}>
          <input
            type="radio"
            name="layout"
            value="pivot"
            checked={layout === "pivot"}
            onChange={() => setLayout("pivot")}
          />{" "}
          Pivot (Buckets as columns)
        </label>
        {layout === "pivot" && (
          // Pivot renders exactly one metric (architecture.md §2) — this is
          // the *only* way to pick which one; the report table's own
          // warning banner (from `table.warnings`) states why the other
          // selected metrics aren't shown.
          <label style={{ display: "block", marginTop: "0.35rem" }}>
            Chart metric:{" "}
            <select
              value={chartMetric ?? metrics[0] ?? ""}
              onChange={(event) => setChartMetric(event.target.value)}
            >
              {metrics.map((key) => (
                <option key={key} value={key}>
                  {formatMetricLabel(key)}
                </option>
              ))}
            </select>
          </label>
        )}
      </fieldset>
    </aside>
  );
}
