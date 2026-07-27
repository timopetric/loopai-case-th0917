# Handoff — row filtering, always-on reasoning trace, Assistant intro: PRD + 12 issues published

Written 2026-07-27. Branch **`feat/reporting-builder`**, working tree has only new, untracked
planning files — nothing has been implemented yet. Never commit to `main`.

This directory's own `HANDOFF.md` (the one you're reading) has been rewritten — the original
handoff that kicked off the `/grill-with-docs` session is superseded by [`PRD.md`](PRD.md) and the
twelve numbered issues below, which now carry every decision that document only sketched.

---

## Where things stand

A full `/grill-with-docs` session (~40+ interviewed questions, several backed by direct codebase
reads and one round of live web/Context7 research) turned the original handoff's two open work
items into a fully-specified PRD and a dependency-ordered issue breakdown. **Nothing has been
implemented yet** — this session was pure design. The next session's job is implementation.

- [`PRD.md`](PRD.md) — the full spec: problem statement, 25 user stories, every implementation
  decision (with the reasoning behind each), testing decisions, explicit out-of-scope list.
  **Read this first**, then read issues 01-12 in order — they are the PRD broken into
  independently-gradable, dependency-linked vertical slices, each with its own acceptance
  criteria.
- [`plans/decisions/adr/0005-stream-raw-reasoning-to-all-users.md`](../../decisions/adr/0005-stream-raw-reasoning-to-all-users.md)
  — new ADR, already written, documenting the deliberate reversal of the "reasoning text is
  dev-only" rule. Read this before touching anything in `app/agent/events.py`,
  `app/agent/presenter.py`, or `app/api/v1/routers/agent.py` — it explains *why* a previously
  hard architectural rule is being reversed, not just that it is.

## The three features, in one paragraph each

1. **Row filter by Actor/Mailbox name** (issues 02-08, 11-12): a new `ReportSpec.entity_filter`
   field, case-insensitive substring match, landing in the engine so preview/exports/Assistant all
   agree by construction. Three previously-undecided edge cases are now settled (filtered totals,
   empty-match Warning, `group_by == "none"` Repair) — see `PRD.md`'s Implementation Decisions for
   the exact wording of each. Exposed both as a builder-rail text input and a new `set_filter`
   Assistant tool.
2. **Always-visible, markdown-rendered Assistant reasoning trace** (issues 01, 09-10): raw
   chain-of-thought streams to every user, in every environment — a deliberate policy reversal
   (ADR-0005), not a bug fix. Three visual states (waiting → thinking, expanded → collapsed),
   segmented by Tool Step, persisted per chat message, manual-collapse respected mid-turn.
   **Accepted, explicit risk**: reasoning text will sometimes name internal tools/enum values —
   this does not relax the same rule for the Assistant's actual reply, only for this one new,
   separately-labeled panel.
3. **Hard-coded Assistant introduction** (issue 11): a static greeting with concrete "try:"
   examples, including the owner's exact chosen line for the new filter: *"try: filter to just
   Theo's numbers."*

Plus one bundled fix (issue 06): a previously-flagged, unrelated enum leak in `_diff_chips`
("Added metric: handle_time" → "Added metric: Handle time") gets fixed while that file is already
open for the filter chips.

## Issue order and dependency shape

```
01 (doc corrections)         02 (entity_filter + engine)          09 (reasoning: backend gate)
    independent               /    |    \                              |
                              03    04    06                        10 (reasoning: frontend UI)
                               \    |    /  \                            |
                                \   |   /    07 (set_filter tool)         |
                                 \  |  /       |                         |
                                  05 (rail)   08 (prompt rewrite)        |
                                     \_____________  ________________ /
                                                  11 (intro)
                                                     |
                                          12 (final verification — Chrome DevTools MCP)
```

