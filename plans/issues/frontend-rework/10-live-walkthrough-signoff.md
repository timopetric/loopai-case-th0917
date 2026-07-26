# 10 — Live walkthrough and design sign-off

Status: ready-for-human

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

The two things the unattended loop in slice 09 cannot do: spend real tokens, and hold an opinion.

**Run the walkthrough once against live services** — live upstream, live model, no development
fakes. This is the only level that proves the **Coverage Window** and the units are right against
today's data, and that a real conversation with the **Assistant** renders as intended rather than
just the scripted one. Confirm the fake banners are absent, and confirm the service still refuses
to start with a development fake flag set rather than assuming it.

**Then judge the result.** Slice 09 can fix a collision or a contrast failure, but it cannot decide
whether the workspace feels like a considered product, whether the adapted palette actually reads
as intentional rather than as a marketing theme bolted onto a data tool, or whether the density is
right for someone who will use this daily. That is the call this slice exists to make.

Pay particular attention to the adaptation the PRD committed to and nobody has yet seen in
practice: cream as an accent with the data surface on white, brand colour confined to actions,
and the chart palette held apart from the brand. If that split does not work visually, this is the
point to say so and revise it — including reopening ADR-0004 if the decision itself was wrong.

Update the checklist in the technical design §12 so it describes the reworked interface, and
record the outcome rather than assuming it.

**Type: HITL.** It spends tokens, and the remaining questions are matters of taste and judgement
rather than correctness.

## Acceptance criteria

- [ ] The walkthrough has been run once against live upstream and live model, and the outcome recorded
- [ ] The development-fake banners are absent, and the refuse-to-start behaviour was confirmed rather than assumed
- [ ] A live Assistant conversation renders correctly, including markdown and the thinking indicator
- [ ] The adapted palette has been judged in practice, and ADR-0004 either stands or is revised
- [ ] The technical design's checklist describes the reworked interface
- [ ] Remaining issues are fixed or recorded as known limitations

## How to verify

Ladder levels are defined in the technical design's verification section. This is level three, run
last and run once, reading the output rather than assuming it.

Issue 18 of the reporting builder still runs afterwards, covering the whole application and the
README.

## Blocked by

09
