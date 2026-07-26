# 07 — Dark mode

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

A dark theme across the whole workspace, following the operating system by default with an
explicit override the user can set.

**The design reference has no dark palette** — it lists this under its own known gaps — so the dark
ramp is derived here rather than looked up. Derive it deliberately: surfaces, text, hairlines and
the accent, each checked for contrast rather than eyeballed. The warm accent that reads as cream
on a light surface needs a genuinely different value on a dark one, not the same hue at lower
opacity.

**The chart is the part that cannot be done by inversion.** The technical design §7 is explicit
that dark mode is *"a selected set of steps validated against the dark surface, not an automatic
inversion"*, and that the palette validator should be run rather than the result eyeballed for
colour-vision safety. So the eight series hues need dark-surface counterparts chosen and
validated, with each entity keeping its slot across both themes — an **Actor** must not change
colour when the theme changes any more than when the date range changes.

Everything that carries meaning through colour needs checking in both themes: the **Warning**
banners, the development-fake banners, the withheld-value dash, the error states, the selected and
active states, and the focus ring.

## Acceptance criteria

- [ ] The workspace renders in both themes, following the system preference by default
- [ ] An explicit user override is available and persists for the session
- [ ] Text and interface contrast meets the accessibility floor in both themes
- [ ] The chart series palette has selected dark-surface values, validated rather than inverted
- [ ] An entity keeps its colour slot across a theme change
- [ ] Warnings, development banners, withheld values, errors and focus states are all legible in both themes
- [ ] No component renders unstyled or with a light-theme surface leaking into dark
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes; the chart's entity-stable colour tests still hold.
**Level 2** — primary. Walk the whole workspace in both themes, including a report with Warnings,
a refused range, an open assumptions modal and an active Assistant turn.

## Blocked by

03, 04, 05, 06
