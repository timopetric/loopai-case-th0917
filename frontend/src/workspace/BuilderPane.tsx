import type { Meta } from "../lib/meta";
import { formatMetricLabel } from "../lib/report";
import { useReportSpecStore } from "../store/reportSpecStore";
import { Chip } from "../ui/Chip";
import { SectionHeader } from "../ui/SectionHeader";
import { SegmentedControl } from "../ui/SegmentedControl";
import { TextInput } from "../ui/TextInput";

/**
 * The left "builder" zone (issue 02 shell; issue 03 restyle: frontend-rework)
 * — metric multi-select, date range (clamped to the Coverage Window from
 * `/api/v1/meta`), granularity, group-by, duration display and the pivot
 * layout toggle (architecture.md §7, panel 1).
 *
 * Every control here reads and writes the single Report Spec store
 * directly — the same store `AssistantPane`/`Chat` applies a whole spec to,
 * which is what makes a control edit and an Assistant spec event "the same
 * path" (issue 02's acceptance criteria). This slice (03) changes how the
 * controls READ — grouped into labelled `SectionHeader` sections built from
 * the token-layer primitives in `../ui/`, so the eye can find a control
 * without reading every label — and gives the already-existing collapse
 * mechanism a live summary, not what any control DOES.
 *
 * `meta` (the metric catalogue and the Coverage Window bounds) is fetched
 * once by `WorkspaceShell` and handed down — it is not Report Spec state,
 * it's the menu of what a spec is allowed to contain. `meta.metrics`
 * already excludes the always-empty `open` counter server-side
 * (`app/upstream.py::_DEAD_METRIC_KEYS`, `METRIC_CATALOGUE`) — this pane
 * renders the catalogue verbatim and must not re-introduce a client-side
 * copy of that exclusion.
 */

/** "2026-07-10" -> "07/10", for the collapsed rail's summary badges. Plain
 * string slicing rather than `Date` parsing: a Coverage Window date has no
 * time component, and parsing/re-formatting through `Date` risks a
 * timezone-driven off-by-one the app is otherwise careful to avoid
 * (CLAUDE.md "Out-of-range dates fail open" section's general caution about
 * date handling). */
function formatShortDate(iso: string): string {
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  return `${parts[1]}/${parts[2]}`;
}

function SummaryBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex w-full flex-col items-center rounded-md bg-cream px-1 py-1.5">
      <span className="text-micro-uppercase text-muted">{label}</span>
      <span className="text-micro font-semibold text-ink-tint">{value}</span>
    </div>
  );
}

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
    const totalMetrics = meta?.metrics.length ?? 0;
    const groupLabel = groupBy === "agent" ? "Actor" : groupBy === "mailbox" ? "Mailbox" : "None";

    return (
      <aside className="flex w-16 shrink-0 flex-col items-center gap-3 border-r border-hairline bg-cream-soft py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand the report builder"
          className="rounded-md p-1.5 text-body-sm text-steel hover:bg-cream-deep hover:text-ink"
        >
          »
        </button>
        <div className="flex w-full flex-col items-center gap-1.5 px-1.5">
          <SummaryBadge label="From" value={formatShortDate(dateFrom)} />
          <SummaryBadge label="To" value={formatShortDate(dateTo)} />
          <SummaryBadge label="Group" value={groupLabel} />
          <SummaryBadge label="Span" value={granularity === "day" ? "Day" : "Total"} />
          <SummaryBadge label="Metrics" value={`${metrics.length}/${totalMetrics}`} />
          <SummaryBadge label="View" value={layout === "pivot" ? "Pivot" : "Table"} />
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-full shrink-0 overflow-y-auto border-hairline bg-cream-soft p-4 lg:w-72 lg:border-r">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-heading-5 font-semibold text-ink">Report builder</h2>
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Collapse the report builder"
          className="rounded-md px-2 py-1 text-body-sm text-steel hover:bg-cream-deep hover:text-ink"
        >
          «
        </button>
      </div>

      <section className="mb-5">
        <SectionHeader title="Coverage" />
        <div className="grid grid-cols-2 gap-2">
          <TextInput
            label="From"
            type="date"
            value={dateFrom}
            min={meta?.coverage_window.from_date}
            max={meta?.coverage_window.to_date}
            onChange={(event) => setDateFrom(event.target.value)}
          />
          <TextInput
            label="To"
            type="date"
            value={dateTo}
            min={meta?.coverage_window.from_date}
            max={meta?.coverage_window.to_date}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
      </section>

      <section className="mb-5">
        <SectionHeader title="Grouping" />
        <SegmentedControl
          name="Grouping"
          value={groupBy}
          onChange={setGroupBy}
          options={[
            { value: "none", label: "None" },
            { value: "agent", label: "Actor" },
            { value: "mailbox", label: "Mailbox" },
          ]}
        />
      </section>

      <section className="mb-5">
        <SectionHeader title="Granularity" />
        <SegmentedControl
          name="Granularity"
          value={granularity}
          onChange={setGranularity}
          options={[
            { value: "day", label: "Per day" },
            { value: "total", label: "Whole period" },
          ]}
        />
      </section>

      <section className="mb-5">
        <SectionHeader
          title="Metrics"
          meta={`${metrics.length} of ${meta?.metrics.length ?? 0} selected`}
        />
        <div className="flex flex-wrap gap-1.5">
          {meta?.metrics.map((metric) => (
            <Chip
              key={metric.key}
              selected={metrics.includes(metric.key)}
              onClick={() => toggleMetric(metric.key)}
            >
              {formatMetricLabel(metric.key)}
              {metric.unit === "hours" ? " (h)" : ""}
            </Chip>
          ))}
        </div>
      </section>

      <section className="mb-5">
        <SectionHeader title="Duration display" />
        <SegmentedControl
          name="Duration display"
          value={durationDisplay}
          onChange={setDurationDisplay}
          options={[
            { value: "avg", label: "Per-ticket avg" },
            { value: "total", label: "Period total" },
          ]}
        />
      </section>

      <section>
        <SectionHeader title="Layout" />
        <SegmentedControl
          name="Layout"
          value={layout}
          onChange={setLayout}
          options={[
            { value: "long", label: "Table" },
            { value: "pivot", label: "Pivot" },
          ]}
        />
        {layout === "pivot" && (
          // Pivot renders exactly one metric (architecture.md §2) — this is
          // the *only* way to pick which one; the report table's own
          // warning banner (from `table.warnings`) states why the other
          // selected metrics aren't shown.
          <div className="mt-2">
            <span className="mb-1 block text-body-sm-medium font-medium text-ink-tint">
              Chart metric
            </span>
            <div className="flex flex-wrap gap-1.5">
              {metrics.map((key) => (
                <Chip
                  key={key}
                  selected={(chartMetric ?? metrics[0]) === key}
                  onClick={() => setChartMetric(key)}
                >
                  {formatMetricLabel(key)}
                </Chip>
              ))}
            </div>
          </div>
        )}
      </section>
    </aside>
  );
}
