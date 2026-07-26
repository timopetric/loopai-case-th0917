# 17 — Live model and Tool Step budget

Status: done

## Parent

[PRD — Reporting Builder (Case TH-0917)](PRD.md)

## What to build

Swap the scripted model for the real one and bound its work.

Wire the confirmed model through the OpenAI-compatible provider using configured credentials.
Prompt templates live as files and are given the current Report Spec, the metric catalogue
including the units caveat, and the Coverage Window.

**Bound the loop by Tool Steps**, where one Tool Step is one model call regardless of how many
tool calls it emits. At the penultimate step, tell the model it has one step left. At the final
step, send the request **with the tool definitions omitted entirely** — not merely with tool
choice disabled, which was verified to make this model emit fabricated tool-call JSON as prose
using a schema that does not exist. Instruct it to summarise in plain prose with no JSON.

The user-facing message names the real constraint plainly and makes the recovery obvious: the
Assistant has used its steps for this turn, here is where it got to, send another message to
continue.

**No code path may ever parse assistant prose as tool calls.** Under a denied-tools condition the
model produces convincing but fabricated tool-call text; acting on it would be an execution risk.

## User stories covered

- **47.** As an analyst, I want the **Assistant** to tell me when it has used its work allowance for a turn, summarise where it got to, and invite another message, so that I am never left with a spinner and no answer.

## Acceptance criteria

- [ ] A plain-English request produces a correct report using the live model
- [ ] The loop stops after the configured number of Tool Steps
- [ ] The final step is sent without tool definitions and returns prose, never JSON
- [ ] The out-of-budget message states what was achieved and invites another message
- [ ] No code path parses assistant prose as tool calls
- [ ] The thinking indicator brackets the model's reasoning phase in real conditions
- [ ] The step limit is configurable by environment variable without a rebuild

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — API-level tests with the fake model for the budget: the loop stops at the configured step count, and the final response is prose.
**Level 3** — **required for this slice.** It is the first to spend real tokens, and the omit-tools-entirely path was never exercised against the live model. Confirm the final answer is prose and not fabricated tool-call JSON.

## Blocked by

16
