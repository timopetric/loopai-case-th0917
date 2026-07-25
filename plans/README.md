# plans/

Planning and specification for Case TH-0917 (InTheLoop take-home).

**`decisions/` is the trusted spec.** Everything in it is current and agreed; build against it.
`old_decision_depricated/` is kept only for the audit trail — nothing there should inform
implementation.

Paths written in backticks inside these documents (e.g. `scratch/fresh-eyes/`) are
**relative to the repo root**, not to this folder.

---

## `decisions/` — the trusted spec

| File | What it is | Read it when |
|---|---|---|
| [`CONTEXT.md`](decisions/CONTEXT.md) | **Domain glossary.** The canonical vocabulary — Report Spec, Duration Metric, Actor, Mailbox, Assistant, Tool Step, Repair, Warning — plus the resolved ambiguities (notably: "agent" was doing three different jobs). | Before naming anything. Any new term goes here first. |
| [`api-report-fresh.md`](decisions/api-report-fresh.md) | **The upstream API contract.** What the reporting endpoint actually does, from ~350 live probes, with a gotchas list of every place the official docs are wrong, and a `## Divergences` section reconciling two independent investigations. | Implementing anything that touches upstream. This overrides the official `/spec`. |
| [`idea.md`](decisions/idea.md) | **Product scope.** The client's ask decoded, the stated assumptions (A1–A6), scope tiers V0/V1/V2, and the explicit cut list. | Deciding what to build and what to drop. |
| [`architecture.md`](decisions/architecture.md) | **Technical design.** Component layout, the `ReportSpec` contract, Assistant tool surface and repair taxonomy, SSE event design, frontend zones, deployment, decision log. | Writing code. This is the most operationally detailed file. |
| [`second-opinion.md`](decisions/second-opinion.md) | **Independent product/architecture critique.** What the product should be given the data's limits, one-night scope ordering, risks, and flags against the fixed decisions. | Sanity-checking priorities, or writing the README's assumptions section. |
| [`problem_statement_and_thoughts.md`](decisions/problem_statement_and_thoughts.md) | **The original ask,** verbatim: the assignment links plus the owner's stated constraints and preferences. | Confirming what was actually requested versus inferred. |
| [`PLAYBOOK.md`](decisions/PLAYBOOK.md) | **Reference, not a decision.** FastAPI service scaffolding distilled from the pobude build. `architecture.md` cites it per section with what is adopted and what is deliberately skipped. Its internal links point into the pobude repo and are expected to be broken here. | Setting up config, auth, error envelopes, project layout. |
| [`adr/`](decisions/adr/) | **Architecture decision records.** One file per hard-to-reverse decision, with the alternatives considered. | Wondering "why on earth is it done this way?" |

### ADRs

| ADR | Decision |
|---|---|
| [`0001`](decisions/adr/0001-fetch-full-coverage-window-and-memoise.md) | Fetch the full coverage window on every miss, memoised 5 minutes, keyed on the `/health` window. Supersedes the earlier "no caching layer" rule. |
| [`0002`](decisions/adr/0002-field-scoped-assistant-tools-that-repair.md) | Field-scoped Assistant tools over one atomic patch, chosen for progressive rendering; cross-field drift is repaired and reported, never rejected. |

---

## `old_decision_depricated/` — superseded, audit trail only

| File | Why it's here |
|---|---|
| [`api-map.md`](old_decision_depricated/api-map.md) | The first session's API contract. Substantially correct and independently reached most of the same conclusions, but `api-report-fresh.md` corrects real errors in it: the required-field list, top-level key counts, the `2026-07-24` window edge, and `resolve_time_count`. |
| [`prompt.md`](old_decision_depricated/prompt.md) | The fresh-eyes prompt used to commission the independent re-derivation. A process artifact; it deliberately contains no findings. |

---

## `scratch/` — evidence, and a build-time dependency

Not specification, but **not disposable either** — two things in it are needed while building:

| Path | Role in the build |
|---|---|
| `scratch/resp-full-unscoped-latest.json` | **Source of the committed test fixture.** Copy to `tests/fixtures/` and pin it. `upstream.py` is faked with this via dependency override in every unit test; the engine, exporter and Assistant tests all assert against its real numbers (16372 resolved, 108 actors, 103 mailboxes). |
| `scratch/fresh-eyes/*.py` | **Re-runnable probes.** If upstream behaviour ever looks wrong mid-build, `verify-range-rule.py`, `verify-units-decisive.py` and `verify-reconcile-and-tz.py` re-establish the contract in seconds rather than by re-reasoning. |
| `scratch/fresh-eyes/agent-report-*.md` | Raw sub-agent findings behind `api-report-fresh.md` — the audit trail for any claim in it. |
| `scratch/agent-spec-lab/` | The 63-test offline lab for patch semantics; its `LAB_NOTES.md` records the proven failure modes. |

The fixture is the load-bearing one: because the upstream dataset is **provably static**
(byte-identical across calendar days), a committed snapshot is a faithful stand-in and will
not go stale. That is what makes the whole test suite runnable without network access.

## Also not in this folder

- **`plans/agents/`** — meta-docs consumed by tooling (issue-tracker layout, triage labels,
  domain conventions). Pre-existing; untouched by this reorganisation.

## Next steps

A **PRD** drawing `decisions/` together into one buildable specification, then numbered issues
derived from it.
