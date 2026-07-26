# 06 — Assistant panel with rendered markdown

Status: done

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

Turn the conversation from a debug log into the panel the product is half graded on.

**Render the Assistant's prose as markdown.** Today it arrives as a bare text node, so a ranked
answer — the most common useful reply — shows literal asterisks and unformatted lines. Use a
renderer built for **streaming**: ordinary markdown parsers need a complete block before they
format correctly, which makes tokens visibly flicker between raw and formatted as they arrive.

Three things must be true of whatever renderer is chosen:

- **Raw HTML stays disabled.** Model output is untrusted; the renderer's hardening defaults are
  the reason this is safe, and loosening them to render something prettier would make it an
  injection vector. Allowlist link protocols too.
- **Re-parsing is bounded.** Re-rendering the whole message on every streamed token is quadratic.
  Parse completed messages once and throttle the in-flight one.
- **It changes presentation only.** The presenter still guarantees no tool name, argument, prompt
  fragment or reasoning text reaches the browser. This slice must not widen what is sent — only
  format what already arrives.

Then the panel itself: user and **Assistant** turns visually distinguished; **Repair** chips as
proper badges rather than inline text; the thinking row as a live indicator with its elapsed
counter, which exists because the model reasons for several seconds before its first action and
without it the interface reads as hung; the raw reasoning panel kept as a collapsed disclosure in
development only; and a composer that submits on enter, shows its busy state, and cannot be
double-submitted.

Errors arrive already sanitised from the presenter. Render them as messages in the conversation
rather than as a bare alert, so a refusal reads as the **Assistant** answering rather than the app
breaking.

## Acceptance criteria

- [ ] Assistant prose renders as markdown, including lists, emphasis and small tables
- [ ] Partial markdown does not visibly flicker between raw and formatted while streaming
- [ ] Raw HTML from model output is not rendered, and link protocols are allowlisted
- [ ] A long streamed reply does not degrade as it grows
- [ ] User and Assistant turns are visually distinct, and Repair chips render as badges
- [ ] The thinking indicator appears promptly, counts elapsed time, and clears on the first actionable event
- [ ] Raw reasoning remains available only in a development environment, collapsed by default
- [ ] The composer submits on enter, shows a busy state, and cannot be double-submitted
- [ ] No tool name, argument, prompt fragment or reasoning text appears anywhere in the panel
- [ ] `make check` passes, including the presenter's negative leak assertion

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the presenter tests still pass unchanged; this slice must not alter what is emitted.
**Level 2** — with the development fakes, hold a conversation and confirm markdown renders, chips
appear, and the thinking row behaves.
**Level 3** — one live turn, confirming a real reply formats correctly and the reasoning preamble
is bracketed by the indicator.

## Blocked by

02
