# 12 — Presets

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Three one-click report definitions, seeded as Report Spec values.

**Day by Actor** — the client's verbatim request, and what loads on first paint so the app answers
the original question before anything is touched. **Day by Mailbox** — the same breakdown across
inboxes. **Actor leaderboard** — the whole range collapsed to a single Bucket, grouped by Actor,
sorted descending.

Selecting a preset replaces the current Report Spec wholesale; the controls then show the preset's
values and remain editable, so a preset is a starting point rather than a mode.

Further preset ideas are recorded as deliberately deferred in the technical design; do not build
them here. Note in particular that any average-based ranking would first need a minimum-count
threshold, or it ranks noise.

## User stories covered

- **3.** As a support operations lead, I want the day × **Actor** report already populated when the app opens, so that I see the answer to my original request before touching a single control.
- **4.** As a support operations lead, I want one-click presets for day × **Actor**, day × **Mailbox**, and an **Actor** leaderboard, so that the three questions I ask most often take no configuration.

## Acceptance criteria

- [ ] Three presets are offered and each produces its described report
- [ ] The day-by-Actor preset is active on first paint with data already displayed
- [ ] Selecting a preset updates every affected control
- [ ] After selecting a preset, all controls remain individually editable

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — assert each preset's Report Spec validates and produces the described shape.
**Level 2** — primary: click each preset and confirm every affected control updates and remains editable.

## Blocked by

07
