/**
 * A rail/panel section header (issue 03: frontend-rework builder rail) —
 * one of the handful of primitives the design reference's component specs
 * describe and this app actually needs (PRD "Design adaptation"; ADR-0004).
 *
 * The rail's own problem this fixes: with every fieldset legend styled
 * identically (the browser default), the eye has to read every label to
 * find a control. A small-caps, letter-spaced eyebrow with a hairline rule
 * gives each section a distinct visual anchor scannable at a glance, and an
 * optional trailing `meta` slot (e.g. "6 of 14 selected") surfaces a count
 * without the caller needing its own layout for it.
 */
export function SectionHeader({ title, meta }: { title: string; meta?: string }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2 border-b border-hairline pb-1.5">
      <h3 className="text-micro-uppercase font-semibold uppercase text-steel">{title}</h3>
      {meta && <span className="text-micro text-muted">{meta}</span>}
    </div>
  );
}
