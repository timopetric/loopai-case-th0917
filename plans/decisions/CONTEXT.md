# Reporting (Case TH-0917)

A browser report builder over a single upstream helpdesk statistics endpoint, with CSV/Excel
export and an LLM assistant that builds reports from plain English. The upstream ignores
almost every request parameter, so all shaping happens in our own engine.

## Language

### Report domain

**Report Spec**:
The declarative definition of a report — metrics, date range, granularity, grouping, sort,
column order, layout, chart metric.
_Avoid_: config, query, params, report definition

**Report Table**:
The executed result of a **Report Spec** — columns, rows, totals, warnings. Carries raw
numeric values plus per-column metadata; formatting happens at render time.
_Avoid_: result, dataset, output

**Metric**:
One of the 15 quantities the upstream reports. Splits into **Counters** (whole numbers,
summable) and **Duration Metrics**.
_Avoid_: event type, KPI, measure

**Duration Metric**:
A **Metric** measured in hours, reported as a *sum* over the bucket with a `_count`
companion. Aggregated only as `Σvalue / Σcount`, never by averaging averages. Displayed as
the per-ticket average by default ("how fast"), or as the total ("how much work").
_Avoid_: time metric, latency, timing

**Bucket**:
One calendar day of data, UTC-aligned. The upstream cannot produce any other bucket size.
_Avoid_: interval, period, tick

**Tick**:
A **Bucket** boundary timestamp. There is always one more tick than there are values; a
value belongs to the tick on its left.
_Avoid_: timestamp, label

**Coverage Window**:
The absolute date range for which upstream data exists — currently 2026-07-10 through
2026-07-23 inclusive. Fixed, not rolling. Requests outside it silently return the whole
window rather than nothing.
_Avoid_: data range, available dates

### People and places

**Actor**:
An entity credited with activity in the upstream `actors` breakdown — 108 of them, mixing
real people ("Elena Kaur") with role accounts ("Support", "Billing").
_Avoid_: **agent** (reserved, see Flagged ambiguities), user, rep

**Mailbox**:
A shared inbox in the upstream `mailbox` breakdown — 103 of them. The client calls these
"inboxes"; we use Mailbox everywhere in code because the upstream does.
_Avoid_: inbox (in code), queue, channel

**Assistant**:
The LLM that edits a **Report Spec** through validated tool calls on our backend.
_Avoid_: **agent** (reserved), bot, copilot

**Tool Step**:
One model call in the **Assistant**'s loop. Bounded by `AGENT_MAX_ITERATIONS`; a model call
emitting several tool calls is still one Tool Step.
_Avoid_: iteration, turn, round, cycle

**Repair**:
An automatic correction the backend applies when one **Report Spec** edit invalidates an
earlier field — resetting a dangling chart metric or clearing an orphaned sort — reported to
the **Assistant** and the user instead of raised as an error.
_Avoid_: fix, coerce, fallback

**Warning**:
A note attached to a **Report Table** explaining something the user must know to read the
numbers correctly — a **Repair** that occurred, a clamped date range, or a metric that
cannot be summed across **Actors**.
_Avoid_: error, alert, notice

## Relationships

- A **Report Spec** executes into exactly one **Report Table**
- A **Report Table** groups by **Actor** or by **Mailbox** — never both at once
- A **Duration Metric** always has a `_count` companion; a **Counter** never does
- The **Assistant** edits a **Report Spec**; it never produces a **Report Table** directly
- A **Report Spec**'s date range is validated against the **Coverage Window** before any
  upstream call

## Example dialogue

> **Dev:** "When the **Assistant** groups a report by **Actor**, can it also break it down by
> **Mailbox** in the same table?"
> **Domain expert:** "No — upstream gives us two independent breakdowns of the same totals,
> not a cross-tab. Grouping by **Actor** and by **Mailbox** are separate reports. The
> **Report Spec** shouldn't even be able to express both."

## Flagged ambiguities

- **"agent" was used for three different things** — the support person, the AI, and the
  upstream `actors` entries. Resolved: the person/entity is an **Actor**, the LLM is the
  **Assistant**, and "agent" is not used unqualified in code. (User-facing copy may still
  say "agent" for the human, since that is the client's word.)
- **"inbox" vs "mailbox"** — the client's email says "inboxes", the upstream API says
  `mailbox`. Resolved: **Mailbox** in code and in the **Report Spec**; "inbox" is allowed in
  UI copy aimed at the client.
- **"iteration"** was ambiguous between model calls, tool calls, and full cycles. Resolved:
  a **Tool Step** is one model call.
