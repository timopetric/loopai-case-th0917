import type { InputHTMLAttributes } from "react";

/**
 * A labelled text/date input (issue 03: frontend-rework builder rail) — one
 * component covers both, since a date input is a text input with
 * `type="date"` and `min`/`max` bounds; the reference draws no visual
 * distinction between them either. `min`/`max` pass straight through native
 * `<input>` props, which is how the rail keeps the date fields clamped to
 * the Coverage Window (`meta.coverage_window`) without this primitive
 * knowing anything about reports.
 */
export function TextInput({
  label,
  ...inputProps
}: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="mb-1 block text-body-sm-medium font-medium text-ink-tint">{label}</span>
      <input
        {...inputProps}
        className="h-9 w-full rounded-md border border-hairline-strong bg-canvas px-3 text-body-sm
          text-ink outline-none transition-[border-color,box-shadow] duration-[var(--motion-base)]
          ease-brand focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}
