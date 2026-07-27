Status: done

# 11 — Hard-coded Assistant introduction

## Parent

[`PRD.md`](PRD.md)

## What to build

Replace `Chat.tsx`'s current placeholder line (`"Ask for a report in plain English — e.g. ..."`,
shown when `messages.length === 0`) with a short, hard-coded (no model call, no tokens, instant on
load) greeting rendered through the existing `Markdown` component.

Content: one line stating what the Assistant can do, 3-4 bullets naming the most-surprising
capabilities as concrete, literal "try:" examples embedded in the copy itself — not abstract
capability descriptions — plus a friendly closing question. Pivot layout remains the headline
example (the one capability the product owner has personally already been surprised by).
Include the filter feature (slices 02-07) with the owner's exact chosen wording:

> try: filter to just Theo's numbers

Vocabulary constraints apply as everywhere else in this app: Actor/Mailbox/Coverage Window
terminology, never an unqualified "agent," never a tool name or enum value anywhere in the copy.

## Acceptance criteria

- [ ] The chat panel shows the new greeting (not the old placeholder) before any message is sent
- [ ] The greeting includes at least 3 concrete "try:" examples, including the exact filter
      wording above
- [ ] No tool name or enum value (`set_metrics`, `"pivot"`, `"agent"` as a wire value, etc.)
      appears in the copy
- [ ] No unqualified "agent" appears in the copy
- [ ] Renders correctly through the existing Markdown pipeline (bullets/short lines, no broken
      formatting)
- [ ] Verified in a real browser (Chrome DevTools MCP)

## Blocked by

- [05 — Builder-rail filter control](05-builder-rail-filter-control.md)
- [10 — Frontend: per-message reasoning trace, three-state indicator](10-frontend-reasoning-ui.md)
