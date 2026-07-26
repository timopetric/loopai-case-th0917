import { Chat } from "../Chat";

/**
 * The right "Assistant" zone (issue 02: frontend-rework) — permanently
 * docked and visible without scrolling, which is the whole reason this
 * slice exists: watching the builder controls move as the Assistant works
 * is the product's most persuasive moment, and it only exists if both are
 * on screen at once (PRD). Today the Assistant sat below several thousand
 * table cells; this pane is what fixes that.
 *
 * `Chat` reads and writes the shared Report Spec store directly (see
 * `Chat.tsx`'s docstring) — this pane only owns the collapse affordance,
 * which is shell-level layout state, not Report Spec state.
 */
export function AssistantPane({
  collapsed,
  onToggleCollapse,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  if (collapsed) {
    return (
      <aside className="flex w-11 shrink-0 flex-col items-center border-l border-hairline bg-surface py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand the Assistant"
          className="rounded-md p-2 text-body-sm text-steel hover:bg-cream-soft hover:text-ink"
        >
          «
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-hairline bg-surface p-4 lg:w-96 lg:border-l">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-heading-5 font-semibold text-ink">Assistant</h2>
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Collapse the Assistant"
          className="rounded-md px-2 py-1 text-body-sm text-steel hover:bg-cream-soft hover:text-ink"
        >
          »
        </button>
      </div>
      <Chat />
    </aside>
  );
}
