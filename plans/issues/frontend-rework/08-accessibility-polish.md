# 08 — Accessibility and interaction polish

Status: done

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

The pass that makes the workspace usable without a mouse and without sight, and that removes the
small frictions a rework tends to leave behind.

The current interface has **no visible focus styling at all**, which makes keyboard use guesswork,
and the streamed **Assistant** reply is announced to nobody.

- **Focus is always visible** and meets contrast in both themes, on every interactive element
  including the table's sortable headers and column controls.
- **The streaming reply is announced politely**, so a screen reader user learns the **Assistant**
  answered without having the whole growing message re-read on every token.
- **Sortable headers expose their sort state** semantically, not only as an arrow glyph.
- **The table stays a table** to assistive technology after virtualisation — a windowed row set
  must not destroy the row and column semantics or the header associations.
- **The modal traps focus**, closes on escape, and returns focus to the control that opened it.
- **Interactive targets meet the touch floor** the reference sets, which several current controls
  miss.
- **Motion respects the reduced-motion preference** — the thinking indicator's animation in
  particular.
- **Keyboard paths work end to end**: reach and operate every builder control, sort a column,
  collapse a pane, open and dismiss the assumptions modal, and send an **Assistant** message.

Also fold in the interaction frictions worth fixing here: a busy state on anything that triggers a
round trip, so sorting a large report does not look like nothing happened; and an export failure
surfaced without disturbing a good report already on screen.

## Acceptance criteria

- [ ] Every interactive element has a visible focus style meeting contrast in both themes
- [ ] The streaming Assistant reply is announced politely, without re-reading on every token
- [ ] Sortable headers expose their sort state semantically
- [ ] The virtualised table preserves row, column and header semantics for assistive technology
- [ ] The assumptions modal traps focus, closes on escape, and restores focus on close
- [ ] Interactive targets meet the touch-target floor
- [ ] Animation is suppressed under a reduced-motion preference
- [ ] The full walkthrough is possible by keyboard alone
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes.
**Level 2** — primary. Unplug the mouse and complete the walkthrough, then run an accessibility
audit over the assembled page in both themes and act on what it reports.

## Blocked by

03, 04, 05, 06
