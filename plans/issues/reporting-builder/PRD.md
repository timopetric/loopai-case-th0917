# PRD — Reporting Builder (Case TH-0917)

Status: ready-for-agent

Source of truth for every decision referenced here: `plans/decisions/` — in particular
`CONTEXT.md` (vocabulary), `api-report-fresh.md` (upstream contract), `architecture.md`
(technical design), and ADR-0001 / ADR-0002. Terms in **bold** are defined in `CONTEXT.md`
and are used with exactly that meaning throughout.

---

## Problem Statement

A support operation runs many **Actors** across many shared **Mailboxes**, and its leadership
has no visibility into who did what, where, and how fast. Today they can ask for a spreadsheet
and someone assembles it by hand; by the time it arrives it answers last week's question, and
answering a slightly different question means asking again and waiting again.

They asked for a CSV broken down per day, per **Actor**, per **Mailbox** — replies, resolved,
handle time, "all of it". But the underlying need is not a file. It is the ability to *pose a
question about team performance and get a trustworthy answer immediately*, then change the
question without involving anyone else.

Two things make this harder than it looks:

1. **The only available data source is unreliable and undocumented in important ways.** Its
   published documentation is wrong about which request parameters work (almost none do), about
   how the data is bucketed, and — most damagingly — about the units of every time-based
   **Metric**, which are hours rather than the documented seconds. Taken at face value, the docs
   produce a report where every duration is wrong by a factor of 3600 and nobody can tell.
2. **The data cannot answer one of the questions being asked.** Per-**Actor** and per-**Mailbox**
   figures arrive as two independent breakdowns of the same totals, so "how many did Elena
   resolve in Returns?" is not derivable at any price. The literal request — per day *and* per
   agent *and* per inbox in one table — is impossible, and pretending otherwise would produce
   confident, invented numbers.

## Solution

A single-page report builder, served from one container, that treats the upstream endpoint as a
bulk data source and does all shaping locally.

The user picks **Metrics**, a date range, and a grouping; a **Report Table** and a chart update
immediately; CSV and Excel exports produce exactly what is on screen. An **Assistant** panel
accepts plain-English requests and builds the same report by editing the same **Report Spec**
the human edits — visibly moving the controls as it works, rather than producing numbers out of
nowhere.

Correctness the user can see:

- Durations are treated as **hours** and labelled as such in every column header, so the
  reader is never silently misled by the upstream documentation's error.
- Averages across **Buckets** and **Actors** are count-weighted (`Σvalue / Σcount`), never an
  average of averages.
- The **Coverage Window** is always on screen, the date picker cannot leave it, and a request
  for a period with no data is refused rather than silently answered with a different fortnight.
- Reports the data cannot support are not merely discouraged — the **Report Spec** cannot
  express them, so neither the UI nor the **Assistant** can produce one.
- Every assumption is one click away in-app, and travels inside the Excel export.

## User Stories

### Seeing the data

1. As a support operations lead, I want a table showing, for each day and each **Actor**, their replies, resolved count and handle time, so that I get the breakdown I originally asked for without anyone assembling it by hand.
2. As a support operations lead, I want the same breakdown per **Mailbox** instead of per **Actor**, so that I can see which of our 103 inboxes carry the load.
3. As a support operations lead, I want the day × **Actor** report already populated when the app opens, so that I see the answer to my original request before touching a single control.
4. As a support operations lead, I want one-click presets for day × **Actor**, day × **Mailbox**, and an **Actor** leaderboard, so that the three questions I ask most often take no configuration.
5. As an analyst, I want to tick and untick individual **Metrics**, so that the table shows the three columns I care about rather than all fifteen.
6. As an analyst, I want to pick a date range with a slider bounded to 2026-07-10 – 2026-07-23, so that I can narrow to a period of interest and cannot accidentally leave the data.
7. As an analyst, I want to group by **Actor**, by **Mailbox**, or not at all, so that I can move between individual, team and whole-operation views.
8. As an analyst, I want to collapse all fourteen days into one **Bucket**, so that I can rank people or inboxes over the whole period instead of day by day.
9. As an analyst, I want to sort by any column ascending or descending, so that I can find the top and bottom of a distribution immediately.
10. As an analyst, I want sorting to reorder rows *within* each day while days stay in chronological order, so that sorting does not destroy the time series I am looking at.
11. As an analyst, I want sorting to apply across the whole table when I have collapsed to a single **Bucket**, so that a leaderboard actually ranks.
12. As an analyst, I want to reorder columns, so that the numbers I am comparing sit next to each other.
13. As an analyst, I want a totals row beneath the table, so that I can sanity-check magnitudes at a glance.
14. As an analyst, I want to switch **Duration Metrics** between per-ticket average and period total, so that I can ask "how fast is Elena?" and "how much time did Elena spend?" without rebuilding the report.
15. As an analyst, I want per-ticket averages computed as total-over-count rather than an average of daily averages, so that combining days or people gives the true figure.
16. As an analyst, I want a layout that puts days across the top as columns, so that I can scan one **Metric** across the period in a compact grid.
17. As an analyst, I want to be told that the day-columns layout shows a single **Metric**, so that I understand why my other selected columns are not displayed.
18. As an analyst, I want **Metrics** that are always empty upstream to be absent from the picker entirely, so that I never build a report that is silently all zeros.

