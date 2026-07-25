import { clearStoredApiKey, getStoredApiKey } from "./apiKey";

/**
 * Dispatched on `window` whenever any API call comes back 401. `App` listens
 * for this to drop back to the sign-in screen. It never touches the URL, so
 * whatever report definition later lives in the query string survives —
 * there is no navigation, just a re-render (architecture.md §7 "Auth
 * failure").
 */
export const UNAUTHORIZED_EVENT = "loopai:unauthorized";

/**
 * `fetch()` wrapper that attaches the shared key to every call and reacts to
 * a 401 by clearing the stored key and notifying the app. There is no token
 * refresh: the key is a non-expiring shared secret, so a 401 mid-session
 * means the server now holds a different one, not that this one expired.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const apiKey = getStoredApiKey();
  const headers = new Headers(init.headers);
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401) {
    clearStoredApiKey();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }

  return response;
}
