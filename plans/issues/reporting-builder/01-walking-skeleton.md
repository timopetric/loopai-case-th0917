# 01 — Walking skeleton

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Stand up the smallest thing that runs end to end: a Python service that serves a built
single-page frontend from its own origin, plus the tooling to run and package it.

Configuration is read from environment variables into a single settings object, with a
committed example file that stays the source of truth for every variable. Logging goes through
loguru to one stderr sink at a level taken from configuration, with the standard library and
the web server's own loggers intercepted so everything shares one format.

The frontend has **no build-time configuration of any kind** — no framework env variables — and
calls the API through relative paths only. This is what makes an image built on a developer
machine behave identically in production, and it must not be compromised later for convenience.

Package it as a multi-stage image: the current Node LTS builds the frontend, the Python runtime
image serves it. The image listens on the port supplied by the platform at runtime.

Provide the developer command surface: separate targets to run the backend and the frontend
each in its own terminal with live output, a combined convenience target, one target that runs
lint, typecheck and tests together as a single green signal, and targets to build and run the
packaged image.

## User stories covered

- **61.** As an operator, I want every setting read from environment variables, so that I can change the key, the model or the work allowance on the platform without a rebuild.
- **65.** As a developer, I want an image built on my machine to behave identically in production, so that a local build and push is safe.

## Acceptance criteria

- [ ] Running the backend target serves an HTML page that loads the frontend bundle
- [ ] Running the frontend target starts a dev server that proxies API calls to the backend
- [ ] The combined check target runs lint, typecheck and tests, and fails if any of them fail
- [ ] Building and running the image serves the same page from a single container on the platform-supplied port
- [ ] An unauthenticated health endpoint returns success
- [ ] No frontend build-time environment variables exist anywhere in the repo
- [ ] The committed example environment file lists every setting the service reads, with comments
- [ ] Logs are emitted through loguru in one consistent format, including the web server's own log lines

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the check command runs and passes (there is little to unit test yet; this slice is about wiring).
**Level 2** — the built image serves the page in a browser with no console errors.

No module tests yet.

## Blocked by

None - can start immediately
