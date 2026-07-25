# 19 — Deploy

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Publish the image and run it on the platform.

Build locally, tag with both a version and the moving latest tag so a redeploy is unambiguous
about what it pulled, and push to the public registry repository. Point the platform's service at
that image rather than building from source, so no registry credentials are needed.

Supply runtime configuration through the platform's environment: the shared key, the upstream
token, and the model credentials. The development-only fake flags must be absent — the service is
built to refuse to start if they are set outside a development environment, and that behaviour
should be confirmed rather than assumed.

Verify the deployed instance by signing in, loading the default report, exporting a file, and
sending the Assistant one request. This is the same walkthrough as the verification slice, run
against the deployed URL.

**Type: HITL.** Requires registry and platform credentials.

## User stories covered

- **66.** As a developer, I want the image published under a predictable name and tagged by version as well as latest, so that a redeploy is unambiguous about what it pulled.

## Acceptance criteria

- [ ] The image is built locally and pushed with both a version tag and the latest tag
- [ ] The platform deploys the pushed image rather than building from source
- [ ] Runtime configuration is supplied through platform environment variables, with no secrets in the image
- [ ] The deployed instance serves the application over its public URL
- [ ] Signing in, loading a report, exporting a file and using the Assistant all work against the deployed instance
- [ ] The deployed instance runs with the development fake flags unset

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 3** against the deployed URL: sign in, load the default report, export a file, send the Assistant one request. Also confirm the service refuses to start with a development fake flag set, rather than assuming it.

## Blocked by

18
