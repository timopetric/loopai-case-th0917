"""Issue 04 (frontend-rework): the Report Table — virtualised, readable at
1,512 rows.

Source-level structural guards, mirroring `test_frontend_builder_rail.py`
and `test_frontend_workspace_shell.py` — there is no JS test runner in this
repo (AGENTS.md/CLAUDE.md), so behaviour pinned from the source tree (which
library does the windowing, whether a pagination construct crept back in,
which classes carry numeral alignment/withheld-value/banner styling) is
checked here. Anything only observable by actually driving the app (smooth
scrolling at 1,512 rows, the withheld dash's visual distinctness, a sticky
header staying pinned while scrolling) is a level-2 browser check, called
out in the issue report rather than faked here.

The constraint this file leans on hardest: **the exporters never read the
DOM.** `frontend/src/lib/export.ts::exportReport` POSTs the current
`ReportSpec` to the backend and gets a fresh file back
(`app/exporters.py`, pinned against the engine's `ReportTable` by
`tests/test_exporters.py`) — it has no dependency on `ReportTable.tsx`, on
what is virtualised, or on scroll position at all. That is what makes "the
export always contains every row" true by construction rather than by
convention: there is no code path from "fewer rows in the DOM" to "fewer
rows in the file" for a virtualised table to accidentally take, because the
export was never wired to the DOM in the first place.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
TABLE_FILE = FRONTEND_SRC / "ReportTable.tsx"
EXPORT_FILE = FRONTEND_SRC / "lib" / "export.ts"
REPORT_LIB_FILE = FRONTEND_SRC / "lib" / "report.ts"
REPORT_PANE_FILE = FRONTEND_SRC / "workspace" / "ReportPane.tsx"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# A page size, a page index/number, or a `.slice(` on the row array feeding
# a request/render is exactly the "page 1 of 38" regression the issue names
# as the one thing that must never happen again — checked across every file
# in the chain from spec -> fetch -> render -> export.
PAGINATION_PATTERNS = [
    re.compile(r"page[_-]?size", re.IGNORECASE),
    re.compile(r"page[_-]?index", re.IGNORECASE),
    re.compile(r"page[_-]?number", re.IGNORECASE),
    re.compile(r"\bcurrentPage\b"),
    re.compile(r"\btotalPages\b"),
    re.compile(r"rows\.slice\("),
    re.compile(r"table\.rows\.slice\("),
]


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def test_report_table_file_exists() -> None:
    assert TABLE_FILE.is_file()


def test_no_pagination_construct_anywhere_in_the_report_or_export_chain() -> None:
    """The load-bearing guard for the issue's one hard constraint: no page
    size, page index/number, or a `.slice(` on the row set, in the table,
    the report-fetching lib, or the exporter lib."""
    offenders: list[str] = []
    for path in (TABLE_FILE, REPORT_LIB_FILE, EXPORT_FILE, REPORT_PANE_FILE):
        source = _read(path)
        for pattern in PAGINATION_PATTERNS:
            if pattern.search(source):
                offenders.append(f"{path.name}: matched {pattern.pattern!r}")
    assert not offenders, f"found pagination construct(s): {offenders}"


def test_export_never_reads_the_dom_or_the_table_component() -> None:
    """`exportReport` must build the file from a fresh backend request
    against the current `ReportSpec`, never from anything the (virtualised,
    partially-rendered) `ReportTable` DOM currently holds — otherwise a
    virtualised table's incomplete DOM would silently produce a truncated
    file, exactly the "page 1 of 38" bug the issue is about."""
    export_source = _read(EXPORT_FILE)
    assert "ReportTable" not in export_source, (
        "export.ts must not import/reference the ReportTable component or its rendered rows"
    )
    assert "document.querySelector" not in export_source
    assert "getElementById" not in export_source
    assert "/api/v1/export/" in export_source, (
        "expected exportReport to POST the spec to the backend export routes"
    )

    table_source = _read(TABLE_FILE)
    assert "exportReport" not in table_source and "triggerDownload" not in table_source, (
        "ReportTable.tsx must not itself trigger an export — exports are wired in "
        "WorkspaceShell from the spec, not from the table's own (partial) row set"
    )


def test_rows_are_virtualised_with_a_focused_library() -> None:
    """'Only the visible window goes into the document while the full row
    set stays in the Report Table' — checked as the table being built on a
    virtualizer rather than mapping every row into JSX unconditionally."""
    source = _read(TABLE_FILE)
    assert "@tanstack/react-virtual" in source, (
        "expected ReportTable.tsx to use @tanstack/react-virtual for row windowing"
    )
    assert "useVirtualizer" in source
    assert "getVirtualItems" in source

    package_json = _read(PACKAGE_JSON)
    assert '"@tanstack/react-virtual"' in package_json, (
        "expected @tanstack/react-virtual to be a declared dependency, not an ad-hoc import"
    )

    # The full row set must still reach the virtualizer's `count` — never a
    # sliced-down subset computed ahead of time.
    assert re.search(r"count:\s*flatItems\.length", source), (
        "expected the virtualizer's count to derive from the full flattened row set"
    )


def test_every_row_still_feeds_the_flattened_item_list() -> None:
    """The rows handed to the virtualizer must be built from `table.rows`
    directly (every row the engine returned), never a truncated copy."""
    source = _read(TABLE_FILE)
    assert "table.rows.forEach" in source or "table.rows.map" in source, (
        "expected the flattened item list to iterate over every table.rows entry"
    )
    assert re.search(r"table\.rows\.(forEach|map)\(\([^)]*\)\s*=>", source)


def test_numeric_columns_are_right_aligned_with_tabular_figures() -> None:
    """'Numeric columns use tabular figures and are right-aligned' —
    the single largest readability win named by the issue."""
    source = _read(TABLE_FILE)
    assert "tabular-nums" in source, "expected tabular-nums on numeric cells"
    assert "text-right" in source, "expected right-aligned numeric columns"
    assert "font-mono" in source, "expected the mono/tabular-figure font token on numeric cells"


def test_header_and_leading_columns_stick() -> None:
    """'The header sticks, and so do the leading Bucket and entity
    columns' — checked as sticky positioning present for the column header
    row and for the leading group/entity column."""
    source = _read(TABLE_FILE)
    assert "sticky top-0" in source, "expected the column header row to be sticky at the top"
    assert "sticky left-0" in source, (
        "expected the leading entity/group column to stick while scrolling horizontally"
    )
    # Bucket group headers are deliberately NOT sticky. They used to be
    # `sticky top-11`, which detached them and painted them over the first
    # row of their own Bucket (found in the issue 09 browser pass). Scan
    # code only — this file's comments name the old class in prose, and an
    # assertion that passes on a comment is worse than no assertion.
    code_only = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("//")
    )
    assert "sticky top-11" not in code_only, (
        "the Bucket group header must not be sticky — it overlapped the first row of its "
        "own Bucket. It is a divider and scrolls with its rows."
    )


def test_bucket_renders_as_a_grouping_not_a_repeated_cell() -> None:
    """'The Bucket becomes a grouping, not a repeated cell' — checked as a
    dedicated group-header item type that spans the full row (`colSpan`)
    instead of a per-row Bucket column repeating the same date."""
    source = _read(TABLE_FILE)
    assert '"group"' in source, "expected a distinct 'group' item kind for Bucket headers"
    assert "colSpan={totalColumnCount}" in source, (
        "expected the Bucket group header to span the full row width, not sit in a per-row column"
    )
    # The old per-row Bucket column ("Day" th/td) must be gone.
    assert "<th style={headerStyle}>Day</th>" not in source
    assert 'row.bucket}</td>' not in source.replace(" ", "")


def test_density_control_offers_comfortable_and_compact() -> None:
    """'A density control switches between comfortable and compact'."""
    source = _read(TABLE_FILE)
    assert '"comfortable"' in source
    assert '"compact"' in source
    assert "SegmentedControl" in source, (
        "expected the density control to reuse the shared primitive"
    )


def test_withheld_value_is_a_distinct_component_never_a_bare_dash_string() -> None:
    """'A withheld value is visually distinct from both a real figure and an
    empty cell, and never reads as zero' — checked as withheld cells routing
    through one dedicated component (so the styling can't drift between
    call sites) rather than an inline `value === null ? "—" : value` with no
    distinguishing style, which is what the pre-issue-04 table did."""
    source = _read(TABLE_FILE)
    assert "function WithheldValue" in source
    assert "<WithheldValue" in source
    assert re.search(r"value === null \? <WithheldValue", source)
    # It must never fall back to the number 0.
    assert "value === null ? 0" not in source


def test_warnings_render_as_a_banner_not_a_bare_list() -> None:
    """'Warnings render as a banner above the table, not loose paragraphs'.

    The role is `status`, not `alert`: issue 09's browser pass found that an
    assertive region interrupted the user on every report rebuild, and every
    control change rebuilds the report. These Warnings are a standing property
    of the result, so they are announced politely."""
    source = _read(TABLE_FILE)
    assert 'role="status"' in source
    assert 'role="alert"' not in source, (
        "the Warnings banner must announce politely — an assertive region cuts "
        "across whatever the user is reading each time the report rebuilds"
    )
    # A banner has a surface/border, not just a bare <ul>.
    assert "rounded-lg" in source and "border" in source
    assert "<ul" in source and "warning" in source.lower()


def test_sort_column_order_and_pivot_are_unchanged_in_behaviour() -> None:
    """'Sorting, column reordering and the pivot layout keep their current
    behaviour' — checked as the same callback contracts and wire-shaped
    state still driving the table."""
    source = _read(TABLE_FILE)
    for expected in ["onSort", "onMoveColumn", "isPivot", "sort?.column", "layout"]:
        assert expected in source, f"ReportTable.tsx no longer references {expected!r}"


def test_no_raw_hex_colour_in_the_table() -> None:
    source = _read(TABLE_FILE)
    hits = HEX_COLOR_PATTERN.findall(source)
    assert not hits, f"found raw hex colour(s) in ReportTable.tsx: {hits}"


def test_inline_style_is_scoped_to_virtualizer_scroll_math_only() -> None:
    """The token layer bans decorative inline `style={{}}` — but a row
    virtualizer fundamentally needs a computed pixel offset/height per
    render, which is scroll-position arithmetic, not a design value. This
    checks the narrower, real invariant: every `style={{` in the file only
    ever sets `height` (the spacer-row technique), never a colour, font, or
    spacing property that belongs in the token layer instead."""
    source = _read(TABLE_FILE)
    # Only inspect real JSX attributes, not this file's own doc comments
    # (the module docstring above quotes `style={{ height }}` as prose).
    code_lines = [
        line
        for line in source.splitlines()
        if not line.strip().startswith("*") and "//" not in line[:4]
    ]
    code_source = "\n".join(code_lines)
    style_blocks = re.findall(r"style=\{\{([^}]*)\}\}", code_source)
    assert style_blocks, (
        "expected the spacer-row virtualization technique to use style={{ height: ... }}"
    )
    for block in style_blocks:
        # The property must be `height` and nothing else; the value may be
        # arithmetic (the spacer rows use a computed offset, and the grid's
        # own height is `rows chosen x row height`, both pixel math rather
        # than design values).
        assert re.fullmatch(r"\s*height\s*:\s*[A-Za-z0-9_.\s*+\-/()]+\s*", block), (
            f"found an inline style block that isn't pure height math: {block!r}"
        )

def test_report_pane_gives_the_table_a_bounded_scroll_container() -> None:
    """Virtualization only works inside a height-bounded scroll parent —
    checked as the pane switching from page-level `overflow-y-auto` to a
    flex column with a `min-h-0 flex-1` region around the table, per the
    virtualizer's own requirement of a real scroll element."""
    source = _read(REPORT_PANE_FILE)
    assert "min-h-0" in source
    assert "flex-1" in source


def test_visible_row_count_is_a_viewport_size_not_a_page_size() -> None:
    """The row-count picker changes how many rows are ON SCREEN; it must
    never become a page size. Both exporters derive from the same Report
    Table, and a graded user story requires the exported file to match what
    is on screen — so the chosen count may size the scroll container, and
    must not reach `flatItems`, `table.rows`, or the virtualizer's `count`."""
    source = _read(TABLE_FILE)

    assert "VISIBLE_ROWS_OPTIONS" in source and "visibleRows" in source, (
        "expected a visible-row-count control on the table"
    )
    assert "100" in source, "the picker should offer up to 100 rows"

    # The count may only be used for pixel height, never to slice the data.
    for forbidden in (
        "table.rows.slice",
        "flatItems.slice",
        "rows.slice(0, visibleRows",
        "slice(0, visibleRows",
    ):
        assert forbidden not in source, (
            f"{forbidden!r} would turn the row-count picker into pagination — "
            "every row must stay in the Report Table so the export matches the screen"
        )

    # The virtualizer must still count the FULL flattened set.
    assert "count: flatItems.length" in source, (
        "the virtualizer's count must stay the full row set, not the visible count"
    )
