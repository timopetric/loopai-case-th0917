Update CLAUDE.md files based on the changes made in this conversation. Follow the leaf-to-root information flow described below.

## What to update

1. **Identify changed files** from this conversation (new files, edited files, deleted files).
2. **Group by directory**. For each affected directory — and each ancestor up to the repo root — decide whether its CLAUDE.md needs updating or creating.
3. **Write changes bottom-up** (leaf directories first, then parents).

## Information flow: leaf → root

Each level should contain only what is *not already visible* from reading the code or a child CLAUDE.md. Progressive disclosure:

| Level | What belongs here |
|-------|------------------|
| **Leaf dir** (e.g. `widget/src/components/`) | Non-obvious implementation details: data flow, key invariants, tricky contracts, render rules, CSS conventions, why a choice was made. Specific file-level facts belong here. |
| **Mid dir** (e.g. `widget/src/`, `backend/app/services/`) | Module-level architecture: directory layout table, entry-point description, cross-file contracts, patterns used across the directory. No duplication of leaf content. |
| **Package root** (e.g. `widget/`, `backend/`, `frontend/`) | Build/dev commands, public API surface, integration points with other packages. Reference child dirs by name only — no copy of their content. |
| **Repo root** (`CLAUDE.md`) | Architectural decisions, cross-package contracts, key env vars, port map, deployment. Never repeats what's in package CLAUDE.md files. |

## Writing rules

- **Edit only what changed** — no reformatting, no new sections for unchanged areas.
- **Be concise**: short sentences, bullet points, tables. No prose padding.
- Lead with the non-obvious. If Claude can infer it from reading the code in 5 seconds, skip it.
- Mention short relative file paths (`api/v1/routers/chatbot.py`) when they make context easier to find.
- Create a CLAUDE.md for a directory only if there is genuinely useful, non-obvious context to document there.
- If a section in an existing CLAUDE.md is now wrong or stale, fix or remove it — don't leave contradictory information.

## Output

After all edits, print a one-line summary per file touched: `UPDATED`, `CREATED`, or `REMOVED` and the relative path. Nothing else.
