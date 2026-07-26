import type { AssumptionNote } from "./lib/assumptions";

/**
 * The modal opened by the coverage banner (issue 09, user story 28): every
 * assumption made about the upstream data, in the exact words
 * `app/assumptions.py` defines — this component renders `notes` as given and
 * adds no text of its own, so it cannot drift from the future Excel "Report
 * info" sheet (issue 11), which will read the same source.
 *
 * Converted to the token layer (issue 07: frontend-rework) — the previous
 * version hardcoded `background: "white"` and `color: "#212529"` via inline
 * `style`, which rendered a light card over a dark workspace regardless of
 * theme (exactly the "light-theme surface leaking into dark" issue 07
 * exists to close). The backdrop stays a plain black scrim at fixed opacity
 * rather than a token: a neutral darkening overlay reads correctly behind
 * either theme's card, so it is intentionally NOT one of the surface
 * tokens that flips between light and dark.
 */
export function AssumptionsModal({
  notes,
  onClose,
}: {
  notes: AssumptionNote[];
  onClose: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Assumptions about this data"
      onClick={onClose}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4"
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-hairline
          bg-canvas p-6 text-ink shadow-xl"
      >
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="text-heading-4 font-semibold text-ink">Assumptions about this data</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md px-2 py-1 text-body-md text-steel hover:bg-cream-soft hover:text-ink"
          >
            ×
          </button>
        </div>
        <p className="text-body-sm text-steel">
          Everything below is inferred or established from the upstream API's real behaviour,
          not from its documentation — the documentation is wrong in several places. This is the
          same content the Excel export's "Report info" sheet carries.
        </p>
        <dl className="mt-4">
          {notes.map((note) => (
            <div key={note.id} className="mb-5 last:mb-0">
              <dt className="mb-1 text-body-sm-medium font-semibold text-ink-tint">
                {note.title}
              </dt>
              <dd className="text-body-sm leading-relaxed text-ink-tint">{note.body}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
