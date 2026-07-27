Status: done

# 01 — ADR-0005 housekeeping: doc corrections

## Parent

[`PRD.md`](PRD.md)

## What to build

`plans/decisions/adr/0005-stream-raw-reasoning-to-all-users.md` already exists (written during
the grilling session) and documents reversing the "reasoning text is dev-only" policy. Two other
documents still describe the old policy and will mislead the next reader if left as-is:

- `plans/CLAUDE.md`'s ADR summary table lists only ADRs 0001-0004 — add a row for 0005.
- `plans/decisions/architecture.md` §6 states reasoning text "must be gated on the environment
  flag, never shipped to production" — correct this to describe the new default-on behavior,
  pointing at ADR-0005 for the rationale and accepted tradeoff.
- `app/agent/events.py`'s module docstring and `ThinkingTextEvent`'s docstring describe the same
  now-reversed gate — correct both to match.

This is pure documentation — no code behavior changes in this slice (the actual gate removal is
slice 09). Keeping the docs and the ADR in sync now means slice 09 isn't the first place anyone
notices the docs disagree with reality.

## Acceptance criteria

- [ ] `plans/CLAUDE.md`'s ADR table includes ADR-0005 with a one-line summary matching its actual decision
- [ ] `architecture.md` §6 no longer states reasoning text is dev-only-gated; it describes the
      default-on behavior and cites ADR-0005
- [ ] `app/agent/events.py`'s docstrings (module-level and `ThinkingTextEvent`) match the new policy
- [ ] `make check` still passes (docs-only change, but confirms nothing else broke)

## Blocked by

None - can start immediately
