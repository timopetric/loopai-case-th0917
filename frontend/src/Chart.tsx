import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMetricLabel } from "./lib/report";
import type { ChartData } from "./lib/report";

/**
 * The fixed, ordered categorical palette (dataviz skill's validated default,
 * architecture.md §7) — exactly 8 hues, light-mode steps. This is a
 * rendering constant, not logic: `app/engine.py::_color_slot` decides WHICH
 * slot an entity gets (a stable hash of its id, tested against the
 * committed fixture in `tests/test_chart.py`) and hands over only the index
 * — the hex values themselves have no meaning anywhere outside the browser,
 * so they live here and only here rather than being duplicated into Python
 * for nothing to check.
 */
const CHART_PALETTE: readonly string[] = [
  "#2a78d6", // 0 blue
  "#eb6834", // 1 orange
  "#1baf7a", // 2 aqua
  "#eda100", // 3 yellow
  "#e87ba4", // 4 magenta
  "#008300", // 5 green
  "#4a3aa7", // 6 violet
  "#e34948", // 7 red
];

/**
 * The line chart above the table (issue 14). Hidden entirely when
 * `chart` is `null` — the report has been collapsed to a single Bucket
 * (`granularity: "total"`), so there is no time axis to plot against
 * (user story 60); the caller (`App.tsx`) doesn't need to know this rule,
 * it just always renders `<Chart chart={table.chart} .../>`.
 *
 * `chart` is `ReportTable.chart` verbatim — the same Report Table the
 * table below renders, never a second fetch (issue 14 acceptance
 * criteria). Top-eight selection and colour-slot assignment already
 * happened server-side (`app/engine.py::_build_chart`/`_color_slot`,
 * tested against the committed fixture in `tests/test_chart.py`); this
 * component only lays the given series out and answers "what unit".
 */
export function Chart({
  chart,
  metricUnit,
  metrics,
  chartMetric,
  onChartMetricChange,
}: {
  chart: ChartData | null;
  metricUnit: "count" | "hours" | "replies" | null;
  /** The currently-selected metrics, for the "chart metric" picker (user
   * story 55: the chart metric is chosen independently of column order). */
  metrics: string[];
  chartMetric: string | null;
  onChartMetricChange: (metric: string) => void;
}) {
  if (!chart) return null;

  const isHours = metricUnit === "hours";
  const yAxisLabel = `${formatMetricLabel(chart.metric)}${isHours ? " (h)" : ""}`;

  // Every series in `chart.series` was built from the same `indices` over
  // the same Buckets (`app/engine.py::_build_chart`), so their `points`
  // share one Bucket axis — reshape into recharts' one-row-per-Bucket shape
  // here, in the view layer, without touching any value.
  const buckets = chart.series[0]?.points.map((point) => point.bucket) ?? [];
  const data = buckets.map((bucket, index) => {
    const row: Record<string, string | number | null> = { bucket };
    for (const series of chart.series) {
      row[series.key] = series.points[index]?.value ?? null;
    }
    return row;
  });

  return (
    <section style={{ marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>Chart</h2>
        <label>
          Metric:{" "}
          <select
            value={chartMetric ?? metrics[0] ?? ""}
            onChange={(event) => onChartMetricChange(event.target.value)}
          >
            {metrics.map((key) => (
              <option key={key} value={key}>
                {formatMetricLabel(key)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {chart.series.length === 0 ? (
        <p>No series to plot.</p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="#e1e0d9" strokeDasharray="0" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 12, fill: "#52514e" }} stroke="#c3c2b7" />
            <YAxis
              tick={{ fontSize: 12, fill: "#52514e" }}
              stroke="#c3c2b7"
              label={{ value: yAxisLabel, angle: -90, position: "insideLeft", fill: "#52514e" }}
            />
            <Tooltip
              formatter={(value, name) => {
                const series = chart.series.find((s) => s.key === name);
                const label = series?.label ?? String(name);
                if (value === null || value === undefined) return ["—", label];
                return [isHours ? `${value} h` : String(value), label];
              }}
            />
            {/* Legend is always present (never colour-alone identity, user
                story 59); the dropped count is disclosed here rather than
                folded into a fabricated "Other" series (issue 14). */}
            <Legend
              formatter={(_value, entry) => {
                const series = chart.series.find((s) => s.key === entry.dataKey);
                return series?.label ?? String(entry.dataKey);
              }}
            />
            {chart.series.map((series) => (
              <Line
                key={series.key}
                type="monotone"
                dataKey={series.key}
                name={series.key}
                stroke={CHART_PALETTE[series.color_slot]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                // `connectNulls` defaults to `false`, kept explicit: a
                // withheld zero-count Duration average (`ChartPoint.value
                // === null`) must render as a gap in the line, never
                // interpolated across or dropped to 0 (issue 14).
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
      {chart.dropped > 0 && (
        <p style={{ color: "#52514e", fontSize: "0.875rem" }}>
          +{chart.dropped} more not shown (capped at the 8 largest by total).
        </p>
      )}
    </section>
  );
}
