# 10 — CSV export

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Deliver the literal client ask: a downloadable spreadsheet of exactly what is on screen.

Export derives from the same Report Table the preview renders, so the file and the screen cannot
disagree. The route accepts a Report Spec and returns a file with an appropriate content type and
filename.

The CSV is **pure data**: it begins at the header row, with units baked into column names and a
totals row at the end. No preamble, no comment lines, no notes rows — anything above the header
breaks naive parsing, and the whole value of CSV is that it is boring. Context travels in the
Excel export instead.

## User stories covered

- **31.** As a support operations lead, I want to download the current report as CSV, so that the original request for a spreadsheet is satisfied.
- **33.** As an analyst, I want the CSV to begin at the header row with no preamble, so that it loads into a spreadsheet or a script without hand-editing.
- **34.** As an analyst, I want the exported file to match exactly what is on screen, so that I never reconcile two versions of the same report.
- **35.** As an analyst, I want units in the exported column headers, so that a colleague opening the file cannot misread the durations.

## Acceptance criteria

- [ ] A download button produces a CSV of the current report
- [ ] The file's contents match the on-screen table, including column order and sort
- [ ] Column headers name their units
- [ ] A totals row is present, honouring the non-additive metric rule
- [ ] The file parses with a standard CSV reader with no special handling
- [ ] An API-level test asserts the response content type and that the body parses

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `exporters` unit tests: the CSV parses with a standard reader with no special handling; units appear in headers; the totals row honours the non-additive rule; content matches the Report Table. API-level test for the response content type.

## Blocked by

05
