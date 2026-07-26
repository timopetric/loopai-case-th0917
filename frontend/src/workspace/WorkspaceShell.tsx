import { useEffect, useRef, useState } from "react";

import type { AssumptionNote } from "../lib/assumptions";
import { fetchAssumptions } from "../lib/assumptions";
import type { ExportFormat } from "../lib/export";
import { exportReport, triggerDownload } from "../lib/export";
import type { Meta } from "../lib/meta";
import { fetchMeta } from "../lib/meta";
import type { Preset, ReportTable as ReportTableData } from "../lib/report";
import { ReportRefusedError, fetchReport } from "../lib/report";
import { encodeSpecToSearchParams, fetchSpecFromQuery } from "../lib/specUrl";
import { useReportSpecStore } from "../store/reportSpecStore";
import { AssistantPane } from "./AssistantPane";
import { BuilderPane } from "./BuilderPane";
import { Header } from "./Header";
import { ReportPane } from "./ReportPane";

/**
 * The three-zone workspace (issue 02: frontend-rework, architecture.md §7) —
 * builder left, report centre, Assistant permanently docked right. Replaces
 * the 689-line `App.tsx` monolith: the panes and the header are separate
 * components (below/`Header.tsx`/`BuilderPane.tsx`/`ReportPane.tsx`/
 * `AssistantPane.tsx`), all reading and writing the single Report Spec
 * store (`store/reportSpecStore.ts`) rather than fourteen prop-drilled
 * `useState`s.
 *
 * What lives HERE, not in a pane: fetch-derived state that is not Report
 * Spec state — `meta`, `assumptions`, the fetched `table`, `reportError`,
 * `exportError`, `presetsReady`, `urlWarning` — and the two side panes'
 * collapse flags, which are shell-level layout state (issue acceptance
 * criteria: "no pane holding another pane's state" — this shell state is
 * nobody's pane-owned state, it's what the shell coordinates between them).
 */
