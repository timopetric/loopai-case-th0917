"""Report Spec presets — three one-click starting points (issue 12).

PRD user stories 3–4: **Day by Actor** is the client's verbatim ask and what
loads on first paint, so the app answers the original question before a
single control is touched. **Day by Mailbox** is the same breakdown across
inboxes. **Actor leaderboard** collapses the whole range to a single Bucket
(`granularity: "total"`), grouped by Actor, sorted descending — on a
Counter (`resolved`), never a Duration Metric average, per architecture.md
§7's gotcha: an average-based leaderboard needs a minimum-`_count` threshold
first (not built here) or it ranks noise. Issue 07's zero-count-average-is-
`None`-and-sorts-last rule (`engine._sort_rows_within_bucket`) is exactly
what would keep idle Actors off the top of such a ranking, but this preset
sidesteps the question entirely by sorting on a Counter instead.

Selecting a preset **replaces the Report Spec wholesale** (the frontend sets
every control from `Preset.spec`); the controls then show the preset's
values and remain individually editable — a preset is a starting point, not
a mode.

`build_presets()` is a pure function of the `CoverageWindow`, mirroring
`app/assumptions.py`'s `build_assumptions()`: the date bounds always come
from the live Coverage Window (never hardcoded past first paint), so a
preset's spec is only ever built with real bounds in hand — same reasoning
`App.tsx`'s docstring gives for `dateFrom`/`dateTo`.

Deliberately NOT built here — recorded as deferred in architecture.md §7 and
out of scope for this issue: backlog pressure, weekday-vs-weekend, first-
response speed, inbox workload balance, SLA hot-spots, capacity view. Each
is a valid `ReportSpec`, none is wired up as a preset in this version.

This is the ONLY place these three specs are defined. `app/api/v1/routers/
meta.py` serves `build_presets(dataset.coverage)` verbatim as `MetaResponse
.presets`; the frontend renders one button per served preset and applies its
`spec` as-is (`App.tsx`'s `applyPreset`), holding no preset definitions of
its own — unlike `ReportSpec` itself, which the frontend's `report.ts`
legitimately mirrors as a *type* (checked by `tsc` and by every response the
backend actually sends), a hand-mirrored copy of these *values* would be
invisible to every test here: a wrong sort column or metric list in a
frontend-only copy would fail nothing in `tests/test_presets.py`, which only
ever calls `build_presets`. Kept in `app/`, not `frontend/`, precisely so
that cannot happen, and so a later issue (13's URL serialisation, 16's
Assistant) has one place to reference rather than re-deriving these three
specs.
"""

from dataclasses import dataclass

from app.models import Metric, ReportSpec, SortSpec
from app.upstream import CoverageWindow

PRESET_METRICS: list[Metric] = [
    Metric.RESOLVED,
    Metric.REPLIES,
    Metric.NEW_TICKETS,
    Metric.RESOLVE_TIME,
]
"""The same starter columns `App.tsx` seeds on first paint (issue 06's
`DEFAULT_METRICS`): the three Counters the client asked for, plus one
Duration Metric so the avg/total toggle has something to demonstrate."""


@dataclass(frozen=True)
class Preset:
    """One preset: a stable machine `id` (for buttons/testing/future URL or
    Assistant reference), a display `label`, and the `ReportSpec` it seeds."""

    id: str
    label: str
    spec: ReportSpec


def build_presets(coverage: CoverageWindow) -> list[Preset]:
    """All three presets, in display order, bound to the real Coverage Window."""
    return [
        Preset(
            id="day-by-agent",
            label="Day by Actor",
            spec=ReportSpec(
                metrics=list(PRESET_METRICS),
                date_from=coverage.from_date,
                date_to=coverage.to_date,
                granularity="day",
                group_by="agent",
            ),
        ),
        Preset(
            id="day-by-mailbox",
            label="Day by Mailbox",
            spec=ReportSpec(
                metrics=list(PRESET_METRICS),
                date_from=coverage.from_date,
                date_to=coverage.to_date,
                granularity="day",
                group_by="mailbox",
            ),
        ),
        Preset(
            id="agent-leaderboard",
            label="Actor leaderboard",
            spec=ReportSpec(
                metrics=list(PRESET_METRICS),
                date_from=coverage.from_date,
                date_to=coverage.to_date,
                granularity="total",
                group_by="agent",
                sort=SortSpec(column=Metric.RESOLVED.value, direction="desc"),
            ),
        ),
    ]


DEFAULT_PRESET_ID = "day-by-agent"
"""What loads on first paint (PRD user story 3) — before any control is touched."""
