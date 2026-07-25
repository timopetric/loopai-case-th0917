# Second opinion — product & architecture

Independent take, written after the API investigation (`api-report-fresh.md`) and taking
the owner's fixed decisions as constraints. Where the evidence makes me want to push back
on a fixed decision I say so explicitly and then work within it.

---

## 1. What this product actually is

The brief describes a reporting product. The API investigation says something narrower and
more useful to know:

> **There is no query engine upstream. There is one 362 KB JSON blob covering 14 days,
> returned in ~0.3 s no matter what you ask for.**

`event_types`, `time_unit`, `time_period`, `timezone`, `community_id`, and `filters` are all
inert; `scope` only trims a list. So the "integration" is a single HTTP call, and **100 % of
the product's value lives in what you do with the payload after it arrives**: shaping,
aggregating, formatting, exporting, and letting a human or an LLM describe the shape they
want.

That reframing should drive the build. Don't spend the night on a request-builder that maps
UI controls onto upstream parameters — those parameters do nothing. Spend it on the
in-memory report engine, correct arithmetic, and the two interfaces to it (the builder UI
and the agent).

The second thing worth saying out loud: **this is a judgement test wearing a coding-task
costume.** The docs contain at least 19 falsifiable claims, of which the units error is a
silent 3600× correctness bug. The brief says as much — "infer the units, don't wait for
perfect info, be upfront about what you assumed." A submission that quietly gets the units
right and *shows its reasoning* beats a prettier one that trusted the PDF.

---

## 2. What the data can and cannot express

This is the hard boundary on scope, so it belongs in the design before any UI is drawn.

**Supported (all client-side from one response):**

| Shape | Source |
|---|---|
| metric × day | top-level arrays |
| metric × agent (× day) | `actors[i][metric][day]` |
| metric × mailbox (× day) | `mailbox[i][metric][day]` |
| any roll-up over days | sum for counters, `Σvalue/Σcount` for durations |
| rankings, leaderboards, day-of-week patterns | derived from the above |

**Not supported, at any price:**

- **Agent × mailbox cross-tab.** `actors` and `mailbox` are independent marginals; the joint
  distribution isn't in the payload and no parameter retrieves it. "How many did Elena
  resolve in Returns?" is unanswerable. This is the constraint most likely to be probed by a
  reviewer and it must be surfaced in the README *and* handled gracefully by the agent.
- Any breakdown by label, topic, category, customer, or domain — keys exist, always empty.
- Sub-daily or multi-day buckets; non-UTC day alignment.
- Anything outside 2026-07-10 → 2026-07-23.

**Concrete recommendation:** encode this in `ReportSpec` as a validator, not as a comment.
`group_by` should be a list drawn from `{day, agent, mailbox}` with a rule that `agent` and
`mailbox` are mutually exclusive. Then the impossible report is unrepresentable, the UI can
grey out the combination, and the agent gets a validation error it can recover from instead
of producing a confidently wrong table. Making illegal states unrepresentable in the shared
contract is the single highest-leverage design decision available here.

---

## 3. Smartest one-night scope

Ordered by value-per-hour. The literal client ask comes first because it is both the
smallest and the most likely to be checked.

**Build first (the spine):**

1. `ReportSpec` + the report engine: fetch once, shape into rows, with **correct
   aggregation** (sum counters; `Σvalue/Σcount` for durations; hours formatted as `h m`).
2. A results table rendering whatever the spec says.
3. **CSV + Excel export of exactly what's on screen.** This is half the literal ask and is
   cheap once rows exist.
4. Three presets, one of which is the brief's verbatim request: *per-day × per-agent*,
   *per-day × per-inbox*, *agent leaderboard*.
5. A **data-coverage banner** and an **assumptions page**. Cheap, and it targets the stated
   grading criteria directly.

**Then (the headline differentiator):**

6. The AI agent, editing the same `ReportSpec` through validated tool calls.

**Cut without regret:** saved/scheduled reports, user management, pagination,
virtualised tables, drill-downs, anything touching `filters`, any granularity or
timezone control.

*Revised 2026-07-25:* **charts are IN**, not cut. Once `ReportTable` carries raw numbers plus
per-column metadata, a chart is a second consumer of an object that already exists — see
`architecture.md` §7 for the settled design (single metric, top-8, entity-stable colour). Most of those either don't work upstream or don't survive contact with a
one-night deadline.

**Keep despite being cheap-looking:** shareable URLs encoding the spec. In a reporting
product "send me that view" is a real workflow, and if the spec is already a serialisable
pydantic model it's an afternoon's worth of value for twenty minutes of work.

---

## 4. How the AI agent should touch the report definition

The fixed decision — the agent edits a validated `ReportSpec` via tool calls, never emits
rows or SQL or code — is right, and it's the part of the design I'd defend hardest. Three
refinements the evidence argues for:

**4.1 Field-scoped tools, not one `write_spec` tool.** Prefer `set_date_range`,
`set_metrics`, `set_grouping`, `set_sort`, `set_columns` over a single tool taking the whole
spec. Partial edits mean the model can fix one thing without restating the rest (fewer
opportunities to hallucinate a field), each call validates independently, and the SSE
narration gets naturally user-friendly beats ("Set the date range to 13–17 July").

*Settled 2026-07-25 (ADR-0002), with two refinements from grilling.* First, the deciding
argument turned out to be neither of the above but **progressive rendering**: each tool
applies immediately and emits its own `spec` event, so the builder controls visibly move one
at a time instead of snapping into place in a single frame. Second, tools must be scoped to a
**cohesive unit**, not to one raw field — `set_date_range(from, to)` rather than separate
`set_date_from`/`set_date_to`, which would allow an inverted range mid-sequence and
manufacture an error out of a valid intent. Cross-field drift (dropping a metric that `sort`
pointed at) is **repaired and reported in the tool result**, never returned as a validation
error.

