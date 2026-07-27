"""Issue 08 (frontend-rework): accessibility and interaction polish.

Source-level structural guards plus REAL computed contrast checks, mirroring
`test_frontend_dark_mode.py`'s idiom — there is no JS test runner in this
repo (AGENTS.md/CLAUDE.md), so behaviour pinned from the source tree (which
selector carries the focus ring, whether the reduced-motion media query
exists, whether the virtualised table's ARIA row indices derive from the
full row set) is checked here.

Several acceptance criteria in the issue are explicitly NOT provable at
this level and are not faked here — see the module-level comments next to
each class for which ones and why. Those require a real browser (or a
screen reader) driving the assembled page, per `architecture.md` §12's
level-2/level-3 ladder.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
TOKENS_FILE = FRONTEND_SRC / "styles" / "tokens.css"
INDEX_CSS_FILE = FRONTEND_SRC / "index.css"
TABLE_FILE = FRONTEND_SRC / "ReportTable.tsx"
CHAT_FILE = FRONTEND_SRC / "Chat.tsx"
MODAL_FILE = FRONTEND_SRC / "AssumptionsModal.tsx"
HEADER_FILE = FRONTEND_SRC / "workspace" / "Header.tsx"
BUILDER_PANE_FILE = FRONTEND_SRC / "workspace" / "BuilderPane.tsx"
ASSISTANT_PANE_FILE = FRONTEND_SRC / "workspace" / "AssistantPane.tsx"
REPORT_PANE_FILE = FRONTEND_SRC / "workspace" / "ReportPane.tsx"
WORKSPACE_SHELL_FILE = FRONTEND_SRC / "workspace" / "WorkspaceShell.tsx"
TEXT_INPUT_FILE = FRONTEND_SRC / "ui" / "TextInput.tsx"
CHIP_FILE = FRONTEND_SRC / "ui" / "Chip.tsx"


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def _read_code_only(path: Path) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", "", _read(path), flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", without_blocks)


# ---------------------------------------------------------------------------
# WCAG contrast — same formula as test_frontend_dark_mode.py, duplicated
# rather than imported: each frontend test file in this repo is a
# self-contained source-level guard (see test_frontend_report_table.py,
# test_frontend_chart.py, etc. — none of them import from one another).
# ---------------------------------------------------------------------------


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _srgb_channel_to_linear(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    r, g, b = (_srgb_channel_to_linear(c) for c in _hex_to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a, lum_b = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


UI_FLOOR = 3.0  # WCAG AA / 1.4.11, non-text UI component contrast (focus rings, borders)


def _parse_hex_vars(block: str) -> dict[str, str]:
    return {
        f"--{name}": value.lower()
        for name, value in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{3,8})", block)
    }


def _light_root_block(css: str) -> str:
    match = re.search(r"^:root \{(.*?)\n\}", css, re.DOTALL | re.MULTILINE)
    assert match, "expected a bare `:root { ... }` block (the light ramp) in tokens.css"
    return match.group(1)


def _dark_attr_block(css: str) -> str:
    match = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.DOTALL)
    assert match, 'expected a `:root[data-theme="dark"] { ... }` block'
    return match.group(1)


class TestFocusRingContrast:
    """'Focus is always visible and meets contrast in both themes, on every
    interactive element' — the computed half of that claim. `--color-focus-
    ring` resolves to `--brand-primary`, which tokens.css documents as
    theme-invariant (same hex in light and dark), so "both themes" means
    "checked against both themes' surfaces," not two different ring
    colours."""

    def _focus_ring_hex(self) -> str:
        css = _read(TOKENS_FILE)
        light = _parse_hex_vars(_light_root_block(css))
        # --color-focus-ring: var(--brand-primary) — resolve one hop.
        assert "--color-focus-ring: var(--brand-primary)" in css
        return light["--brand-primary"]

    def test_index_css_defines_a_focus_visible_rule_outside_any_tailwind_layer(self) -> None:
        """Must sit outside `@layer` — a rule inside `@layer base` would
        still lose to Tailwind's `outline-none` utility (in the
        `utilities` layer) regardless of selector order, per CSS cascade
        layer semantics: layered rules always lose to unlayered ones."""
        css = _read(INDEX_CSS_FILE)
        match = re.search(r":focus-visible\s*\{([^}]*)\}", css)
        assert match, "expected a `:focus-visible { ... }` rule in index.css"
        assert "outline" in match.group(1)

        # Confirm the rule is not nested inside any `@layer { ... }` block.
        layer_blocks = re.findall(r"@layer[^{]*\{(.*?)\n\}", css, re.DOTALL)
        for block in layer_blocks:
            assert ":focus-visible" not in block, (
                "the :focus-visible rule must be outside every @layer block, "
                "or Tailwind's outline-none utility will keep winning"
            )

    def test_focus_ring_clears_ui_floor_against_light_theme_surfaces(self) -> None:
        ring = self._focus_ring_hex()
        css = _read(TOKENS_FILE)
        light = _parse_hex_vars(_light_root_block(css))
        for surface_name in ("--surface-canvas", "--surface-page", "--surface-cream"):
            ratio = contrast_ratio(ring, light[surface_name])
            assert ratio >= UI_FLOOR, (
                f"focus ring {ring} against light {surface_name} {light[surface_name]} "
                f"is only {ratio:.2f}:1, below the {UI_FLOOR}:1 floor"
            )

    def test_focus_ring_clears_ui_floor_against_dark_theme_surfaces(self) -> None:
        ring = self._focus_ring_hex()
        css = _read(TOKENS_FILE)
        dark = _parse_hex_vars(_dark_attr_block(css))
        for surface_name in ("--surface-canvas", "--surface-page", "--surface-cream"):
            ratio = contrast_ratio(ring, dark[surface_name])
            assert ratio >= UI_FLOOR, (
                f"focus ring {ring} against dark {surface_name} {dark[surface_name]} "
                f"is only {ratio:.2f}:1, below the {UI_FLOOR}:1 floor"
            )

    def test_outline_none_usages_do_not_use_important(self) -> None:
        """A component using Tailwind's `outline-none` (SignIn, TextInput,
        Chat's input) relies on the global unlayered rule above still
        beating it. An `!important` on any of those would break that —
        `!important` reverses normal author-origin cascade-layer ordering
        and would make the component's own (invisible) outline win again."""
        for path in (FRONTEND_SRC / "SignIn.tsx", TEXT_INPUT_FILE, CHAT_FILE):
            source = _read(path)
            for line in source.splitlines():
                if "outline-none" in line:
                    assert "!" not in line.split("outline-none")[1][:20], (
                        f"{path.name}: outline-none used with an !important-style "
                        "escape, which would defeat the global focus ring"
                    )


class TestReducedMotion:
    """'Motion respects prefers-reduced-motion — the thinking indicator's
    animation in particular.' The media query wraps a blanket kill-switch
    rather than a single `animate-pulse` override, so it also covers the
    hover/focus colour transitions the token layer defines everywhere
    else."""

    def test_reduced_motion_media_query_exists(self) -> None:
        css = _read(INDEX_CSS_FILE)
        assert "@media (prefers-color-scheme: dark)" not in css.split(
            "prefers-reduced-motion"
        )[0][-40:] or True  # sanity no-op; real assertion below
        assert "prefers-reduced-motion: reduce" in css

    def test_reduced_motion_block_disables_animation_and_transition(self) -> None:
        css = _read(INDEX_CSS_FILE)
        start = css.index("@media (prefers-reduced-motion: reduce)")
        # Brace-match from the media query's opening `{` to find its full
        # body, since the block nests a second rule (`*, *::before, ...`)
        # inside it and a non-greedy regex can't tell the inner `}` from
        # the outer one.
        open_brace = css.index("{", start)
        depth = 0
        end = None
        for i in range(open_brace, len(css)):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        assert end is not None, "unbalanced braces in prefers-reduced-motion block"
        body = css[open_brace:end]
        assert "animation-duration" in body
        assert "transition-duration" in body

    def test_thinking_row_animation_is_a_plain_utility_not_inline_style(self) -> None:
        """The reduced-motion override works by beating Tailwind's
        `animate-pulse` utility class — it cannot beat an inline
        `style={{ animation: ... }}`, since inline styles win over even
        unlayered stylesheet rules. Issue 10 folded the standalone
        `ThinkingRow` indicator into the per-message `ReasoningPanel` (two
        pulsing dots on screen at once, one with nothing behind it, was the
        exact bug this consolidation exists to fix) — pin the utility class
        to `ReasoningPanel` now so the global override still reaches it."""
        source = _read_code_only(CHAT_FILE)
        assert "animate-pulse" in source
        assert "ThinkingRow" not in source, (
            "expected the standalone ThinkingRow indicator to be gone — its "
            "elapsed-time counter now lives inside ReasoningPanel's summary"
        )
        assert re.search(r"function ReasoningPanel[\s\S]*?animate-pulse", source)
        # No inline animation style anywhere in the chat panel.
        assert "style={{" not in source or "animation" not in source


class TestSortableHeaderSemantics:
    """'Sortable headers expose their sort state semantically, not only as
    an arrow glyph' — `aria-sort` on the `<th>`, not just the ▲/▼ text
    the header button already renders."""

    def test_sortable_column_headers_carry_aria_sort(self) -> None:
        source = _read_code_only(TABLE_FILE)
        assert "aria-sort" in source, "expected aria-sort on the sortable column headers"
        # Derives from the exact same sort state the arrow glyph already
        # reads (`sort?.column === column.key`, `sort.direction === "desc"`)
        # rather than a second, independently-tracked notion of "sorted".
        aria_sort_block = re.search(r"aria-sort=\{([\s\S]*?)\}\s*\n\s*className=", source)
        assert aria_sort_block, "expected an aria-sort={...} expression on the column <th>"
        expr = aria_sort_block.group(1)
        assert "sort?.column === column.key" in expr
        assert 'sort.direction === "desc"' in expr
        assert '"descending"' in expr and '"ascending"' in expr and '"none"' in expr

    def test_pivot_headers_are_not_sortable_and_carry_no_aria_sort(self) -> None:
        """Pivot columns are Buckets, not metrics — `spec.sort` has nothing
        to bind to there (ReportTable.tsx's own docstring), so the pivot
        branch of the header must not claim a sort state it doesn't have."""
        source = _read(TABLE_FILE)
        pivot_branch = re.search(r"isPivot \? \(\s*<>(.*?)</>\s*\) : \(", source, re.DOTALL)
        assert pivot_branch, "expected to find the pivot/long conditional header branch"
        assert "aria-sort" not in pivot_branch.group(1)


class TestVirtualizedTableSemantics:
    """The constraint that matters most: the table must stay a table to
    assistive technology after virtualisation, and any ARIA row index added
    to repair that must reflect the row's position in the FULL row set —
    never its position in the rendered window.

    `@tanstack/react-virtual`'s `getVirtualItems()` already returns items
    whose `.index` is an index into the full `count` passed to
    `useVirtualizer` (not a 0..N-1 index over just the rendered window) —
    so the fix is to feed that same absolute index straight into
    `aria-rowindex`, never a separately-incremented counter that would
    silently drift to window-relative once overscan or scroll position
    changes which rows are actually mounted.
    """

    def test_table_declares_a_row_count_covering_the_full_row_set(self) -> None:
        source = _read(TABLE_FILE)
        assert re.search(r"aria-rowcount=\{flatItems\.length \+ 2\}", source), (
            "expected <table aria-rowcount={flatItems.length + 2}> (header + full "
            "flattened rows + totals row), not a count of what's rendered"
        )

    def test_row_index_is_derived_from_virtual_row_index_not_a_render_local_counter(
        self,
    ) -> None:
        source = _read(TABLE_FILE)
        # The virtualized rows must use virtualRow.index (absolute, full-set
        # position) directly in aria-rowindex, offset only by the fixed
        # header row — never `map`'s own iteration index over
        # `virtualRows`, which would be window-relative.
        assert re.search(r"aria-rowindex=\{virtualRow\.index \+ 2\}", source), (
            "expected aria-rowindex to be virtualRow.index + 2 (absolute position "
            "in the full flattened row set, header row is 1) — using the array "
            "index react-virtual assigns, not a locally incremented counter"
        )

    def test_header_and_footer_rows_have_explicit_row_indices(self) -> None:
        source = _read(TABLE_FILE)
        assert "aria-rowindex={1}" in source, (
            "expected the column header <tr> to be aria-rowindex 1"
        )
        assert re.search(r"aria-rowindex=\{flatItems\.length \+ 2\}", source), (
            "expected the totals footer row to be the last row index"
        )

    def test_column_headers_carry_scope_col(self) -> None:
        """Header associations (constraint: 'must not destroy ... the
        header associations') — every real column header gets an explicit
        `scope=\"col\"` rather than relying on `<thead>` positional
        inference, which a windowed `<tbody>` (only some rows ever mounted)
        makes riskier to lean on."""
        source = _read(TABLE_FILE)
        assert 'scope="col"' in source

    def test_spacer_rows_stay_hidden_from_assistive_technology(self) -> None:
        """The collapsed-space spacer rows are a virtualisation
        implementation detail, not real data — they must stay
        `aria-hidden` (already true before this issue; pinned here so a
        refactor can't silently drop it while adding the new
        aria-rowindex/aria-rowcount attributes)."""
        source = _read(TABLE_FILE)
        assert source.count('aria-hidden="true"') >= 2


class TestAssumptionsModalFocusManagement:
    """'The modal traps focus, closes on escape, and returns focus to the
    control that opened it.' Structural checks only — whether Tab actually
    wraps and whether focus visibly lands back on the header's link is a
    level-2 browser/screen-reader check (see the issue report)."""

    def test_modal_listens_for_escape_and_calls_onclose(self) -> None:
        source = _read_code_only(MODAL_FILE)
        assert "Escape" in source
        assert "onClose" in source

    def test_modal_captures_and_restores_the_previously_focused_element(self) -> None:
        source = _read_code_only(MODAL_FILE)
        assert "document.activeElement" in source
        assert ".focus()" in source

    def test_modal_traps_tab_within_its_own_focusable_elements(self) -> None:
        source = _read_code_only(MODAL_FILE)
        assert '"Tab"' in source or "'Tab'" in source
        assert "shiftKey" in source

    def test_modal_moves_focus_into_itself_on_open(self) -> None:
        """A dialog that opens without moving focus leaves a keyboard user's
        cursor behind the backdrop, still 'inside' the page that triggered
        it — the trap only works once focus is actually inside the
        dialog to begin with."""
        source = _read_code_only(MODAL_FILE)
        mounts_focus_on_open = bool(
            re.search(r"focus\w*\??\.\[0\]\?\.focus\(\)", source)
        ) or ("querySelectorAll" in source and ".focus()" in source)
        assert mounts_focus_on_open


class TestStreamingAnnouncement:
    """'The streaming reply is announced politely, without having the whole
    growing message re-read on every token.' Two structural pieces:

    1. The message log's live-region semantics must not treat a text
       mutation inside an already-added bubble as a reportable change —
       otherwise every token arriving via `onToken` re-triggers the
       region's announcement, which is exactly the bug named in the issue.
       `role="log"` implies `aria-live="polite"` with a default
       `aria-relevant` that includes text mutations; `aria-relevant=
       "additions"` narrows that to whole new messages only.
    2. A SEPARATE, short live region announces once, when the turn
       actually finishes (`onDone`) — not derived from the growing
       message text itself, so it cannot fire more than once per turn.
    """

    def test_log_region_is_scoped_to_additions_only(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r'role="log"[^>]*aria-relevant="additions"', source) or re.search(
            r'aria-relevant="additions"[^>]*role="log"', source
        ), (
            'expected the message-log container to pair role="log" with '
            'aria-relevant="additions", so token-by-token text mutations to the '
            "growing assistant bubble are not treated as reportable changes"
        )

    def test_a_separate_one_shot_region_announces_completion(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r'aria-live="polite"[^>]*className="sr-only"', source) or re.search(
            r'className="sr-only"[^>]*aria-live="polite"', source
        ), "expected a dedicated sr-only aria-live=polite region"

    def test_completion_region_is_updated_from_ondone_not_from_every_token(self) -> None:
        source = _read_code_only(CHAT_FILE)
        # There must be a piece of state set inside onDone that feeds the
        # sr-only region, and onToken must not write to that same state.
        on_done_match = re.search(r"onDone:\s*\(\)\s*=>\s*\{([^}]*)\}", source, re.DOTALL)
        assert on_done_match, "expected an onDone handler"
        assert "setAnnouncement" in on_done_match.group(1), (
            "expected onDone to set the announcement text exactly once per turn"
        )
        on_token_match = re.search(r"onToken:\s*\([^)]*\)\s*=>\s*\{([\s\S]*?)\n\s*\},", source)
        assert on_token_match
        assert "setAnnouncement" not in on_token_match.group(1), (
            "onToken must never touch the announcement region — that would "
            "reintroduce a per-token re-announcement"
        )


class TestTouchTargetFloor:
    """'Interactive targets meet the touch floor the design reference
    sets' — 44px (`design-reference-mistral.md`'s "Touch Targets" section:
    'Buttons render at 40-44px effective height... Form inputs render at
    44px height'). Checked as the relevant controls carrying an `h-11`/
    `min-h-11` (44px) sizing class. Pill-style controls (`SegmentedControl`)
    are exempted per the same reference section ('Pill tabs render at ~32px
    tall — bumps to 44px on mobile'), so they are deliberately not checked
    here."""

    def test_header_action_buttons_meet_the_floor(self) -> None:
        source = _read(HEADER_FILE)
        assert "h-11" in source

    def test_text_input_meets_the_floor(self) -> None:
        source = _read(TEXT_INPUT_FILE)
        assert "h-11" in source

    def test_chat_input_and_send_button_meet_the_floor(self) -> None:
        source = _read(CHAT_FILE)
        assert "h-11" in source

    def test_modal_close_button_meets_the_floor(self) -> None:
        source = _read(MODAL_FILE)
        assert "h-11" in source and "w-11" in source

    def test_pane_collapse_toggles_meet_the_floor(self) -> None:
        builder_source = _read(BUILDER_PANE_FILE)
        assistant_source = _read(ASSISTANT_PANE_FILE)
        assert "h-11" in builder_source or "min-h-11" in builder_source
        assert "h-11" in assistant_source or "min-h-11" in assistant_source

    def test_chip_meets_the_floor(self) -> None:
        source = _read(CHIP_FILE)
        assert "min-h-11" in source or "h-11" in source

    def test_table_column_reorder_buttons_are_a_real_target(self) -> None:
        """The two column-reorder buttons sit inside a dense data table, where
        44px square would widen every metric column. They are sized to 24px
        square instead — WCAG 2.5.8's actual AA floor, and a real
        non-overlapping box rather than an invisible expanded hit area that
        would collide with its neighbour two pixels away. The header row is
        already 44px tall, so this costs no vertical space."""
        source = _read(TABLE_FILE)
        move_buttons = re.findall(r"aria-label=\{`Move ", source)
        assert len(move_buttons) == 2, (
            f"expected the two column-reorder buttons, found {len(move_buttons)}"
        )
        assert source.count("h-6 w-6") >= 2, (
            "expected both column-reorder buttons to carry an explicit 24px "
            "square size rather than content-width padding"
        )


class TestBusyStateOnRoundTrip:
    """'A busy state on anything that triggers a round trip, so sorting a
    large report does not look like nothing happened.'"""

    def test_workspace_shell_tracks_report_loading_state(self) -> None:
        source = _read_code_only(WORKSPACE_SHELL_FILE)
        assert "reportLoading" in source
        assert "setReportLoading(true)" in source
        assert "setReportLoading(false)" in source

    def test_report_pane_surfaces_the_loading_state(self) -> None:
        source = _read_code_only(REPORT_PANE_FILE)
        assert "loading" in source
        assert "aria-busy" in source


class TestExportFailureDoesNotDisturbAGoodReport:
    """'An export failure surfaced without disturbing a good report already
    on screen.' Already true by construction before this issue (the export
    catch block only ever calls `setExportError`, never touches `table`) —
    pinned here as a regression guard rather than left as an implicit
    assumption."""

    def test_export_catch_block_never_clears_the_table(self) -> None:
        source = _read_code_only(WORKSPACE_SHELL_FILE)
        handle_export = re.search(
            r"async function handleExport[\s\S]*?\n  \}\n", source
        )
        assert handle_export, "expected a handleExport function"
        body = handle_export.group(0)
        assert "setTable(null)" not in body
        assert "setTable(" not in body

    def test_export_error_and_report_error_render_as_separate_banners(self) -> None:
        header_source = _read(HEADER_FILE)
        report_pane_source = _read(REPORT_PANE_FILE)
        assert "exportError" in header_source
        assert "reportError" in report_pane_source
        assert "exportError" not in report_pane_source
        assert "reportError" not in header_source
