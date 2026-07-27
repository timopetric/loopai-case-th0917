# Stream raw model reasoning to all users, not just development

`architecture.md` §6 and the `RawEvent`/`PresenterEvent` split in `app/agent/events.py` treat
raw chain-of-thought as internal-only by construction: `ThinkingTextEvent` (the reasoning-text
wire event) was gated on `settings.is_development`, and the module docstring calls that gate
"the security boundary named in AGENTS.md" — no dataclass in `PresenterEvent` was supposed to be
capable of holding tool names, arguments, or reasoning prose, in production, ever.

The owner asked for the opposite: the "Thinking…" indicator should default to visible and
expanded on every send, render the model's actual reasoning as markdown, and stay available in
production — not just behind `DEV_FAKE_LLM`/`is_development`. This is a deliberate reversal of
that boundary, not a bug fix, so it gets an ADR rather than a silent edit.

## Decision

Drop the `settings.is_development` gate on `include_reasoning_text`. `app/api/v1/routers/agent.py`
passes `include_reasoning_text=True` unconditionally; `ThinkingTextEvent` streams to every user,
in every environment. The frontend renders it as markdown in a collapsible panel, open by default
while a turn is in flight.

## Considered Options

- **Keep the gate, fix only the flash bug** (the "Thinking…" row toggling too fast to read).
  Preserves the original security boundary exactly. Rejected: does not satisfy the owner's actual
  ask, which is to *see the reasoning*, not just a longer-lived status row.
- **Show reasoning to all users, but sanitize/rewrite it first** (strip tool names and enum
  values before forwarding). Rejected for now: reliably scrubbing free-form chain-of-thought is
  itself an open problem (regexing out `set_metrics`-shaped tokens is brittle; a second LLM pass
  to rewrite it adds cost and latency to every Tool Step, and can still miss a paraphrase). Revisit
  if the unfiltered leak proves worse in practice than expected.
- **Stream raw reasoning to all users, unfiltered (chosen).** Cheapest to build, matches what was
  asked for, accepted with eyes open on the residual risk below.

## Consequences

- **Tool names and enum values will appear in the chat.** `set_metrics`, `get_meta`,
  `"agent"`/`"mailbox"` wire values, and similar internals routinely show up in a reasoning model's
  chain-of-thought (measured: 87 of 103 stream chunks were reasoning deltas in the one live smoke
  test run). This directly contradicts the standing "never show tool names or enum values in the
  conversation" rule for the *reply* — that rule still holds for `token`/`chips`/prose; it no
  longer holds for the reasoning panel, which is now an explicitly separate, explicitly-labeled
  surface ("Thinking" vs. the Assistant's actual answer).
- **Guard 1's risk moves, not disappears.** architecture.md §5 documents that under
  `tool_choice="none"` the model can emit a fenced JSON blob impersonating a tool call in its own
  text. That guard's rule — never parse assistant prose as tool calls — already covered this for
  final content; it now also covers reasoning text, which is displayed but must never be executed
  or treated as structured data by any code path. Nothing about that execution-safety rule changes;
  what changes is that a user can now *see* a fabricated-tool-call-shaped blob if the model ever
  emits one mid-reasoning, same as they always could in a final answer under that failure mode.
- **This is a one-way door in practice.** Once users can see and rely on the reasoning trace,
  removing it again is a visible regression, not a quiet revert — unlike the dev-only flag it
  replaces, which could be flipped without anyone but a developer noticing.
- `app/agent/events.py`'s docstring and `architecture.md` §6 need their "must be gated on the
  environment flag, never shipped to production" language corrected to match this decision —
  otherwise the next reader is flatly misled by comments that no longer describe what the code
  does.
- No change to what `token`/`chips`/`spec`/`error` events may ever contain — the rest of the
  presenter's leak containment (tool names never interpolated into status/error text, `detail`
  never forwarded, etc.) is unaffected and still enforced exactly as before.
