# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`plans/decisions/CONTEXT.md`** — the domain glossary. Single-context repo; there is no `CONTEXT-MAP.md`.
- **`plans/decisions/adr/`** — read ADRs that touch the area you're about to work in.

Also know what is *not* authoritative: `plans/old_decision_depricated/` is superseded, and
`scratch/` is evidence containing conclusions that were later overturned — read
`scratch/README.md` before using anything from it. The trusted spec is `plans/decisions/`.

If any of these files don't exist, **proceed silently**. (In this repo they all exist.) Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo (single context, docs under `plans/`):

```
/
├── AGENTS.md               ← root router (CLAUDE.md is a symlink to it)
├── plans/
│   ├── CLAUDE.md           ← index of everything in plans/
│   ├── decisions/          ← THE TRUSTED SPEC
│   │   ├── CONTEXT.md      ← domain glossary
│   │   ├── adr/            ← 0001-…, 0002-…, 0003-…
│   │   └── architecture.md, api-report-fresh.md, idea.md, …
│   ├── issues/<slug>/      ← PRD.md + numbered issues
│   ├── old_decision_depricated/   ← superseded, audit trail only
│   └── agents/             ← this file and its siblings
└── scratch/                ← evidence, not spec (see its README first)
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `plans/decisions/CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
