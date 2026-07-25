# 11 — Excel export with Report info sheet

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

The same report as a workbook, plus the context a forwarded file otherwise loses.

The first sheet holds the data, matching the CSV. A second sheet, "Report info", carries the
report definition in readable form, the Coverage Window, the units note, and any Warnings raised
when the report was built.

This is where the investigation becomes visible in the deliverable: someone opening the workbook
finds a plain statement that durations are hours despite the vendor documentation claiming
seconds. Excel supports multiple sheets natively, so nothing is being abused — the format people
open by hand carries the caveats, while the machine-readable format stays clean.

## User stories covered

- **32.** As a support operations lead, I want to download the current report as Excel, so that colleagues can open it directly.
- **36.** As a reviewer, I want the Excel file to carry a second sheet describing the report, its date range and its caveats, so that context survives being forwarded.

## Acceptance criteria

- [ ] A download button produces a workbook of the current report
- [ ] The first sheet matches the CSV output
- [ ] A second sheet lists the report definition, Coverage Window, units note and Warnings
- [ ] Durations are written as numbers so spreadsheet formulas work, with units in the header
- [ ] An API-level test asserts the response content type and that both sheets exist

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `exporters` unit tests: both sheets exist; the first matches the CSV; the information sheet carries definition, Coverage Window, units note and Warnings; durations are written as numbers. API-level test for the content type.
**Level 2** — open the file and confirm it looks right.

## Blocked by

10
