import { useEffect, useState } from "react";

import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT, apiFetch } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";
import type { Meta } from "./lib/meta";
import { fetchMeta } from "./lib/meta";

/**
 * Walking-skeleton page (issue 01), now behind the sign-in gate (issue 02),
 * now showing the Coverage Window from `/api/v1/meta` (issue 03).
 * The report builder UI arrives in later slices; this proves the SPA is
 * served from the backend's own origin and can reach it through a relative
 * path, with no build-time configuration.
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
    </main>
  );
}