**4.2 The tool schema is the capability boundary.** Do not expose parameters the API can't
honour. No `granularity`, no `timezone`, no `filters`. Metrics as a strict enum. If a
capability isn't in the schema, the model can't promise it — this is far more reliable than
prompt instructions telling it what not to do. For the genuinely impossible request
(agent × mailbox), the validator should return a specific, actionable error the agent can
relay: *"That cross-tab isn't available in the source data; I can show you per-agent or
per-inbox separately."* Honest refusal is a feature here, and it demonstrates exactly the
judgement the brief is grading.

**4.3 Let the agent read, not just write.** Give it one read-only tool returning a compact
summary of the current result (row count, totals, top/bottom entries). Without it, "who was
slowest last week?" forces the model to guess a spec and stop. With it, the agent can build
a report, look at it, and refine — and it can answer the question in prose *while* leaving a
correct report on screen. That's the demo that lands.

**Guardrails I'd insist on:** cap the tool loop (the existing `AGENT_MAX_ITERATIONS=8` is
sensible); validate every date range against the coverage window *before* calling upstream
and have the agent say "there's no data in that range" rather than silently rendering July;
and never let raw tool names, arguments, or prompt text reach the browser — already the
fixed decision, and it matters more than usual because the tool names leak the whole
architecture.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Units taken from the docs (seconds)** | Critical, silent | Hours, `×3600` only at the boundary; unit-test one known singleton value |
| **Averaging averages across buckets/agents** | High, silent | Aggregate durations only as `Σvalue/Σcount`; make the row builder refuse to mean a mean |
| **Out-of-coverage dates silently return July data** | High | Validate against 2026-07-10→23 in your own layer; banner + explicit empty state |
| **`actioned_emails` summed across agents (+52 %)** | Medium | Suppress the total, or footnote it, on any agent-grouped view |
| **Agent promises unsupported reports** | Medium | Capability-bounded tool schema (§4.2) |
| **Reviewer opens the app after the upstream sleeps/dies** | Medium | See §6.2 |
| **108 agents / 103 mailboxes in a picker** | Low | Searchable multi-select, not a dropdown; but entity pickers only matter for client-side slicing |
| **Last bucket (07-23) is a partial day** | Low but embarrassing | Flag it in the UI; don't let it silently distort trends |
| **qwen tool-calling reliability** | Medium | Strict JSON schemas, one repair retry on invalid tool args, low temperature (0.1 is already set) |

---

## 6. Flags on the fixed decisions

Not overrides — the owner's calls stand. These are the places where the evidence makes me
want to register a concern.

**6.1 "No caching layer" vs a provably static payload.** The upstream returns a
byte-identical 362 KB blob for every request, verified static over a 153-second window, and
`/health` advertises a fixed coverage window. Meanwhile the agent will trigger several
report renders per conversation. Calling upstream live for each one costs ~0.3–0.9 s and
buys zero freshness. I'd argue for a trivial in-process memo keyed on `(from, to)` — a dict,
not a "caching layer" — and I'd note it in the README as a deliberate, reversible choice.
**Working within the decision:** at minimum, fetch **once per report render** and shape all
metrics/groupings from that one response, rather than issuing a call per metric or per
group-by. That's not caching, just not being wasteful.

**6.2 "No mock mode" vs demo-day risk.** Agreed for the happy path — live calls are more
honest and the brief rewards it. But the entire submission is unreviewable if this free-tier
Railway app is asleep or retired when a reviewer opens it. Since the data is provably
static, the fixture you're already committing for tests is a byte-exact copy of production.
I'd flag that a *last-resort* fallback (serve the fixture, with a visible "upstream
unavailable — showing snapshot from <date>" banner) is close to free and protects the grade.
Being loud about the degradation is what keeps it honest rather than a mock in disguise.

**6.3 Login screen with a single shared key.** Right call given the agent spends tokens, and
worth one line in the README explaining *why* auth exists at all — it reads as
over-engineering otherwise. Note the upstream itself has no real auth (any non-empty bearer
token works) and CORS is wide open, so your key is protecting your LLM budget, not the data.

**6.4 `ReportSpec` as the single shared contract.** The strongest decision in the set, and
the evidence reinforces it: with no server-side query capability, the spec *is* the query
language. Push as much of §2's impossibility into its validators as you can.

**6.5 Backend-hosted agent + server-translated SSE.** Correct, and load-bearing for keeping
prompts private. One note: user-friendly translation should happen at the *event* level with
a fixed vocabulary, not by asking the LLM to narrate itself — cheaper, faster, and it can't
leak.

**6.6 Frontend built and served by FastAPI, one container.** Fine, and it sidesteps CORS
entirely (though the upstream's `Access-Control-Allow-Origin: *` means a browser could call
it directly — that's not a reason to, given the agent and the shared key must live
server-side).

---

## 7. What I'd tell the reviewer

If I had one paragraph in the README, it would be this: *the documented API is largely
fictional — seven of ten request fields are inert, filtering doesn't exist, bucketing is
always daily UTC, and the time metrics are in hours rather than the documented seconds, a
3600× difference I verified by isolating single-ticket samples. The data is one static
14-day window. So this app treats the endpoint as a bulk data source and implements
reporting client-side; the report definition is a single validated model shared by the UI,
the exporters, and the AI agent, and it is deliberately incapable of expressing reports the
data cannot support — such as agent × inbox cross-tabs, which the two independent breakdown
arrays make impossible.*

That paragraph demonstrates inference under incomplete information, states the assumptions,
and is honest about the shortcuts — which is what the brief says it is grading.
