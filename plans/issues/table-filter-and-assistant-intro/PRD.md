Status: ready-for-agent

# PRD — Row filtering, a visible Assistant reasoning trace, and a hard-coded introduction

Source: a `/grill-with-docs` session on 2026-07-27, working from
[`HANDOFF.md`](HANDOFF.md) in this same directory. Every decision below was interviewed
branch-by-branch against the actual code (`app/models.py`, `app/engine.py`,
`app/agent/presenter.py`, `app/agent/tools.py`, `app/agent/events.py`, `frontend/src/Chat.tsx`,
`frontend/src/workspace/BuilderPane.tsx`, `frontend/src/store/reportSpecStore.ts`,
`app/exporters.py`, `app/spec_url.py`) rather than assumed — file/line references in the
grilling transcript back each decision below.

## Problem Statement

Three gaps, reported directly by the product owner after using the app:

1. **The report table has no way to narrow rows to one Actor or Mailbox.** Typing `theo` should
   show only Theo's rows — today there is no such control anywhere, in the builder rail or the
   Assistant.
2. **The Assistant's "thinking" indicator is functionally invisible.** On a real turn, it either
   flashes past too fast to read, or — because raw reasoning text is gated to development only
   — there is nothing behind it to read even when it does show. The owner wants to actually see
   what the Assistant is reasoning about, by default, in production, not just a pulsing dot.
3. **A new user has no idea what the Assistant can do.** The chat opens with one placeholder
   line. The owner discovered the pivot-layout capability by accident, by asking for it, with
   nothing in the UI suggesting it existed.

## Solution

