Status: done

# 08 — System prompt rewrite and tool-schema description overhaul

## Parent

[`PRD.md`](PRD.md)

## What to build

Rewrite `app/agent/prompts/report_agent_system.jinja` and `app/agent/tools.py`'s
`_TOOL_DESCRIPTIONS` dict together, per live research gathered during the grilling session
(Anthropic/OpenAI/LangChain guidance on tool-calling prompt design, plus Qwen-specific caveats):

1. **Convert the system prompt's `##` markdown sections to XML tags** (`<coverage_window>`,
   `<metric_catalogue>`, `<current_spec>`, `<tools>`, etc.). This was flagged during design as a
   genuine open question — the strongest evidence for XML-tag structuring is Claude-specific, and
   one source explicitly recommends markdown for Qwen-family models — but the owner chose to
   proceed with XML anyway, to be settled empirically (see acceptance criteria below) rather than
   decided from general guidance alone.

2. **No hand-authored few-shot tool-call examples.** Do not add worked user→tool-call→answer
   transcripts to the prompt. Qwen3's own documentation warns that ReAct-style stopword/
   action-marker few-shot templates can leak into the model's own `<think>` block and corrupt
   tool-call parsing — the same class of risk architecture.md's existing Guard 1 (never parse
   assistant prose as tool calls) already exists to contain.

3. **Substantially rewrite all ten `_TOOL_DESCRIPTIONS` strings** (the nine existing tools plus
   `set_filter` from slice 07) — self-contained, 3-4+ sentences each, stating not just what the
   tool does but *when* to use it and its edge-case/repair behavior, per the research: "detailed
   descriptions are by far the most important factor in tool performance" (Anthropic); describe
   when/when-not to call each function (OpenAI); state when to use the tool, not just its name
   (LangChain). `set_filter`'s description in particular must be fully self-sufficient — stating
   the case-insensitive substring behavior, that an empty string clears it, and the
   `group_by == "none"` no-effect-but-reported behavior directly in the schema description, not
   relying on the system prompt to carry that.

4. **Add one line to the system prompt** telling the Assistant it may call `get_meta` first to
   confirm a name before calling `set_filter`, if it isn't confident a loosely-typed name will
   match.

5. **Add one style-note instruction** (not an embedded example) permitting the model's final
   prose to optionally use a small markdown table when summarizing a change whose shape is
   naturally tabular (e.g. columns/row-count changed) — explicitly not a replacement for chips,
   never a full row-data dump, and not expected on every turn.

## Acceptance criteria

- [ ] The rewritten prompt renders correctly through Jinja with no template errors, for both the
      fake-LLM and real-LLM code paths
- [ ] All ten tool descriptions are self-contained (a reader with no other context could
      understand each tool's purpose, parameters, and edge-case behavior from its description
      alone)
- [ ] No few-shot tool-call transcript appears anywhere in the prompt
- [ ] `scratch/fresh-eyes/llm-smoke-tool-calling.py` (or an updated version covering `set_filter`)
      is re-run against the real model after the rewrite, and its results are recorded — this is
      the test that empirically settles whether the XML-tag conversion helped, hurt, or made no
      difference to tool-calling accuracy relative to the prior markdown-heading version
  - [ ] If the smoke test shows a clear regression attributable to the XML conversion, revert to
        markdown headings and note the finding in this issue's comments before closing it
- [ ] `make check` passes

## Blocked by

- [07 — The `set_filter` Assistant tool](07-set-filter-tool.md)
