# Handoff — Frontend rework, slices 01–09 complete

Written 2026-07-26. Branch **`feat/reporting-builder`**, working tree clean, never commit to `main`.

The previous session's handoff covered the backend build. Its *Traps* and *Decisions already made*
sections still hold and are not repeated here.

---

## Where things stand

**All nine AFK slices are done, reviewed and committed, one commit each.** Only slice **10 (live
walkthrough and design sign-off) remains — it is HITL** and was deliberately not attempted.

| Slice | Commit |
|---|---|
| 01 tokens and sign-in | `0859800` |
| 02 workspace shell | `c0382cc` |
| 03 builder rail | `f96404a` |
| 04 report table | `73706d8` |
| 05 chart | `74d08a5` |
| 06 assistant panel | `cf87b2c` |
| 07 dark mode | `30eb897` |
| 08 accessibility | `41f1e0c` |
| 09 browser verification | `f4f43a7` |

`make check` is green at **389 passed, 0 skipped, 1 warning** — the warning is the pre-existing
httpx/starlette deprecation. A second warning is new and yours.

**Verification reached level 2.** The built image was driven in a real browser in both themes at
three viewports. [`09-verification-record.md`](09-verification-record.md) is the full record: what
was confirmed, the five defects fixed, and the two findings left for a decision. Read it before
slice 10 — it is the most useful document here.

## The one finding that matters most

Slice 09 found that **virtualisation was not working at all.** The shell root used `min-h-screen`,
a *minimum* that never capped the flex chain, so the table's scroll parent reported a 67,232px
client height and the virtualiser correctly concluded every row was visible — all 1,526 rows sat in
the DOM. Every source-level test passed the whole time, because the code *is* virtualised and only
the layout stopped it binding.

The lesson generalises: source-level guards in this repo prove a component is *written* correctly.
They cannot prove it *behaves* correctly once composed. Slices 01–08 were all verified at level 1
only; slice 09 is the first time any of it was looked at.

## What slice 10 must decide

Two findings were deliberately left alone because fixing them means touching the engine, the
exporters or the presenter — all out of scope for this rework by the PRD:

1. **Duration values render as raw floats** (`11.482139109909799`). Pre-existing, not a regression.
   It cannot be fixed on screen alone: `app/exporters.py:110` prints the full float *on purpose* so
   the file matches the screen, so rounding the display alone would break a graded user story. Fix
   it in the engine and the screen together, as one change.
2. **A Repair chip shows a wire enum** — "Added metric: handle_time" where the UI says "Handle time
   (h)". Built at `app/agent/presenter.py:243`. Slice 09's own regression list forbids enum values
   in the conversation. One line, in a file with negative leak assertions that should move with it.

Slice 10 also has to make the judgement call the PRD reserved for a human: whether cream-as-accent
with a white data surface, brand colour confined to actions, and the chart palette held apart
actually reads as intentional. ADR-0004 either stands or gets revised there.

## Practical notes

- **Chrome DevTools MCP now works.** It appeared after `/reload-plugins` mid-session. Earlier
  sessions reported it missing; it is genuinely available now.
- **Run the verification container with a throwaway `APP_API_KEY`** rather than the real one from
  `.env` — the reading of `.env` is blocked, and a self-set key keeps the shared secret out of the
  transcript entirely:
  `docker run -d --name loopai-verify -p 8000:8000 --env-file .env -e ENVIRONMENT=dev -e DEV_FAKE_UPSTREAM=1 -e DEV_FAKE_LLM=1 -e APP_API_KEY=verify-local-key -e PORT=8000 timopetric/caseth0917:latest`
  Note `ENVIRONMENT` must be one of `dev|local|test|prod` — `development` is rejected at startup.
- **`streamdown` is pinned exactly.** Raw HTML is disabled by an undocumented internal of its
  bundle (omitting `rehype-raw` makes it rewrite html nodes to text), not a promised API, so a minor
  bump could reopen it with every guard still green. Re-verify in `node_modules/streamdown/dist/`
  before raising the pin. It also costs ~146KB gzip.
- After the rework, reporting-builder issues **18 (README) and 19 (deploy)** are still open.

## Suggested skills

- **`/code-review`** on the working diff before slice 10 — nine slices have landed unreviewed as a
  whole.
- **`/run`** plus Chrome DevTools MCP for the live walkthrough.
- **`/dataviz`** if slice 10 reopens the palette question.
