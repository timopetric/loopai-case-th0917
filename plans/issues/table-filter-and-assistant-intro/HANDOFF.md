# Handoff — row filtering, and an Assistant that introduces itself

Written 2026-07-26. Branch **`feat/reporting-builder`**, working tree clean. Never commit to `main`.

Two pieces of work, both agreed with the owner and neither started. Nothing here has been designed
into an issue file yet — that is the next session's first job if it wants one.

---

## Where the project stands

The frontend rework is **finished through slice 09**, one commit per slice, and was driven in a real
browser against the built image. `make check` is green at **391 passed, 0 skipped, 1 warning** (the
pre-existing httpx/starlette deprecation — a second warning is new and yours).

Read these two, in order, before touching anything:

- [`../frontend-rework/HANDOFF.md`](../frontend-rework/HANDOFF.md) — the state of the rework, the
  per-slice commits, and the traps that survived it
- [`../frontend-rework/09-verification-record.md`](../frontend-rework/09-verification-record.md) —
  what the browser pass confirmed and fixed. **The most useful document in the repo right now.**

Recent commits worth knowing about, beyond those two documents:

| Commit | What |
|---|---|
| `bbd1a9e` | Durations round to 2dp in the engine and render as `31h 55m` on screen; exports stay numeric |
| `956bc8c` | Row-count control (later pinned) |
| `f3f3c74` | The table-collapses-to-one-row fixes |

**Still open, unchanged:** the reporting-builder's own issues **18 (README)** and **19 (deploy)**,
and frontend-rework slice **10** (live walkthrough and design sign-off, HITL).

---

## Work item 1 — filter rows by Actor / Mailbox name

The owner wants to type something like `theo mancini` and see only that Actor's rows.

**The one thing that decides the whole design: this belongs in the engine, not the browser.** Both
exporters POST the Report Spec to the backend and get a fresh file — they never read the DOM. Filter
client-side and the screen shows 14 rows while the CSV still returns all 1,512, silently breaking
the same graded user story that pagination would have. Doing it as a spec field makes every consumer
inherit it for free.

The shape of it, from a survey already done:

| File | Work |
|---|---|
| `app/models.py` | one optional field on `ReportSpec` |
| `app/engine.py` | ~10 lines. `_entity_rows` already takes a plain `entities: list[EntityBreakdown]`; filter that list before the loop and rows, totals and the chart's top-eight all follow |
| `app/exporters.py` | free, but add a row to the workbook's definition sheet so the file records that it was filtered |
| `app/spec_url.py` | encode/decode + validation, so a filtered report survives a shared link |
| `frontend/` | a text input in the builder rail, wired to the existing Zustand store |

It must be local rather than pushed upstream: the upstream `filters` parameter **does nothing at
all** (`api-report-fresh.md`, gotcha 8). That is fine — ADR-0001 already fetches and memoises the
whole Coverage Window.

**Three decisions the owner has not made yet:**

1. **What the Total row means when filtered** — recommend the filtered rows, so the footer agrees
   with what is above it.
2. **What happens when nothing matches** — an empty table reads as a bug. Recommend a **Warning**
   through the banner that already exists.
3. **What happens when `group_by` is `"none"`** — there are no entities, so the filter is
   meaningless. ADR-0002's established pattern applies: cross-field drift is **repaired and
   reported**, never rejected.

**Two things to weigh.** The main PRD explicitly defers an *Actor/Mailbox multi-select picker*; a
substring filter is the cheap cousin of that deferred feature and may well replace it — decide which.
And giving the **Assistant** a `set_filter` tool roughly doubles the work (tool schema, repair
taxonomy, presenter chip, prompt), so land the control first and add the tool as a separate slice.

---

## Work item 2 — a hard-coded Assistant introduction

Today the conversation opens with one line of placeholder text
(`frontend/src/Chat.tsx:189`): *"Ask for a report in plain English — e.g. …"*. The owner tried
switching to the pivot layout by asking, it worked, and nothing in the interface had suggested it
was possible.

So: replace that empty state with a **short, hard-coded** greeting that says what the Assistant can
do and invites the user to ask. The owner's words: *"short and sweet"*, *"not too long"*, a concise
summary plus a friendly closing question.

**Hard-coded, deliberately** — no model call, no tokens, instant on load.

The capabilities worth advertising are exactly the nine tools in `app/agent/tools.py`
(`set_date_range`, `set_metrics`, `set_grouping`, `set_sort`, `set_columns`, `set_chart`,
`set_layout`, …). Pick the three or four that will most surprise a new user — the pivot layout is
the proven example.

**Constraints that bind this, and they are easy to trip:**

- **Never show tool names or enum values in the conversation.** Write "switch to a pivot layout",
  never `set_layout` or `"pivot"`. This is a hard rule in `AGENTS.md`, and there is an outstanding
  finding of exactly this kind (below).
- **Glossary vocabulary** — **Actor**, **Mailbox**, **Assistant**, **Bucket**, **Coverage Window**.
  Unqualified "agent" is banned in UI copy.
- It renders through the same markdown path as a real reply (`frontend/src/lib/markdown.tsx`), so
  keep it to text a streaming renderer handles trivially — a short line and a few bullets.

---

## The outstanding finding, still unfixed

**A Repair chip shows a wire enum**: the conversation renders "Added metric: handle_time" where the
rail says "Handle time (h)". Built at **`app/agent/presenter.py:243`** —
`f"Added metric: {m.value}"`. Slice 09's own regression list forbids enum values in the
conversation, so this is a real hit.

It was left alone because the frontend rework was scoped out of `app/`, and the presenter carries the
negative leak assertions. **That scope no longer binds** — work item 1 changes the backend anyway. It
is one line plus a label lookup; do it while you are in there, and move the presenter's tests with
it.

---

## Practical notes

- **Verification container.** Port 8000 is often held by the owner's own `make backend`. Use another
  port and a throwaway key, which also keeps the real secret out of the transcript (reading `.env` is
  blocked, correctly):
  ```
  docker run -d --name loopai-verify -p 8010:8000 --env-file .env \
    -e ENVIRONMENT=dev -e DEV_FAKE_UPSTREAM=1 -e DEV_FAKE_LLM=1 \
    -e APP_API_KEY=verify-local-key -e PORT=8000 timopetric/caseth0917:latest
  ```
  `ENVIRONMENT` must be one of `dev|local|test|prod` — `development` is rejected at startup. Sign in
  by setting `sessionStorage.loopai.apiKey`.
- **Chrome DevTools MCP works.** It appeared after `/reload-plugins`. Use it; the browser pass found
  five defects that every source-level test was blind to.
- **`min-h-0` on flex wrappers is load-bearing in three places.** Remove one and the table's scroll
  parent grows to ~67,000px, the virtualiser concludes every row is visible, and all 1,512 land in
  the DOM — with the whole suite still green. No source-level test can catch it. Measure in a browser
  after any layout change.
- **Beware assertions that pass on prose.** A test pinning the sticky Bucket header kept passing
  after the behaviour was removed, because a nearby comment contained the literal class name. Guards
  in this repo grep source; strip comments before scanning.

## Suggested skills

- **`/tdd-implement-scope`** once these are written up as issues in this directory.
- **`/code-review`** on the working diff — nine rework slices have landed without a whole-diff review.
- **`/run`** plus Chrome DevTools MCP to verify the filter behaves against the built image.
