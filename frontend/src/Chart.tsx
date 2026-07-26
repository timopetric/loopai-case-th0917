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
import type {
  DefaultLegendContentProps,
  LabelProps as RechartsLabelProps,
  TooltipContentProps,
} from "recharts";

import { formatMetricLabel } from "./lib/report";
import type { ChartData, ChartSeries } from "./lib/report";
import { useThemeStore } from "./store/themeStore";

/**
 * The fixed, ordered categorical palette (dataviz skill's validated default,
 * architecture.md §7) — exactly 8 hues, light-mode steps. This is a
 * rendering constant, not logic: `app/engine.py::_color_slot` decides WHICH
 * slot an entity gets (a stable hash of its id, tested against the
 * committed fixture in `tests/test_chart.py`) and hands over only the index
 * — the hex values themselves have no meaning anywhere outside the browser,
 * so they live here and only here rather than being duplicated into Python
 * for nothing to check.
 *
 * NOT part of the rebrand (issue 05): brand colour must never enter this
 * array, and it is a fixed-length literal, never grown or computed at
 * runtime — `series.color_slot` is always looked up directly, never via
 * modulo, so a bug that produced an out-of-range slot would fail loudly
 * instead of silently wrapping onto an existing hue.
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
 * The dark-surface counterpart of `CHART_PALETTE` (issue 07: frontend-rework,
 * architecture.md §7 — "a selected set of steps validated against the dark
 * surface, not an automatic inversion"). Same eight hue families, same
 * order, same length — SLOT 3 IS SLOT 3 IN BOTH ARRAYS, which is what keeps
 * an entity's colour identical across a theme change: `seriesColor` below
 * always indexes both arrays with the exact same `series.color_slot`, never
 * a derived or recomputed index.
 *
 * Every value here is a chosen dark-band step from the dataviz skill's own
 * documented reference palette, re-validated with `scripts/validate_palette.js`
 * against this app's actual dark canvas token (`--surface-canvas` under the
 * dark ramp, see `tokens.css`) rather than the skill's own reference dark
 * surface. All six checks pass at that surface — lightness band, chroma
 * floor, CVD separation (adjacent pairs), the normal-vision floor, and
 * contrast — with a strictly better contrast margin than the skill's own
 * reference dark surface, since this app's dark canvas is darker still. The
 * exact measured numbers are recorded in the issue report and in
 * `tests/test_frontend_dark_mode.py`, not repeated here as literal hex
 * values (this docstring is scanned by a test that forbids raw hex outside
 * the two palette array bodies). The green slot is deliberately left
 * unchanged from the light array: it already clears every check on both
 * surfaces, so "selected, not inverted" here means "selected to be the same
 * value," not a hue shift for its own sake.
 */
const CHART_PALETTE_DARK: readonly string[] = [
  "#3987e5", // 0 blue
  "#d95926", // 1 orange
  "#199e70", // 2 aqua
  "#c98500", // 3 yellow
  "#d55181", // 4 magenta
  "#008300", // 5 green
  "#9085e9", // 6 violet
  "#e66767", // 7 red
];

/** With four or fewer series, identity must not depend on colour alone
 * (architecture.md §7 gap this slice closes) — each line also gets a
 * direct label at its last plotted point, not just a legend entry. */
const DIRECT_LABEL_THRESHOLD = 4;

/** Looks up the same `color_slot` in whichever array matches the resolved
 * theme (`store/themeStore.ts`) — the slot itself never changes, only the
 * value stored at it, which is the whole point: an Actor (or Mailbox) keeps
 * its colour identity across a theme change exactly as it does across a
 * date-range change, because both arrays are indexed by the same
 * backend-assigned integer. */
function seriesColor(series: ChartSeries, isDark: boolean): string {
  return isDark ? CHART_PALETTE_DARK[series.color_slot] : CHART_PALETTE[series.color_slot];
}

/** The index of the last non-null point in a series — a withheld value
 * renders as a gap (`connectNulls={false}`), so the direct label must sit
 * at the last real value, not at a trailing gap. */
