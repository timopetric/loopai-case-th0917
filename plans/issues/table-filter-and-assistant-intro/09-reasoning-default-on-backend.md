Status: done

# 09 — ADR-0005 backend wiring: stream raw reasoning to all users

## Parent

[`PRD.md`](PRD.md)

## What to build

Implement the policy ADR-0005 already documents (and slice 01 already corrected the surrounding
docs for): make the Assistant's raw reasoning stream to every user, in every environment, not
just development.

- `app/api/v1/routers/agent.py`: change `include_reasoning_text=settings.is_development` to an
  unconditional `True`. The `settings.is_development` gate is removed entirely from this call
  site.
- `app/agent/fake_model.py`: reword the scripted `ReasoningDelta` strings to remove unqualified
  "agent" and any other internal-sounding phrasing (e.g. "The user wants a per-agent breakdown" →
  "The user wants a per-Actor breakdown"). This fixture's text is no longer an internal-only test
  artifact once reasoning is shown to every user by default — it's the exact content every
  dev/demo walkthrough will show first.
- `tests/test_api.py` (or wherever the existing SSE no-leak assertion lives): the existing
  blanket "no tool name, argument, or prompt fragment appears anywhere in the stream" assertion
  must be narrowed. Per ADR-0005, tool names/enum values may now legitimately appear inside
  `thinking_text` events specifically — the assertion needs to check `token`/`chips`/`status`/
  `error`/`spec` events only, not the stream as a whole. Add a **new**, explicit test asserting
  `thinking_text` events **are** present in the stream even when `settings.is_development` is
  `False` — this is what actually proves the gate is gone, rather than merely not failing by
  coincidence.

## Acceptance criteria

- [ ] A stream produced with `is_development == False` still contains `thinking_text` events with
      real reasoning content
- [ ] The no-leak test suite still passes, correctly scoped to exclude `thinking_text` from the
      "never contains internals" assertion while still enforcing it for every other event type
- [ ] `fake_model.py`'s reasoning strings contain no unqualified "agent"
- [ ] `make check` passes

## Blocked by

None - can start immediately (independent of the filter work)
