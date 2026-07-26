# 01 — Tailwind and the token layer, proven on the sign-in screen

Status: done

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

The styling foundation, plus the one screen that proves it works end to end.

Introduce Tailwind and a token layer adapted from the design reference: colour, type scale,
spacing, radii and motion. The tokens are the deliverable — every later slice consumes them and
none should reach for a raw hex value.

Adapt rather than copy. The reference describes a marketing site; the PRD's adaptation table is
binding. In particular the cream family is an **accent** surface for rails, cards and banners,
while the data surface stays white; the licensed display face is replaced by **Instrument Serif**
at display sizes only; and the hero, sunset band and photography are dropped entirely.

**Fonts are self-hosted and bundled** — Instrument Serif for display, Inter for body, JetBrains
Mono where a monospaced figure helps. A CDN link would add an external runtime dependency and
would fail differently in production than in development, which is the exact class of mistake the
no-build-time-configuration rule exists to prevent.

Then convert the **sign-in screen** completely. It is small and self-contained, and converting it
is what turns this from an unverifiable tooling change into a slice you can look at. It also
exercises the parts most likely to break in the built image: font loading, the Tailwind build, and
the token layer surviving the production bundle.

Record the design adaptation as **ADR-0004**, including the decision that brand colour is confined
to calls to action and active states and never enters the chart series palette, with the
alternatives considered.

## Acceptance criteria

- [ ] Tailwind builds in both the dev server and the packaged image
- [ ] A token layer defines colour, type scale, spacing, radii and motion, and later slices can consume it without raw hex values
- [ ] Instrument Serif, Inter and JetBrains Mono are bundled in the image, with no request to any external host at runtime
- [ ] The sign-in screen is fully converted and states in one line why a key is needed
- [ ] Signing in still works, and an unauthorised response still returns to sign-in with the report definition intact
- [ ] No `VITE_*` or any other build-time frontend configuration is introduced
- [ ] ADR-0004 records the adaptation, including brand colour being excluded from the chart series palette
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command passes; the guard test asserting no build-time frontend
configuration still holds.
**Level 2** — run the **built image** and load the sign-in screen: fonts render, no console
errors, and no network request leaves the origin.

## Blocked by

None - can start immediately
