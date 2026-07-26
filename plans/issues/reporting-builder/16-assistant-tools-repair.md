# 16 — Assistant tools and Repair

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Give the Assistant its hands: nine tools that edit the Report Spec, and the rules that keep the
spec coherent while it does.

Seven write tools, each scoped to a **cohesive unit** rather than a raw field — the date range is
set as a pair, never as separate bounds, because setting one bound first would leave the range
momentarily inverted and manufacture an error out of a perfectly valid intent. Two read tools let
the Assistant fetch metadata and run the current report, so it can answer questions about results
rather than guessing.

Each write applies immediately and emits its own Report Spec event, so the builder controls
visibly move one step at a time. This progressive rendering is the reason for field-scoped tools
over a single atomic patch (ADR-0002).

**Repair, don't reject.** When one call invalidates an earlier field — dropping the metric a sort
or the chart pointed at, or charting a metric not currently selected — the backend repairs the
spec and reports what it adjusted in the tool result, so the Assistant can mention it in prose.
The adjustments also become Warnings. Genuine input errors (unknown metric, malformed date, empty
metric list, a range outside coverage) still return an error for one retry. The full taxonomy is
in the technical design and doubles as the test checklist.

**Batch reconciliation.** The model emits several tool calls in one message — verified live, three
at a time. Within a batch, discard any adjustment to a field that a later call in the same batch
explicitly sets; otherwise the Assistant narrates a Repair that did not survive the turn.

## User stories covered

- **37.** As a support operations lead, I want to type "resolved and handle time by agent for last week" and get that report, so that I need not learn the controls.
- **40.** As an analyst, I want to ask "who was slowest?" and get a prose answer, so that I need not read every row myself.
- **41.** As an analyst, I want the **Assistant** to base every number it states on the report it actually built, so that it cannot quote a figure it invented.
- **42.** As an analyst, I want the **Assistant** to refuse an impossible request with a reason and an alternative, so that I learn what the data supports instead of receiving fiction.
- **43.** As an analyst, I want the **Assistant** to tell me when my dates fall outside the **Coverage Window** and offer the range it does have, so that I can adjust in one step.
- **44.** As an analyst, I want the **Assistant** to never invent a **Metric** name, so that every column it produces is real.
- **45.** As an analyst, I want to refine over several messages — "now just the weekdays", "sort by handle time" — so that I can converge on what I meant.
- **46.** As an analyst, I want the **Assistant** to describe only the changes that survived my request, so that it does not tell me a sort was cleared when it then set a new one.

## Acceptance criteria

- [ ] Each of the nine tools is exposed with a strict schema and applies to the Report Spec
- [ ] Setting a date range is a single call and can never leave the range inverted
- [ ] Each write emits a Report Spec event, and the controls move incrementally rather than all at once
- [ ] Dropping a metric that the sort or chart referenced repairs the spec and reports the adjustment
- [ ] Charting an unselected metric adds it and reports the adjustment
- [ ] A range outside coverage errors rather than repairing
- [ ] In a multi-call batch, an adjustment superseded by a later call is not reported
- [ ] Unit tests cover every row of the repair taxonomy and the multi-call batch case

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the heaviest test slice. Walk the repair taxonomy row by row as individual cases, and cover the multi-call batch where a later call supersedes an earlier Repair (assert the superseded adjustment is **not** reported). `apply_batch` is pure, so none of this needs a model.
**Level 2** — with the fake model, confirm controls move incrementally rather than snapping into place.

## Blocked by

15
