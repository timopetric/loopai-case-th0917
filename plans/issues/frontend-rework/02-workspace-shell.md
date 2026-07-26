# 02 — Three-pane workspace shell with the Assistant docked right

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

The layout the technical design specified and the build never implemented: a workspace of three
zones — builder, report, **Assistant** — with the **Assistant permanently docked on the right**.

This is the slice that changes what the product feels like. Today the **Assistant** sits below
several thousand table cells, so nobody sees the controls move as it works; that visible movement
is the whole reason the tools are field-scoped rather than one atomic patch.

Two structural changes make the rest of the rework possible, and both are documented decisions
that were skipped:

- **Split the monolithic app component** into the three panes plus a header. At 689 lines with
  around fourteen pieces of local state, no layout change inside it is pleasant or safe.
- **Adopt the single Report Spec store** the technical design §7 calls for. Prop-drilling the spec
  and its setters through three sibling panes is what makes the current structure resist this
  layout, and the store is also what lets an **Assistant** spec event and a human control edit
  land in exactly the same place.

The panes may keep their existing internals for now — the point of this slice is the shell, the
store and the docking. Restyling each pane is slices 03 to 06.

The header carries the product name, the **Coverage Window**, the assumptions link, the presets
and the export actions. The developer status line currently rendered to users is removed.

Both side panes collapse, so a wide report can reclaim the width, and the layout degrades
sensibly on a narrow viewport rather than crushing three columns together.

## Acceptance criteria

- [ ] The workspace renders three zones with the Assistant docked on the right and visible without scrolling
- [ ] A single Report Spec store holds the spec, and both a control edit and an Assistant spec event update it through the same path
- [ ] The app component is split into panes and a header, with no pane holding another pane's state
- [ ] Sending the Assistant a request visibly moves the builder controls while the report stays on screen
- [ ] Both side panes can be collapsed and restored
- [ ] The layout is usable on a narrow viewport rather than a crushed three-column grid
- [ ] The developer status line no longer appears in the interface
- [ ] Every existing behaviour still works: presets, URL round-trip, exports, the 401 return to sign-in, Warning banners
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes, including the Report Spec URL round-trip and the auth
tests.
**Level 2** — primary for this slice. With the development fakes, send the Assistant a request and
confirm the controls move while the report and the conversation are both visible.

## Blocked by

01