- A new `entity_filter` field on the Report Spec: a free-text, case-insensitive substring match
  against Actor or Mailbox names (whichever the report is currently grouped by), landing in the
  engine (so preview, exports, and the Assistant's `run_report` all agree automatically), exposed
  both as a builder-rail text input and a new Assistant tool, `set_filter`.
- The Assistant's reasoning stream becomes a permanent, default-on product feature: raw
  chain-of-thought streams to every user, rendered as markdown, collapsible, persisted per
  message in the chat history — reversing a previously-hard architectural rule that gated this to
  development only (**ADR-0005**, already written to `plans/decisions/adr/0005-stream-raw-reasoning-to-all-users.md`).
- A short, hard-coded (no model call) Assistant greeting replaces the placeholder line, naming 3-4
  of the most surprising capabilities with concrete example prompts to try, including the new
  filter.
- Along the way: the system prompt and the tool-schema descriptions the model actually reads get
  substantially rewritten per current tool-calling best practice (researched live during this
  session — Anthropic/OpenAI/LangChain converge on "the schema `description` field should be
  self-contained and exhaustive"), and a previously-flagged, unrelated leak (`_diff_chips` showing
  a wire enum value instead of a label) gets fixed while the same file is open.

## User Stories

1. As a report reader, I want to type an Actor's name into a text field, so that the table shows
   only that Actor's rows without me re-grouping or scrolling to find them.
2. As a report reader, I want the same filter to apply when I'm grouped by Mailbox instead, so
   that I can narrow by inbox name the same way I narrow by person.
3. As a report reader, I want my typed filter to match partial names (`theo` matches `Theo
   Mancini`), so that I don't need to know or type someone's exact full name.
4. As a report reader, I want the filter input to visibly explain why it's inert when I'm not
   grouped by Actor or Mailbox, so that I don't wonder whether it's broken.
5. As a report reader, I want the Total row to reflect only the filtered rows, so that the footer
   agrees with what's actually on screen above it.
6. As a report reader, I want a clear on-screen warning when my filter matches nobody, so that an
   empty table reads as "no match" rather than as a bug.
7. As a report reader, I want my filter text preserved even if I temporarily switch grouping to
   "None", so that toggling grouping back and forth doesn't make me re-type it.
8. As a report reader, I want the filter to survive a shared report link, so that a filtered view
   I send a colleague opens already filtered.
9. As a report reader, I want a downloaded Excel file to state what filter (if any) produced it,
   so that I don't mistake a filtered export for the complete dataset.
10. As a report reader, I understand a downloaded CSV will not state the filter in the file itself
    (CSV is pure data, by existing design) — the row count itself is the only signal in that
    format, matching how CSV already doesn't self-describe date range or grouping either.
11. As an Assistant user, I want to type "filter to just Theo's numbers" in plain English, so that
    I don't have to touch the builder rail at all.
12. As an Assistant user, I want the Assistant to resolve a loosely-typed name (checking the real
    Actor/Mailbox list first if it's unsure) before filtering, so that a fuzzy request still lands
    on the right person.
13. As an Assistant user, I want the Assistant to tell me plainly when my filter request has no
    effect because the report isn't grouped by anything, so that I understand why nothing visibly
    changed.
14. As an Assistant user, I want to clear a filter I previously set (by asking, or by clearing the
    rail input), so that I can go back to seeing everyone.
15. As an Assistant user, I want the Assistant's own summary of a multi-step change to optionally
    show a small table (e.g. what changed, or the report's new row/column count) when that's
    clearer than a sentence, so that a complex change is easy to scan — but I don't want every
    reply padded with a table when a sentence would do.
16. As an Assistant user, I want to see the Assistant's actual reasoning while it works, rendered
    as readable markdown, not just a pulsing dot, so that I understand what it's doing and why.
17. As an Assistant user, I want a distinct "waiting for a response" state before reasoning starts
    and a "thinking" state once it does, so that I can tell the difference between "request sent,
    nothing back yet" and "the model is actively working."
18. As an Assistant user, I want the reasoning panel collapsed by default once a turn finishes, but
    easy to re-open, so that finished turns don't clutter the chat but the trace isn't lost either.
19. As an Assistant user, I want a manual collapse/expand I perform mid-turn to be respected (not
    snapped back open by the next auto-update), so that the panel behaves like any other
    collapsible control.
20. As an Assistant user, I want the collapsed reasoning summary to still show a subtle "still
    working" signal if the model hasn't finished that step yet, so that collapsing the text
    doesn't make we lose track of whether it's done.
21. As an Assistant user, I want each past turn's reasoning trace to remain in the chat history
    (not wiped by the next message I send), so that I can scroll back and re-read how an earlier
    change was reasoned through.
22. As a new user, I want the chat to open with a short greeting stating what the Assistant can do
    and a couple of concrete things to try, so that I discover capabilities I wouldn't find by
    staring at the builder rail.
23. As a new user, I want that greeting to mention the new filter with a concrete example ("try:
    filter to just Theo's numbers"), so that I know it exists from the very first screen.
24. As a developer reading the Assistant's conversation, I want every Repair chip to show the
    label the rail already uses ("Handle time (h)"), never the wire enum value
    (`handle_time`), so that the conversation never contradicts the glossary's own vocabulary
    rule.
25. As the product owner, I want a written ADR documenting the reversal of the "reasoning text is
    dev-only" rule, so that a future reader of the code isn't misled by comments that still
    describe the old policy, and so the tradeoff being accepted is on record, not implicit.

## Implementation Decisions

### `entity_filter` — the Report Spec field

- New field: `ReportSpec.entity_filter: str | None = None`. A pydantic field validator normalizes
  empty and whitespace-only input to `None` and trims surrounding whitespace on any non-empty
  value — "filter is set" and "filter has a non-empty value" can never disagree, matching how
  `columns_order`/`chart_metric` already use `None` to mean "not set" throughout this model.
- Matching is a plain case-insensitive substring check against `EntityBreakdown.name`
  (`query.lower() in name.lower()`) — no diacritic/accent folding. Verified against the real
  fixture (`scratch/resp-full-unscoped-latest.json`): all 211 Actor/Mailbox names are plain ASCII,
  so accent-folding solves a problem that does not exist in the real dataset.
- The field has an effect only when `group_by != "none"`; it filters Actor rows under
  `group_by == "agent"` and Mailbox rows under `group_by == "mailbox"`. One field, not two
  independent ones — it follows whichever grouping is currently active, mirroring how `group_by`
  itself is already a single scalar rather than a pair of booleans.

### Engine behavior (three previously-undecided edge cases, now settled)

- **Totals reflect the filtered rows**, not the full dataset — the footer must agree with what's
  above it. This is a deliberate, noted exception to `engine.py`'s existing "totals are
  recomputed from the top-level dataset, never from summed rows" rule; that rule's purpose
  (avoiding "averaging averages") is orthogonal to filtering, which operates on which rows are
  included in the first place, not how a row's own average is computed.
- **A filter that matches nothing produces an empty table plus a Warning** naming the exact typed
  query (e.g. `No Actor/Mailbox name matched "theo mancinni" — showing an empty report.`). The
  warning echoes the raw user-typed string; this is confirmed safe because `ReportTable.warnings`
  renders through plain JSX string interpolation in `ReportTable.tsx` (no `dangerouslySetInnerHTML`,
  no markdown renderer on that path) — the same rendering path every other warning (e.g. the
  clamped-date-range message) already uses to echo derived-from-user-input values.
  is set but `group_by == "none"`, the backend **repairs, not rejects**: the filter is ignored and
  a new `RepairCode` member (`ENTITY_FILTER_IGNORED`, fixed phrase "entity filter has no effect
  without grouping by Actor or Mailbox") is reported, exactly matching ADR-0002's established
  "cross-field drift is repaired and reported, never rejected" pattern. This is a genuinely
  reachable state, not defensive-only code: the frontend deliberately keeps `entityFilter` alive
  in the store even while the rail control is disabled (see below), so a user toggling grouping to
  "None" with a filter still typed will actually send this combination.

### Frontend — builder rail

- New "Filter" section in `BuilderPane.tsx`, placed directly below "Grouping", using the existing
  `TextInput` primitive — always rendered, `disabled` with an explanatory placeholder (e.g.
  "Group by Actor or Mailbox to filter") when `groupBy === "none"`, rather than appearing/
  disappearing as grouping changes (avoids rail layout reflow on every grouping toggle). Label
  reads "Filter by Actor name" or "Filter by Mailbox name" depending on current `groupBy`.
- The rail input debounces (~300-400ms after typing stops) before writing to the Zustand store —
  a bare `onChange` writing straight to the store would fire a network request and a chart
  re-render on every keystroke. The store's `entityFilter` field, once written, is treated
  identically to every other spec field by the existing report-fetch effect and the existing
  URL-sync effect in `WorkspaceShell.tsx` (both are already un-debounced and use
  `history.replaceState`, confirmed by reading the current code — no new debounce layer needed
  anywhere downstream of the store write).
- The rail control **never emits a chip** — chips remain exclusively an Assistant-conversation
  concept (`ChatMessage.chips`), matching how every other rail control (metrics, dates, grouping)
  already behaves with no chip of its own.
- The store keeps `entityFilter`'s value even while the rail control is disabled (toggling
  grouping to "None" does not clear it) — switching grouping back restores the filter exactly as
  the user left it, and this is what makes the `group_by == "none"` + filter-set Repair a real
  path the backend must actually handle.

### `app/spec_url.py`

- `entity_filter` round-trips through the URL query the same way `chart_metric` does: present in
  `encode_spec`'s output only when non-`None`, decoded the same way, so a filtered report survives
  a shared link.

### `app/exporters.py`

- **XLSX**: the existing "Report info" sheet's "Report definition" section gets one new,
  **unconditionally present** row, `["Entity filter", spec.entity_filter or "None"]`, placed
  after "Grouped by" — matching the sheet's existing style, where every spec dimension (Metrics,
  Date range, Granularity, Grouped by, Duration display, Layout) already prints a row every time,
  never conditionally omitted. No separate "N of M matched" row — the sheet doesn't report
  match/row counts for any other dimension today, so adding one only for the filter would be new
  scope, not filling a gap; the empty-match case is already covered for free by the existing
  "Warnings" section, which already lists `table.warnings` unconditionally.
- **CSV**: no change. CSV's "pure data, no preamble" rule (architecture.md §3) is a settled,
  deliberate constraint that already means CSV doesn't self-describe date range or grouping
  either — a filtered CSV simply has fewer rows, with no in-file explanation, matching every
  other spec dimension's existing (non-)treatment in that format. The export filename also stays
  unchanged (it currently encodes only the date range, nothing else) — adding a filter-only
  filename marker would be inconsistent special-casing of one spec field over several others that
  equally affect row count and get no filename treatment today.

### The Assistant tool: `set_filter`

- `set_filter(query: str)` — a single required string field, no `Optional`. An empty string
  clears the filter, using the exact same `.strip() or None` normalization already applied to the
  Report-Spec-level field (Q8's answer) — no second, tool-only representation of "clear."
- No name-resolution logic inside the tool itself: the engine's substring match already tolerates
  loose input identically whether it comes from the rail or the Assistant. Precision is a
  prompting concern, not a schema one — the system prompt tells the Assistant it may call
  `get_meta` first (already an existing tool, already returns every Actor/Mailbox id+name pair,
  ~211 entries, cheap) if it wants to confirm a name before filtering.
- Presenter additions: `_STATUS_TEXT["set_filter"]`, a `_diff_chips` entry (`f"Filter: {after
  .entity_filter}"` when set, `"Filter cleared"` when unset), and a `_repair_chip` entry for
  `ENTITY_FILTER_IGNORED`.
- `_run_report`'s tool-result dict gains an always-present, nullable `"entity_filter"` field —
  self-describing the active filter on every call, rather than relying on the model's own
  short-term memory of having just called `set_filter` in the same turn. This mirrors `get_meta`'s
  existing "always return full context, never assume the model remembers" pattern.

### The outstanding enum-leak fix (bundled in, per the handoff's own instruction)

- `_diff_chips`'s `"Added metric: {m.value}"` / `"Removed metric: {m.value}"` currently print the
  wire enum value (`handle_time`) instead of the label the rail already shows ("Handle time (h)"
  minus the unit suffix, i.e. `_metric_label(m)`, already defined in the same file). One-line fix
  plus reusing the existing helper — this was flagged as a known, unfixed finding in the handoff
  and is now in scope because this same file (`presenter.py`) is already being modified for the
  filter's chips.

### The reasoning/"thinking" indicator — default-on, in production (ADR-0005)

- **Backend**: `app/api/v1/routers/agent.py` passes `include_reasoning_text=True`
  unconditionally — the `settings.is_development` gate is removed. `ThinkingTextEvent` now
  streams to every user, every environment.
- **This is a deliberate, permanent reclassification of what "browser-safe" means for reasoning
  text**, recorded in `plans/decisions/adr/0005-stream-raw-reasoning-to-all-users.md` (already
  written during the grilling session). `architecture.md` §6 and `app/agent/events.py`'s
  docstrings need their "must be gated on the environment flag, never shipped to production"
  language corrected to match — those comments currently describe the policy being reversed here
  and would flatly mislead the next reader if left as-is.
- **Accepted, explicit residual risk**: raw chain-of-thought will sometimes name internal tools
  (`set_metrics`, `get_meta`) or enum values (`"agent"`/`"mailbox"` wire values) — this
  contradicts the standing "never show tool names or enum values in the conversation" rule, but
  only for the reasoning panel specifically; that rule is unchanged and still fully enforced for
  the Assistant's actual reply (`token`/`chips`/`spec`/`error` events, and everything
  `_diff_chips`/`_STATUS_TEXT`/`_ERROR_TEXT` produce).
- `app/agent/fake_model.py`'s scripted `ReasoningDelta` strings get reworded to remove unqualified
  "agent" (e.g. "per-agent breakdown" → "per-Actor breakdown") — this fixture's text is no longer
  an internal-only test artifact once reasoning is shown to every user by default; it is exactly
  the content every dev/demo walkthrough will show first.

### Frontend reasoning UI — state machine and data model

- `reasoning` moves from single shared `Chat` component state onto each `ChatMessage` (a new
  `reasoning: string` field alongside the existing `text`/`chips`), so every turn keeps its own
  permanent, scrollable, re-expandable reasoning trace — consistent with how `chips` already
  persist per message rather than being wiped by the next turn.
- Reasoning text is segmented into paragraphs at each Tool Step boundary: a separator is inserted
  whenever `thinking: start` fires and the message's `reasoning` is already non-empty, so a
  multi-Tool-Step turn (the architecture's own documented case — `thinking` fires once per Tool
  Step) reads as distinct bursts of thought, not one run-on string.
- Rendered through the existing `Markdown`/`Streamdown` component — same sanitize pipeline
  already used for the Assistant's replies, no new renderer.
- **Three visual states per message**, in order:
  1. **Waiting** — `busy` is true, no `thinking: start` has fired yet for this message, no
     reasoning text has arrived. Plain, non-animated "Waiting for a response…" text. This state
     requires **no new backend event** — it is entirely derivable from client-side facts the
     frontend already has the instant `send()` is called (a request is in flight; nothing has
     come back). Considered and rejected: an explicit `turn_start` SSE event — it would carry no
     information the client doesn't already have at the moment it clicks Send.
  2. **Thinking** — `thinking: start` has fired for the current Tool Step. Animated pulsing-dot
     indicator, panel auto-expanded, showing the accumulating reasoning text as markdown.
  3. **Collapsed** — after `thinking: end` (or `done`), the panel auto-collapses by default. The
     collapsed summary line **keeps the pulsing animation** if that specific Tool Step's model
     call is still genuinely in flight (i.e., the user manually collapsed it while `thinking` was
     still true) — it only becomes a static, inert summary once the whole turn reaches `done`.
     This distinguishes "collapsed but still working" from "collapsed and finished," rather than
     conflating them.
- **Manual override respected mid-turn**: if the user manually collapses/expands a message's
  panel while its Tool Step is still active, that choice is not overridden by the next
  auto-collapse/auto-expand transition for *that* message. The *next new* turn still starts fresh
  with the default auto-expand-on-start behavior — this is not a persisted global preference
  (considered and deferred as unnecessary scope for this pass; can be added later if the default
  proves annoying).
- Bug fix bundled in: `reasoning` currently accumulates across the entire session in
  `Chat.tsx` (never reset between turns) — moving it onto each message and starting a new empty
  string per turn fixes this as a side effect of the redesign.

### System prompt and tool-schema descriptions (`app/agent/tools.py`, `app/agent/prompts/report_agent_system.jinja`)

- **Section structure**: convert the system prompt from `##` markdown headings to XML-tag
  sections (`<coverage_window>`, `<metric_catalogue>`, `<tools>`, etc.). Live research during
  this session found the strongest evidence for XML-tag structuring is Claude-specific, and one
  source explicitly recommends markdown for Qwen-family models — this decision was surfaced and
  the owner chose to proceed with XML anyway, to be settled empirically by re-running the
  existing live smoke test (`scratch/fresh-eyes/llm-smoke-tool-calling.py`) against the real model
  after the rewrite, rather than pre-deciding from general guidance alone.
- **No hand-authored few-shot tool-call examples.** Originally planned, then reversed after
  research: Qwen3's own documentation warns that ReAct-style stopword/action-marker few-shot
  templates can leak into the model's own `<think>` block and corrupt tool-call parsing — the
  same class of risk architecture.md's existing Guard 1 (never parse assistant prose as tool
  calls) already exists to contain. Given that specific, model-family-documented risk, no worked
  user→tool-call→answer transcripts are added to the prompt.
- **Tool-schema `description` strings get substantially rewritten**, for all 9 existing tools plus
  the new `set_filter` — self-contained, 3-4+ sentences each, stating not just what the tool does
  but *when* to use it and its edge-case/repair behavior, per convergent Anthropic/OpenAI/
  LangChain guidance gathered live during this session (Anthropic: "detailed descriptions are by
  far the most important factor in tool performance"; OpenAI: describe when/when-not to call each
  function; LangChain: description should state when to use the tool, not just restate its name).
  This is where the weight that few-shot examples would have carried now goes instead.
- `set_filter`'s description must be fully self-sufficient (not dependent on the system prompt to
  explain substring matching or the `group_by == "none"` interaction) — e.g. stating the
  case-insensitive substring behavior, that an empty string clears it, and that it has no effect
  without Actor/Mailbox grouping (reported by the backend, not an error), directly in the schema
  description.
- **The Assistant's final prose may optionally use a small markdown table** when summarizing a
  change whose *shape* is naturally tabular (e.g. columns/row-count changed) — a plain style-note
  instruction only, no embedded example table (markdown table syntax is generic and
  well-represented in general model training, unlike a bespoke tool-call transcript, so the
  anchoring risk that ruled out few-shot tool-call examples doesn't apply here). This is
  explicitly **not** a replacement for chips: chips remain the deterministic, guaranteed-accurate
  summary of what changed; the optional table is the model's own prose formatting choice, used
  only when it judges a table clearer than a sentence, kept small, never a full row-data dump, and
  not expected on every turn.

### The Assistant's hard-coded introduction (`frontend/src/Chat.tsx`)

- Replaces the current placeholder line (`"Ask for a report in plain English — e.g. ..."`),
  rendered when `messages.length === 0`, through the existing `Markdown` component. Hard-coded,
  no model call, no tokens, instant on load — unchanged from the original handoff's framing.
- Names 3-4 of the most-surprising capabilities as concrete, literal "try:" examples embedded in
  the copy itself (not just abstract capability descriptions) — pivot layout remains the headline
  example (the one capability the owner has personally already been surprised by), and the new
  filter is included as one bullet with the owner's exact chosen wording: **"try: filter to just
  Theo's numbers."**
- Vocabulary constraints apply as they do everywhere else: Actor/Mailbox/Coverage Window
  terminology, never an unqualified "agent," never a tool name or enum value in the copy.

## Testing Decisions

Good tests here assert observable behavior (what a caller/user sees) rather than internal
implementation shape — matching this repo's existing style (`tests/test_engine.py`,
`tests/test_agent_tools.py`, `tests/test_agent_presenter.py`, `tests/test_api.py`,
`tests/test_spec_url.py` are all direct prior art for the modules below).

- **`app/models.py` (`entity_filter` validator)**: unit tests asserting `""`/`"   "` normalize to
  `None`, surrounding whitespace is trimmed on a real value, and the field round-trips through
  normal construction — pure, no I/O.
- **`app/engine.py`**: unit tests against the committed fixture dataset covering: substring match
  works (partial name), case-insensitivity, totals reflect only filtered rows, empty-match
  produces an empty row set plus the exact expected warning text, and `group_by == "none"` with a
  filter set produces the `ENTITY_FILTER_IGNORED` Repair and otherwise renders normally,
  ungrouped. Same fixture and assertion style `tests/test_engine.py` already uses for the
  non-additive-metric and zero-count-average cases.
- **`app/spec_url.py`**: extend the existing round-trip test to include `entity_filter`, both set
  and absent, mirroring how `chart_metric` is already tested there — this file's own docstring
  notes fields are enumerated from `ReportSpec.model_fields` specifically so an added field that
  isn't taught to the encoder fails a test rather than shipping a silently-broken link.
- **`app/exporters.py`**: unit test asserting the XLSX "Report info" sheet contains the "Entity
  filter" row with the correct value (and `"None"` when unset), and a CSV test confirming the file
  is byte-for-byte unaffected by `entity_filter`'s presence beyond the row count itself (i.e., no
  accidental preamble leak).