### Trusting the data

19. As a support operations lead, I want every duration column labelled with its unit, so that I never read hours as seconds — a mistake the upstream documentation actively invites.
20. As a support operations lead, I want the **Coverage Window** shown permanently in the header, so that I always know the numbers describe 10–23 July 2026 and nothing else.
21. As an analyst, I want a date range that only partly overlaps the **Coverage Window** to be clamped with an explicit **Warning**, so that I understand why the result is narrower than I asked.
22. As an analyst, I want a date range with no data at all — June 2026, say — to be refused outright, so that I am never shown July's numbers as though they answered my question.
23. As an analyst, I want to see how many tickets sit behind an average when I hover a cell, so that I can tell a solid figure from one resting on a single ticket.
24. As an analyst, I want `actioned_emails` to show a dash rather than a total when grouped by **Actor**, so that I am not handed a number that overstates reality by half.
25. As an analyst, I want to know the final day in the window is partial, so that I do not read a genuine drop into what is really incomplete data.
26. As an analyst, I want to understand that the **Actor** list mixes real people with role accounts such as "Support" and "Billing", so that I do not mistake a shared queue for an individual's performance.
27. As an analyst, I want any automatic **Repair** to my report stated plainly, so that I understand why my sort disappeared when I removed a **Metric**.
28. As a support operations lead, I want one click to a list of every assumption made about this data, so that I can judge how far to trust the report.
29. As a support operations lead, I want to be told clearly that per-**Actor**-per-**Mailbox** figures are unavailable, so that I stop looking for a way to produce them.
30. As a reviewer, I want the units assumption to be justified rather than merely asserted, so that I can see it was inferred from evidence rather than guessed.

### Exporting

31. As a support operations lead, I want to download the current report as CSV, so that the original request for a spreadsheet is satisfied.
32. As a support operations lead, I want to download the current report as Excel, so that colleagues can open it directly.
33. As an analyst, I want the CSV to begin at the header row with no preamble, so that it loads into a spreadsheet or a script without hand-editing.
34. As an analyst, I want the exported file to match exactly what is on screen, so that I never reconcile two versions of the same report.
35. As an analyst, I want units in the exported column headers, so that a colleague opening the file cannot misread the durations.
36. As a reviewer, I want the Excel file to carry a second sheet describing the report, its date range and its caveats, so that context survives being forwarded.

### Working with the Assistant

