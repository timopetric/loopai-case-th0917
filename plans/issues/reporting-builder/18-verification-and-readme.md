# 18 — Verification pass and README

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Run the full verification ladder against the assembled application, fix what it finds, and write
the document the work is graded on.

Climb all three levels of the ladder in the technical design. Level one is the offline command
covering lint, typecheck, unit and API-level tests. Level two drives the **built image** in a real
browser through Chrome DevTools MCP against development fakes — free and deterministic, for
layout, interaction, wiring and copy, reading the console and network panels for errors that never
surface elsewhere. Level three repeats the walkthrough against the live upstream and live model,
which is the only level that proves the units and the Coverage Window are right against today's
data.

Work through the checklist in the technical design; every row maps to a decision capable of
regressing silently. Run levels two and three against the built image, never only the dev server —
a build-time configuration mistake cannot appear any other way.

Then write the README: how to run it, what was assumed, what was deliberately cut and why, and
what would come next. The assumptions section is the highest-value part — the units finding, the
impossibility of an Actor-by-Mailbox cross-tab, the fixed data window, and the inert upstream
parameters — because the brief grades inference under incomplete information and transparency
about shortcuts, not polish.

**Type: HITL.** The README is the graded artifact and warrants human review before submission.

## User stories covered

- **55.** As an analyst, I want to choose which **Metric** the chart plots independently of the column order, so that the visual matches my question.
- **66.** As a developer, I want the image published under a predictable name and tagged by version as well as latest, so that a redeploy is unambiguous about what it pulled.
- **67.** As a developer, I want the arithmetic, repair rules, event mapping and exports covered by tests that need neither network nor an LLM, so that I can refactor confidently and run them anywhere.
- **68.** As a developer, I want a browser-driven checklist over the assembled application, so that build-time and integration mistakes surface before a reviewer meets them.
- **69.** As a developer, I want the checklist run against the built image rather than the dev server, so that a build-time configuration mistake cannot slip through.
- **70.** As a reviewer, I want a README stating what was assumed, what was cut and why, so that I can assess judgement rather than only output.

## Acceptance criteria

- [ ] The offline check command passes cleanly
- [ ] Every row of the verification checklist has been exercised against the built image
- [ ] The walkthrough has been run once against live upstream and live model, and the outcome recorded
- [ ] Issues found during verification are fixed or explicitly recorded as known limitations
- [ ] The README covers setup, assumptions, decisions, deliberate cuts and next steps
- [ ] The README states the units finding and how it was determined
- [ ] The README states that an Actor-by-Mailbox cross-tab is not derivable from the source

## How to verify

Ladder levels are defined in the technical design's verification section.

All three levels — this slice *is* the verification pass. Level 1 must be green; level 2 walks the full checklist against the built image; level 3 runs the same walkthrough against live services once, with the outcome recorded rather than assumed.

## Blocked by

17
