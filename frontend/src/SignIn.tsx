import { useState, type FormEvent } from "react";

import { apiFetch } from "./lib/apiClient";
import { setStoredApiKey } from "./lib/apiKey";

interface SignInProps {
  onSignedIn: () => void;
}

/**
 * Sign-in gate (issue 02, user story 52), converted to the token layer
 * (issue 01, frontend-rework). The backend runs the Assistant and spends
 * LLM tokens on every call, so the whole API sits behind one shared key
 * entered here rather than being open to the internet.
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
    <main className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm rounded-xl border border-beige-deep bg-cream-soft p-8">
        <h1 className="font-display text-heading-1 text-ink">loopai</h1>
        <p className="mt-1 text-body-sm text-steel">Reporting builder</p>

        <p className="mt-5 text-body-sm text-ink-tint">
          A shared key is required because every report you build here spends metered LLM tokens
          on the Assistant.
        </p>

        <form onSubmit={handleSubmit} className="mt-6">
          <label htmlFor="api-key" className="block text-body-sm-medium font-medium text-ink-tint">
            Access key
          </label>
          <input
            id="api-key"
            type="password"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            autoFocus
            placeholder="Paste your key"
            className="mt-2 h-11 w-full rounded-md border border-hairline-strong bg-canvas px-4
              text-body-md text-ink outline-none transition-[border-color,box-shadow]
              duration-[var(--motion-base)] ease-brand placeholder:text-muted
              focus:border-primary focus:ring-2 focus:ring-primary/20"
          />

          <button
            type="submit"
            disabled={checking || key.length === 0}
            className="mt-5 h-11 w-full rounded-md bg-primary text-button-md font-medium
              text-on-primary transition-colors duration-[var(--motion-base)] ease-brand
              hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-hairline-strong
              disabled:text-muted"
          >
            {checking ? "Checking…" : "Sign in"}
          </button>
        </form>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md bg-danger-soft px-4 py-3 text-body-sm text-danger"
          >
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
