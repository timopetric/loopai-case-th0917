# Dev-only fakes for the verification loop

`architecture.md` §0 states "no mock mode" — the app always calls the real upstream. That
remains true for anything shipped. But the browser-driven verification loop (§12) is run
repeatedly by a coding agent while iterating on layout, wiring and copy, and forcing every
iteration through the live upstream and a paid LLM makes that loop slow, costly, and dependent
on a free-tier service staying awake.

We therefore allow two **development-only** flags, `DEV_FAKE_UPSTREAM` and `DEV_FAKE_LLM`, which
serve the committed fixture and a scripted tool-call sequence respectively. They are honoured
**only** when `ENVIRONMENT` is a development value; in any other environment the app refuses to
start if they are set, rather than silently ignoring them. When either is active the UI shows a
persistent banner naming which fake is on.

This preserves the intent of the original decision — no silent mock can ever serve a user, and
no shipped configuration can be confused for real data — while giving the agent a fast, free,
deterministic loop for everything that is not actually about live data.

## Considered Options

- **Live-only verification.** Honours the original rule literally. Rejected: every UI iteration
  costs OpenRouter tokens and depends on upstream uptime, which is the main thing slowing an
  agent's self-correction loop.
- **A general mock mode with a boundary ABC and swappable implementations** (the PLAYBOOK
  pattern). Rejected as disproportionate: two env flags and a dependency override achieve the
  same thing for this project's size, and D2 already rejected the boundary machinery.

## Consequences

- The fakes are a **development affordance, not an architecture**. Test code continues to use
  dependency override directly and does not read these flags.
- Fail-closed, not fail-open: setting a fake flag outside development is a startup error. A
  fake that silently activates in production would be far worse than no fake at all.
- The visible banner is load-bearing. Screenshots taken by an agent during verification must be
  self-evidently fixture-backed, or they will eventually be mistaken for evidence that live data
  works.
- Live verification is still **required before declaring work done** — see the §12 ladder. The
  fakes make iteration cheap; they do not replace the real check.