- **`app/agent/tools.py`**: unit tests for `_set_filter` covering the clear-via-empty-string case,
  the `group_by == "none"` repair path, and a case-insensitive substring match — same style as
  the existing `TestSetGroupingOrphaningSort`-class tests already in `tests/test_agent_tools.py`.
- **`app/agent/presenter.py`**: unit tests for the new `_diff_chips` filter-set/filter-cleared
  chip text, the `ENTITY_FILTER_IGNORED` repair chip text, and — bundled fix — a regression test
  asserting `"Added metric: Handle time"` (the label), never `"Added metric: handle_time"` (the
  wire value), closing the handoff's previously-flagged outstanding finding.
- **`app/api/v1/routers/agent.py` / API-level (`test_api.py`)**: extend the existing SSE-ordering
  and no-leak assertions to cover the new default-on reasoning text — specifically, a test that
  `thinking_text` events are present **without** `settings.is_development` being set (proving the
  gate is actually gone, not just conditionally passing), and that the existing "no tool name,
  argument, or prompt fragment appears anywhere in the stream" assertion is updated to its new,
  narrower scope (tool names/enums may now legitimately appear inside `thinking_text` specifically,
  per ADR-0005 — the assertion must be revised to check `token`/`chips`/`status`/`error` events
  only, not blanket-fail on any occurrence anywhere in the stream).
