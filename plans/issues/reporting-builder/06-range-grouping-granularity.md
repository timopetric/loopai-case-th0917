# 06 — Date range, grouping and granularity controls

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Make the report configurable along its three primary axes.

A date-range control bounded to the Coverage Window, so a range with no data cannot be selected
by mouse at all. A grouping control offering Actor, Mailbox, or no grouping. A granularity
control offering per-day Buckets or collapsing the whole range into one Bucket.

Collapsing to a single Bucket is what makes ranking possible, so the engine must handle it as a
first-class case rather than a special one: Counters sum over the range and Duration Metrics use
the same weighted rule over the whole range.

A metric multi-select lets the user choose which columns appear, from the catalogue supplied by
the metadata route. Metrics that are always empty upstream are absent from the catalogue
entirely, so a user cannot build a report that is silently all zeros.

## User stories covered

- **2.** As a support operations lead, I want the same breakdown per **Mailbox** instead of per **Actor**, so that I can see which of our 103 inboxes carry the load.
- **6.** As an analyst, I want to pick a date range with a slider bounded to 2026-07-10 – 2026-07-23, so that I can narrow to a period of interest and cannot accidentally leave the data.
- **7.** As an analyst, I want to group by **Actor**, by **Mailbox**, or not at all, so that I can move between individual, team and whole-operation views.
- **8.** As an analyst, I want to collapse all fourteen days into one **Bucket**, so that I can rank people or inboxes over the whole period instead of day by day.
- **11.** As an analyst, I want sorting to apply across the whole table when I have collapsed to a single **Bucket**, so that a leaderboard actually ranks.

## Acceptance criteria

- [ ] The date picker cannot select dates outside the Coverage Window
- [ ] Changing the date range re-renders the table for that range only
- [ ] Grouping can be switched between Actor, Mailbox and none, and the table changes accordingly
- [ ] Collapsing to a single Bucket produces one row per entity with correctly aggregated values
- [ ] Selecting and deselecting metrics adds and removes columns
- [ ] The always-empty metric is not offered in the picker
- [ ] Engine unit tests cover the single-Bucket collapse for both metric families

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `engine` unit tests for the single-Bucket collapse across both metric families.
**Level 2** — each control changes the table as expected, and the date picker refuses to move outside the Coverage Window.

## Blocked by

04
