# loopai — agent router

InTheLoop take-home, Case TH-0917: a report builder over one upstream helpdesk statistics API,
with CSV/Excel export and an LLM assistant that builds reports from plain English.

**This file is a router. It points; it does not duplicate.** If a section here grows past a few
lines, it belongs in a doc and this file keeps only the pointer.

## What to trust

| Location | Status |
|---|---|
| `plans/decisions/` | **Authoritative.** Current, agreed spec. Build against this. |
| `plans/issues/<slug>/` | PRD and implementation issues. |
| `plans/old_decision_depricated/` | **Superseded.** Audit trail only — never build from it. |
| `scratch/` | **Evidence, not spec.** Contains conclusions later overturned. **Read `scratch/README.md` before using anything in there.** |

Where two documents disagree, `plans/decisions/architecture.md` wins.

## Where things are

- **Spec index** — `plans/CLAUDE.md` describes every file in `plans/` and when to read it.
- **Glossary** — `plans/decisions/CONTEXT.md`. Read before naming anything.
- **ADRs** — `plans/decisions/adr/`. Read the ones touching your area before changing behaviour.
- **Upstream API contract** — `plans/decisions/api-report-fresh.md`. This **overrides** the
  vendor's published `/spec`, which is wrong in ~19 places.
- **Technical design** — `plans/decisions/architecture.md`. The operational spine: modules,
  tool surface, repair taxonomy, SSE events, deployment, verification ladder.
- **Issue tracker conventions** — `plans/agents/issue-tracker.md`.
- **Triage labels** — `plans/agents/triage-labels.md` (`needs-triage`, `needs-info`,
  `ready-for-agent`, `ready-for-human`, `wontfix`).

## Vocabulary — one trap worth stating here

**"Agent" is banned as an unqualified term.** It meant three different things. Use **Actor** for
a support person or upstream `actors` entry, and **Assistant** for the LLM. Everything else —
Report Spec, Duration Metric, Coverage Window, Tool Step, Repair, Warning — is in the glossary.

## Before you touch upstream data

Three mistakes are expensive and easy to make. Full detail in `api-report-fresh.md`; these are
the pointers, not the explanations:

1. **Duration metrics are in HOURS**, not the documented seconds, and each is a *sum* with a
   `_count` companion. Aggregate as `Σvalue / Σcount` — never average the averages.
2. **There is no Actor × Mailbox cross-tab** and never can be. The two breakdowns are
   independent marginals.
3. **Out-of-range dates fail open** — the upstream silently returns its whole window. Validate
   locally against the Coverage Window before calling.

## Commands

```
make check      # lint + typecheck + unit + API-level tests — offline, run after every edit
make backend    # uvicorn --reload, own terminal
make frontend   # vite dev server, own terminal
make run        # the built image — required target for browser verification
```

Verification is a three-level ladder (`architecture.md` §12): `make check`, then a browser via
Chrome DevTools MCP against development fakes, then a browser against live services. **Reach
level 3 before declaring work done.**

## Hard rules

- **No `VITE_*` or any build-time frontend configuration.** All API calls use relative paths.
  A build-time value would bind the image to the machine that built it and fail only in
  production, after a green deploy.
- **Never parse assistant prose as tool calls.** Denied real tools, the model emits fabricated
  tool-call JSON as text; acting on it is an execution risk.
- **Never send tool names, arguments, prompts or raw model reasoning to the browser.**
- **Never log** the shared API key, the OpenRouter key, or full prompts.
- `DEV_FAKE_UPSTREAM` / `DEV_FAKE_LLM` are development-only; the app must refuse to start if
  they are set anywhere else (ADR-0003).
