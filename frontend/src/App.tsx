import { useEffect, useState } from "react";

import { ReportTable } from "./ReportTable";
import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT, apiFetch } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";
import type { Meta } from "./lib/meta";
import { fetchMeta } from "./lib/meta";
import type { ReportSpec, ReportTable as ReportTableData, SortSpec } from "./lib/report";
import { ReportRefusedError, fetchReport, formatMetricLabel } from "./lib/report";

/**
 * The client's literal ask (PRD user story 3): day × Actor, populated the
 * moment the app opens, no controls touched. `resolve_time` is included
 * alongside the Counters so the avg/total toggle has something to
 * demonstrate — Duration Metrics are aggregated as of issue 05. These are
 * only the *initial* values of the builder controls added in issue 06 —
 * every one of them is editable afterwards, and the date bounds are always
 * re-derived from `/api/v1/meta`, never hardcoded past this first paint.
 */
const DEFAULT_METRICS = ["resolved", "replies", "new_tickets", "resolve_time"];
const DEFAULT_DATE_FROM = "2026-07-10";
const DEFAULT_DATE_TO = "2026-07-23";
const DEFAULT_GRANULARITY: ReportSpec["granularity"] = "day";
const DEFAULT_GROUP_BY: ReportSpec["group_by"] = "agent";

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
  const [reportError, setReportError] = useState<string | null>(null);
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
  const [metrics, setMetrics] = useState<string[]>(DEFAULT_METRICS);
  const [dateFrom, setDateFrom] = useState<string>(DEFAULT_DATE_FROM);
  const [dateTo, setDateTo] = useState<string>(DEFAULT_DATE_TO);
  const [granularity, setGranularity] = useState<ReportSpec["granularity"]>(DEFAULT_GRANULARITY);
  const [groupBy, setGroupBy] = useState<ReportSpec["group_by"]>(DEFAULT_GROUP_BY);

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
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    if (dateFrom > dateTo) {
      // Both inputs are individually clamped to the Coverage Window, but an
      // inverted range (from > to) is still reachable by editing the two
      // independently — refuse locally rather than sending a spec the
      // engine's own validator would 422 on.
      setReportError("The start date must be on or before the end date.");
      return;
    }
    fetchReport({
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
    })
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
      <h1>loopai — reporting builder</h1>
      {meta && (
        <p>
          Coverage Window: {meta.coverage_window.from_date} – {meta.coverage_window.to_date}
        </p>
      )}
      <p>Backend status: {status}</p>
      <h2>Report builder</h2>
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
    </main>
  );
}
