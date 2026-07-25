import { useEffect, useState } from "react";

import { ReportTable } from "./ReportTable";
import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT, apiFetch } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";
import type { Meta } from "./lib/meta";
import { fetchMeta } from "./lib/meta";
import type { ReportSpec, ReportTable as ReportTableData } from "./lib/report";
import { fetchReport } from "./lib/report";

/**
 * The client's literal ask (PRD user story 3): day × Actor, populated the
 * moment the app opens, no controls touched. `resolve_time` is included
 * alongside the Counters so the avg/total toggle below has something to
 * demonstrate — Duration Metrics are aggregated as of issue 05. The date
 * range spans the whole Coverage Window; a real builder UI with metric/date/
 * group controls arrives in later slices (issue 06).
 */
const DEFAULT_SPEC: Omit<ReportSpec, "duration_display"> = {
  metrics: ["resolved", "replies", "new_tickets", "resolve_time"],
  date_from: "2026-07-10",
  date_to: "2026-07-23",
  granularity: "day",
  group_by: "agent",
};

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
   * The one Report Spec control this slice adds (issue 05, user story 14):
   * per-ticket average ("how fast") vs period total ("how much work") for
   * Duration Metrics. A full builder UI (this alongside metric/date/group
   * controls, all driving one spec-in-state) is issue 06's scope; this is
   * the minimal wiring needed to close issue 05's own acceptance criterion
   * honestly rather than deferring it.
   */
  const [durationDisplay, setDurationDisplay] = useState<"avg" | "total">("avg");

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
    fetchReport({ ...DEFAULT_SPEC, duration_display: durationDisplay })
      .then((result) => {
        setTable(result);
        setReportError(null);
      })
      .catch(() => setReportError("Could not load the report."));
  }, [signedIn, durationDisplay]);

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
      <h2>Resolved, replies, new tickets and resolve time — by day and Actor</h2>
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
      {reportError && <p role="alert">{reportError}</p>}
      {table && <ReportTable table={table} />}
    </main>
  );
}
