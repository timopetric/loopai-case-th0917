---
description: Sequentially implement issues using TDD, a deterministic test gate, and Haiku review — on a dedicated branch, never main
argument-hint: [issues-dir]
---

**Read every markdown file in the issues directory before doing anything else.**

Issues directory: $1

**Phase 0 — Branch safety (do this first, before any implementation)**
- Run `git rev-parse --abbrev-ref HEAD` to find the current branch.
- **Never implement or commit on `main` (or `master`).** If the current branch is the default
  branch, **stop and propose a new branch** — derive a sensible name from the feature slug (the
  issues directory name), e.g. `feat/<issues-dir-slug>`. Ask the human to confirm or rename it.
  Only after the human approves, create and switch to it (`git switch -c <name>`), then proceed.
- If already on a non-default branch, confirm with the human that this branch is the intended
  target before proceeding.
- All work and commits in this run happen on that branch. Do not commit to main under any circumstance.

**Implementation process**

Work issues **sequentially in dependency order** — sort by the `NN-` prefix, but read each
issue's **Blocked by** section and never start an issue whose blockers aren't done. Do not batch
or parallelize. Track progress with the todo tool (one todo per issue).

For each issue, run this loop (**max 2 implement attempts**, then stop and escalate):

**Phase 1 — Implement (fresh Sonnet subagent)**
Instruct it to:
- Read the issue file, then **every doc it links** — the PRD, and everything the PRD links in turn
  (e.g. CONTEXT.md, the design docs under docs/design/, and the relevant ADRs under docs/adr/).
  Read the files of any blocking issues too, to match established patterns.
- Invoke the `/tdd` skill via the Skill tool at the start of its work and follow red→green→refactor.
- Implement **only this issue's scope** — nothing more. Write tests that map directly to the
  issue's acceptance criteria.
- Run `make lint` and the relevant tests: `make test-unit`, and `make test-integration` for
  DB-touching work. **Use the make targets** — `make test-integration` sets up its own test
  database. Do NOT hardcode a `TEST_DATABASE_URL`; if a target is missing, read the Makefile.
- Return: which files changed, which tests were added, and the **actual final output** of the
  test command (not a paraphrase).

**Phase 2 — Deterministic gate (the orchestrator runs this itself — no model)**
Run the **full** suite plus lint: `make lint && make test`.
- This is ground truth — never trust the implementer's prose over the real exit code.
- **A skip is not a pass.** Read the pytest summary line: if the DB-touching (integration) tests
  report `skipped` or collected 0, the gate **fails** — a missing `TEST_DATABASE_URL`/DB makes
  integration tests silently skip and report green. Require them to actually run (0 skipped) before
  treating the suite as passing.
- Fail → hand the **real** failure output back to Phase 1 as additional context and re-implement.
- Gate on the *full* suite, not just this issue's tests, so regressions surface immediately.
- **Bootstrap fallback:** the `make lint`/`make test` targets don't exist until the tooling issue
  (issue 01) builds them. If a target is missing, fall back to the underlying tools for that issue
  only — `uv run ruff check .` and `uv run pytest` (with the integration DB up) — then use the make
  targets from the next issue on.

**Phase 3 — Judgment review (fresh Haiku subagent — only once Phase 2 is green)**
Give it the issue's acceptance criteria and have it review **independently**:
- Read the real `git diff` (not the implementer's summary). This diff is scoped to the current
  issue *only because prior issues were committed in Phase 4* — keep that per-issue commit.
- Read the new tests and confirm they actually assert the specified behaviour — flag
  tautological, over-mocked, missing-assertion, or skipped tests.
- Confirm every acceptance criterion is met and that no out-of-scope files were touched.
Return a clear **PASS** or **FAIL** with specific paths and reasons.
- FAIL → back to Phase 1 with the reasons, then re-run Phases 2–3.

**Phase 4 — Checkpoint (on PASS)**
- Stage the issue's changes and **commit** using this exact format (match the tone/verbosity of
  the existing `git log`):

  ```
  <type>(<scope>): <short imperative subject, ≤72 chars, no period>

  <2–3 sentence description>: what changed and why — the problem solved or
  decision made, not a list of files.

  - <bullet>: one logical change per bullet, grouped by layer or concern
  - <bullet>
  ```

  Rules: conventional-commits type (`feat`/`fix`/`chore`/`docs`/`refactor`/`test`); scope derived
  from the issue (e.g. the module/slice, not invented); description explains the *why* and overall
  shape; bullets are one-per-logical-concern (not per file), 1–2 lines each. Be concise.
- **Flip the issue file's `Status:` line to `done`** (see docs/agents/triage-labels.md).
- Commit that status change too (may be part of the same commit), then move to the next issue.

**Escalation**
If an issue still fails after 2 full attempts, **stop the loop**, leave the work uncommitted with a
short note of what's blocking, and report to the human. Do not loop forever, and do not skip ahead
to a later issue whose blocker just failed.