37. As a support operations lead, I want to type "resolved and handle time by agent for last week" and get that report, so that I need not learn the controls.
38. As a support operations lead, I want to watch the date slider, grouping and metric checkboxes change one at a time as the **Assistant** works, so that I can see what it did and correct it.
39. As a support operations lead, I want a visible "thinking" indicator while the **Assistant** reasons, so that a multi-second pause does not look like a crash.
40. As an analyst, I want to ask "who was slowest?" and get a prose answer, so that I need not read every row myself.
41. As an analyst, I want the **Assistant** to base every number it states on the report it actually built, so that it cannot quote a figure it invented.
42. As an analyst, I want the **Assistant** to refuse an impossible request with a reason and an alternative, so that I learn what the data supports instead of receiving fiction.
43. As an analyst, I want the **Assistant** to tell me when my dates fall outside the **Coverage Window** and offer the range it does have, so that I can adjust in one step.
44. As an analyst, I want the **Assistant** to never invent a **Metric** name, so that every column it produces is real.
45. As an analyst, I want to refine over several messages — "now just the weekdays", "sort by handle time" — so that I can converge on what I meant.
46. As an analyst, I want the **Assistant** to describe only the changes that survived my request, so that it does not tell me a sort was cleared when it then set a new one.
47. As an analyst, I want the **Assistant** to tell me when it has used its work allowance for a turn, summarise where it got to, and invite another message, so that I am never left with a spinner and no answer.
48. As a security-conscious reviewer, I want no internal tool names, arguments, prompts or raw model reasoning to appear anywhere in the interface, so that implementation details are not exposed to end users.
49. As a developer, I want the raw model reasoning visible in a collapsible panel when running locally, so that I can debug the **Assistant** without shipping that to production.

### Sharing and access

50. As an analyst, I want the report definition captured in the URL, so that I can send a colleague the exact view I am looking at.
51. As an analyst, I want an opened shared link to reproduce the report faithfully — metrics, dates, grouping, sort, column order and chart selection — so that we are certainly discussing the same thing.
52. As an operator, I want the application behind a shared key entered at a sign-in screen, so that the **Assistant**'s token spend is not open to the internet.
53. As a user whose key stops working mid-session, I want to be returned to sign-in with my report preserved, so that I can resume without rebuilding it.

### Chart

54. As a support operations lead, I want a line chart of one **Metric** over the period, so that I can see trend and shape rather than reading a grid of numbers.
55. As an analyst, I want to choose which **Metric** the chart plots independently of the column order, so that the visual matches my question.
56. As an analyst, I want the chart limited to the eight largest series with the remainder disclosed as a count, so that it stays readable rather than becoming a hairball of 108 lines.
57. As an analyst, I want each **Actor** to keep the same colour when I change the date range, so that the chart does not appear to change subject when the ranking shifts.
58. As an analyst, I want hovering a point to show the exact value and which series it belongs to, so that I can read specifics without leaving the chart.
59. As an analyst, I want a legend naming every plotted series, so that identity never depends on colour alone.
60. As an analyst, I want the chart to disappear when I collapse the report to a single **Bucket**, so that I am never shown a line with nothing to plot against.

### Operating and building

61. As an operator, I want every setting read from environment variables, so that I can change the key, the model or the work allowance on the platform without a rebuild.
62. As an operator, I want the upstream dataset fetched once and reused for a few minutes, so that adjusting report settings does not re-fetch identical data.
63. As an operator, I want the **Coverage Window** discovered from the upstream at runtime, so that if its data moves the app follows within minutes and needs no redeploy.
64. As an operator, I want the app to fall back to known-good dates if the upstream health check is unreachable, so that a partial outage does not take the whole app down.
65. As a developer, I want an image built on my machine to behave identically in production, so that a local build and push is safe.
66. As a developer, I want the image published under a predictable name and tagged by version as well as latest, so that a redeploy is unambiguous about what it pulled.
67. As a developer, I want the arithmetic, repair rules, event mapping and exports covered by tests that need neither network nor an LLM, so that I can refactor confidently and run them anywhere.
68. As a developer, I want a browser-driven checklist over the assembled application, so that build-time and integration mistakes surface before a reviewer meets them.
69. As a developer, I want the checklist run against the built image rather than the dev server, so that a build-time configuration mistake cannot slip through.
70. As a reviewer, I want a README stating what was assumed, what was cut and why, so that I can assess judgement rather than only output.

## Implementation Decisions

### The upstream contract is a bulk source, not a query engine

Established empirically (`api-report-fresh.md`); implementation must not re-derive it:

- Only `from_date` and `to_date` affect the response. `community_id`, `event_types`,
  `time_type`, `time_unit`, `time_period`, `timezone` and `filters` are inert. `scope` only
  trims the **Mailbox** breakdown list.
- Every response returns all **Metrics** and the full 108-**Actor** / 103-**Mailbox**
  breakdown regardless of the request.
- **Buckets** are always whole UTC days. There is no other granularity.
- **Duration Metrics** are **sums expressed in hours**, each with a `_count` companion. The
  documented "seconds" is wrong.
