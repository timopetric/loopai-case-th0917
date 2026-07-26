import type { ReactNode } from "react";

/**
 * A selectable chip (issue 03: frontend-rework builder rail) — the
 * reference's chip component spec, used here for the Metric multi-select.
 * `aria-pressed` carries the selected state for assistive tech since this
 * is a toggle button, not a native checkbox — the Metrics section header's
 * "N of M selected" count (BuilderPane) is the only place the selection
 * total is surfaced, so this component stays a dumb, controlled toggle.
 */
export function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={
        "rounded-full border px-3 py-1 text-body-sm-medium font-medium transition-colors " +
        "duration-[var(--motion-fast)] ease-brand " +
        (selected
          ? "border-primary bg-primary text-on-primary"
          : "border-hairline-strong bg-canvas text-ink-tint hover:bg-cream-soft hover:text-ink")
      }
    >
      {children}
    </button>
  );
}
