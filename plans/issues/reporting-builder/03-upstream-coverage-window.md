# 03 — Upstream client and Coverage Window

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Introduce the only module that talks to the upstream reporting API, and surface what it knows
to the user.

Fetch the **entire Coverage Window** on every cache miss and memoise that single normalised
dataset in-process for five minutes, slicing requested ranges locally afterwards. The cache key
is the Coverage Window itself, read from the upstream's undocumented health route and memoised
on the same interval, falling back to hardcoded dates only when that route is unreachable. This
means upstream data moving to new dates is picked up without redeploying. Background and
rationale: ADR-0001.

Normalise units here and nowhere else: duration metrics arrive as sums expressed in **hours**
with a count companion, despite the vendor documentation claiming seconds. Raw upstream shapes
must not escape this module — everything downstream sees normalised types.

Expose a metadata route returning the Coverage Window, the Actor and Mailbox lists, and the
metric catalogue. The frontend shows the Coverage Window permanently in the header.

Add the development-only fake-upstream flag: when set, serve the committed fixture instead of
calling out. It is honoured only in a development environment and the service refuses to start
if it is set anywhere else (ADR-0003). While active the UI shows a persistent banner.

## User stories covered

- **20.** As a support operations lead, I want the **Coverage Window** shown permanently in the header, so that I always know the numbers describe 10–23 July 2026 and nothing else.
- **62.** As an operator, I want the upstream dataset fetched once and reused for a few minutes, so that adjusting report settings does not re-fetch identical data.
- **63.** As an operator, I want the **Coverage Window** discovered from the upstream at runtime, so that if its data moves the app follows within minutes and needs no redeploy.
- **64.** As an operator, I want the app to fall back to known-good dates if the upstream health check is unreachable, so that a partial outage does not take the whole app down.

## Acceptance criteria

- [ ] A first request fetches from upstream; a second within five minutes does not
- [ ] The Coverage Window is read from the upstream health route and used as the cache key
- [ ] When the health route is unreachable, the hardcoded window is used and the service still works
- [ ] Duration values are normalised to hours before leaving the module
- [ ] The metadata route returns the Coverage Window, 108 Actors, 103 Mailboxes and the metric catalogue
- [ ] The frontend header shows the Coverage Window returned by the metadata route
- [ ] Setting the fake-upstream flag in a development environment serves the fixture and shows a banner
- [ ] Setting the fake-upstream flag outside development prevents the service from starting

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `upstream` unit tests: hours normalisation; Coverage Window parsed from the health route; the hardcoded fallback when that route is unreachable; and a second call within the window served without a second fetch. API-level test for the metadata route's shape.
**Level 3** — confirm the window shown matches what the live upstream reports today.

## Blocked by

02
