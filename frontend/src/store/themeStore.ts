import { create } from "zustand";

/**
 * The theme store (issue 07: frontend-rework, architecture.md §7).
 *
 * `null` means "follow the operating system" — the default (acceptance
 * criterion: "the workspace renders in both themes, following the system
 * preference by default"). `"light"`/`"dark"` is the explicit user
 * override, which must win over the OS setting the moment it is set
 * (second acceptance criterion).
 *
 * Persistence is deliberately `sessionStorage`, not `localStorage`: the
 * issue's language is "persists for the session," not "persists forever,"
 * and `localStorage` would silently outlive the tab. This is also not a
 * `VITE_*`/build-time value — AGENTS.md's hard rule against build-time
 * frontend configuration — it is read and written at runtime only.
 *
 * The resolved theme is applied to `<html>` as `data-theme="light"` /
 * `data-theme="dark"` only when there IS an explicit override; with no
 * override the attribute is absent entirely and `tokens.css`'s
 * `@media (prefers-color-scheme: dark)` block alone decides, so a user who
 * has never touched the toggle stays byte-for-byte on the pre-issue-07
 * "follow the OS" behaviour.
 *
 * A single Zustand store (matching `reportSpecStore.ts`'s justification:
 * "tiny, Claude-familiar") rather than a React Context, so `Chart.tsx` (a
 * plain function component several layers below `Header.tsx`, which owns
 * the toggle) can read the resolved theme with a plain selector hook
 * instead of both needing to sit inside the same Provider subtree.
 */

export type ThemeOverride = "light" | "dark" | null;
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "loopai:theme-override";

function readStoredOverride(): ThemeOverride {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw === "light" || raw === "dark" ? raw : null;
  } catch {
    // Private browsing / storage disabled — fail open to "follow the OS"
    // rather than throwing during module init.
    return null;
  }
}

function writeStoredOverride(value: ThemeOverride): void {
  try {
    if (value) {
      window.sessionStorage.setItem(STORAGE_KEY, value);
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // The override still applies for this render via the in-memory store;
    // it just won't survive a reload if storage is unavailable.
  }
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Reflects the *explicit* override onto `<html>` — never the resolved
 * theme, so "no override" leaves no trace of an attribute for `tokens.css`
 * to accidentally match against. */
function applyThemeAttribute(override: ThemeOverride): void {
  const root = document.documentElement;
  if (override) {
    root.setAttribute("data-theme", override);
  } else {
    root.removeAttribute("data-theme");
  }
}

export function resolveTheme(override: ThemeOverride, systemDark: boolean): ResolvedTheme {
  return override ?? (systemDark ? "dark" : "light");
}

interface ThemeState {
  /** `null` = follow the OS; otherwise the explicit user choice. */
  override: ThemeOverride;
  /** Mirrors `matchMedia("(prefers-color-scheme: dark)")`, kept in the
   * store (rather than read ad hoc) so `resolved` can be derived once. */
  systemDark: boolean;
  /** What every component should actually render — the single source of
   * truth `Chart.tsx` and the token layer effectively agree on. */
  resolved: ResolvedTheme;
  setOverride: (value: ThemeOverride) => void;
  /** Called only by the `matchMedia` listener wired up in `initThemeWatcher`. */
  setSystemDark: (value: boolean) => void;
}

export const useThemeStore = create<ThemeState>((set, get) => {
  const initialOverride = readStoredOverride();
  const initialSystemDark = systemPrefersDark();
  return {
    override: initialOverride,
    systemDark: initialSystemDark,
    resolved: resolveTheme(initialOverride, initialSystemDark),
    setOverride: (value) => {
      writeStoredOverride(value);
      applyThemeAttribute(value);
      set({ override: value, resolved: resolveTheme(value, get().systemDark) });
    },
    setSystemDark: (value) => {
      set((state) => ({ systemDark: value, resolved: resolveTheme(state.override, value) }));
    },
  };
});

/**
 * Wires the OS `prefers-color-scheme` listener and applies the initial
 * `data-theme` attribute for whatever override was already in
 * `sessionStorage` (e.g. a page reload mid-session). Called once from
 * `App.tsx`, not as top-level module code — top-level `window` access
 * would run in any environment that merely imports this module.
 */
export function initThemeWatcher(): () => void {
  applyThemeAttribute(useThemeStore.getState().override);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  function handleChange(event: MediaQueryListEvent) {
    useThemeStore.getState().setSystemDark(event.matches);
  }
  media.addEventListener("change", handleChange);
  return () => media.removeEventListener("change", handleChange);
}
