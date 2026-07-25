---
name: to-handoff
description: After a grilling/design session, drive the full delivery chain non-interactively — invoke to-prd, then to-issues, then handoff back-to-back, supplying the standing default choices so no approval gates stop the flow. Use once you've decided grilling is done and want a PRD, issues, and a handoff without babysitting each step.
argument-hint: "(optional) what the next session will focus on — passed through to handoff"
---

# To Handoff

You've just finished a design/grilling session (typically `/grill-with-docs`). Everything
after this point — PRD → issues → handoff — is mechanical: the user picks the recommended
default every time. This skill drives that chain end-to-end so the user runs **one command
instead of three plus two approval gates**.

## What this skill is (and is NOT)

- It is a **thin orchestrator**. It invokes `to-prd`, then `to-issues`, then `handoff`
  **one at a time via the Skill tool**, in that order — exactly as the user would type them
  by hand. It does NOT re-implement or copy their templates; those three skills remain the
  single source of truth for their own behavior.
- The one thing it adds: it **pre-supplies the answers** to the confirmation questions those
  skills would otherwise stop and ask, using the user's standing defaults below.

## Autonomy contract

- **Do not open an approval gate.** No `AskUserQuestion` for the module/test scope or the
  issue split — those decisions are pre-answered below.
- **Stay visible.** As you pass each pre-filled choice, state it in one line ("Passing to
  to-prd: extract all deep modules, test everything incl. contracts + trigger wiring") and
  print the resulting artifact summary before moving on. The user can interrupt (Esc) and
  correct for the rare 1% case; absent that, proceed.
- **Only stop for genuine blockers** — a real ambiguity or contradiction the grilling never
  resolved, not a routine preference. If you must stop, ask the single narrowest question,
  then continue the chain.

## Standing default choices to supply

These are the choices the user has picked every time; pass them into the sub-skills so their
confirmation steps are already answered:

**For `to-prd`:**
- User stories are **concrete and exhaustive** — cover everything discussed in the session,
  in `As an <actor>, I want <feature>, so that <benefit>` form.
- **Extract all** identified deep modules (don't ask which subset).
- Mandate tests for the **widest** scope: pure modules **+** endpoint/contract tests **+**
  end-to-end trigger/wiring tests.
- Write any ADRs that crystallized during grilling first (to-prd's own flow already covers
  this), then the PRD. Publish with the `ready-for-agent` triage label.

**For `to-issues`:**
- Use the **finest reasonable tracer-bullet split** — prefer many thin vertical slices over
  few thick ones (this is the "most issues" split the user always takes).
- Dependency order, **AFK-preferred**, publish with the `ready-for-agent` label.

## Process

1. **to-prd** — invoke the `to-prd` skill. Announce the standing choices above as you pass
   them; do not stop to confirm. When it finishes, print a one-block PRD summary + path.

2. **to-issues** — invoke the `to-issues` skill. Announce the finest-split choice; do not
   quiz. When it finishes, print the numbered slice breakdown + dependency shape.

3. **handoff** — invoke the `handoff` skill. Pass this skill's argument through as the
   next-session focus. If no argument was given, default the focus to **implementing the
   just-published issues with TDD** and suggest `/tdd-implement-scope` as the next skill.

4. **Close out** — print a compact final index: PRD path, issues directory, handoff file
   path, and the exact command to run in the next session.

If the user passed an argument, treat it as the handoff focus and thread it through step 3.
