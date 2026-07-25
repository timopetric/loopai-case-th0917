# scratch/ — evidence, not specification

> **Read this before trusting anything in this directory.**
>
> These are raw probe scripts and saved API responses from two investigation passes. They are
> the *audit trail* for how the upstream contract was established — **not** a statement of what
> is true now, and **not** a design document.
>
> **The specification lives in `plans/decisions/`.** For the upstream API specifically, the only
> current reference is `plans/decisions/api-report-fresh.md`. If anything here disagrees with
> it, this directory is wrong.

## Why this warning matters

Several files here contain conclusions that were **later overturned by the very same
investigation**, sometimes within a single file. Reading them in isolation will produce
confidently wrong assumptions. The known traps:

| Superseded claim found in `api-probe-findings.md` | What is actually true |
|---|---|
| "The `mailbox` breakdown is broken/near-empty — don't trust it" (pass 1, finding #7) | **False.** Pass 1 tested only the 5 mailboxes from the docs' example, which happen to have `resolved = 0`. Across all 103 mailboxes the breakdown reconciles exactly. Corrected in pass 2 of the same file. |
| "`scope` and `filters` do nothing" (pass 1, finding #4) | Partly false. `filters` is inert, but `scope` **does** trim the `mailbox[]` breakdown list. Corrected in pass 2. |
| "Rolling 'last 14 days' window anchored to now" (pass 2, finding #7) | **False.** The window is fixed at absolute dates. Corrected in pass 3. |
| "Window runs to `2026-07-24`" | Misleading. `2026-07-24T00:00Z` is the closing *boundary tick*; the last day with data is **2026-07-23**, as `/health` states. |

The file is structured newest-pass-first, so its own later sections correct its earlier ones.
Skim the whole thing or none of it.

## What is here, and what it is for

| Path | Status | Use |
|---|---|---|
| `resp-full-unscoped-latest.json` | **Live dependency** | Source of the committed test fixture. Copy to `tests/fixtures/` and pin it. Safe because the upstream dataset is provably static across calendar days. |
| `fresh-eyes/verify-*.py` | **Live dependency** | Re-runnable probes. If upstream behaviour looks wrong mid-build, these re-establish the contract in seconds — range rules, units arithmetic, breakdown reconciliation. |
| `fresh-eyes/agent-report-*.md` | Evidence | Raw sub-agent findings behind `api-report-fresh.md`; the audit trail for any claim in it. |
| `fresh-eyes/llm-smoke-*.{py,json}` | Evidence | The live model smoke test (tool calling, parallel calls, enum discipline). Contains no API key. |
| `agent-spec-lab/` | Evidence + prior art | 63 offline tests on spec-patch semantics; `LAB_NOTES.md` records proven failure modes. The pattern to follow for spec-editing tests. |
| `api-probe-findings.md` | **Superseded** | Historical only — see the traps table above. |
| `probe-*.py`, `resp-*.json`, `*-output.txt` | Historical | First-pass probes and their saved responses. |
| `spec-research.md` | Historical | The brief and official docs captured verbatim. The official docs are wrong in ~19 places; see the gotchas list in `api-report-fresh.md`. |

## Rule of thumb

Use this directory to **re-verify** a fact against the live API, or to pull the test fixture.
Do not use it to **learn** what is true — that is what `plans/decisions/` is for.
