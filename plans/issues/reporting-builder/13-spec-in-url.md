# 13 — Shareable links

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Make the report definition addressable so a view can be sent to a colleague.

The Report Spec is serialised into the URL and restored from it on load. Every field that affects
what is displayed must round-trip — metrics, dates, grouping, granularity, sort, column order,
layout, chart metric and the duration display toggle — so an opened link reproduces the report
exactly rather than approximately.

Restoration goes through the same validation as any other input, so a hand-edited or stale link
cannot push the app into a state a user could not reach through the controls. An invalid link
falls back to the default report with a Warning rather than failing.

## User stories covered

- **50.** As an analyst, I want the report definition captured in the URL, so that I can send a colleague the exact view I am looking at.
- **51.** As an analyst, I want an opened shared link to reproduce the report faithfully — metrics, dates, grouping, sort, column order and chart selection — so that we are certainly discussing the same thing.

## Acceptance criteria

- [ ] Changing any control updates the URL
- [ ] Opening a URL reproduces the report exactly, including chart metric and duration display
- [ ] A link with an invalid or stale definition falls back to the default report with a Warning
- [ ] Restored definitions pass the same validation as user input
- [ ] A test asserts a Report Spec survives a serialise/deserialise round-trip unchanged

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — a round-trip test is the core of this slice: every field that affects display survives serialise-then-deserialise unchanged. Also test that an invalid or stale link falls back to the default with a Warning rather than failing.
**Level 2** — copy the URL, open it in a fresh tab, confirm an identical report.

## Blocked by

07
