/**
 * The shared API key lives in sessionStorage only — for the tab's lifetime,
 * never persisted longer than that (issue 02: "stored for the session").
 */
const STORAGE_KEY = "loopai.apiKey";

export function getStoredApiKey(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}

export function setStoredApiKey(key: string): void {
  sessionStorage.setItem(STORAGE_KEY, key);
}

export function clearStoredApiKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
