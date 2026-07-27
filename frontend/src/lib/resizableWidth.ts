import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Drag-to-resize width for a docked side panel, persisted to `localStorage`
 * (unlike `sessionStorage`-based `themeStore`/`apiKey`: panel width carries
 * no sensitive or auth-adjacent data, so surviving across tabs and restarts
 * is a pure convenience with no downside).
 *
 * The panel is resized from its left edge, so dragging the handle left
 * (negative pointer movement) grows a right-docked panel and vice versa —
 * callers pass `direction: "left"` (handle on the left edge, panel to its
 * right) accordingly.
 */
/** Tailwind's `lg` breakpoint — kept in sync with the `lg:` utilities the
 * callers of `useResizableWidth` apply alongside its returned width. A
 * `matchMedia` listener (not a one-off `window.innerWidth` read) so the
 * resizable width only applies once, and stops applying, exactly when the
 * layout actually crosses the breakpoint — including a live browser resize,
 * which a render-time read would miss. */
const LG_BREAKPOINT_QUERY = "(min-width: 1024px)";

function readStoredWidth(storageKey: string): number | null {
  try {
    return window.localStorage.getItem(storageKey) ? Number(window.localStorage.getItem(storageKey)) : null;
  } catch {
    // Private browsing / storage disabled — fail open to `defaultWidth`
    // rather than throwing during module init (mirrors `themeStore.ts`).
    return null;
  }
}

function writeStoredWidth(storageKey: string, width: number): void {
  try {
    window.localStorage.setItem(storageKey, String(width));
  } catch {
    // The width still applies for this render via in-memory state; it just
    // won't survive a reload if storage is unavailable.
  }
}

function useIsAboveBreakpoint(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export function useResizableWidth({
  storageKey,
  defaultWidth,
  minWidth,
  maxWidth,
}: {
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
}) {
  const isAboveBreakpoint = useIsAboveBreakpoint(LG_BREAKPOINT_QUERY);
  const [width, setWidth] = useState(() => {
    const stored = readStoredWidth(storageKey);
    if (stored !== null && Number.isFinite(stored)) {
      return Math.min(maxWidth, Math.max(minWidth, stored));
    }
    return defaultWidth;
  });
  const [resizing, setResizing] = useState(false);
  const dragState = useRef<{ startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    writeStoredWidth(storageKey, width);
  }, [storageKey, width]);

  useEffect(() => {
    if (!resizing) return;

    function onPointerMove(event: PointerEvent) {
      if (!dragState.current) return;
      const delta = dragState.current.startX - event.clientX;
      const next = Math.min(maxWidth, Math.max(minWidth, dragState.current.startWidth + delta));
      setWidth(next);
    }

    function onPointerUp() {
      dragState.current = null;
      setResizing(false);
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [resizing, minWidth, maxWidth]);

  const onHandlePointerDown = useCallback(
    (event: React.PointerEvent) => {
      dragState.current = { startX: event.clientX, startWidth: width };
      setResizing(true);
    },
    [width],
  );

  return { width, resizing, onHandlePointerDown, isAboveBreakpoint };
}
