Status: done

# 10 — Frontend: per-message reasoning trace, three-state indicator

## Parent

[`PRD.md`](PRD.md)

## What to build

Redesign `Chat.tsx`'s reasoning display around three states and a new per-message data model:

**Data model**: move `reasoning` from a single shared `Chat`-component `useState` onto each
`ChatMessage` (a new `reasoning: string` field alongside the existing `text`/`chips`) — every
turn keeps its own permanent, scrollable, re-expandable reasoning trace, consistent with how
`chips` already persist per message rather than being wiped by the next turn. This also fixes an
existing bug where `reasoning` currently accumulates across the whole session instead of
resetting per turn.

**Segmentation**: insert a paragraph break in the accumulating reasoning text whenever
`thinking: start` fires and the message's `reasoning` is already non-empty — a multi-Tool-Step
turn (the architecture's own documented case: `thinking` fires once per Tool Step) reads as
distinct bursts of thought, not one run-on string.

**Rendering**: through the existing `Markdown`/`Streamdown` component — same sanitize pipeline
already used for the Assistant's replies, no new renderer.

**Three visual states, in order**:

1. **Waiting** — `busy` is true, no `thinking: start` has fired yet for this message, no reasoning
   text has arrived. Plain, non-animated "Waiting for a response…" text. No new backend event —
   entirely derivable from client-side state the frontend already has the instant `send()` is
   called.
2. **Thinking** — `thinking: start` has fired for the current Tool Step. Animated pulsing-dot
   indicator, panel auto-expanded, showing the accumulating reasoning text as markdown.
3. **Collapsed** — after `thinking: end` (or `done`), the panel auto-collapses by default. The
   collapsed summary line keeps the pulsing animation if that Tool Step's model call is still
   genuinely in flight (i.e. the user manually collapsed it while `thinking` was still true); it
   only becomes a static, inert summary once the whole turn reaches `done`.

**Manual override**: if the user manually collapses/expands a message's panel while its Tool Step
is still active, that choice is not overridden by the next auto-collapse/auto-expand transition
for that specific message. The next new turn still starts fresh with the default auto-expand
behavior — this is not a persisted global preference.

## Acceptance criteria

- [ ] Sending a message shows "Waiting for a response…" (no animation) before any reasoning
      arrives
- [ ] The moment reasoning starts, the panel auto-expands with an animated pulsing-dot indicator
      and renders accumulating markdown
- [ ] A multi-Tool-Step turn shows visually distinct paragraphs per Tool Step, not one run-on
      block
- [ ] After a Tool Step's `thinking: end`, the panel auto-collapses; a manual collapse mid-turn is
      not snapped back open by the next event
- [ ] A message manually collapsed while still genuinely in flight shows a pulsing (not static)
      collapsed summary; once `done` fires, it becomes static
- [ ] Past turns' reasoning traces remain in the chat history and are re-expandable after sending
      a new message
- [ ] Verified in a real browser (Chrome DevTools MCP) against `make run` with `DEV_FAKE_LLM` —
      this project does not unit-test the frontend; this is a Level 2/3 browser-checklist item

## Blocked by

- [09 — ADR-0005 backend wiring: stream raw reasoning to all users](09-reasoning-default-on-backend.md)
