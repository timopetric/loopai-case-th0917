import { useEffect, useState } from "react";

import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT, apiFetch } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";

/**
 * Walking-skeleton page (issue 01), now behind the sign-in gate (issue 02).
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
  }, [signedIn]);

  if (!signedIn) {
    return <SignIn onSignedIn={() => setSignedIn(true)} />;
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>loopai — reporting builder</h1>
      <p>Backend status: {status}</p>
    </main>
  );
}
