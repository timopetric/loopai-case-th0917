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
 * moment the app opens, no controls touched. Metrics are Counters only —
 * this slice's engine does not yet aggregate Duration Metrics (issue 05).
 * The date range spans the whole Coverage Window; a real builder UI with
 * metric/date/group controls arrives in later slices.
 */
const DEFAULT_SPEC: ReportSpec = {
  metrics: ["resolved", "replies", "new_tickets"],
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
    fetchReport(DEFAULT_SPEC)
      .then((result) => {
        setTable(result);
        setReportError(null);
      })
      .catch(() => setReportError("Could not load the report."));
  }, [signedIn]);

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
      <h2>Resolved, replies and new tickets — by day and Actor</h2>
      {reportError && <p role="alert">{reportError}</p>}
      {table && <ReportTable table={table} />}
    </main>
  );
}
