# 15 — Assistant streaming skeleton

Status: ready-for-agent

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Build the conversation channel and its plumbing before any tool exists, driven by a scripted fake
model so the whole path is demoable without spending tokens.

A streaming endpoint accepts a message plus the current Report Spec and returns server-sent
events. It is a POST carrying state, and authentication uses the same header as every other
route, so the frontend streams via fetch rather than the native event-source API.

A **presenter** translates raw model and tool events into a small, stable, user-facing vocabulary:
a thinking state, a status line, chips describing what changed, the full validated Report Spec
after each change, streamed assistant prose, a completion event, and a sanitised error. The
presenter is a pure function and is **the chokepoint that keeps internals out of the browser** —
no tool name, argument, prompt fragment or raw model reasoning may pass through it.

The thinking event exists because the model reasons before acting: the majority of stream chunks
are reasoning deltas before the first actionable one, and without an indicator the interface
appears hung. It carries **state only, never reasoning text**. In a development environment only,
raw reasoning may additionally stream to a collapsible panel.

The chat UI renders the vocabulary: a thinking row with an elapsed counter, chips as tags, and
streamed prose. Each Report Spec event updates the same store the builder edits.

Add the development-only fake-model flag returning a scripted sequence, subject to the same
refuse-outside-development rule as the fake upstream (ADR-0003).

## User stories covered

- **38.** As a support operations lead, I want to watch the date slider, grouping and metric checkboxes change one at a time as the **Assistant** works, so that I can see what it did and correct it.
- **39.** As a support operations lead, I want a visible "thinking" indicator while the **Assistant** reasons, so that a multi-second pause does not look like a crash.
- **48.** As a security-conscious reviewer, I want no internal tool names, arguments, prompts or raw model reasoning to appear anywhere in the interface, so that implementation details are not exposed to end users.
- **49.** As a developer, I want the raw model reasoning visible in a collapsible panel when running locally, so that I can debug the **Assistant** without shipping that to production.

## Acceptance criteria

- [ ] The stream endpoint authenticates with the same header as other routes
- [ ] Events arrive as well-formed server-sent events in the expected order
- [ ] A thinking indicator appears promptly and clears when the first actionable event arrives
- [ ] Report Spec events update the builder controls
- [ ] The presenter emits no tool name, argument, prompt fragment or reasoning text
- [ ] Raw reasoning is available in a collapsible panel only in a development environment
- [ ] With the fake-model flag set, a scripted conversation drives the report end to end
- [ ] Presenter unit tests include a negative assertion that internals never leak

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — `presenter` unit tests including the **negative assertion** that no tool name, argument, prompt fragment or reasoning text can appear in any emitted event. API-level test driving the stream with the fake model and asserting event order.
**Level 2** — with the fake model, confirm the thinking indicator appears promptly and clears, and that chips and prose render.

## Blocked by

07
