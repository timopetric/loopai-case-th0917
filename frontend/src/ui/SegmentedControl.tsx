/**
 * A segmented, single-choice control (issue 03: frontend-rework builder
 * rail) — the reference's segmented-control component spec, adapted from
 * the token layer rather than the reference's own colours (ADR-0004: brand
 * orange is confined to CTAs/active states, which is exactly the "active
 * segment" role here).
 *
 * Generic over the option value so callers keep their own wire-value union
 * types (e.g. `ReportSpec["group_by"]`) instead of this component widening
 * them to `string` — the wire value behind an option (`"agent"`, `"day"`,
 * ...) is a prop, never rendered as visible text itself, so restyling a
 * control never risks the "no unqualified agent visible to a user" rule:
 * the caller supplies the human label separately.
 */
export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export function SegmentedControl<T extends string>({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={name}
      className="inline-flex w-full gap-0.5 rounded-md border border-hairline-strong bg-canvas p-0.5"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={
              "flex-1 rounded-sm px-2 py-1.5 text-body-sm-medium font-medium transition-colors " +
              "duration-[var(--motion-fast)] ease-brand " +
              (active
                ? "bg-primary text-on-primary"
                : "text-steel hover:bg-cream-soft hover:text-ink")
            }
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
