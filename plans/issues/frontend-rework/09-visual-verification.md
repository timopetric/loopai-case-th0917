# 09 — Browser-driven self-correction loop against the built image

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

Drive the reworked workspace in a real browser, look at it, and fix what is wrong — unattended.

This is the autonomy loop the technical design §12 describes at level two: run the **built image**
with the development fakes, drive it through Chrome DevTools MCP, screenshot the result, notice
your own mistakes, and correct them without human involvement. It costs no tokens and no upstream
calls, so iterate until the interface is actually good rather than merely complete.

**Prerequisite:** this slice needs Chrome DevTools MCP available. Confirm it is present before
starting. If it is unavailable, stop and say so rather than substituting curl checks and declaring
the interface verified — a screenshot is the entire point of this slice.

**Status of that prerequisite, 2026-07-26:** the owner configured the MCP server and reloaded
plugins partway through the implementation run. It did not become visible to the running session —
three probes (keyword search and a direct lookup by tool name) found nothing, because the tool
roster is fixed when a session starts. **It is expected to work in a fresh session; start one and
re-confirm before running this slice.** Two earlier sessions reported the tool missing outright,
so re-confirm rather than assume.

Run against the **built image, not the development server**. The rework adds a CSS build step and
bundled font files, which are exactly what works locally and fails in the image.

Walk the product end to end in **both themes**: sign in, land on the default report, click each
preset, change grouping and granularity, select and deselect **Metrics**, sort a column, reorder
columns, switch to the pivot layout, narrow the range, provoke a clamped range and a refused one,
open the assumptions modal, download both exports, and hold a conversation with the **Assistant**
that visibly moves the controls.

Read the console and network panels on every screen. A font that failed to load, a request leaving
the origin, a hydration warning or a 401 loop surface here and nowhere else.

Then judge what you see, and fix it. Specifically look for what tests cannot catch: cramped or
colliding layout at narrow and wide viewports, text that wraps badly, contrast that is
technically passing but hard to read, a table that is still visually noisy, controls that are hard
to find, and an **Assistant** panel that does not read as a conversation.

Confirm the decisions capable of regressing silently:

- the exported file still matches the virtualised table, at full row count
- a withheld value reads as withheld in the table and the workbook, and as an empty field in CSV
- duration headers still name their unit, and the count still appears on hover
- an **Actor** keeps its colour across a date change *and* a theme change
- no tool name, argument or enum value appears anywhere in the conversation
- the development-fake banners are visible whenever a fake is active, so a screenshot cannot later
  be mistaken for live evidence

Record what you changed and what you could not fix.

## Acceptance criteria

- [ ] Chrome DevTools MCP is confirmed available, or the slice stops and reports it
- [ ] The full walkthrough has been driven in a browser against the built image, in both themes
- [ ] Screenshots were taken and actually inspected at narrow, laptop and wide viewports
- [ ] The console and network panels are clean on every screen, with no request leaving the origin
- [ ] An export taken from a virtualised table contains every row and matches the screen
- [ ] Every silent-regression check above has been exercised rather than assumed
- [ ] Visual and interaction problems found were fixed, and anything left is written down
- [ ] `make check` still passes after the fixes

## How to verify

Ladder levels are defined in the technical design's verification section. This slice is level two,
run to exhaustion: the loop is cheap and repeatable, so the standard is "it looks right", not "it
rendered".

## Blocked by

07, 08
