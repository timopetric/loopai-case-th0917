# 03 — Builder rail

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

The left zone, restyled into a scannable rail rather than a stack of default browser fieldsets.

Every control the builder already has stays and keeps its behaviour: date range bounded to the
**Coverage Window**, grouping, granularity, the **Metric** multi-select driven by the server
catalogue, the duration display toggle, sort and layout. This slice changes how they read and how
quickly a user can find them, not what they do.

Build the small set of primitives the reference's component specs describe and this app actually
needs — text and date inputs, a segmented control, selectable chips, and a section header — from
the token layer. Do not adopt a component library; there are only a handful of primitives here and
each is used in more than one pane.

Two things the current rail gets wrong and this slice must fix: the sections have no visual
hierarchy, so the eye cannot find a control without reading every label; and there is no
indication of how many **Metrics** are selected out of how many available, which matters when the
catalogue has fourteen and the picker is scrolled.

The rail collapses to a narrow strip that still shows the active configuration in summary, so
collapsing does not mean losing track of what the report is.

Keep the glossary vocabulary exactly: **Actor**, **Mailbox**, **Bucket**, **Coverage Window**. The
wire value `"agent"` behind the grouping control is correct and must not change.

## Acceptance criteria

- [ ] Every existing control is present and behaves as before
- [ ] Controls are grouped into labelled sections with a clear hierarchy
- [ ] The Metric picker shows how many of the catalogue are selected, and the always-empty metric is still absent
- [ ] The date inputs still cannot select outside the Coverage Window
- [ ] Selecting a preset still updates every affected control and leaves them individually editable
- [ ] The rail collapses to a summary of the active configuration and restores
- [ ] UI copy uses glossary terms, with no unqualified "agent" visible to a user
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes.
**Level 2** — primary for this slice. Drive every control and confirm the report changes as
expected, then collapse the rail and confirm the summary is accurate.

## Blocked by

02
