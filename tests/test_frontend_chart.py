"""Issue 05 (frontend-rework): the chart's chrome in the token layer.

Source-level structural guards, mirroring `test_frontend_report_table.py` and
`test_frontend_builder_rail.py` — there is no JS test runner in this repo
(AGENTS.md/CLAUDE.md), so behaviour pinned from the source tree (which hex
values exist where, whether the direct-label threshold is 4, whether the
frame chrome reaches for token CSS variables instead of literals) is checked
here. Anything only observable by actually driving the app (label
collisions at eight series, hover feel, crosshair snapping) is a level-2
browser check, called out in the issue report rather than faked here.

The one constraint this file leans on hardest, straight from the issue: the
eight-hue series palette (`CHART_PALETTE` in `Chart.tsx`) is NOT part of the
rebrand. It must stay exactly eight hues, contain no brand colour, and no
ninth hue may ever be generated — so this file parses both `Chart.tsx` and
`tokens.css` and cross-checks them, rather than asserting on either file in
isolation.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
CHART_FILE = FRONTEND_SRC / "Chart.tsx"
TOKENS_FILE = FRONTEND_SRC / "styles" / "tokens.css"

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def _chart_palette_block(source: str) -> str:
    match = re.search(
        r"const CHART_PALETTE:\s*readonly string\[\]\s*=\s*\[(.*?)\];",
        source,
        re.DOTALL,
    )
    assert match, "expected a `const CHART_PALETTE: readonly string[] = [...]` array in Chart.tsx"
    return match.group(1)


def _brand_hex_values(tokens_source: str) -> set[str]:
    values = set()
    for name in ("--brand-primary", "--brand-primary-deep", "--brand-on-primary"):
        match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{3,8}})", tokens_source)
        if match:
            values.add(match.group(1).lower())
    assert values, "expected to find at least one brand hex value in tokens.css"
    return values


class TestPaletteIsUnchangedByTheRebrand:
    def test_palette_has_exactly_eight_hues(self) -> None:
        source = _read(CHART_FILE)
        block = _chart_palette_block(source)
        hexes = HEX_COLOR_PATTERN.findall(block)
        assert len(hexes) == 8, f"expected exactly 8 palette hues, found {len(hexes)}: {hexes}"

    def test_palette_contains_no_brand_colour(self) -> None:
        chart_source = _read(CHART_FILE)
        tokens_source = _read(TOKENS_FILE)
        palette_block = _chart_palette_block(chart_source)
        palette_hexes = {h.lower() for h in HEX_COLOR_PATTERN.findall(palette_block)}
        brand_hexes = _brand_hex_values(tokens_source)
        collision = palette_hexes & brand_hexes
        assert not collision, f"chart palette must not contain brand colour(s): {collision}"

    def test_no_ninth_hue_can_ever_be_generated(self) -> None:
        """The palette is a fixed literal array indexed by a bounded
        `color_slot` (0-7, guaranteed server-side and pinned by
        `tests/test_chart.py`) — never grown, never computed at runtime.
        Checked as: no dynamic colour synthesis (hsl()/chroma()/random) and
        no array-mutating calls on the palette anywhere in the file."""
        source = _read(CHART_FILE)
        forbidden = ["hsl(", "chroma(", "Math.random", ".push(", ".concat(", "Array.from"]
        offenders = [token for token in forbidden if token in source]
        assert not offenders, f"found colour-generation construct(s): {offenders}"

        # Indexing must be a direct, bounds-respecting lookup of the
        # server-provided slot — never modulo arithmetic against a counter,
        # which would silently wrap instead of the backend's own 0-7 cap.
        assert "CHART_PALETTE[series.color_slot]" in source or re.search(
            r"CHART_PALETTE\[\s*[\w.]*color_slot\s*\]", source
        ), "expected a direct CHART_PALETTE[...color_slot] lookup"
        assert "% CHART_PALETTE.length" not in source and "% 8" not in source, (
            "colour-slot lookup must not wrap via modulo — the backend already "
            "guarantees 0-7, and wrapping would silently paper over a bug that "
            "should be a data-integrity failure instead"
        )


class TestDirectLabelThreshold:
    def test_direct_label_threshold_is_four(self) -> None:
        source = _read(CHART_FILE)
        # The threshold may be a named constant rather than an inline
        # literal — accept either, but the value itself must be 4
        # (architecture.md §7 / issue 05).
        inline = re.search(r"chart\.series\.length\s*<=\s*4\b", source)
        named_constant = re.search(
            r"const\s+(\w+)\s*(?::\s*number)?\s*=\s*4\s*;.*?chart\.series\.length\s*<=\s*\1\b",
            source,
            re.DOTALL,
        )
        assert inline or named_constant, (
            "expected the direct-label gate to trigger at 4 or fewer series, "
            "via either an inline literal or a named constant equal to 4"
        )

    def test_direct_labels_are_wired_onto_the_line_marks(self) -> None:
        source = _read(CHART_FILE)
        assert "label=" in source, "expected a `label` prop on the Line marks for direct labelling"


class TestChromeUsesTheTokenLayer:
    def test_no_raw_hex_colour_outside_the_palette_definition(self) -> None:
        """Axes, grid, tooltip, legend and the disclosure must all resolve
        colour through the token layer (CSS custom properties / Tailwind
        classes) — the only hex literals allowed in the whole file are the
        eight palette entries themselves."""
        source = _read(CHART_FILE)
        palette_block = _chart_palette_block(source)
        source_without_palette = source.replace(palette_block, "")
        hits = HEX_COLOR_PATTERN.findall(source_without_palette)
        assert not hits, f"found raw hex colour(s) outside the palette block: {hits}"

    def test_axis_and_grid_reference_token_css_variables(self) -> None:
        source = _read(CHART_FILE)
        assert "var(--color-hairline" in source, (
            "expected the grid/axis lines to use a hairline token"
        )
        has_text_token = (
            "var(--color-steel)" in source
            or "var(--color-slate)" in source
            or "var(--color-muted)" in source
        )
        assert has_text_token, "expected axis tick/label text to use a text token"

    def test_no_inline_style_colours_the_series_swatch_via_series_stroke_on_text(self) -> None:
        """'Values and labels wear text tokens, never the series colour'
        (architecture.md §7) — the legend/tooltip text must not be coloured
        via the series' own stroke/fill, only its little swatch mark may be."""
        source = _read(CHART_FILE)
        # The old un-styled Legend/Tooltip left recharts' own defaults in
        # place, which colour item *text* by series colour. Custom
        # content renderers are the fix; assert they're present.
        assert "content={" in source, (
            "expected custom Tooltip/Legend content renderers so text can be "
            "pinned to token colours instead of recharts' default per-series text colour"
        )


class TestUnchangedChartRules:
    """Everything the issue says must stay exactly as it is."""

    def test_still_one_metric_one_y_axis(self) -> None:
        source = _read(CHART_FILE)
        assert source.count("<YAxis") == 1
        assert "yAxisId" not in source, "a second axis id would mean a dual axis"

    def test_gap_semantics_are_preserved(self) -> None:
        source = _read(CHART_FILE)
        assert "connectNulls={false}" in source, (
            "a withheld value must still render as a gap, never connected or dropped to zero"
        )

    def test_dropped_disclosure_still_present(self) -> None:
        source = _read(CHART_FILE)
        assert "chart.dropped" in source

    def test_chart_still_hides_on_a_null_chart(self) -> None:
        source = _read(CHART_FILE)
        assert "if (!chart) return null;" in source
