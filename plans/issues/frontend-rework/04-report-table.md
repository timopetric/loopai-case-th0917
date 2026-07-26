# 04 — Report Table: readable and virtualised

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

Make the table readable at the size it actually reaches. The default report — day × **Actor** over
the whole **Coverage Window** — is 1,512 rows and 6,048 cells, rendered in full, with no sticky
header and no numeric alignment. It is the first thing a user sees.

**Virtualise the rows.** Only the visible window goes into the document while the full row set
stays in the **Report Table**.

> **Do not paginate.** Both exporters derive from the same **Report Table**, and a user story
> requires the exported file to match exactly what is on screen. Showing page 1 of 38 while
> exporting all 1,512 rows would break that, silently. Virtualisation keeps the two identical by
> construction — every row is still there, just not all in the document at once.

Then the legibility work, in rough order of how much it helps:

- **Numerals align.** Tabular figures, numeric columns right-aligned. This is the single largest
  readability gain in the table: it is what makes 16,372 and 1,467 comparable at a glance.
- **The header sticks**, and so do the leading **Bucket** and entity columns, so a row read at the
  bottom of a long scroll is still identifiable.
- **The Bucket becomes a grouping, not a repeated cell.** `10 Jul` printed 108 consecutive times
  is noise; one header per **Bucket** with its rows beneath is the same information, quieter.
- **Density control**, comfortable and compact, so a user can trade whitespace for rows.
- **Row banding and hover**, to track horizontally across five or more columns.
- **Withheld values read as deliberate.** The dash for a zero-count **Duration Metric** average and
  for `actioned_emails` totalled across **Actors** should be visibly distinct from a real figure
  and from an empty cell — quieter, but never mistakable for a zero.
- **Warnings surface above the table** as a proper banner rather than loose paragraphs.

Sorting, column reordering and the pivot layout keep their current behaviour. Note that each of
those currently costs a round trip to rebuild the report; if the interaction feels sluggish at
this row count, an optimistic local reorder while the request is in flight is worth considering,
but correctness comes first.

## Acceptance criteria

- [ ] The default day-by-Actor report scrolls smoothly with only the visible rows in the document
- [ ] The table is virtualised and not paginated, and an export still matches what is on screen
- [ ] Numeric columns use tabular figures and are right-aligned
- [ ] The header and the leading columns stay visible while scrolling
- [ ] Buckets render as grouped sections rather than a repeated cell per row
- [ ] A density control switches between comfortable and compact
- [ ] A withheld value is visually distinct from both a real figure and an empty cell, and never reads as zero
- [ ] Warnings render as a banner above the table
- [ ] Sorting, column order and the pivot layout behave as before
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes, including the exporter tests that pin the file against the
Report Table.
**Level 2** — primary. Load the default report, scroll to the end, sort, switch density, and
confirm a downloaded CSV still contains every row.

## Blocked by

02
