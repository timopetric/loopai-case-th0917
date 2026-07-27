"""Issue 03 (frontend-rework): the left builder rail restyle.

Source-level structural guards, mirroring `test_frontend_workspace_shell.py`
and `test_frontend_fonts_bundled.py` — there is no JS test runner in this
repo (AGENTS.md/CLAUDE.md), so behaviour pinned from the source tree (which
controls still exist, which primitives they're built from, what the
collapsed rail shows) is checked here. Anything only observable by actually
driving the app (a control edit re-fetching the report, the collapsed
strip's summary matching what a human just set) is a level-2 browser check,
called out in the issue report rather than faked here.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
BUILDER_FILE = FRONTEND_SRC / "workspace" / "BuilderPane.tsx"
UI_DIR = FRONTEND_SRC / "ui"

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def _collapsed_block(source: str) -> str:
    """Slice out the `if (collapsed) { ... }` early-return block so summary
    assertions can be scoped to what renders when the rail is collapsed,
    not the full expanded markup."""
    start = source.index("if (collapsed)")
    # The collapsed branch is the first top-level return in the component;
    # slice up to the closing of that block (the next `return (` marks the
    # expanded rail).
    end = source.index("return (", source.index("return (", start) + 1)
    return source[start:end]


def test_ui_primitives_exist_and_are_used_by_the_rail() -> None:
    """The issue asks for a small primitive set built from the token layer
    (text/date input, segmented control, selectable chips, section header),
    reusable by later slices — not one-off markup baked into BuilderPane."""
    assert UI_DIR.is_dir(), f"expected reusable primitives under {UI_DIR}"

    primitive_files = list(UI_DIR.glob("*.tsx"))
    assert len(primitive_files) >= 4, (
        f"expected at least 4 primitive components in {UI_DIR}, found {primitive_files}"
    )

    builder_source = _read(BUILDER_FILE)
    for primitive in primitive_files:
        stem = primitive.stem
        assert stem in builder_source, (
            f"BuilderPane.tsx does not appear to use the {stem} primitive from {UI_DIR}"
        )


def test_rail_still_has_every_existing_control() -> None:
    """'Every existing control is present and behaves as before' (acceptance
    criteria) — checked as the same store fields/wire values still being
    read and written, regardless of what markup renders them."""
    source = _read(BUILDER_FILE)

    for expected in [
        "dateFrom",
        "setDateFrom",
        "dateTo",
        "setDateTo",
        "coverage_window",
        "granularity",
        "setGranularity",
        "groupBy",
        "setGroupBy",
        "toggleMetric",
        "durationDisplay",
        "setDurationDisplay",
        "layout",
        "setLayout",
        "chartMetric",
        "setChartMetric",
    ]:
        assert expected in source, f"BuilderPane.tsx no longer references {expected!r}"

    # The wire values behind grouping/granularity/layout/duration-display
    # must survive the restyle unchanged (CONTEXT.md: "agent" is correct on
    # the wire and must not change).
    wire_values = [
        '"agent"', '"mailbox"', '"none"', '"day"', '"total"', '"avg"', '"long"', '"pivot"',
    ]
    for wire_value in wire_values:
        assert wire_value in source, f"expected wire value {wire_value} to survive"


def test_metric_picker_shows_a_selected_count() -> None:
    """'The Metric picker shows how many of the catalogue are selected'
    (acceptance criteria) — checked as the rendered count deriving from the
    live selection (`metrics.length`) and the live catalogue size
    (`meta`/`metrics` length), not a hardcoded number."""
    source = _read(BUILDER_FILE)
    assert "metrics.length" in source, "expected a live count of selected metrics"
    assert re.search(r"meta\??\.metrics(\?\.)?\.length", source), (
        "expected a live count of the metric catalogue size"
    )
    assert re.search(r"\bof\b", source), (
        "expected an 'N of M' style selected-count label in the Metrics section"
    )


def test_no_raw_hex_or_inline_style_in_the_rail() -> None:
    source = _read(BUILDER_FILE)
    hex_hits = HEX_COLOR_PATTERN.findall(source)
    assert not hex_hits, f"found raw hex colour(s) in BuilderPane.tsx: {hex_hits}"
    assert "style={{" not in source, "found inline style={{}} left in BuilderPane.tsx"


def test_no_unqualified_agent_in_the_rail_copy() -> None:
    source = _read(BUILDER_FILE)
    for lineno, line in enumerate(source.splitlines(), start=1):
        lowered = line.lower()
        assert "by agent" not in lowered, f"line {lineno}: unqualified 'agent' in copy"
        # A bare visible label of "Agent" (not "Actor") would also be a
        # regression; the grouping option's *label* must read "Actor".
    assert ">agent<" not in source.lower().replace(" ", ""), (
        "found a bare 'agent' JSX text node — grouping option must be labelled 'Actor'"
    )


def test_filter_control_is_always_rendered_not_conditional_on_grouping() -> None:
    """Issue 05: the Filter section must never appear/disappear as `groupBy`
    changes (that reflows the whole rail on every grouping toggle) — checked
    as there being no conditional (`groupBy !== "none" &&` / ternary guarding
    a mount) wrapping the filter control. It is disabled instead, which is
    covered by the next test."""
    source = _read(BUILDER_FILE)
    assert "entityFilter" in source, "expected the Filter control to read `entityFilter`"
    assert "setEntityFilter" in source, "expected the Filter control to write via `setEntityFilter`"

    # None of the existing "conditionally mount based on groupBy" patterns
    # should wrap the filter control — the pivot chart-metric picker shows
    # what that pattern looks like (`layout === "pivot" && (...)`); the
    # filter control must not have a `groupBy`-gated equivalent.
    assert 'groupBy === "none" && (' not in source
    assert 'groupBy !== "none" && (' not in source


def test_filter_control_disables_rather_than_hides_when_ungrouped() -> None:
    """When `groupBy === "none"` the filter input is `disabled` with an
    explanatory placeholder, not removed — this is what keeps the control
    always rendered (previous test) while still being unusable for a
    grouping that has no Actor/Mailbox breakdown to filter."""
    source = _read(BUILDER_FILE)
    assert re.search(r'groupBy\s*===\s*"none"', source), (
        "expected the filter control's disabled condition to key off groupBy === \"none\""
    )
    assert "disabled" in source
    assert "Group by Actor or Mailbox to filter" in source


def test_filter_label_follows_the_current_grouping() -> None:
    """Label reads 'Filter by Actor name' or 'Filter by Mailbox name',
    dynamically following `groupBy` — not a static label. Two hardcoded
    strings sitting side by side (e.g. in a comment, or both rendered at
    once) would satisfy a plain substring check without either depending on
    `groupBy` at all, so this pins the actual conditional: the Mailbox label
    must be selected by a `groupBy === "mailbox"` comparison."""
    source = _read(BUILDER_FILE)
    assert "Filter by Actor name" in source
    assert "Filter by Mailbox name" in source
    assert re.search(
        r'groupBy\s*===\s*"mailbox"\s*\?\s*"Filter by Mailbox name"', source
    ), (
        "expected the Mailbox label to be chosen by a groupBy === \"mailbox\" "
        "ternary, not a static/hardcoded label"
    )


def test_filter_control_debounces_before_writing_to_the_store() -> None:
    """A bare `onChange` writing straight through would fire a network
    request and a chart re-render on every keystroke (issue 05) — checked as
    a `setTimeout`-based debounce sitting between the input's `onChange` and
    the `setEntityFilter` store write, rather than `setEntityFilter` being
    called directly from an `onChange` handler."""
    source = _read(BUILDER_FILE)
    assert "setTimeout" in source, "expected a debounce timer gating the store write"
    assert re.search(r"onChange=\{[^}]*setEntityFilter", source) is None, (
        "the filter input's onChange must not call setEntityFilter directly (no debounce)"
    )


def test_external_filter_update_cancels_a_pending_debounce() -> None:
    """A pending debounce timer must not outlive an external store change.
    Without this, the race is: the user types (a timer is pending, nothing
    committed yet); the Assistant/a shared URL writes `entityFilter`
    externally; the sync effect updates the visible value but leaves the old
    timer running; the timer then fires and overwrites both the box and the
    store with the stale typed value — the control ends up showing something
    the store/URL/fetched report disagree with. The fix is for the
    external-sync effect (the one keyed on the `entityFilter` prop, matched
    against `lastCommitted`) to clear the pending timeout as part of handling
    a genuine external change. Checked as a `clearTimeout(timeoutRef` call
    appearing before the effect's `setValue`/`lastCommitted` sync — i.e.
    inside the sync branch, not only in the unmount-cleanup effect."""
    source = _read(BUILDER_FILE)
    effect_start = source.index("useEffect(() => {\n    if ((entityFilter")
    effect_end = source.index("}, [entityFilter]);", effect_start)
    sync_effect = source[effect_start:effect_end]
    assert "clearTimeout(timeoutRef" in sync_effect, (
        "the external-sync effect must cancel any pending debounce timer, or a "
        "keystroke made just before an external update can still overwrite it "
        "after the fact"
    )


def test_filter_control_never_renders_a_chip() -> None:
    """Chips are exclusively an Assistant-conversation concept (issue 05) —
    the Filter section must be built from `TextInput` alone, not `Chip`."""
    source = _read(BUILDER_FILE)
    filter_section_start = source.index('title="Filter"')
    next_section_start = source.index("<section", source.index("</section>", filter_section_start))
    filter_section = source[filter_section_start:next_section_start]
    assert "Chip" not in filter_section, "the Filter control must never emit a chip"


def test_entity_filter_store_field_and_setter_exist() -> None:
    """The store gains `entityFilter`/`setEntityFilter`, wired into
    `buildSpec`/`applySpec` exactly like every other field (issue 05)."""
    store_source = _read(REPO_ROOT / "frontend" / "src" / "store" / "reportSpecStore.ts")
    assert "entityFilter" in store_source
    assert "setEntityFilter" in store_source
    assert "entity_filter" in store_source, (
        "expected buildSpec/applySpec to map entityFilter <-> the wire field entity_filter"
    )


def test_collapsed_rail_shows_a_live_configuration_summary() -> None:
    """'The rail collapses to a narrow strip that still shows the active
    configuration in summary' — checked as the collapsed branch reading the
    same live store fields the expanded rail does, not static placeholder
    text."""
    source = _read(BUILDER_FILE)
    collapsed = _collapsed_block(source)

    for expected in ["dateFrom", "dateTo", "groupBy", "granularity", "metrics.length", "layout"]:
        assert expected in collapsed, (
            f"collapsed rail summary does not reference live state {expected!r}"
        )
