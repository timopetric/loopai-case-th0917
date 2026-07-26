# 14 — Chart

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

A line chart of one metric over time, sitting above the table.

**One metric, one axis** — never two scales. Counters and durations cannot share a y-axis, which
is why the chart metric is a single field on the Report Spec, defaulting to the first selected
metric and editable both from the chart and by the Assistant.

One series per group row, capped at the eight largest by total, with the remainder **dropped** and
the legend disclosing how many are not shown. An aggregated "Other" series is not acceptable: it
would be wrong for the non-additive metric and meaningless for durations.

**Colour follows the entity, not its rank** — assign a hue from a fixed ordered palette by a
stable hash of the entity identifier. Assigning by position would repaint every surviving series
whenever the date range changes the ranking, which reads as the chart changing subject. Never
generate a ninth hue.

A legend is always present so identity never depends on colour alone; hovering shows the exact
value and its series. The chart is hidden entirely when the report has been collapsed to a single
Bucket, since there is no time axis to plot against.

## User stories covered

- **54.** As a support operations lead, I want a line chart of one **Metric** over the period, so that I can see trend and shape rather than reading a grid of numbers.
- **55.** As an analyst, I want to choose which **Metric** the chart plots independently of the column order, so that the visual matches my question.
- **56.** As an analyst, I want the chart limited to the eight largest series with the remainder disclosed as a count, so that it stays readable rather than becoming a hairball of 108 lines.
- **57.** As an analyst, I want each **Actor** to keep the same colour when I change the date range, so that the chart does not appear to change subject when the ranking shifts.
- **58.** As an analyst, I want hovering a point to show the exact value and which series it belongs to, so that I can read specifics without leaving the chart.
- **59.** As an analyst, I want a legend naming every plotted series, so that identity never depends on colour alone.
- **60.** As an analyst, I want the chart to disappear when I collapse the report to a single **Bucket**, so that I am never shown a line with nothing to plot against.

## Acceptance criteria

- [ ] A line chart renders the selected chart metric over the Buckets
- [ ] The chart metric can be changed independently of column order
- [ ] At most eight series render, with the legend disclosing the number not shown
- [ ] A given entity keeps its colour when the date range changes
- [ ] Hovering a point shows the exact value and series name
- [ ] The chart is hidden when the report is collapsed to a single Bucket
- [ ] The chart derives from the same Report Table as the table, not a second data path

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the pure parts are testable and worth testing: top-eight selection by total, and that colour is assigned from the entity identifier rather than its rank (change the range so the ranking changes, assert the colour does not).
**Level 2** — primary for this slice. A chart's correctness is largely visual: legend, hover, hiding without a time axis, and readability with many series.

## Blocked by

07
