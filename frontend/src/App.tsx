import { useEffect, useState } from "react";

/**
 * Walking-skeleton page (issue 01). The report builder UI arrives in later
 * slices; this proves the SPA is served from the backend's own origin and
 * can reach it through a relative path, with no build-time configuration.
 */
export function App() {
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");

  useEffect(() => {
    fetch("/healthz")
      .then((res) => (res.ok ? setStatus("ok") : setStatus("error")))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>loopai — reporting builder</h1>
      <p>Backend status: {status}</p>
    </main>
  );
}
