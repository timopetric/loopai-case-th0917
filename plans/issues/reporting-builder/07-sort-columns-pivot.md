# 07 — Sort, column order and pivot layout

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Table presentation: three related controls sharing one engine pass.

**Sort** applies *within* each Bucket, never globally — days stay in chronological order and rows
are ordered inside each day. A global sort would destroy the time series the report exists to
show. When the report has been collapsed to a single Bucket there is only one Bucket, so sorting
is global by definition, which is what makes a leaderboard rank.

**Column order** is explicit and user-controllable, so the numbers being compared can sit side by
side.

**Pivot layout** puts Buckets across the top as columns for a compact scan of one metric over the
period. Because several metrics would multiply the column count and make the export unreadable,
pivot renders the chart metric only — and the UI says so, rather than silently dropping columns.

## User stories covered

- **9.** As an analyst, I want to sort by any column ascending or descending, so that I can find the top and bottom of a distribution immediately.
- **10.** As an analyst, I want sorting to reorder rows *within* each day while days stay in chronological order, so that sorting does not destroy the time series I am looking at.
- **12.** As an analyst, I want to reorder columns, so that the numbers I am comparing sit next to each other.
- **16.** As an analyst, I want a layout that puts days across the top as columns, so that I can scan one **Metric** across the period in a compact grid.
- **17.** As an analyst, I want to be told that the day-columns layout shows a single **Metric**, so that I understand why my other selected columns are not displayed.

## Acceptance criteria

- [ ] Sorting reorders rows within each day while days remain in chronological order
- [ ] Sorting a single-Bucket report ranks across the whole table
- [ ] Column order can be changed and the table and exports both respect it
- [ ] Pivot layout renders Buckets as columns
- [ ] Pivot layout renders a single metric and the UI states this
- [ ] Engine unit tests cover sort-within-Bucket and both layouts

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `engine` unit tests: sorting reorders within each day while day order is preserved; sorting a single-Bucket report ranks globally; explicit column order is honoured; pivot renders one metric.
**Level 2** — confirm visually, since layout regressions do not fail a test.

## Blocked by

06
