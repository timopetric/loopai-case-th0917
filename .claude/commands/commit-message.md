---
description: Generate a commit message for staged changes by inspecting git history for style and conversation context for intent
---

Generate a commit message for the currently staged files.

**Step 1 — Gather context (run in parallel):**
- Run `git diff --stat HEAD` to see which files are staged and the scope of changes
- Run `git log -5 --format="%H%n%B%n---END---"` to read the last 5 commit messages in full for style reference
- Scan the current conversation history for what was implemented (intent, scope, key decisions)

**Step 2 — Draft the commit message** in this exact format:

```
<type>(<scope>): <short imperative subject line>

<2–3 sentence description>: what changed and why — the problem solved
or the decision made, not a list of files.

- <bullet>: one logical change per bullet, grouped by layer or concern
- <bullet>
- <bullet>
...
```

Rules:
- Subject line: conventional commits format (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`); imperative mood; no period; ≤72 chars
- Description paragraph: 2–3 sentences max; explain the *why* and the overall shape of the change, not the file list
- Bullets: one per logical concern (not per file); include enough detail to understand what changed without reading the diff; keep each bullet to 1–2 lines
- Match the verbosity and tone of the existing commit history — if the repo uses terse bullets, be terse; if it uses fuller sentences, match that
- Do not invent scope; derive it from the staged files and conversation context
- Be concise and to the point.

**Step 3 — Output** the commit message as a plain fenced code block so it can be copied directly.

Do not commit anything. Output only the message.
