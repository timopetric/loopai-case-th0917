import type { AssumptionNote } from "./lib/assumptions";

/**
 * The modal opened by the coverage banner (issue 09, user story 28): every
 * assumption made about the upstream data, in the exact words
 * `app/assumptions.py` defines — this component renders `notes` as given and
 * adds no text of its own, so it cannot drift from the future Excel "Report
 * info" sheet (issue 11), which will read the same source.
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
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          background: "white",
          color: "#212529",
          borderRadius: 8,
          padding: "1.5rem",
          maxWidth: 720,
          maxHeight: "85vh",
          overflowY: "auto",
          boxShadow: "0 4px 24px rgba(0, 0, 0, 0.3)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.5rem",
          }}
        >
          <h2 style={{ margin: 0 }}>Assumptions about this data</h2>
          <button onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p style={{ color: "#495057" }}>
          Everything below is inferred or established from the upstream API's real behaviour,
          not from its documentation — the documentation is wrong in several places. This is the
          same content the Excel export's "Report info" sheet carries.
        </p>
        <dl>
          {notes.map((note) => (
            <div key={note.id} style={{ marginBottom: "1.25rem" }}>
              <dt style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{note.title}</dt>
              <dd style={{ margin: 0, lineHeight: 1.5 }}>{note.body}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