- A date range that misses the **Coverage Window** silently returns the whole window.
- `actioned_emails` over-counts by ~52% when summed across **Actors**; it reconciles exactly
  across **Mailboxes**. Every other **Metric** reconciles on both.
- `open` is always zero and is not offered in the UI.
- Auth accepts any non-empty bearer token; the value is never validated.

### Report Spec is the single contract

One validated model, shared by the builder, the **Assistant**, the engine, the exporters and
the URL. Shape (decision-bearing fields only):

```python
metrics: list[Metric]                       # strict enum
date_from, date_to: date                    # validated against the Coverage Window
granularity: Literal["day", "total"]
group_by: Literal["none", "agent", "mailbox"]   # agent AND mailbox is unrepresentable
sort: SortSpec | None
columns_order: list[str] | None
layout: Literal["long", "pivot"]            # pivot renders chart_metric only
chart_metric: Metric | None                 # defaults to metrics[0]; must be ∈ metrics
duration_display: Literal["avg", "total"]   # default "avg" = Σvalue / Σcount
```

`group_by` being a single value is deliberate and load-bearing: the impossible
**Actor** × **Mailbox** cross-tab cannot be expressed, so no code path can produce one.

### Modules

| Module | Interface | Responsibility |
|---|---|---|
| `upstream` | `get_dataset()`, `get_coverage_window()` | HTTP, the 5-minute memo, `/health` discovery with a hardcoded fallback, and hours normalisation — all behind two calls. The only module that knows the upstream is weird. |
| `spec` | `ReportSpec`, `repair(spec) → (spec, adjustments)` | Validation plus the **Repair** rules. Pure. |
| `engine` | `execute(spec, dataset) → ReportTable` | Slice, group, aggregate, sort, lay out, and attach **Warnings**. Pure. |
| `exporters` | `to_csv(table)`, `to_xlsx(table, spec, window)` | Both derive from **Report Table**, so preview and files cannot disagree. |
| `agent.tools` | `apply_batch(spec, calls) → (spec, adjustments)` | The nine tools and batch reconciliation. Pure given a spec. |
| `agent.presenter` | `present(raw_event) → UIEvent \| None` | Maps model/tool events to the SSE taxonomy; the chokepoint that keeps internals out of the browser. Pure. |
| `agent.loop` | `run(message, spec) → AsyncIterator[UIEvent]` | Tool loop, Tool Step budget, forced final answer. |
| `api` | Report, export, meta, agent-stream routes | Thin; authentication applied once at the router. |

Four of these are pure functions, which is why the risky surface is testable without network or
LLM.

### Data access (ADR-0001)

Always fetch the **whole Coverage Window**, memoise that one normalised dataset for five
minutes, and slice locally. The cache key is the **Coverage Window** itself, read from the
upstream's undocumented health route (also memoised five minutes, with hardcoded dates as an
unreachable-fallback), so upstream data moving is picked up without redeploying. Narrowing the
request would save roughly 40 ms and 190 KB; knowing the window locally is what allows an
out-of-range request to be refused honestly instead of silently answered.

### Aggregation rules

- **Counters** sum.
- **Duration Metrics** aggregate as `Σvalue / Σcount` across **Buckets** and entities. Averaging
  averages is a defect, not a style choice.
- Sorting applies within the **Bucket**; with `granularity: "total"` there is one **Bucket**, so
  it is global — which is what makes the leaderboard view work.
- `actioned_emails` renders a dash in the totals row when grouped by **Actor**, with a
  **Warning**; not blank, not a number.
- The `_count` behind an average appears in the cell tooltip.

### Date handling

The picker is bounded by the **Coverage Window**. For the **Assistant**: a partial overlap is
clamped and the adjustment reported; a zero overlap is refused, returning the real window so the
**Assistant** can offer an alternative. An out-of-range range must never reach upstream.

### Assistant (ADR-0002)

Nine field-scoped tools, each covering a cohesive unit — date range as a pair, never separate
bounds, so no single call can leave the **Report Spec** transiently invalid. Two are read-only
(run report, fetch metadata). Each write applies immediately and emits its own spec event, so
the controls visibly move one step at a time; this progressive rendering is the reason for
field-scoping over a single atomic patch.

