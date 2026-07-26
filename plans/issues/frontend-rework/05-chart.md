# 05 — Chart in the new visual system

Status: ready-for-agent

## Parent

[PRD — Frontend rework (Case TH-0917)](PRD.md)

## What to build

Bring the chart's chrome into the token layer without touching the rules that make it honest.

Restyle the frame: axes, grid, tooltip, legend and the not-shown disclosure, using the recessive
treatment the technical design §7 describes — two-pixel lines, a receding grid, and values and
labels wearing text tokens rather than the series colour.

**The series palette is not part of the rebrand.** The eight hues are assigned from a stable digest
of the entity identifier so an **Actor** keeps its colour when the date range changes the ranking.
Brand colour must not enter that palette, and no ninth hue may ever be generated. Where the brand
palette and the dataviz constraints disagree inside the chart frame, the dataviz constraints win —
this is ADR-0004, and it exists because a saturated orange primary alongside a sunshine yellow
family would collapse series distinctiveness and colour-vision safety.

Close the one gap the technical design §7 names and the original chart slice left open: **with
four or fewer series, label them directly** as well as in the legend, so identity never depends on
colour alone.

Everything else stays: one **Metric** on one axis and never a dual axis; the eight largest series
by total with the remainder dropped and counted rather than aggregated; a withheld value drawn as
a gap rather than connected or dropped to zero; and no chart at all when the report collapses to a
single **Bucket**.

## Acceptance criteria

- [ ] Axes, grid, tooltip and legend use the token layer, with values and labels in text tokens rather than series colours
- [ ] The eight-hue series palette is unchanged, entity-stable, and contains no brand colour
- [ ] No ninth hue can be generated
- [ ] With four or fewer series, each is labelled directly as well as in the legend
- [ ] The chart still hides when the report collapses to a single Bucket
- [ ] A withheld value still renders as a gap, not a drop to zero
- [ ] The chart still derives from the same Report Table as the table
- [ ] `make check` passes

## How to verify

Ladder levels are defined in the technical design's verification section.

**Level 1** — the existing chart tests still pass: top-eight selection, and colour surviving a
ranking change.
**Level 2** — primary. A chart's correctness is largely visual: hover, legend, direct labels at
four series, and readability at eight.

## Blocked by

02
