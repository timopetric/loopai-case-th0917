import { useState, type FormEvent } from "react";

import { apiFetch } from "./lib/apiClient";
import { setStoredApiKey } from "./lib/apiKey";

interface SignInProps {
  onSignedIn: () => void;
}

/**
 * Sign-in gate (issue 02, user story 52). The backend runs the Assistant and
 * spends LLM tokens on every call, so the whole API sits behind one shared
 * key entered here rather than being open to the internet.
 */
export function SignIn({ onSignedIn }: SignInProps) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setChecking(true);

    // Store optimistically, then verify: apiFetch attaches whatever is
    // stored and clears it again on a 401, so a wrong key never lingers.
    setStoredApiKey(key);
    try {
      const response = await apiFetch("/api/v1/session");
      if (response.ok) {
        onSignedIn();
      } else {
        setError("That key was not accepted.");
      }
    } catch {
      setError("Could not reach the server. Try again.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: "24rem" }}>
      <h1>loopai — reporting builder</h1>
      <p>The backend runs the AI Assistant and spends tokens, so it stays behind a shared key.</p>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="api-key">Access key</label>
          <br />
          <input
            id="api-key"
            type="password"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            autoFocus
          />
        </div>
        <button type="submit" disabled={checking || key.length === 0}>
          {checking ? "Checking…" : "Sign in"}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
