# Handoff — Frontend rework, mid-run

Written 2026-07-26. Branch **`feat/reporting-builder`**, working tree clean, never commit to `main`.

This continues the run described in the previous session's handoff. That document's *Traps*,
*Decisions already made* and *Process notes* sections are all still current — **read them, they are
not repeated here.**

---

## Where things stand

Slices **01–05 are done, reviewed and committed, one commit each.** Slice **06 has not been
started** — it was the next thing about to run when the session stopped.

| Slice | Commit | Status |
|---|---|---|
| 01 tokens and sign-in | `0859800` | done |
| 02 workspace shell | `c0382cc` | done |
| 03 builder rail | `f96404a` | done |
| 04 report table | `73706d8` | done |
| 05 chart | `74d08a5` | done |
| 06 assistant panel | — | **next, not started** |
| 07 dark mode | — | blocked on 06 |
| 08 accessibility | — | blocked on 06 |
| 09 visual verification | — | **cannot run, see below** |
| 10 live walkthrough | — | HITL |

Each issue file under `plans/issues/frontend-rework/` carries its own `Status:` line, flipped to
`done` as part of that slice's commit. The commit messages record what changed and why; the diffs
are scoped one slice per commit, so `git show <sha>` is the fastest way to see any slice.

`make check` is green at **303 passed, 0 skipped, 1 warning** — the warning is the pre-existing
httpx/starlette deprecation. A second warning is new and yours.

## The process being followed

`/tdd-implement-scope` with `plans/issues/frontend-rework`. Per slice: a Sonnet implementer, then
`make check` run by the orchestrator directly as the deterministic gate, then an independent Haiku
review of the real diff, then a per-issue commit and a `Status: done` flip. Resume at slice 06.

That loop has held up. Two things worth keeping:

- **Verify the load-bearing property yourself rather than reading the reviewer's prose.** Every
  slice so far had one criterion worth checking by hand — the fonts were real woff2 binaries, the
  `"agent"` wire value survived the copy change, `CHART_PALETTE` was byte-identical. All three
  passed, but the check was cheap and the failure mode is silent.
- **Both reviews so far passed on the first attempt.** Nothing has needed a second implement pass.

## What slice 06 needs to know

The prompt was written and not sent. The parts that took thought:

- **`streamdown` is the decided renderer** — settled with the user, chosen *because* Tailwind was
  adopted. Do not relitigate. If it proves technically unusable, fall back to `react-markdown` +
  `remark-gfm` and **say so**; do not silently substitute.
- **The presenter's containment is not a styling concern.** Nothing under `app/` may change, and
  `tests/test_agent_presenter.py` carries a negative leak assertion that must pass unmodified. This
  slice formats what already arrives; it must not widen what is sent.
- **Model output is untrusted** — raw HTML stays disabled, link protocols allowlisted. Worth a
  guard test that no `rehype-raw` / `dangerouslySetInnerHTML` / `allowDangerousHtml` appears.
- **The development-only reasoning disclosure cannot be gated on a build-time frontend value** —
  that is the `VITE_*` hard rule. The dev-fake banners already solve this problem; follow the same
  mechanism.

## One decision made mid-run that is not in any issue file

Slice 02 added `withMetricsCleanup` to the spec store: unchecking a metric now also clears a `sort`
or `chart_metric` pointing at it. This was not asked for by the issue, and I checked it before
accepting it — `app/models.py:109` rejects that combination, so the old code sent a request
guaranteed to 422. It is a genuine bug fix, recorded in the `c0382cc` commit message rather than
left silent.

## Known limitation carried forward

Slice 04's Bucket group headers are `sticky top-10` and are only mounted within the virtualiser's
overscan. Scrolling fast deep inside one very large Bucket (the default report has 108 rows per
Bucket) can momentarily lose the sticky Bucket label until the next Bucket's header scrolls into
range. The table header and leading columns are unaffected. Documented rather than fixed; worth a
look during slice 09 if it ever runs.

## Slice 09 — start a fresh session for it

**Chrome DevTools MCP was not available to this session,** exactly as the previous session
reported. The owner then configured the server and reloaded plugins partway through the run; it
still did not appear, because the tool roster is fixed when a session starts. Three probes —
keyword searches and a direct lookup by tool name — all found nothing.

**So it should work in a new session.** Start one, re-confirm the tool is actually present, and
run slice 09 then. Do not substitute curl checks and declare the interface verified; slice 09's
own first acceptance criterion is that it either confirms the tool or stops and reports.

This means **no slice in this rework has been verified above level 1.** Every implementer has said
so plainly in its own report. `make check` passes and the production Vite build compiles; nobody
has looked at any of it in a browser. That is the single biggest outstanding risk in the rework,
and slices 07 and 08 (dark mode, accessibility) are the two where it bites hardest — both are
substantially visual, and both will land unverified unless the tool becomes available.

If it does become available, run 09 before 10.

## Suggested skills

- **`/tdd-implement-scope`** with `plans/issues/frontend-rework` — resume the loop at slice 06.
- **`/frontend-design`** before slice 06, and again for 07 — visual judgement is the deliverable.
- **`/dataviz`** was used in slice 05 and would apply again to the dark chart palette in 07, where
  the eight hues need dark-surface counterparts *selected and validated*, never inverted.
- **`/code-review`** on the working diff before slice 10.
