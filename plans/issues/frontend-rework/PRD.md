# PRD — Frontend rework (Case TH-0917)

Status: ready-for-agent

**This document is the source of truth for the frontend rework.** It sits beneath the app's main
PRD — [`../reporting-builder/PRD.md`](../reporting-builder/PRD.md) still governs *what the product
does*. This one governs *how it looks and feels*, and nothing here may change product behaviour.

| Read next | For |
|---|---|
| [`../reporting-builder/PRD.md`](../reporting-builder/PRD.md) | The product. Its user stories still bind. |
| [`../../decisions/architecture.md`](../../decisions/architecture.md) | **§7 (Frontend)** — the three zones, the chart rules, the Zustand store. This rework is largely §7 finally being implemented. |
| [`../../decisions/design-reference-mistral.md`](../../decisions/design-reference-mistral.md) | The styling reference. Saved verbatim; **read the adaptation section below before applying it literally.** |
| [`../../decisions/CONTEXT.md`](../../decisions/CONTEXT.md) | Glossary. **Actor** / **Assistant**; unqualified "agent" is banned in UI copy. |
| [`../../decisions/adr/`](../../decisions/adr/) | ADR-0004 (design adaptation) lands in slice 01. |

---

## Problem Statement

The application is functionally complete and its numbers are trustworthy, but the interface does
not let a user get at them.

Measured against the committed fixture:

| Finding | Detail |
|---|---|
| The default view renders **1,512 rows / 6,048 cells** | Day × **Actor** over the **Coverage Window**, unvirtualised, in one `<table>` |
| The **Assistant** sits *below* that table | It is the graded half of the brief and is effectively unreachable |
| `App.tsx` is **689 lines** with ~14 `useState` hooks | Every control, all state and the whole layout in one component |
| There is **no stylesheet** | 100% inline `style={{}}`; no tokens, no dark mode, no responsive rules, no hover or focus states |
| **Markdown is not rendered** | Assistant prose arrives as a bare text node, so lists and emphasis appear as literal syntax |
| The table has no **sticky header**, no aligned numerals, no density control | At row 800 the reader cannot tell which column is which |

Two documented decisions were never implemented: `architecture.md` §7 specifies **three zones**
(builder, preview, **Assistant**) and **one Zustand store**. Neither exists.

## Solution

A three-pane workspace, built on Tailwind and a token layer adapted from the design reference,
with the **Assistant** permanently docked on the right so its edits to the **Report Spec** are
visible as they happen.

The load-bearing changes:

- **The Assistant is always on screen.** Watching the builder controls move as it works is the
  product's most persuasive moment, and it only exists if both are visible at once.
- **The Report Table becomes readable at scale** — virtualised, sticky header, aligned numerals,
  grouped **Buckets**, density control.
- **Assistant prose renders as markdown**, so a ranked answer reads as a list rather than raw
  syntax.
- **A real token layer**, so dark mode and consistent spacing are possible at all.

## Design adaptation — read before applying the reference

The reference describes a **marketing site**. This is a data-dense analytical tool that people
stare at rather than glance at. Applying it literally would damage legibility, so these
adaptations are decided, not open:

| Reference | Why it does not transfer | Adaptation |
|---|---|---|
| Cream `#fff8e0` page surface | Behind thousands of scanned figures it lowers contrast and tires the eye | Cream is an **accent** surface — rails, cards, banners. **The data surface is white.** |
| `PP Editorial Old` display face | Commercial licence; cannot ship | **Instrument Serif** (OFL), display sizes only |
| 84px hero, sunset stripe band, photography | No place in a report builder | Dropped. The lower type registers are kept. |
| No dark-mode tokens (the reference lists this under *Known Gaps*) | We need dark mode | Derive a dark ramp; the chart palette is **selected** for dark and validated, never inverted (§7) |

**The one genuine conflict, and its resolution.** The reference is built on a saturated orange
primary and a sunshine yellow family. `architecture.md` §7 fixes the chart palette as eight
entity-stable hues and requires that *"values and labels wear text tokens, never the series
colour."* Flooding the UI with orange, or admitting it into the series palette, destroys series
distinctiveness and CVD-safety.

**Inside the chart frame the dataviz constraints win; brand colour stays outside it.** The
reference agrees — *"keep `{colors.primary}` confined to primary CTAs, active states."* Recorded
as ADR-0004.

## Constraints that bind this work

These come from the app's hard rules and from earlier slices. Breaking any of them is a defect
even if the UI looks better:

- **No `VITE_*` or any build-time frontend configuration.** Tailwind is fine — it is CSS tooling,
  not an environment value baked into the bundle. Fonts must be **self-hosted and bundled**, never
  fetched from a CDN, so an image built locally behaves identically in production.
- **The export must match what is on screen.** Both exporters derive from the same **Report
  Table**, so the table may be **virtualised but never paginated** — showing page 1 of 38 while
  exporting all 1,512 rows would break a graded user story.
- **Never render raw HTML from model output.** Keep the markdown renderer's hardening defaults and
  allowlist link protocols. Model output is untrusted.
- **The presenter's containment is unchanged.** No tool name, argument, prompt fragment or raw
  reasoning may reach the browser. This rework touches presentation only.
- **The withheld-value sentinels stay.** A zero-count **Duration Metric** average and
  `actioned_emails` totalled across **Actors** render as a dash on screen and in the workbook, and
  as an empty field in CSV. Styling may make the dash quieter; it may not make it a zero.
- **Glossary vocabulary in all UI copy** — **Actor**, **Mailbox**, **Assistant**, **Bucket**,
  **Coverage Window**, **Warning**. The wire value `"agent"` is correct and must not change.

## Out of Scope

- Any change to product behaviour, the **Report Spec**, the engine, the exporters or the API.
- An **Actor** / **Mailbox** multi-select picker — still deferred by the main PRD.
- The deferred preset ideas in `architecture.md` §7.
- Charts beyond the single-**Metric** time series.
- A component library beyond what the token layer needs. No shadcn/ui adoption; build the handful
  of primitives this app actually uses.
- Replacing `recharts`.
