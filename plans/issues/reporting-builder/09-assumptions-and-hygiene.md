# 09 — Assumptions modal and data hygiene

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Make the honesty visible. The brief grades transparency about assumptions, so this is a product
feature rather than documentation.

A persistent coverage banner opens a modal listing every assumption made about the data: that
durations are hours despite the documentation claiming seconds and how that was determined; that
Buckets are whole UTC days and no other granularity exists; that there is no Actor-by-Mailbox
cross-tab; that the actioned-emails metric cannot be summed across Actors; and that one metric is
always empty upstream and is therefore hidden. This is the same content the Excel export carries,
sourced once.

Two further hygiene touches: the final day in the window holds partial data and will drag any
trailing average down, so it is flagged rather than silently distorting trends. And the Actor list
mixes real people with role accounts such as "Support" and "Billing", which the UI notes so a
shared queue is not mistaken for an individual's performance.

## User stories covered

- **18.** As an analyst, I want **Metrics** that are always empty upstream to be absent from the picker entirely, so that I never build a report that is silently all zeros.
- **26.** As an analyst, I want to understand that the **Actor** list mixes real people with role accounts such as "Support" and "Billing", so that I do not mistake a shared queue for an individual's performance.
- **28.** As a support operations lead, I want one click to a list of every assumption made about this data, so that I can judge how far to trust the report.
- **29.** As a support operations lead, I want to be told clearly that per-**Actor**-per-**Mailbox** figures are unavailable, so that I stop looking for a way to produce them.
- **30.** As a reviewer, I want the units assumption to be justified rather than merely asserted, so that I can see it was inferred from evidence rather than guessed.

## Acceptance criteria

- [ ] The coverage banner opens a modal listing every stated assumption
- [ ] The modal explains the units finding rather than merely asserting it
- [ ] The modal states that an Actor-by-Mailbox cross-tab is unavailable
- [ ] The partial final day is flagged where it could mislead
- [ ] The UI indicates that the Actor list includes role accounts as well as people
- [ ] The modal content and the export's information sheet come from one source

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — assert the modal's content and the export's information sheet derive from one source, so they cannot drift apart.
**Level 2** — primary for this slice: open the modal and read it. Its value is whether a human finds it clear, which no test can judge.

## Blocked by

05, 08
