# 02 — Auth gate end to end

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Put the whole API behind a single shared key, and give the frontend a way to supply it.

The key is compared against configuration and the check is applied once at the API router level
rather than per route, so a new route cannot accidentally ship unprotected. The health endpoint
stays public.

The frontend shows a sign-in screen when it has no key, stores the key for the session, and
attaches it to every request. If any API call returns unauthorised, the app clears the stored
key and returns to sign-in while preserving the current report definition in the URL, so the
user lands back on the same report after signing in again. There is no token refresh — the key
is a non-expiring shared secret, so an unauthorised response mid-session means the server
restarted with a different key.

The sign-in screen states in one line why a key is needed: the backend runs the Assistant and
spends tokens, so it cannot be left open.

## User stories covered

- **52.** As an operator, I want the application behind a shared key entered at a sign-in screen, so that the **Assistant**'s token spend is not open to the internet.
- **53.** As a user whose key stops working mid-session, I want to be returned to sign-in with my report preserved, so that I can resume without rebuilding it.

## Acceptance criteria

- [ ] A request to any API route without a key is rejected as unauthorised
- [ ] A request with the wrong key is rejected as unauthorised
- [ ] A request with the correct key succeeds
- [ ] The health endpoint remains reachable without a key
- [ ] Entering a valid key on the sign-in screen grants access for the session
- [ ] An unauthorised response mid-session returns the user to sign-in without losing the report definition
- [ ] An API-level test asserts the auth dependency is actually attached to the router

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — API-level tests: a request with no key is rejected, a wrong key is rejected, the correct key succeeds, and the health route stays public. The no-key case is the one that catches an auth dependency that was never attached.
**Level 2** — sign in, then confirm an unauthorised response returns to sign-in with the report definition intact.

## Blocked by

01