**Repair, don't reject.** When a call invalidates an earlier field — dropping the **Metric** a
sort or chart pointed at, or charting a **Metric** not yet selected — the backend repairs the
spec and reports what it adjusted in the tool result, so the **Assistant** can say so. Genuine
input errors still error once for retry. Full taxonomy in `architecture.md` §5.

**Batch reconciliation.** Verified live: the model emits multiple tool calls in one message.
Within a batch, discard any adjustment to a field that a later call in the same batch explicitly
sets — otherwise the **Assistant** narrates a **Repair** that did not survive the turn.

**Budget.** Tool Steps are model calls, bounded by configuration (default 20). At the
penultimate step the model is warned; at the last, the request is sent **with the tools omitted
entirely** — not merely with tool choice disabled, which was verified to make the model emit
fabricated tool-call JSON as prose. No code path may ever parse assistant prose as tool calls.

**Streaming.** The model reasons before acting — a measured majority of stream chunks are
reasoning deltas before the first actionable one. A thinking event brackets that gap so the UI
does not read as hung; it carries **state only, not reasoning text**, because raw
chain-of-thought names internal tools and enum values. Raw reasoning may be streamed to a
collapsible panel in development mode only.

### Frontend

One page: a sign-in gate, a workspace of three zones (builder, report, **Assistant**), and an
assumptions modal. Report state lives in one store mirrored to the URL. Three presets, with
day × **Actor** loading first because it is the literal request.

Chart: one **Metric**, one axis — never dual-axis. Top eight series by total, remainder dropped
with the count disclosed rather than aggregated into an "Other" that would be wrong for
`actioned_emails`. Colour is assigned by a stable hash of the entity id, never by rank, so
changing dates does not repaint survivors. Legend always present; hover shows exact values.
Hidden entirely when there is no time axis.

**No build-time configuration of any kind.** All API calls use relative paths against the same
origin. This is what makes an image built on a developer machine safe to run in production.

### Exports

CSV is pure data: units in column headers, totals row, no preamble, since anything above the
header breaks naive parsing. Excel adds a second information sheet carrying the spec summary,
the **Coverage Window**, the units note and any **Warnings** — the format opened by hand carries
the caveats.

### Deployment

One container: frontend built with the current Node LTS in a build stage, served by the Python
runtime image. Built locally, pushed to a public registry, deployed by tag. Runtime secrets come
from the platform's environment; none are baked in.

## Testing Decisions

**What makes a good test here.** Tests assert *external behaviour* — given a **Report Spec** and
a dataset, what does the **Report Table** contain; given a batch of tool calls, what does the
resulting spec and adjustment list look like. They do not assert internal call sequences,
private helpers, or module structure, all of which will change during the build. Every test runs
offline: no network, no LLM.

**Prior art.** `scratch/agent-spec-lab/` established patch semantics with 63 offline tests
against a fake model and is the pattern to follow for spec-editing tests. The committed fixture
is a byte-exact snapshot of a real upstream response; because the upstream dataset is provably
static across days, it is a faithful stand-in that cannot go stale. Assertions may safely use
its real figures (16,372 resolved, 108 **Actors**, 103 **Mailboxes**).

**Modules under test:**

1. **`engine`** — the highest-value target, because a wrong number looks entirely plausible on
   screen. Cover: count-weighted duration aggregation against hand-computed values; sorting
   within **Bucket** preserving day order; the `actioned_emails` dash in totals; **Warnings**
   raised for clamped ranges and non-additive **Metrics**; grouping by **Actor** and by
   **Mailbox** each reconciling to the top-level totals; `granularity: "total"` collapsing
   correctly.
2. **`spec.repair`** — each row of the repair taxonomy: dropped **Metric** orphaning chart and
   sort; charting an unselected **Metric** adding it; partial-overlap clamping; zero-overlap and
   empty-metrics rejection.
3. **`agent.tools.apply_batch`** — single calls, and crucially multi-call batches where a later
   call supersedes an earlier **Repair**, asserting the superseded adjustment is not reported.
4. **`agent.presenter`** — event mapping, and a negative test asserting no tool name, argument
   or prompt fragment can appear in any emitted event.
5. **`exporters`** — CSV parses with a standard reader with no preamble handling; units present
   in headers; Excel contains both sheets; both formats agree with the **Report Table**.