export function WorkspaceShell() {
  const buildSpec = useReportSpecStore((state) => state.buildSpec);
  const applySpec = useReportSpecStore((state) => state.applySpec);
  // Re-render this effect-driving component whenever any spec field
  // changes, mirroring the old `App.tsx` dependency arrays — reading the
  // individual fields (rather than the whole store object) keeps the
  // fetch/URL-sync effects below re-running on exactly the same triggers
  // they always did.
  const metrics = useReportSpecStore((state) => state.metrics);
  const dateFrom = useReportSpecStore((state) => state.dateFrom);
  const dateTo = useReportSpecStore((state) => state.dateTo);
  const granularity = useReportSpecStore((state) => state.granularity);
  const groupBy = useReportSpecStore((state) => state.groupBy);
  const durationDisplay = useReportSpecStore((state) => state.durationDisplay);
  const sort = useReportSpecStore((state) => state.sort);
  const columnsOrder = useReportSpecStore((state) => state.columnsOrder);
  const layout = useReportSpecStore((state) => state.layout);
  const chartMetric = useReportSpecStore((state) => state.chartMetric);

  const [meta, setMeta] = useState<Meta | null>(null);
  const [table, setTable] = useState<ReportTableData | null>(null);
  /** True for the duration of any report round trip — not just the very
   * first one (`presetsReady` already covers that). Issue 08: frontend-
   * rework accessibility polish names this explicitly: "sorting a large
   * report currently looks like nothing happened," because the table
   * simply sits there, stale, until the new `ReportTable` swaps in. A
   * click that visibly does nothing for a second or more reads as broken,
   * not busy, especially over a screen reader with no spinner to glance
   * at. `ReportPane` renders this as an `aria-busy` region plus a small
   * "Updating…" status, layered ON TOP of the still-good previous table
   * (never a blank/loading swap) — the same "don't disturb a good result"
   * principle the export-failure handling below already follows. */
  const [reportLoading, setReportLoading] = useState(false);
  const [assumptions, setAssumptions] = useState<AssumptionNote[] | null>(null);
  const [showAssumptions, setShowAssumptions] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [presetsReady, setPresetsReady] = useState(false);
  const [urlWarning, setUrlWarning] = useState<string | null>(null);
  const [builderCollapsed, setBuilderCollapsed] = useState(false);
  const [assistantCollapsed, setAssistantCollapsed] = useState(false);

  /** Set for exactly one report-fetch cycle: the one immediately after a
   * spec was restored from the URL (issue 13) — see `App.tsx`'s previous
   * docstring for the full reasoning; unchanged by this slice. */
  const restoringFromUrl = useRef(false);

  function applyPreset(preset: Preset) {
    applySpec(preset.spec);
  }

  async function handleExport(format: ExportFormat) {
    setExportError(null);
    try {
      const { blob, filename } = await exportReport(buildSpec(), format);
      triggerDownload(blob, filename);
    } catch (err) {
      if (err instanceof ReportRefusedError) {
        setExportError(
          err.coverage
            ? `That date range has no data. The Coverage Window is ` +
              `${err.coverage.from_date} – ${err.coverage.to_date}.`
            : err.message,
        );
        return;
      }
      setExportError(`Could not download the ${format.toUpperCase()} export.`);
    }
  }

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch(() => setMeta(null));
    fetchAssumptions()
      .then(setAssumptions)
      .catch(() => setAssumptions(null));

    // Restore the Report Spec from the URL (issue 13), same behaviour as
    // the old `App.tsx` — decoding happens server-side via
    // `GET /api/v1/spec` (`app/spec_url.py::decode_spec`), the only place
    // that validation logic exists.
    fetchSpecFromQuery(window.location.search)
      .then(({ spec, warnings }) => {
        applySpec(spec);
        if (warnings.length > 0) {
          setUrlWarning(warnings[0]);
        } else {
          setUrlWarning(null);
          restoringFromUrl.current = window.location.search.length > 0;
        }
        setPresetsReady(true);
      })
      .catch(() => {
        // Could not even ask the server (offline, etc.) — fail safe: no
        // report is requested at all.
      });
    // Runs once: `WorkspaceShell` only mounts once the user is signed in
    // (`App.tsx`), so there is no `signedIn` transition to react to here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!presetsReady) return;
    if (dateFrom > dateTo) {
      setReportError("The start date must be on or before the end date.");
      return;
    }
    const wasRestoringFromUrl = restoringFromUrl.current;
    restoringFromUrl.current = false;

    setReportLoading(true);
    fetchReport(buildSpec())
      .then((result) => {
        setTable(result);
        setReportError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ReportRefusedError) {
          if (wasRestoringFromUrl && meta && meta.presets.length > 0) {
            applyPreset(meta.presets[0]);
            setUrlWarning(
              "That link's dates fall outside the current Coverage Window — showing the default report instead.",
            );
            return;
          }
          setTable(null);
          setReportError(
            err.coverage
              ? `That date range has no data. The Coverage Window is ` +
                `${err.coverage.from_date} – ${err.coverage.to_date}.`
              : err.message,
          );
          return;
        }
        setReportError("Could not load the report.");
      })
      .finally(() => setReportLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    presetsReady,
    metrics,
    dateFrom,
    dateTo,
    granularity,
    groupBy,
    durationDisplay,
    sort,
    columnsOrder,
    layout,
    chartMetric,
  ]);

  useEffect(() => {
    if (!presetsReady) return;
    const params = encodeSpecToSearchParams(buildSpec());
    const next = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState(null, "", next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    presetsReady,
    metrics,
    dateFrom,
    dateTo,
    granularity,
    groupBy,
    durationDisplay,
    sort,
    columnsOrder,
    layout,
    chartMetric,
  ]);

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <Header
        meta={meta}
        assumptions={assumptions}
        showAssumptions={showAssumptions}
        onShowAssumptions={() => setShowAssumptions(true)}
        onCloseAssumptions={() => setShowAssumptions(false)}
        presets={meta?.presets ?? []}
        onApplyPreset={applyPreset}
        onExportCsv={() => handleExport("csv")}
        onExportXlsx={() => handleExport("xlsx")}
        exportDisabled={!table}
        urlWarning={urlWarning}
        exportError={exportError}
      />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row lg:overflow-hidden">
        <BuilderPane
          meta={meta}
          collapsed={builderCollapsed}
          onToggleCollapse={() => setBuilderCollapsed((prev) => !prev)}
        />
        <ReportPane
          table={table}
          reportError={reportError}
          presetsReady={presetsReady}
          loading={reportLoading}
          meta={meta}
        />
        <AssistantPane
          meta={meta}
          collapsed={assistantCollapsed}
          onToggleCollapse={() => setAssistantCollapsed((prev) => !prev)}
        />
      </div>
    </div>
  );
}
