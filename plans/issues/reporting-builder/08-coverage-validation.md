# 08 — Coverage validation and Warnings

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Defend against the upstream's most dangerous behaviour: a date range that falls outside its data
does not return nothing — it silently returns the *whole* window. Asked for June, it answers with
July and says nothing.

Because the Coverage Window is now known locally, this is preventable. Validate every requested
range before any upstream call, and treat two cases differently:

- **Partial overlap** (the user asked for 5–12 July, data starts on the 10th): clamp to the
  overlap and attach a Warning saying so. The intent is obvious, so doing the right thing and
  reporting it is correct.
- **Zero overlap** (the user asked for June): refuse. Return the real Coverage Window so the
  caller can offer an alternative. Never substitute.

An out-of-range request must never reach the upstream.

Surface Warnings as banners beneath the table. Warnings are the general channel for anything the
reader must know to interpret the numbers — a clamped range, an automatic Repair, a non-additive
metric — and they must also reach the exports.

## User stories covered

- **21.** As an analyst, I want a date range that only partly overlaps the **Coverage Window** to be clamped with an explicit **Warning**, so that I understand why the result is narrower than I asked.
- **22.** As an analyst, I want a date range with no data at all — June 2026, say — to be refused outright, so that I am never shown July's numbers as though they answered my question.
- **25.** As an analyst, I want to know the final day in the window is partial, so that I do not read a genuine drop into what is really incomplete data.
- **27.** As an analyst, I want any automatic **Repair** to my report stated plainly, so that I understand why my sort disappeared when I removed a **Metric**.

## Acceptance criteria

- [ ] A partially overlapping range is clamped and produces a Warning naming the applied range
- [ ] A range with no overlap is refused, and the response carries the real Coverage Window
- [ ] No request with an out-of-range date reaches the upstream
- [ ] Warnings render as banners beneath the table
- [ ] An API-level test covers both the clamped and the refused case

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `spec`/`engine` unit tests for both cases: partial overlap clamps and raises a Warning; zero overlap raises an error carrying the real window. API-level tests for both, plus an assertion that no out-of-range request reaches the upstream.
**Level 2** — the refusal is legible in the UI rather than a silent empty table.

## Blocked by

03, 06
