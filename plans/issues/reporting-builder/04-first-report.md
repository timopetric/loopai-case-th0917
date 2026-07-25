# 04 — First report: Counters, day by Actor

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

The tracer bullet's payload: a real table of real numbers, through every layer.

Introduce the Report Spec as a validated model — at this stage metrics, a date range and a
grouping are enough — and make it the single object the UI edits, the API accepts and the engine
executes. Crucially, grouping is a **single** value: grouping by Actor and by Mailbox at the
same time must be unrepresentable, because the upstream provides two independent breakdowns and
no cross-tab. This constraint is the reason the model exists.

Add the engine as a pure function from a Report Spec plus a dataset to a Report Table. For this
slice it need only handle Counters, which simply sum. The Report Table carries raw numeric
values plus per-column metadata — never pre-formatted strings — so that later consumers (chart,
exporters) derive from the same object rather than re-deriving numbers.

Add the report route and render the result as a plain table grouped by day and Actor.

## User stories covered

- **1.** As a support operations lead, I want a table showing, for each day and each **Actor**, their replies, resolved count and handle time, so that I get the breakdown I originally asked for without anyone assembling it by hand.
- **3.** As a support operations lead, I want the day × **Actor** report already populated when the app opens, so that I see the answer to my original request before touching a single control.
- **5.** As an analyst, I want to tick and untick individual **Metrics**, so that the table shows the three columns I care about rather than all fifteen.
- **7.** As an analyst, I want to group by **Actor**, by **Mailbox**, or not at all, so that I can move between individual, team and whole-operation views.
- **13.** As an analyst, I want a totals row beneath the table, so that I can sanity-check magnitudes at a glance.

## Acceptance criteria

- [ ] Requesting a report returns a Report Table whose rows match the fixture's real values
- [ ] A Report Spec that groups by both Actor and Mailbox cannot be constructed
- [ ] Counters sum correctly across days and across entities
- [ ] Grouping by Actor and grouping by Mailbox each reconcile to the same overall totals
- [ ] The frontend renders a table of days by Actors with a Counter column
- [ ] A totals row is present beneath the table
- [ ] The Report Table exposes raw numbers and column metadata, not formatted strings
- [ ] Engine unit tests cover Counter aggregation without network access

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `engine` unit tests: Counters sum across days and entities; grouping by Actor and by Mailbox each reconcile to the same totals. A `spec` test asserting a dual-grouping Report Spec cannot be constructed. API-level test that the report route returns a table.
**Level 2** — the table renders with real values.

## Blocked by

03