function lastPlottedIndex(series: ChartSeries): number {
  for (let i = series.points.length - 1; i >= 0; i--) {
    if (series.points[i].value !== null) return i;
  }
  return -1;
}

/**
 * A custom tooltip content renderer (recharts `Tooltip`'s `content` prop).
 * Recharts' default tooltip colours each row's text with the series'
 * stroke colour, which is exactly the "identity depends on colour" failure
 * §7 rules out for values and labels — text here stays in text tokens
 * (`text-ink`/`text-steel`); only the small line-key swatch before each
 * label carries the series hue, per the dataviz skill's "line keys, not
 * boxes" guidance.
 */
function ChartTooltip({
  active,
  payload,
  label,
  chart,
  isHours,
  isDark,
}: TooltipContentProps & { chart: ChartData; isHours: boolean; isDark: boolean }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-hairline bg-canvas px-3 py-2 shadow-sm">
      <p className="mb-1 text-micro font-semibold text-steel">{label}</p>
      <ul className="flex flex-col gap-1">
        {payload.map((entry) => {
          const series = chart.series.find((s) => s.key === entry.dataKey);
          const entryLabel = series?.label ?? String(entry.dataKey);
          const value = entry.value;
          return (
            <li key={String(entry.dataKey)} className="flex items-center gap-2">
              <span
                aria-hidden
                className="h-0.5 w-3 shrink-0 rounded-full"
                style={{
                  backgroundColor: series ? seriesColor(series, isDark) : "var(--color-muted)",
                }}
              />
              <span className="text-body-sm text-ink-tint">{entryLabel}</span>
              <span className="ml-auto font-mono text-body-sm-medium tabular-nums text-ink">
                {value === null || value === undefined
                  ? "—"
                  : isHours
                    ? `${value} h`
                    : String(value)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * A custom legend content renderer (recharts `Legend`'s `content` prop).
 * Same reasoning as `ChartTooltip`: recharts' default legend colours item
 * *text* by series colour, which this replaces with a text token plus a
 * colour swatch — the legend is always present for ≥2 series (§7) and is
 * the dependable identity channel direct labels merely supplement.
 */
function ChartLegend({
  payload,
  chart,
  isDark,
}: DefaultLegendContentProps & { chart: ChartData; isDark: boolean }) {
  if (!payload || payload.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
      {payload.map((entry) => {
        const series = chart.series.find((s) => s.key === entry.dataKey);
        const entryLabel = series?.label ?? String(entry.dataKey);
        return (
          <li
            key={String(entry.dataKey)}
            className="flex items-center gap-1.5 text-body-sm-medium text-ink-tint"
          >
            <span
              aria-hidden
              className="h-0.5 w-3 shrink-0 rounded-full"
              style={{
                backgroundColor: series ? seriesColor(series, isDark) : "var(--color-muted)",
              }}
            />
            {entryLabel}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The line chart above the table (issue 14, restyled in issue 05). Hidden
 * entirely when `chart` is `null` — the report has been collapsed to a
 * single Bucket (`granularity: "total"`), so there is no time axis to plot
 * against (user story 60); the caller (`ReportPane.tsx`) doesn't need to
 * know this rule, it just always renders `<Chart chart={table.chart} .../>`.
 *
 * `chart` is `ReportTable.chart` verbatim — the same Report Table the
 * table below renders, never a second fetch (issue 14 acceptance
 * criteria). Top-eight selection and colour-slot assignment already
 * happened server-side (`app/engine.py::_build_chart`/`_color_slot`,
 * tested against the committed fixture in `tests/test_chart.py`); this
 * component only lays the given series out, styles the frame with the
 * token layer, and answers "what unit".
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
  // The single source of truth for "which theme is actually in effect"
  // (`store/themeStore.ts`) — read here rather than a direct OS media-query
  // check, so this component reacts the instant the Header's explicit
  // toggle changes, not just when the OS setting does.
  const isDark = useThemeStore((state) => state.resolved === "dark");

  if (!chart) return null;

  const isHours = metricUnit === "hours";
  const yAxisLabel = `${formatMetricLabel(chart.metric)}${isHours ? " (h)" : ""}`;
  const showDirectLabels = chart.series.length <= DIRECT_LABEL_THRESHOLD;

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
    <section className="mb-4 rounded-lg border border-hairline bg-canvas p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="text-heading-5 font-semibold text-ink">Chart</h2>
        <label className="flex items-center gap-2 text-body-sm text-steel">
          Metric:
          <select
            value={chartMetric ?? metrics[0] ?? ""}
            onChange={(event) => onChartMetricChange(event.target.value)}
            className="rounded-md border border-hairline-strong bg-canvas px-2 py-1 text-body-sm text-ink-tint"
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
        <p className="text-body-sm text-steel">No series to plot.</p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          {/* Right margin makes room for the direct labels riding the line
              ends (≤4 series) without clipping them at the plot edge. */}
          <LineChart data={data} margin={{ top: 8, right: showDirectLabels ? 72 : 24, left: 8, bottom: 8 }}>
            {/* Recessive grid (architecture.md §7): a hairline, one step
                off the canvas, never the strong border. */}
            <CartesianGrid stroke="var(--color-hairline)" strokeDasharray="0" vertical={false} />
            <XAxis
              dataKey="bucket"
              tick={{ fill: "var(--color-steel)", fontSize: 12 }}
              stroke="var(--color-hairline-strong)"
              tickLine={false}
              axisLine={{ stroke: "var(--color-hairline-strong)" }}
            />
            <YAxis
              tick={{ fill: "var(--color-steel)", fontSize: 12 }}
              stroke="var(--color-hairline-strong)"
              tickLine={false}
              axisLine={{ stroke: "var(--color-hairline-strong)" }}
              label={{
                value: yAxisLabel,
                angle: -90,
                position: "insideLeft",
                fill: "var(--color-steel)",
              }}
            />
            {/* Crosshair + tooltip on hover by default (architecture.md
                §7); custom content keeps values/labels in text tokens
                rather than recharts' default per-series text colour. */}
            <Tooltip
              content={(props) => (
                <ChartTooltip {...props} chart={chart} isHours={isHours} isDark={isDark} />
              )}
              cursor={{ stroke: "var(--color-hairline-strong)", strokeWidth: 1 }}
            />
            {/* Legend is always present (never colour-alone identity, user
                story 59); the dropped count is disclosed here rather than
                folded into a fabricated "Other" series (issue 14). */}
            <Legend content={(props) => <ChartLegend {...props} chart={chart} isDark={isDark} />} />
            {chart.series.map((series) => {
              const lastIndex = lastPlottedIndex(series);
              return (
                <Line
                  key={series.key}
                  type="monotone"
                  dataKey={series.key}
                  name={series.key}
                  stroke={seriesColor(series, isDark)}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  // `connectNulls` defaults to `false`, kept explicit: a
                  // withheld zero-count Duration average (`ChartPoint.value
                  // === null`) must render as a gap in the line, never
                  // interpolated across or dropped to 0 (issue 14).
                  connectNulls={false}
                  isAnimationActive={false}
                  // Close the §7 gap: with 4 or fewer series, label each
                  // directly (at its last plotted point) as well as in the
                  // legend, so identity never depends on colour alone.
                  // Label text wears a text token, never the series colour.
                  label={
                    showDirectLabels
                      ? (props: RechartsLabelProps) => {
                          const x = Number(props.x);
                          const y = Number(props.y);
                          if (props.index !== lastIndex || Number.isNaN(x) || Number.isNaN(y)) {
                            return <g />;
                          }
                          return (
                            <text
                              x={x + 8}
                              y={y}
                              dy={4}
                              textAnchor="start"
                              className="fill-ink-tint text-[11px] font-medium"
                            >
                              {series.label}
                            </text>
                          );
                        }
                      : undefined
                  }
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
      {chart.dropped > 0 && (
        <p className="mt-2 text-body-sm text-steel">
          +{chart.dropped} more not shown (capped at the 8 largest by total).
        </p>
      )}
    </section>
  );
}