- **Frontend**: this project does not unit-test the frontend (established precedent, per
  `spec_url.py`'s own docstring) — the reasoning state machine (waiting → thinking → collapsed,
  manual-override respect, per-message persistence) and the filter rail control are verified via
  the Level 2/3 browser checklist below, not source-level tests.
- **Live smoke test**: re-run `scratch/fresh-eyes/llm-smoke-tool-calling.py` (or an updated
  version covering `set_filter`) against the real model after the prompt/tool-description rewrite,
  to empirically confirm the XML-tag structure and richer descriptions haven't regressed
  tool-calling accuracy — this is the test that actually settles the XML-vs-markdown question the
  research left open.
- **Browser verification, ordered as the final step** (per explicit instruction this session):
  `make check` first for every change, but the full Chrome DevTools MCP walkthrough — sign in,
  exercise the filter rail control and the Assistant's `set_filter` path, watch the three-state
  reasoning indicator live, confirm the hard-coded intro renders, verify a filtered CSV/XLSX
  export — is the **last** thing done before declaring this work complete, matching
  architecture.md §12's existing "Level 3 last, once" rule, extended here to explicitly gate on
  finishing everything else first rather than being interleaved mid-implementation.

## Out of Scope

- An Actor/Mailbox multi-select picker (the PRD's previously-deferred feature) — the substring
  filter is treated as its cheaper replacement for this pass, not built alongside it.
- Diacritic/accent-insensitive matching — no real data in the current fixture needs it; revisit
  only if the upstream dataset ever adds non-ASCII names.
- A persisted global user preference for reasoning-panel default-collapsed/expanded state — only
  per-turn and per-message behavior is built now.
- A deterministic, chip-derived "changes" table UI element — considered and explicitly rejected in
  favor of chips remaining the sole deterministic summary; the model's own optional markdown table
  is prose formatting, not a new structured component.
- Reworking `set_sort`'s tool description for its within-bucket-not-global semantic, and any other
  pre-existing tool-description weaknesses not directly touched by this pass's broader rewrite —
  covered by the rewrite itself since all 9 descriptions are in scope, but no dedicated
  regression-hunting pass beyond that.
- A sanitize/rewrite pass on reasoning text to strip tool names/enum values before display — this
  was a considered-and-rejected alternative to ADR-0005's chosen approach (ship the raw text,
  accept the leak), not a deferred future task with a committed timeline.

