import { create } from "zustand";

import type { ReportSpec, SortSpec } from "../lib/report";

/**
 * The single Report Spec store (issue 02: frontend-rework, architecture.md
 * §7 — "one `ReportSpec` store (Zustand — tiny, Claude-familiar)").
 *
 * Before this slice, every builder control was a separate `useState` in the
 * 689-line `App.tsx`, prop-drilled into the builder markup and read again by
 * `buildReportSpec()` for the fetch/export/URL-sync effects and by `Chat`
 * for the Assistant's starting point. That made the three-pane layout this
 * issue introduces impossible without duplicating state: the builder pane,
 * the report pane and the Assistant pane are now three separate React
 * subtrees, and there is exactly one place a `ReportSpec` field lives.
 *
 * `BuilderPane` calls the individual setters (`toggleMetric`, `setDateFrom`,
 * ...) for a human control edit; `Chat`/`AssistantPane` calls `applySpec`
 * wholesale on every `spec` event from the Assistant stream
 * (`agentStream.ts`'s `onSpec`, ADR-0002). Both go through this one store,
 * which is the acceptance criterion this file exists to satisfy: "a control
 * edit and an Assistant spec event update it through the same path."
 *
 * `ReportPane` and the URL/fetch effects in `WorkspaceShell` read the same
 * store rather than being handed a spec as a prop — so nothing downstream
 * can observe a builder edit and an Assistant edit as different kinds of
 * update.
 */

/**
 * Placeholder values for the builder controls before `/api/v1/meta` (and the
 * presets it carries) has answered. These are ONLY UI bootstrap values so
 * the date `<input>`s have something non-empty to show — they are never
 * sent as a report request: `WorkspaceShell`'s report-fetching effect is
 * gated on `presetsReady`, which only becomes `true` once the real
 * day-by-Actor preset (built server-side against the real Coverage Window)
 * has been applied via `applySpec`.
 */
const PLACEHOLDER_DATE_FROM = "2026-07-10";
const PLACEHOLDER_DATE_TO = "2026-07-23";

export interface ReportSpecState {
  metrics: string[];
  dateFrom: string;
  dateTo: string;
  granularity: ReportSpec["granularity"];
  groupBy: ReportSpec["group_by"];
  durationDisplay: "avg" | "total";
  sort: SortSpec | null;
  columnsOrder: string[] | null;
  layout: NonNullable<ReportSpec["layout"]>;
  chartMetric: string | null;
  /** Kept even while the builder-rail control is disabled (`groupBy ===
   * "none"`) — toggling grouping away and back must restore exactly what
   * was typed, not clear it. This is deliberate: it is what makes the
   * `group_by == "none"` + filter-set Repair a reachable path rather than
   * dead code the UI prevents (table-filter-and-assistant-intro issue 05). */
  entityFilter: string | null;
}

export interface ReportSpecActions {
  toggleMetric: (key: string) => void;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  setGranularity: (value: ReportSpec["granularity"]) => void;
  setGroupBy: (value: ReportSpec["group_by"]) => void;
  setDurationDisplay: (value: "avg" | "total") => void;
  toggleSort: (columnKey: string) => void;
  /** `currentOrder` is the table's own current column order (post
   * `columns_order`, post-engine) — the only source of truth for "what's on
   * screen right now", supplied by `ReportPane` from `table.columns` rather
   * than read from possibly-stale store state. */
  moveColumn: (columnKey: string, direction: "left" | "right", currentOrder: string[]) => void;
  setLayout: (value: NonNullable<ReportSpec["layout"]>) => void;
  setChartMetric: (value: string | null) => void;
  setEntityFilter: (value: string | null) => void;
  /** Apply a full `ReportSpec` wholesale (presets, a shared-link restore, or
   * an Assistant `spec` event) — every control is still individually
   * editable immediately afterwards; this is a starting point, not a mode. */
  applySpec: (spec: ReportSpec) => void;
  /** The exact `ReportSpec` the on-screen report was built from — used by
   * the report fetch, both exporters, the URL sync and the Assistant's
   * starting point, so none of them can diverge from what's on screen. */
  buildSpec: () => ReportSpec;
}

