# 05 — Duration Metrics and correct aggregation

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Add the metric family where a wrong answer looks entirely plausible on screen.

Duration Metrics are sums expressed in hours, each with a count companion. They aggregate across
days and across entities as **total over count** — a count-weighted mean. Averaging daily
averages produces a different, wrong number and must not appear anywhere.

Add a display toggle on the Report Spec choosing between the per-ticket average (the default,
answering "how fast") and the period total (answering "how much work").

Every duration column header states its unit, because the vendor documentation says seconds and
anyone reading the export will assume seconds unless told otherwise. The engine emits raw
numbers and the renderers format them, so the on-screen presentation can be human-friendly while
exported values stay numeric.

Hovering a cell reveals the count behind the average, so a figure resting on one ticket is
distinguishable from one resting on hundreds.

One metric is non-additive: the actioned-emails counter double-counts when summed across Actors
(and only across Actors). When a report is grouped by Actor, its totals cell shows a dash with an
accompanying Warning rather than a number or a blank.

## User stories covered

- **14.** As an analyst, I want to switch **Duration Metrics** between per-ticket average and period total, so that I can ask "how fast is Elena?" and "how much time did Elena spend?" without rebuilding the report.
- **15.** As an analyst, I want per-ticket averages computed as total-over-count rather than an average of daily averages, so that combining days or people gives the true figure.
- **19.** As a support operations lead, I want every duration column labelled with its unit, so that I never read hours as seconds — a mistake the upstream documentation actively invites.
- **23.** As an analyst, I want to see how many tickets sit behind an average when I hover a cell, so that I can tell a solid figure from one resting on a single ticket.
- **24.** As an analyst, I want `actioned_emails` to show a dash rather than a total when grouped by **Actor**, so that I am not handed a number that overstates reality by half.

## Acceptance criteria

- [ ] A duration aggregated over several days equals total-over-count, verified against hand-computed values
- [ ] Switching the display toggle changes between per-ticket average and period total
- [ ] Every duration column header names its unit
- [ ] Hovering a duration cell reveals the underlying count
- [ ] Grouped by Actor, the actioned-emails totals cell shows a dash and raises a Warning
- [ ] Grouped by Mailbox, the same metric totals normally
- [ ] Engine unit tests cover weighted aggregation and the non-additive case

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `engine` unit tests are the priority for this slice, since a wrong average looks entirely plausible on screen. Cover: a duration aggregated over several days equals total-over-count, checked against hand-computed values; averaging daily averages gives a *different* number (assert we do not produce it); the display toggle; and the non-additive metric's dash when grouped by Actor.
**Level 2** — the count tooltip appears on hover.

## Blocked by

04
