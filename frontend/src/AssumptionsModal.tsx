import { useEffect, useRef } from "react";

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
 *
 * Focus management (issue 08: frontend-rework accessibility polish) — a
 * dialog that opens without moving focus into itself, trapping Tab there,
 * and giving focus back to whatever opened it is a keyboard dead end: the
 * user's cursor either stays behind the backdrop (can't reach the modal at
 * all without many Tabs) or, worse, can Tab OUT of the modal into content
 * hidden behind the scrim. All three (move focus in, trap Tab within the
 * dialog's own focusable elements, restore focus to the opener) are
 * self-contained in the effect below rather than pushed onto every caller
 * — `Header.tsx`'s "What assumptions..." link doesn't need to know or hold
 * a ref, it just conditionally renders this component.
 */
const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function AssumptionsModal({
  notes,
  onClose,
}: {
  notes: AssumptionNote[];
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Captured on mount, when `document.activeElement` is still whatever
    // control the caller had just activated (the header's assumptions
    // link) — restoring focus there on close is what "returns focus to
    // the control that opened it" means.
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const dialog = dialogRef.current;
    const focusables = dialog
      ? Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      : [];
    focusables[0]?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;

      const current = Array.from(
        dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (current.length === 0) return;

      const first = current[0];
      const last = current[current.length - 1];
      // Wrap Tab/Shift+Tab at the dialog's own edges instead of letting
      // focus escape into the (visually hidden, but still in the DOM)
      // page behind the backdrop — the trap itself.
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Assumptions about this data"
      onClick={onClose}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4"
    >
      <div
        ref={dialogRef}
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
            className="flex h-11 w-11 items-center justify-center rounded-md text-body-md
              text-steel hover:bg-cream-soft hover:text-ink"
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