export type ReportSpecStore = ReportSpecState & ReportSpecActions;

/** A metric that stops being selected can leave `sort`/`chartMetric`
 * pointing at a column that no longer exists (the backend validator 422s
 * that spec — architecture.md §2: both must be ∈ metrics) — clear them here
 * rather than let the request fail, a minimal client-side echo of the
 * "Repair" idea for the one control (the metric checkboxes) that can
 * invalidate another field by itself. */
function withMetricsCleanup(
  metrics: string[],
  state: Pick<ReportSpecState, "sort" | "columnsOrder" | "chartMetric">,
): Pick<ReportSpecState, "metrics" | "sort" | "columnsOrder" | "chartMetric"> {
  return {
    metrics,
    sort: state.sort && !metrics.includes(state.sort.column) ? null : state.sort,
    chartMetric: state.chartMetric && !metrics.includes(state.chartMetric) ? null : state.chartMetric,
    columnsOrder: state.columnsOrder
      ? state.columnsOrder.filter((key) => metrics.includes(key))
      : state.columnsOrder,
  };
}

export const useReportSpecStore = create<ReportSpecStore>((set, get) => ({
  metrics: [],
  dateFrom: PLACEHOLDER_DATE_FROM,
  dateTo: PLACEHOLDER_DATE_TO,
  granularity: "day",
  groupBy: "agent",
  durationDisplay: "avg",
  sort: null,
  columnsOrder: null,
  layout: "long",
  chartMetric: null,
  entityFilter: null,

  toggleMetric: (key) =>
    set((state) => {
      if (state.metrics.includes(key)) {
        // A Report Spec always needs at least one metric — refuse to
        // uncheck the last one rather than letting the request 422.
        if (state.metrics.length <= 1) return {};
        return withMetricsCleanup(
          state.metrics.filter((m) => m !== key),
          state,
        );
      }
      return withMetricsCleanup([...state.metrics, key], state);
    }),

  setDateFrom: (value) => set({ dateFrom: value }),
  setDateTo: (value) => set({ dateTo: value }),
  setGranularity: (value) => set({ granularity: value }),
  setGroupBy: (value) => set({ groupBy: value }),
  setDurationDisplay: (value) => set({ durationDisplay: value }),

  toggleSort: (columnKey) =>
    set((state) => {
      if (state.sort && state.sort.column === columnKey) {
        return {
          sort: { column: columnKey, direction: state.sort.direction === "desc" ? "asc" : "desc" },
        };
      }
      return { sort: { column: columnKey, direction: "desc" } };
    }),

  moveColumn: (columnKey, direction, currentOrder) => {
    const from = currentOrder.indexOf(columnKey);
    if (from === -1) return;
    const to = direction === "left" ? from - 1 : from + 1;
    if (to < 0 || to >= currentOrder.length) return;
    const next = [...currentOrder];
    [next[from], next[to]] = [next[to], next[from]];
    set({ columnsOrder: next });
  },

  setLayout: (value) => set({ layout: value }),
  setChartMetric: (value) => set({ chartMetric: value }),
  // Deliberately does not read/clear `groupBy` — `entityFilter` survives the
  // control being disabled (see the field's own doc comment above).
  setEntityFilter: (value) => set({ entityFilter: value }),

  applySpec: (spec) =>
    set({
      metrics: spec.metrics,
      dateFrom: spec.date_from,
      dateTo: spec.date_to,
      granularity: spec.granularity,
      groupBy: spec.group_by,
      durationDisplay: spec.duration_display ?? "avg",
      sort: spec.sort ?? null,
      columnsOrder: spec.columns_order ?? null,
      layout: spec.layout ?? "long",
      chartMetric: spec.chart_metric ?? null,
      entityFilter: spec.entity_filter ?? null,
    }),

  buildSpec: () => {
    const state = get();
    return {
      metrics: state.metrics,
      date_from: state.dateFrom,
      date_to: state.dateTo,
      granularity: state.granularity,
      group_by: state.groupBy,
      duration_display: state.durationDisplay,
      sort: state.sort,
      columns_order: state.columnsOrder,
      layout: state.layout,
      chart_metric: state.chartMetric,
      entity_filter: state.entityFilter,
    };
  },
}));
