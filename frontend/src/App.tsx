import { useEffect, useRef, useState } from "react";

import { AssumptionsModal } from "./AssumptionsModal";
import { Chart } from "./Chart";
import { Chat } from "./Chat";
import { ReportTable } from "./ReportTable";
import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT, apiFetch } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";
import type { AssumptionNote } from "./lib/assumptions";
import { fetchAssumptions } from "./lib/assumptions";
import type { ExportFormat } from "./lib/export";
import { exportReport, triggerDownload } from "./lib/export";
import type { Meta } from "./lib/meta";
import { fetchMeta } from "./lib/meta";
import type { Preset, ReportSpec, ReportTable as ReportTableData, SortSpec } from "./lib/report";
import { ReportRefusedError, fetchReport, formatMetricLabel } from "./lib/report";
import { encodeSpecToSearchParams, fetchSpecFromQuery } from "./lib/specUrl";

/**
 * Placeholder values for the builder controls before `/api/v1/meta` (and the
 * presets it now carries — issue 12) has answered. These are ONLY UI
 * bootstrap values for the `<input>`s to have something non-empty to show —
 * they are never sent as a report request: the report-fetching effect below
 * is gated on `presetsReady`, which only becomes true once the real
 * day-by-Actor preset (`meta.presets[0]`, built server-side against the real
 * Coverage Window in `app/presets.py`) has been applied. This is what
 * guarantees first paint never requests a date range outside the real
 * window, even if the upstream window has moved since these were written.
 */
const PLACEHOLDER_DATE_FROM = "2026-07-10";
const PLACEHOLDER_DATE_TO = "2026-07-23";

/**
 * Walking-skeleton page (issue 01), now behind the sign-in gate (issue 02),
 * showing the Coverage Window from `/api/v1/meta` (issue 03), and now the
 * first real report — the day × Actor table with real numbers (issue 04).
 * A full builder UI (metric picker, date slider, grouping, presets) arrives
 * in later slices; this proves real data flows end to end through the
 * engine and the route.
 *
 * Auth failure handling: on a 401 from any `apiFetch` call, `apiClient`
 * clears the stored key and fires `UNAUTHORIZED_EVENT`; the listener below
 * drops back to the sign-in screen. Nothing here touches the URL, so
 * whatever report definition later lives in the query string (issue 13)
 * survives the round trip through sign-in (user story 53).
 */