01 and 09 are independent starting points. 02 is the other root, feeding 03/04/06 in parallel,
then 07 (needs 02+06), then 08 (needs 07). 05 needs 02+03. 11 converges the filter track (05) and
the reasoning track (10). **12 is the explicit final gate — do not run the full browser
walkthrough until 02-11 are all done and `make check` is green.** This was a specific instruction
from the product owner during design: Chrome DevTools MCP verification is one of the *last*
steps, not interleaved mid-implementation, so it catches whatever the narrower per-slice checks
missed rather than being redone piecemeal.

## Two live research findings baked into issue 08 — don't re-litigate them

During design, a subagent ran live web + Context7 research on tool-calling prompt best practices,
and it **reversed two decisions already made earlier in the same session**:

- **Few-shot tool-call examples were planned, then dropped.** Qwen3's own docs warn that
  ReAct-style stopword/action-marker few-shot templates can leak into the model's own `<think>`
  block and corrupt parsing — the same class of risk architecture.md's Guard 1 already exists to
  contain. Issue 08 explicitly says: no hand-authored tool-call transcripts.
- **XML-tag prompt sectioning is going ahead anyway, despite mixed evidence.** The strongest
  evidence for XML tags is Claude-specific; one source explicitly recommends markdown for
  Qwen-family models. The owner chose to proceed with XML regardless, on the condition that the
  live smoke test (`scratch/fresh-eyes/llm-smoke-tool-calling.py`) empirically settles it
  afterward — **issue 08's acceptance criteria include re-running that smoke test and reverting to
  markdown if it shows a regression.** Don't skip this step; it's the only thing that actually
  answers the open question rather than assuming either side of the research.

The real payoff of that research is issue 08's core deliverable: all ten tool-schema
`description` strings (nine existing + `set_filter`) get substantially rewritten to be
self-contained (3-4+ sentences, stating *when* to use each tool and its edge-case behavior) —
this is where the weight the dropped few-shot examples would have carried now goes instead, per
converging Anthropic/OpenAI/LangChain guidance gathered live.

## A design decision worth restating, because it's easy to get backwards

The Assistant's final prose may **optionally** use a small markdown table (issue 08, item 5) —
this is explicitly **not** a replacement for chips, and chips are **not** being redesigned as a
table. Chips stay the deterministic, guaranteed-accurate summary of what changed (built from a
validated spec diff, never model prose). The optional table is a separate, much smaller thing:
permission for the model's own free-text reply to occasionally take tabular shape (e.g. "3
columns changed, 12 rows now shown") when that's clearer than a sentence — no embedded worked
example in the prompt, just a style-note instruction, per the owner's explicit framing during
design ("it's not needed every time... it should just be some overview of stuff").

## Suggested skills for the next session

- **`/tdd-implement-scope`** — this directory's issues are already written for exactly this: fully
  specified, dependency-ordered, AFK-preferred, `ready-for-agent` labeled. Feed it issues 01-12 in
  order.
- **`/code-review`** on the working diff once a meaningful chunk of issues 01-11 land, before
  reaching issue 12 — cheaper to catch problems before the final browser pass than during it.
- **`/run` + Chrome DevTools MCP** for issue 12 specifically, once everything else is done —
  don't reach for this earlier; the whole point of ordering it last was to avoid re-running it
  piecemeal after every slice.

## Practical notes carried over from the previous handoff, still true

- **Verification container** (from the prior `HANDOFF.md`, still accurate): port 8000 is often
  held by the owner's own `make backend`. Use another port and a throwaway key:
  ```
  docker run -d --name loopai-verify -p 8010:8000 --env-file .env \
    -e ENVIRONMENT=dev -e DEV_FAKE_UPSTREAM=1 -e DEV_FAKE_LLM=1 \
    -e APP_API_KEY=verify-local-key -e PORT=8000 timopetric/caseth0917:latest
  ```
- **`min-h-0` on flex wrappers is load-bearing in three places** (frontend-rework's own finding,
  still true, not touched by this work) — don't remove one without checking in a browser.
- The product owner's stated preference this session, worth carrying forward: they want plain
  ABC-style multiple-choice questions with a stated recommendation and reasoning (not open-ended
  prose questions) when a design decision needs their input mid-implementation.