## Further Notes

- **Housekeeping carried over from the grilling session, to do before/alongside implementation**:
  add ADR-0005 to `plans/CLAUDE.md`'s ADR summary table (currently lists only 0001-0004); correct
  `architecture.md` §6's and `app/agent/events.py`'s docstring language to match ADR-0005's policy
  rather than describing the reversed dev-only gate.
- This PRD's scope spans backend (`app/models.py`, `app/engine.py`, `app/exporters.py`,
  `app/spec_url.py`, `app/agent/tools.py`, `app/agent/presenter.py`,
  `app/api/v1/routers/agent.py`, `app/agent/fake_model.py`, the jinja prompt) and frontend
  (`frontend/src/Chat.tsx`, `frontend/src/workspace/BuilderPane.tsx`,
  `frontend/src/store/reportSpecStore.ts`) — the finest reasonable tracer-bullet issue split
  should still keep each issue's vertical slice runnable and independently verifiable via
  `make check`, per this repo's existing per-slice-commit convention
  (`plans/issues/frontend-rework/HANDOFF.md` is the precedent for that style).
- The full multiple-choice interview transcript behind every decision above lives in this
  conversation's history; where a decision's reasoning matters more than this summary captures
  (e.g. the exact wording tradeoffs considered for the empty-match warning, or the full research
  citations behind the tool-description rewrite), that transcript is the fuller record.
