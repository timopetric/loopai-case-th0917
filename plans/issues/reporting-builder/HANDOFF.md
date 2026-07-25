# Handoff — Reporting Builder (Case TH-0917)

Written 2026-07-25 at the end of the design phase. **The next session implements.**

Everything decided is already written down. This document deliberately does **not** repeat it —
it tells you where things stand, what to read in what order, and the handful of things that are
true but easy to miss.

---

## Where things stand

**Design is complete and committed** (HEAD `c397d9f`, working tree clean). **No application code
exists yet** — no `app/`, no `frontend/`, no `tests/`, no `Dockerfile`, no `Makefile`. The repo
currently contains only documentation, evidence, and a `.venv`.

The upstream API was investigated exhaustively (~350 live probes), the live LLM was smoke-tested
against the real tool surface, and every design question raised in a long grilling session has
been resolved and recorded. There are no open design decisions blocking a start.

## Read in this order

1. **`AGENTS.md`** (repo root; `CLAUDE.md` symlinks to it) — the router. Trust hierarchy, the
   vocabulary trap, three upstream landmines, hard rules.
2. **`plans/CLAUDE.md`** — index of every planning document and when to read it.
3. **`plans/issues/reporting-builder/PRD.md`** — problem, solution, 70 user stories,
   implementation and testing decisions, out-of-scope.
4. **The issue you are about to build** — `plans/issues/reporting-builder/NN-*.md`.
5. **`plans/decisions/architecture.md`** — the operational spine. Read the sections your issue
   touches. Most detailed file in the repo.

Read `plans/decisions/api-report-fresh.md` before writing anything that touches upstream data,
and `plans/decisions/CONTEXT.md` before naming anything.

## Start here

**Issue 01 (`01-walking-skeleton.md`) is unblocked.** The dependency chain is linear to 07, then
branches four ways:

```
01 → 02 → 03 → 04 ─┬→ 05 → 10 → 11
                   │    └→ 09
                   └→ 06 ─┬→ 07 ─┬→ 12  13  14
                          │      └→ 15 → 16 → 17 → 18 → 19
                          └→ 08 → 09
```

Critical path is 01→07→15→17→18→19. Slices 12, 13 and 14 are slack and can be dropped if time
runs short without breaking anything downstream.

17 of 19 are AFK. Only **18** (verification pass + README) and **19** (deploy) are HITL.

## Things that are true and easy to miss

Each of these is documented, but each has already caused a wrong assumption at least once:

- **`scratch/` contains conclusions that were later overturned**, sometimes within the same file
  — a "broken" mailbox breakdown, a "rolling" data window, "scope does nothing". Read
  `scratch/README.md` before using anything from that directory. Its traps table lists each one.
- **Duration metrics are in HOURS**, not the documented seconds, and are *sums* with a `_count`
  companion. This is the single most expensive mistake available.
- **The vendor's published `/spec` is wrong in ~19 places.** `api-report-fresh.md` supersedes it
  entirely. Do not "check the official docs" to resolve a disagreement.
- **`plans/agents/domain.md` was hand-corrected** to point at this repo's real paths. If a setup
  skill regenerates it, the fix must be reapplied.
- **The frontend must have zero build-time configuration.** No `VITE_*`, ever. A build-time value
  binds the image to the machine that built it and fails only in production, after a green deploy.
- **Never parse assistant prose as tool calls.** Verified live: denied real tools, the model emits
  convincing but fabricated tool-call JSON naming a schema that does not exist.

## Environment and credentials

- **`.env` exists and holds a real, working OpenRouter key.** Be frugal — the design-phase smoke
  test cost ~12.5k tokens across 11 calls and that was enough to answer everything. `.env` is
  gitignored; the key must never appear in a file, a log, or a commit.
- **Model `qwen/qwen3.6-plus` is confirmed working.** Tool calling, parallel calls, enum
  discipline and out-of-range judgement were all verified — results are in
  `plans/decisions/architecture.md` §5, including the two guards that came out of it.
- **Node 24 "Krypton"** is Active LTS (checked 2026-07-25). Build stage only.
- **Docker Hub `timopetric/caseth0917`**, public. The owner builds locally and pushes; Railway
  deploys the image rather than building from source.
- **`chrome-devtools-mcp@chrome-devtools-plugins` is configured** but has never been exercised
  against this app — it is new in the next session. Levels 2 and 3 of the verification ladder
  depend on it.
- `uv` venv already exists at the repo root.

## Suggested skills for the next session

- **`/tdd-implement-scope`** — the best fit for the main run: sequential issue implementation with
  TDD, a deterministic test gate and review, on a dedicated branch rather than `main`. The issues
  were written with acceptance criteria phrased as checkable behaviour precisely so they can drive
  this.
- **`/tdd`** if you prefer to drive a single slice by hand.
- **`/run`** to launch the app for the level-2 browser loop.
- **`/code-review`** on the working diff before the HITL slices.
- **`/triage`** if issue states need updating as work progresses.
- **`/grill-with-docs`** only if a *new* design question appears — the existing ones are settled,
  and `CONTEXT.md` plus the ADRs should be updated inline if it does.

## Known risks

- **The one unverified behaviour** is the forced-final-answer path in slice 17: sending the final
  Tool Step with tool definitions omitted. Everything else about the model is proven. Exercise it
  early rather than at the end.
- **The repair rules (ADR-0002) are specified, not proven.** The taxonomy table in
  `architecture.md` §5 doubles as the test checklist for slice 16; the multi-call batch case is the
  one most likely to be skipped.
- **The upstream is a free-tier Railway app** and could be asleep or retired when a reviewer opens
  the submission. `DEV_FAKE_UPSTREAM` (ADR-0003) exists for the dev loop but is refused outside
  development by design — this is a deliberate, accepted risk, not an oversight.
- **Time.** This is scoped as a one-night sprint. `plans/decisions/idea.md` has the V0/V1/V2 tiers
  and the explicit cut list; `second-opinion.md` §3 has the build-first ordering. If the night
  runs short, cut slices 12–14 before cutting anything on the critical path.

## One process note

Sub-agents in this environment are **blocked from writing files matching report/findings
patterns**. They return their findings as text instead, and the orchestrator must write them to
disk. This cost several retries during the design phase — if you delegate research, expect to
persist the results yourself.