export function App() {
  const [signedIn, setSignedIn] = useState<boolean>(() => getStoredApiKey() !== null);
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [table, setTable] = useState<ReportTableData | null>(null);
  /**
   * The coverage banner's modal (issue 09, user story 28). `assumptions` is
   * fetched once alongside `meta`; the banner is always clickable once it
   * loads, and the modal renders `assumptions` verbatim — see
   * `AssumptionsModal`'s docstring for why it holds no text of its own.
   */
  const [assumptions, setAssumptions] = useState<AssumptionNote[] | null>(null);
  const [showAssumptions, setShowAssumptions] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  /** CSV/Excel download errors (issue 10, issue 11, user stories 32/34):
   * kept separate from `reportError` so a failed download never clears or is
   * confused with the on-screen report, which may still be perfectly fine. */
  const [exportError, setExportError] = useState<string | null>(null);
  /**
   * Duration display (issue 05, user story 14): per-ticket average ("how
   * fast") vs period total ("how much work") for Duration Metrics.
   */
  const [durationDisplay, setDurationDisplay] = useState<"avg" | "total">("avg");

  /**
   * The three primary builder axes (issue 06). Metrics, grouping and
   * granularity are plain client state; the date range is bounded to the
   * Coverage Window reported by `/api/v1/meta` via the date inputs' `min`/
   * `max` (so an out-of-window range cannot be picked by mouse at all —
   * refusing one that arrives some other way, e.g. a hand-edited URL or the
   * Assistant, is issue 08's job, not this one's).
   */
  const [metrics, setMetrics] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState<string>(PLACEHOLDER_DATE_FROM);
  const [dateTo, setDateTo] = useState<string>(PLACEHOLDER_DATE_TO);
  const [granularity, setGranularity] = useState<ReportSpec["granularity"]>("day");
  const [groupBy, setGroupBy] = useState<ReportSpec["group_by"]>("agent");
  /**
   * Becomes `true` once the day-by-Actor preset served by `/api/v1/meta`
   * has been applied (see the effect below) — the report-fetching effect
   * is gated on this, not on `meta` alone, so the very first request the
   * app makes always carries the real preset's (or a restored link's) real
   * dates, never the placeholders above.
   */
  const [presetsReady, setPresetsReady] = useState(false);

  /**
   * Set for exactly one report-fetch cycle: the one immediately after a
   * spec was restored from the URL (issue 13). `GET /api/v1/spec`
   * (`app/spec_url.py::decode_spec`) already validated the spec against
   * `ReportSpec`'s own rules, but NOT against the Coverage Window, which is
   * only known once THIS app's own `/api/v1/meta` call has answered — a
   * link whose dates have drifted outside a *moved* window (issue 08)
   * surfaces here as `ReportRefusedError` on this first fetch. That is
   * exactly the "stale link" case issue 13 names: caught below and turned
   * into the same fallback-to-default-with-a-Warning behaviour as a link
   * that failed to decode at all, rather than left to read as an ordinary
   * refused-range error banner a user could fix by editing the date
   * inputs.
   */
  const restoringFromUrl = useRef(false);
  /** Warning shown when a shared link could not be honoured verbatim —
   * either it failed to decode, or its dates fell outside a moved Coverage
   * Window — and the app fell back to the default report instead (issue
   * 13 acceptance criteria). Distinct from `reportError`, which is about
   * the CURRENT controls, not a link that was just opened. */
  const [urlWarning, setUrlWarning] = useState<string | null>(null);

  /**
   * Table presentation (issue 07): sort ranks within each Bucket, never
   * globally (a `granularity: "total"` report has one Bucket, so the same
   * state/handler ranks the whole table — no special case here either).
   * `columnsOrder` starts `null` ("use `metrics` order as given") and is set
   * the first time a move button is used, seeded from the table's own
   * current column order so a move is always relative to what's on screen.
   * `layout`/`chartMetric` add the pivot toggle; pivot renders
   * `chartMetric` only (`null` = server default `metrics[0]`).
   */
  const [sort, setSort] = useState<SortSpec | null>(null);
  const [columnsOrder, setColumnsOrder] = useState<string[] | null>(null);
  const [layout, setLayout] = useState<ReportSpec["layout"]>("long");
  const [chartMetric, setChartMetric] = useState<string | null>(null);

  function toggleMetric(key: string) {
    setMetrics((prev) => {
      if (prev.includes(key)) {
        // A Report Spec always needs at least one metric — refuse to
        // uncheck the last one rather than letting the request 422.
        return prev.length > 1 ? prev.filter((m) => m !== key) : prev;
      }
      return [...prev, key];
    });
  }

  function toggleSort(columnKey: string) {
    setSort((prev) => {
      if (prev && prev.column === columnKey) {
        return { column: columnKey, direction: prev.direction === "desc" ? "asc" : "desc" };
      }
      return { column: columnKey, direction: "desc" };
    });
  }

  function moveColumn(columnKey: string, direction: "left" | "right") {
    // The table's own current order (post `columns_order`, post-engine) is
    // the only source of truth for "what's on screen right now" — seed from
    // it rather than from possibly-stale local state.
    const current = table ? table.columns.map((c) => c.key) : metrics;
    const from = current.indexOf(columnKey);
    if (from === -1) return;
    const to = direction === "left" ? from - 1 : from + 1;
    if (to < 0 || to >= current.length) return;
    const next = [...current];
    [next[from], next[to]] = [next[to], next[from]];
    setColumnsOrder(next);
  }

  /**
   * Apply a full `ReportSpec` wholesale, setting every control from it in
   * one go (issue 12, PRD user story 4) — nothing about the controls
   * themselves changes, they are the same plain `useState` setters every
   * individual control already uses, so this is a starting point, not a
   * mode: every control remains individually editable immediately
   * afterwards. Shared by preset buttons (`applyPreset` below) and
   * restoring a spec from a shared link (issue 13) — every field that
   * affects what is displayed (architecture.md §2's field list) has a
   * setter call here, so a link missing a call here would silently fail to
   * reproduce that field.
   */
  function applySpec(spec: ReportSpec) {
    setMetrics(spec.metrics);
    setDateFrom(spec.date_from);
    setDateTo(spec.date_to);
    setGranularity(spec.granularity);
    setGroupBy(spec.group_by);
    setDurationDisplay(spec.duration_display ?? "avg");
    setSort(spec.sort ?? null);
    setColumnsOrder(spec.columns_order ?? null);
    setLayout(spec.layout ?? "long");
    setChartMetric(spec.chart_metric ?? null);
  }

  function applyPreset(preset: Preset) {
    applySpec(preset.spec);
  }

  /**
   * The exact `ReportSpec` the on-screen table was built from — the single
   * builder used by both the preview fetch and the export downloads, so a
   * download can never diverge from what the report route just rendered
   * (user story 34, "the exported file matches exactly what is on screen").
   */
  function buildReportSpec(): ReportSpec {
    return {
      metrics,
      date_from: dateFrom,
      date_to: dateTo,
      granularity,
      group_by: groupBy,
      duration_display: durationDisplay,
      sort,
      columns_order: columnsOrder,
      layout,
      chart_metric: chartMetric,
    };
  }

  /**
   * Download the current report as CSV or Excel (issue 10, issue 11).
   * `exportReport` already goes through `apiFetch`, so the shared key
   * attaches and a 401 still bounces to sign-in exactly like every other
   * call — this handler only has to react to a refused date range (the same
   * 422 the preview can hit) and any other failure, rather than doing
   * nothing visible on click.
   */
  async function handleExport(format: ExportFormat) {
    setExportError(null);
    try {
      const { blob, filename } = await exportReport(buildReportSpec(), format);
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

  // A metric that stops being selected can leave `sort`/`chartMetric`
  // pointing at a column that no longer exists — the backend validator
  // would 422 that spec (architecture.md §2: both must be ∈ metrics), so
  // clear them here rather than let the request fail (a minimal client-side
  // echo of the "Repair" idea; the full agent-facing repair module is a
  // later slice).
  useEffect(() => {
    setSort((prev) => (prev && !metrics.includes(prev.column) ? null : prev));
    setChartMetric((prev) => (prev && !metrics.includes(prev) ? null : prev));
    setColumnsOrder((prev) => (prev ? prev.filter((key) => metrics.includes(key)) : prev));
  }, [metrics]);

  useEffect(() => {
    function handleUnauthorized() {
      setSignedIn(false);
    }
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  useEffect(() => {
    if (!signedIn) return;
    apiFetch("/healthz")
      .then((res) => setStatus(res.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
    fetchMeta()
      .then(setMeta)
      .catch(() => setMeta(null));
    fetchAssumptions()
      .then(setAssumptions)
      .catch(() => setAssumptions(null));

    // Restore the Report Spec from the URL (issue 13) — or the default
    // report if there is none, or it fails to decode. Decoding itself
    // happens server-side, in `GET /api/v1/spec`
    // (`app/spec_url.py::decode_spec`, the only place that validation
    // logic exists, going through `ReportSpec`'s own pydantic validators):
    // a hand-edited or hostile query string is judged by exactly the rules
    // every other caller of `ReportSpec` is judged by, never by a second,
    // driftable copy of those rules living in the browser. This is one
    // extra request inside a loading phase the app already has (the same
    // one `fetchMeta` runs in) — no perceptible cost, no new spinner.
    //
    // Reads `window.location.search` FRESH on every `signedIn` transition,
    // not a value frozen at first mount: once `presetsReady`, the URL-sync
    // effect below keeps it mirroring the CURRENT spec at all times, so a
    // re-render triggered by signing back in after a 401 (issue 02) reads
    // back exactly the spec that was on screen when the 401 happened —
    // that behaviour only becomes meaningful now that the URL genuinely
    // carries the spec.
    fetchSpecFromQuery(window.location.search)
      .then(({ spec, warnings }) => {
        applySpec(spec);
        if (warnings.length > 0) {
          setUrlWarning(warnings[0]);
        } else {
          setUrlWarning(null);
          // Only a link that decoded cleanly needs the stale-Coverage-
          // Window check on the next fetch — a warning here already means
          // the default (always built from the live window) was applied.
          restoringFromUrl.current = window.location.search.length > 0;
        }
        // Unblocks the report-fetching effect below — this is the ONLY
        // path that sets it, so the very first request the app makes
        // always carries either a restored link's real dates or the
        // default preset's, never the placeholders above.
        setPresetsReady(true);
      })
      .catch(() => {
        // Could not even ask the server (offline, etc.) — fail safe: no
        // report is requested at all, same as the pre-issue-13 "meta never
        // answered" state, rather than guessing a spec.
      });
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn || !presetsReady) return;
    if (dateFrom > dateTo) {
      // Both inputs are individually clamped to the Coverage Window, but an
      // inverted range (from > to) is still reachable by editing the two
      // independently — refuse locally rather than sending a spec the
      // engine's own validator would 422 on.
      setReportError("The start date must be on or before the end date.");
      return;
    }
    const wasRestoringFromUrl = restoringFromUrl.current;
    // One-shot: only the very first fetch after a URL restore gets the
    // special stale-link handling below — every subsequent refusal (the
    // user editing the date inputs by hand) is the ordinary `reportError`
    // path.
    restoringFromUrl.current = false;

    fetchReport(buildReportSpec())
      .then((result) => {
        setTable(result);
        setReportError(null);
      })
      .catch((err: unknown) => {
        // A refused (zero-overlap) range is never shown as a table — a
        // stale table under the error would look like an answer to the
        // question just asked (architecture.md §12: "a date outside
        // coverage is refused, not silently substituted"). A clamped,
        // partially-overlapping range is not this path at all: the backend
        // returns 200 with the real table plus a `warnings` banner.
        if (err instanceof ReportRefusedError) {
          if (wasRestoringFromUrl && meta && meta.presets.length > 0) {
            // A stale link (issue 13): its dates decoded fine but no
            // longer overlap the CURRENT Coverage Window (issue 08) — the
            // exact "hand-edited or stale link" case named in the issue.
            // Fall back to the default report, same as a link that failed
            // to decode at all, rather than leave the user staring at a
            // refusal for a date range they never chose.
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
      });
  }, [
    signedIn,
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

  /**
   * Keep the URL in sync with the current Report Spec (issue 13 acceptance
   * criteria: "Changing any control updates the URL"). `replaceState`, not
   * `pushState` — every keystroke/click updating the address bar is the
   * point, but it must not spam browser history with an entry per
   * character typed into a date input. Gated on `presetsReady` exactly
   * like the fetch effect above, so the placeholder dates never get
   * written into the URL before the real preset (or a restored link) has
   * been applied.
   */
  useEffect(() => {
    if (!signedIn || !presetsReady) return;
    const params = encodeSpecToSearchParams(buildReportSpec());
    const next = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState(null, "", next);
  }, [
    signedIn,
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

  if (!signedIn) {
    return <SignIn onSignedIn={() => setSignedIn(true)} />;
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      {meta?.dev_fake_upstream && (
        <div
          role="status"
          style={{
            background: "#fff3cd",
            color: "#664d03",
            border: "1px solid #ffe69c",
            borderRadius: 4,
            padding: "0.5rem 1rem",
            marginBottom: "1rem",
            fontWeight: 600,
          }}
        >
          DEV_FAKE_UPSTREAM is on — this report is built from the committed fixture, not live
          data.
        </div>
      )}
      {meta?.dev_fake_llm && (
        <div
          role="status"
          style={{
            background: "#fff3cd",
            color: "#664d03",
            border: "1px solid #ffe69c",
            borderRadius: 4,
            padding: "0.5rem 1rem",
            marginBottom: "1rem",
            fontWeight: 600,
          }}
        >
          DEV_FAKE_LLM is on — the Assistant runs a scripted conversation, not a real model.
        </div>
      )}
      <h1>loopai — reporting builder</h1>
      {meta && (
        <p>
          Coverage Window: {meta.coverage_window.from_date} – {meta.coverage_window.to_date}
          {" · "}
          <button
            type="button"
            onClick={() => setShowAssumptions(true)}
            disabled={!assumptions}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              color: "#0d6efd",
              textDecoration: "underline",
              cursor: assumptions ? "pointer" : "default",
              font: "inherit",
            }}
          >
            What assumptions does this report make?
          </button>
        </p>
      )}
      {showAssumptions && assumptions && (
        <AssumptionsModal notes={assumptions} onClose={() => setShowAssumptions(false)} />
      )}
      <p>Backend status: {status}</p>
      {urlWarning && (
        <p role="alert" style={{ color: "#664d03" }}>
          {urlWarning}
        </p>
      )}
      <h2>Report builder</h2>
      <fieldset style={{ marginBottom: "1rem", display: "inline-block" }}>
        <legend>Presets</legend>
        {meta?.presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => applyPreset(preset)}
            style={{ marginRight: "0.5rem" }}
          >
            {preset.label}
          </button>
        ))}
      </fieldset>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
        <fieldset style={{ display: "inline-block" }}>
          <legend>Date range</legend>
          <label style={{ marginRight: "0.75rem" }}>
            From{" "}
            <input
              type="date"
              value={dateFrom}
              min={meta?.coverage_window.from_date}
              max={meta?.coverage_window.to_date}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label>
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

        <fieldset style={{ display: "inline-block" }}>
          <legend>Grouping</legend>
          <label>
            <select
              value={groupBy}
              onChange={(event) => setGroupBy(event.target.value as ReportSpec["group_by"])}
            >
              <option value="none">No grouping</option>
              <option value="agent">By Actor</option>
              <option value="mailbox">By Mailbox</option>
            </select>
          </label>
        </fieldset>

        <fieldset style={{ display: "inline-block" }}>
          <legend>Granularity</legend>
          <label style={{ marginRight: "0.75rem" }}>
            <input
              type="radio"
              name="granularity"
              value="day"
              checked={granularity === "day"}
              onChange={() => setGranularity("day")}
            />
            Per day
          </label>
          <label>
            <input
              type="radio"
              name="granularity"
              value="total"
              checked={granularity === "total"}
              onChange={() => setGranularity("total")}
            />
            Whole period (one Bucket)
          </label>
        </fieldset>
      </div>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend>Metrics</legend>
        {meta?.metrics.map((metric) => (
          <label key={metric.key} style={{ display: "inline-block", marginRight: "1rem" }}>
            <input
              type="checkbox"
              checked={metrics.includes(metric.key)}
              onChange={() => toggleMetric(metric.key)}
            />
            {formatMetricLabel(metric.key)}
            {metric.unit === "hours" ? " (h)" : ""}
          </label>
        ))}
      </fieldset>

      <fieldset style={{ marginBottom: "1rem", display: "inline-block" }}>
        <legend>Duration display</legend>
        <label style={{ marginRight: "1rem" }}>
          <input
            type="radio"
            name="duration_display"
            value="avg"
            checked={durationDisplay === "avg"}
            onChange={() => setDurationDisplay("avg")}
          />
          Per-ticket average (how fast)
        </label>
        <label>
          <input
            type="radio"
            name="duration_display"
            value="total"
            checked={durationDisplay === "total"}
            onChange={() => setDurationDisplay("total")}
          />
          Period total (how much work)
        </label>
      </fieldset>

      <fieldset style={{ marginBottom: "1rem", display: "inline-block" }}>
        <legend>Layout</legend>
        <label style={{ marginRight: "1rem" }}>
          <input
            type="radio"
            name="layout"
            value="long"
            checked={layout === "long"}
            onChange={() => setLayout("long")}
          />
          Table (rows = Bucket × group)
        </label>
        <label style={{ marginRight: "1rem" }}>
          <input
            type="radio"
            name="layout"
            value="pivot"
            checked={layout === "pivot"}
            onChange={() => setLayout("pivot")}
          />
          Pivot (Buckets as columns)
        </label>
        {layout === "pivot" && (
          // Pivot renders exactly one metric (architecture.md §2) — this is
          // the *only* way to pick which one; the report table's own
          // warning banner (from `table.warnings`) states why the other
          // selected metrics aren't shown.
          <label>
            {" "}
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
      {reportError && <p role="alert">{reportError}</p>}
      <div style={{ marginBottom: "1rem" }}>
        <button type="button" onClick={() => handleExport("csv")} disabled={!table}>
          Download CSV
        </button>{" "}
        <button type="button" onClick={() => handleExport("xlsx")} disabled={!table}>
          Download Excel
        </button>
      </div>
      {exportError && <p role="alert">{exportError}</p>}
      {!presetsReady && !reportError && (
        // Before the day-by-Actor preset lands (`/api/v1/meta`'s `presets`),
        // no report has been requested at all (issue 12: never with the
        // placeholder dates above) — a labelled loading state here, not a
        // blank gap, is what stands in for the table until then.
        <p role="status">Loading report…</p>
      )}
      {table && (
        <Chart
          chart={table.chart}
          metricUnit={
            (meta?.metrics.find((m) => m.key === table.chart?.metric)
              ?.unit as "count" | "hours" | "replies" | undefined) ?? null
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
          layout={layout ?? "long"}
          sort={sort}
          onSort={toggleSort}
          onMoveColumn={moveColumn}
        />
      )}
      <Chat spec={buildReportSpec()} onApplySpec={applySpec} />
    </main>
  );
}