6. **`upstream`** normalisation — hours conversion; **Coverage Window** parsing; fallback when
   the health route is unreachable; the memo serving a second call without a second fetch.

7. **API-level tests** (one file) — the seams that pure functions cannot cover. Driven through
   FastAPI's `TestClient` in-process, with `upstream` faked from the committed fixture and a
   **fake LLM** returning scripted tool calls. Offline, no Docker, no tokens. Cover:
   authentication actually attached to the router; export routes returning spreadsheet
   content-types and a CSV that parses with a standard reader; a **Report Spec** surviving a
   round-trip through URL query parameters; the agent stream emitting well-formed events in the
   expected order; the Tool Step budget forcing a final prose answer; and a negative assertion
   that no tool name, argument or prompt fragment appears anywhere in the stream.

   *Deliberately called "API-level", not "integration".* There is no database and no
   infrastructure to stand up; nothing here requires a container. Reading this as a mandate for
   heavyweight integration testing would be a misinterpretation.

**Explicitly not tested against real services.** No test hits the live upstream (its
availability is non-deterministic and the committed fixture is byte-exact), and no test hits the
live LLM by default (cost and flakiness) — at most one opt-in case behind a marker, skipped
unless requested. Browser end-to-end automation via Playwright or Selenium is out of scope; the
Chrome MCP ladder covers the same ground far more cheaply.

**Verification is a three-level ladder** (`architecture.md` §12), and the agent must reach level
3 before declaring work done. Level 1 is `make check` — lint, typecheck, unit and API-level
tests, offline and free, run after every edit. Level 2 drives the built image in a real browser
via Chrome DevTools MCP against development fakes (ADR-0003) — free, deterministic and
repeatable, so the agent can iterate on layout and wiring, screenshot the result, notice its own
mistakes and fix them unattended. Level 3 repeats the walkthrough against the live upstream and
the live model, the only level that proves the units and the **Coverage Window** are right
against today's data.

**Not unit-tested:** `agent.loop` in isolation (its budget and streaming behaviour are covered end-to-end by the
API-level tests with a fake LLM, which is both cheaper and more realistic than mocking its
internals) and the entire frontend. The browser-driven
checklist in `architecture.md` §12 covers the assembled application, including the checks that
map to decisions capable of silently regressing.

## Out of Scope

- **Actor** × **Mailbox** cross-tabs — not derivable from the source at any price.
- Breakdown by label, topic, category, customer or domain — the upstream keys exist but are
  always empty and the corresponding filters are inert.
- Any **Bucket** size other than a whole UTC day; timezone-aligned days; the `week` granularity,
  dropped because the window begins mid-week and produces ragged partials.
- Server-side filtering, sorting, pagination or metric selection — none exist upstream.
- The `open` **Metric** — always zero.
- A database, saved named reports, scheduling, and user management. Sharing is by URL.
- Real authentication or per-user accounts; a single shared key protects token spend only.
- An **Actor**/**Mailbox** multi-select picker in the builder — presets and the **Assistant**
  cover the need for now; the underlying spec fields exist.
- Charts beyond a single-**Metric** time series; no dual-axis, no small multiples.
- Mock or offline runtime mode. Snapshots are test fixtures, never a runtime path.
- Deferred preset ideas recorded in `architecture.md` §7, including any average-based leaderboard,
  which would first need a minimum-count threshold to avoid ranking noise.

## Further Notes

**Highest residual risk is the live model, not the code.** Tool calling, enum discipline,
parallel calls and out-of-range judgement were all verified against the real model; what remains
unverified is the forced-final-answer path with tools omitted, which should be exercised early.

**Two guards exist for reasons that are not obvious from the code**, and both must survive
refactoring: never parse assistant prose as tool calls, and never stream raw reasoning text to
the browser.

**The `Repair` rules are the most state-heavy part of the system** and are specified rather than
exhaustively proven. The taxonomy table in `architecture.md` §5 doubles as the test checklist;
batch reconciliation in particular needs multi-call coverage.

**Grading context.** The brief rewards inference under incomplete information, stated
assumptions, and prioritisation — not polish. The units finding, the honest refusal of
impossible reports, and the in-app assumptions surface are therefore product features rather
than documentation chores, and should not be cut for cosmetic work.
