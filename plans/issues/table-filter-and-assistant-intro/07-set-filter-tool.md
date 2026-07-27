Status: done

# 07 — The `set_filter` Assistant tool

## Parent

[`PRD.md`](PRD.md)

## What to build

A tenth Assistant tool, `set_filter(query: str)`, following the exact same shape as the existing
nine tools in `app/agent/tools.py`:

- **Schema**: `query: str`, required, no `Optional` wrapper. An empty string clears the filter,
  using the identical `.strip() or None` normalization already built into `ReportSpec.
  entity_filter`'s validator (slice 02) — no second, tool-only representation of "clear."
- **No name-resolution logic inside the tool.** The engine's substring match (slice 02) already
  tolerates loose input identically whether it comes from the rail or the Assistant. If the model
  wants precision, it can call the existing `get_meta` tool first (already returns every Actor/
  Mailbox id+name pair) — this is a prompting concern, handled in slice 08, not a schema one here.
- **Repair path**: calling `set_filter` while `group_by == "none"` goes through the same
  `ENTITY_FILTER_IGNORED` Repair built in slice 02 — the tool applies it, reports the adjustment,
  does not error.
- **`_run_report`'s result dict gains an always-present, nullable `"entity_filter"` field** —
  self-describing the active filter on every `run_report` call, rather than relying on the
  model's short-term memory of having just called `set_filter` earlier in the same turn. Mirrors
  `get_meta`'s existing "always return full context" pattern.
- `TOOL_NAMES`, `_ARGS_MODEL`, `_DISPATCH`, and `build_tool_definitions`'s generation all need the
  new tool registered exactly like the existing nine.

Tool-schema `description` wording is intentionally deferred to slice 08 (which rewrites all ten
descriptions together for consistency) — this slice can use a minimal placeholder description if
needed to keep tests passing, but the real, self-sufficient description lands in 08.

## Acceptance criteria

- [ ] `set_filter(query="theo")` sets `ReportSpec.entity_filter` to `"theo"` and the diff produces
      the chip from slice 06
- [ ] `set_filter(query="")` clears an existing filter back to `None`
- [ ] `set_filter` called with `group_by == "none"` produces the `ENTITY_FILTER_IGNORED` Repair,
      does not raise, and the spec proceeds ungrouped
- [ ] `run_report`'s tool result always includes an `entity_filter` key (real value or `null`)
- [ ] Unit tests in `tests/test_agent_tools.py`, same style as the existing
      `TestSetGroupingOrphaningSort`-class tests, cover all of the above
- [ ] `make check` passes

## Blocked by

- [02 — `entity_filter` on ReportSpec + engine filtering](02-entity-filter-engine.md)
- [06 — Presenter: filter chips/repair text, plus the bundled enum-leak fix](06-presenter-filter-chips-and-enum-fix.md)
