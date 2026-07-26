"""Issue 07 (frontend-rework): dark mode.

Source-level structural guards plus a REAL computed check, mirroring
`test_frontend_chart.py` and `test_frontend_report_table.py` — there is no
JS test runner in this repo (AGENTS.md/CLAUDE.md), so behaviour pinned from
the source tree (which selectors carry the dark ramp, whether the eight
chart hues have dark counterparts, whether `sessionStorage` rather than
`localStorage` backs the override) is checked here. Anything only
observable by actually driving the app (the toggle visibly repainting the
workspace, the OS `prefers-color-scheme` listener firing on a live change,
label collisions in the chart) is a level-2 browser check called out in the
issue report rather than faked here.

The one constraint this file leans on hardest: `TestComputedContrast` does
not grep for a hex value and call it a day — it parses the literal hex
values straight out of `tokens.css` and runs the actual WCAG relative-
luminance contrast formula against them in Python, the same formula the
`dataviz` skill's own validator and any browser accessibility inspector
would use. A grep can tell you a value changed; only the formula can tell
you whether it is still legible.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
TOKENS_FILE = FRONTEND_SRC / "styles" / "tokens.css"
CHART_FILE = FRONTEND_SRC / "Chart.tsx"
THEME_STORE_FILE = FRONTEND_SRC / "store" / "themeStore.ts"
APP_FILE = FRONTEND_SRC / "App.tsx"
ASSUMPTIONS_MODAL_FILE = FRONTEND_SRC / "AssumptionsModal.tsx"

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# Component/library files that must never leak a light-only raw hex value —
# the token layer covers all colour in this app. Chart.tsx is excluded: its
# two palette arrays (light + dark) are the one place literal hex is
# permitted, already exhaustively checked by test_frontend_chart.py.
COMPONENT_FILES = [
    p
    for p in FRONTEND_SRC.rglob("*.tsx")
    if p.name != "Chart.tsx"
]


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def _read_code_only(path: Path) -> str:
    """Source with `/* ... */` block comments and `//` line comments
    stripped (extends `test_frontend_assistant_panel.py::_read_code_only`,
    which only stripped block comments, to line comments too) — several
    guards below scan for tokens (a raw hex, `localStorage`, `matchMedia`)
    that this file's own comments legitimately *name in prose* while
    explaining why the code doesn't use them. Scanning only code keeps
    those guards honest."""
    without_blocks = re.sub(r"/\*.*?\*/", "", _read(path), flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", without_blocks)


# ---------------------------------------------------------------------------
# tokens.css parsing helpers
# ---------------------------------------------------------------------------


def _light_root_block(css: str) -> str:
    """The first, unconditional `:root { ... }` block — the light values.
    Non-greedy up to the first `\\n}` is safe here because this particular
    block contains no nested braces."""
    match = re.search(r"^:root \{(.*?)\n\}", css, re.DOTALL | re.MULTILINE)
    assert match, "expected a bare `:root { ... }` block (the light ramp) in tokens.css"
    return match.group(1)


def _dark_media_block(css: str) -> str:
    match = re.search(
        r':root:where\(:not\(\[data-theme="light"\]\)\)\s*\{(.*?)\n  \}',
        css,
        re.DOTALL,
    )
    assert match, (
        'expected `:root:where(:not([data-theme="light"])) { ... }` inside the '
        "`@media (prefers-color-scheme: dark)` block"
    )
    return match.group(1)


def _dark_attr_block(css: str) -> str:
    match = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.DOTALL)
    assert match, 'expected a `:root[data-theme="dark"] { ... }` block (the explicit override)'
    return match.group(1)


def _parse_vars(block: str) -> dict[str, str]:
    return {
        f"--{name}": value.lower()
        for name, value in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{3,8})", block)
    }


def _theme_color_map(css: str) -> dict[str, str]:
    """`@theme`'s `--color-X: var(--underlying-Y)` entries, as
    `{"--color-X": "--underlying-Y"}` — the bridge between a Tailwind
    utility class (`bg-X`) and the runtime-swappable custom property it
    actually resolves to."""
    match = re.search(r"@theme \{(.*?)\n\}", css, re.DOTALL)
    assert match, "expected an `@theme { ... }` block in tokens.css"
    return dict(re.findall(r"(--color-[\w-]+):\s*var\((--[\w-]+)\)", match.group(1)))


# ---------------------------------------------------------------------------
# WCAG contrast — computed, not eyeballed
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
    """WCAG 2.x contrast ratio: (L1 + 0.05) / (L2 + 0.05), L1 >= L2."""
    lum_a, lum_b = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_ratio_sanity() -> None:
    """Pins the formula itself against well-known reference values before
    trusting it to gate anything: pure black on white is exactly 21:1, and
    a colour against itself is exactly 1:1."""
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#336699", "#336699") == pytest.approx(1.0, abs=0.01)


TEXT_FLOOR = 4.5  # WCAG AA, normal-size text
UI_FLOOR = 3.0  # WCAG AA, non-text UI component contrast (borders, focus rings)


class TestTokenLayerStructure:
    """The two dark-application paths (OS default, explicit override) must
    carry byte-identical values — a reviewer diffing them apart would be
    the first sign the ramp had drifted between "follow the system" and
    "the user picked dark"."""

    def test_light_and_both_dark_blocks_parse(self) -> None:
        css = _read(TOKENS_FILE)
        light = _parse_vars(_light_root_block(css))
        media_dark = _parse_vars(_dark_media_block(css))
        attr_dark = _parse_vars(_dark_attr_block(css))
        assert light, "expected hex custom properties in the light :root block"
        assert media_dark, "expected hex custom properties in the media dark block"
        assert attr_dark, "expected hex custom properties in the data-theme dark block"

    def test_media_dark_and_explicit_dark_are_identical(self) -> None:
        css = _read(TOKENS_FILE)
        media_dark = _parse_vars(_dark_media_block(css))
        attr_dark = _parse_vars(_dark_attr_block(css))
        assert media_dark == attr_dark, (
            "the OS-driven dark block and the explicit data-theme=dark block must "
            "carry the exact same values — a mismatch would mean 'follow the "
            "system' and 'the user picked dark' render differently"
        )

    def test_explicit_light_override_can_beat_a_dark_os_preference(self) -> None:
        """The media block must be guarded so that setting `data-theme="light"`
        while the OS prefers dark still renders light — otherwise the
        explicit override in `themeStore.ts` would be a no-op half the time."""
        css = _read(TOKENS_FILE)
        assert ':not([data-theme="light"])' in css, (
            'expected the dark media query to be guarded with :not([data-theme="light"]) '
            "so an explicit light override wins over a dark OS preference"
        )

    def test_explicit_override_selector_exists(self) -> None:
        css = _read(TOKENS_FILE)
        assert ':root[data-theme="dark"]' in css

    def test_every_theme_color_token_has_a_dark_counterpart_or_is_declared_invariant(
        self,
    ) -> None:
        """'No component may render unstyled or with a light-theme surface
        leaking into dark' — the structural half of that: every colour a
        component can reach for via a Tailwind utility class (`bg-cream`,
        `text-ink`, ...) resolves through `@theme` to an underlying custom
        property, and that property must be redefined for dark UNLESS it is
        one of the handful deliberately kept identical in both modes (the
        brand accent, and the two dark-surface-only tokens used for code
        blocks). A colour missing from this allowlist AND missing from the
        dark block would silently render its light value under a dark
        theme — the light-theme leak the issue names explicitly."""
        css = _read(TOKENS_FILE)
        theme_map = _theme_color_map(css)
        dark_vars = set(_parse_vars(_dark_attr_block(css)).keys())

        # Deliberately theme-invariant by design (documented in tokens.css /
        # ADR-0004): the brand accent (confined to CTAs/active states, kept
        # identical per architecture.md §7's "brand colour stays out of..."
        # adjacent rule and this project's own contrast measurements showing
        # it does not need a dark step), and the two tokens that are always
        # a dark surface regardless of theme (code blocks, on-dark text).
        invariant_underlying = {
            "--brand-primary",
            "--brand-primary-deep",
            "--brand-on-primary",
            "--surface-code",
            "--text-on-dark",
            "--text-on-dark-muted",
        }

        missing = []
        for color_name, underlying in theme_map.items():
            if underlying in invariant_underlying:
                continue
            if not underlying.startswith("--surface") and not underlying.startswith(
                "--text"
            ) and not underlying.startswith("--border") and not underlying.startswith(
                "--feedback"
            ):
                continue
            if underlying not in dark_vars:
                missing.append(f"{color_name} -> {underlying}")
        assert not missing, (
            f"theme colour(s) with no dark counterpart and not on the invariant "
            f"allowlist: {missing}"
        )


class TestNoRawHexOutsideTheTokenLayer:
    """`AssumptionsModal.tsx` used to hardcode `background: "white"` /
    `color: "#212529"` via inline `style` — exactly the light-surface-leak
    failure mode the issue names. Every component file (Chart.tsx excepted,
    covered by its own dedicated palette tests) must resolve colour through
    the token layer."""

    def test_no_component_file_has_a_raw_hex_colour(self) -> None:
        offenders: dict[str, list[str]] = {}
        for path in COMPONENT_FILES:
            hits = HEX_COLOR_PATTERN.findall(_read_code_only(path))
            if hits:
                offenders[str(path.relative_to(REPO_ROOT))] = hits
        assert not offenders, f"found raw hex colour(s): {offenders}"

    def test_assumptions_modal_no_longer_uses_inline_light_only_style(self) -> None:
        source = _read_code_only(ASSUMPTIONS_MODAL_FILE)
        assert 'background: "white"' not in source
        assert "#212529" not in source
        assert "bg-canvas" in source and "text-ink" in source


class TestChartDarkPalette:
    """The dataviz-skill-validated dark-surface counterparts of the eight
    series hues (architecture.md §7). Length/no-brand-colour/direct-index
    checks for BOTH arrays live in `test_frontend_chart.py`, which this
    file's docstring cross-references rather than duplicates; this class
    covers what's specific to entity-slot stability across a theme change.
    """

    def _palette(self, name: str) -> list[str]:
        source = _read(CHART_FILE)
        match = re.search(
            rf"const {name}:\s*readonly string\[\]\s*=\s*\[(.*?)\];", source, re.DOTALL
        )
        assert match, f"expected `const {name}: readonly string[] = [...]` in Chart.tsx"
        return [h.lower() for h in HEX_COLOR_PATTERN.findall(match.group(1))]

    def test_light_and_dark_palettes_are_the_same_length(self) -> None:
        light = self._palette("CHART_PALETTE")
        dark = self._palette("CHART_PALETTE_DARK")
        assert len(light) == len(dark) == 8, (
            f"light has {len(light)} hues, dark has {len(dark)} — both must be exactly 8"
        )

    def test_seriescolor_indexes_both_palettes_by_the_same_color_slot(self) -> None:
        """This IS the "entity keeps its colour slot across a theme change"
        guarantee, made structural rather than a documentation claim: both
        arrays are looked up with the literal same expression,
        `series.color_slot` — never a derived, offset, or independently
        computed index for the dark branch."""
        source = _read(CHART_FILE)
        assert re.search(r"CHART_PALETTE\[series\.color_slot\]", source), (
            "expected CHART_PALETTE[series.color_slot]"
        )
        assert re.search(r"CHART_PALETTE_DARK\[series\.color_slot\]", source), (
            "expected CHART_PALETTE_DARK[series.color_slot]"
        )

    def test_chart_reads_the_resolved_theme_from_the_shared_theme_store(self) -> None:
        """Chart.tsx must not read `matchMedia` or `import.meta.env` itself —
        it defers to the one shared theme resolution (`themeStore.ts`) that
        the Header's explicit toggle also writes to, so a toggle click and
        the chart repainting are never two different sources of truth."""
        source = _read_code_only(CHART_FILE)
        assert "useThemeStore" in source
        assert "matchMedia" not in source
        assert "import.meta.env" not in source


class TestThemeStore:
    """The explicit override (issue 07 acceptance criteria: "an explicit
    user override is available and persists for the session")."""

    def test_store_file_exists(self) -> None:
        assert THEME_STORE_FILE.is_file()

    def test_override_persists_via_session_storage_not_local_storage(self) -> None:
        """'Persists for the session,' not indefinitely — `sessionStorage`
        clears when the tab closes, `localStorage` would not. Using the
        wrong one would be a silent behavioural regression no type checker
        catches."""
        source = _read_code_only(THEME_STORE_FILE)
        assert "sessionStorage" in source
        assert "localStorage" not in source

    def test_no_build_time_configuration_anywhere_in_the_theme_store(self) -> None:
        source = _read_code_only(THEME_STORE_FILE)
        assert "import.meta.env" not in source
        assert "VITE_" not in source

    def test_default_is_null_meaning_follow_the_operating_system(self) -> None:
        source = _read(THEME_STORE_FILE)
        assert "prefers-color-scheme: dark" in source
        assert "ThemeOverride = " in source and '"light" | "dark" | null' in source

    def test_override_is_reflected_as_a_data_theme_attribute_not_a_class(self) -> None:
        """Must match `tokens.css`'s selectors exactly (`:root[data-theme=...]`)
        — a class-based mechanism here would silently fail to match either
        dark selector in tokens.css."""
        source = _read(THEME_STORE_FILE)
        assert 'setAttribute("data-theme"' in source
        assert "removeAttribute(\"data-theme\")" in source

    def test_app_wires_the_theme_watcher_regardless_of_sign_in_state(self) -> None:
        """Dark mode must apply to `SignIn.tsx` too, not just the signed-in
        workspace — the watcher is started from `App.tsx`, above the
        sign-in gate, not from `WorkspaceShell.tsx`."""
        app_source = _read(APP_FILE)
        assert "initThemeWatcher" in app_source


class TestWithheldValueStaysDistinctInBothThemes:
    """'The withheld-value dash must stay visibly distinct from a real
    figure and from an empty cell, and never read as a zero — in BOTH
    themes.' `ReportTable.tsx`'s `WithheldValue` already routes every
    withheld cell through one component styled with `text-stone`
    (`test_frontend_report_table.py` pins the component's existence); this
    file's job is confirming `text-stone` itself is still legible — not
    identical to full ink, not below the UI floor — under the dark ramp
    this issue adds."""

    def test_dark_stone_clears_the_ui_contrast_floor_on_both_surfaces_it_appears_on(
        self,
    ) -> None:
        css = _read(TOKENS_FILE)
        dark = _parse_vars(_dark_attr_block(css))
        stone, canvas, page = dark["--text-stone"], dark["--surface-canvas"], dark["--surface-page"]
        assert contrast_ratio(stone, canvas) >= UI_FLOOR
        assert contrast_ratio(stone, page) >= UI_FLOOR

    def test_dark_stone_is_visibly_dimmer_than_full_ink(self) -> None:
        """'Distinct from a real figure' — a real numeral renders in
        `text-ink`; the dash must not converge on that same contrast, or a
        withheld cell and a real one become visually indistinguishable."""
        css = _read(TOKENS_FILE)
        dark = _parse_vars(_dark_attr_block(css))
        stone_contrast = contrast_ratio(dark["--text-stone"], dark["--surface-canvas"])
        ink_contrast = contrast_ratio(dark["--text-ink"], dark["--surface-canvas"])
        assert stone_contrast < ink_contrast - 3, (
            "the withheld dash's contrast against canvas must sit well below "
            "full ink's, or it stops reading as visually distinct"
        )


class TestComputedContrast:
    """The load-bearing check the issue calls for by name: parse the actual
    hex values out of `tokens.css` and compute real WCAG contrast ratios —
    not a grep for "looks dark enough." Every assertion here recomputes the
    ratio from the literal hex pair; nothing is hardcoded from the
    docstring numbers above (those exist for human review, not as the
    source of truth the test trusts)."""

    def setup_method(self) -> None:
        css = _read(TOKENS_FILE)
        self.light = _parse_vars(_light_root_block(css))
        self.dark = _parse_vars(_dark_attr_block(css))

    # --- light (unchanged by this slice, asserted as a regression guard) ---

    def test_light_ink_on_canvas(self) -> None:
        ratio = contrast_ratio(self.light["--text-ink"], self.light["--surface-canvas"])
        assert ratio >= TEXT_FLOOR

    def test_light_ink_tint_on_canvas(self) -> None:
        assert (
            contrast_ratio(self.light["--text-ink-tint"], self.light["--surface-canvas"])
            >= TEXT_FLOOR
        )

    def test_light_steel_on_canvas_and_cream(self) -> None:
        canvas = self.light["--surface-canvas"]
        cream = self.light["--surface-cream"]
        assert contrast_ratio(self.light["--text-steel"], canvas) >= TEXT_FLOOR
        assert contrast_ratio(self.light["--text-steel"], cream) >= TEXT_FLOOR

    def test_light_danger_on_canvas_and_danger_soft(self) -> None:
        assert (
            contrast_ratio(self.light["--feedback-danger"], self.light["--surface-canvas"])
            >= TEXT_FLOOR
        )
        assert (
            contrast_ratio(self.light["--feedback-danger"], self.light["--feedback-danger-soft"])
            >= TEXT_FLOOR
        )

    # --- dark (derived by this slice) ---

    def test_dark_ink_on_canvas(self) -> None:
        assert contrast_ratio(self.dark["--text-ink"], self.dark["--surface-canvas"]) >= TEXT_FLOOR

    def test_dark_ink_tint_on_canvas(self) -> None:
        assert (
            contrast_ratio(self.dark["--text-ink-tint"], self.dark["--surface-canvas"])
            >= TEXT_FLOOR
        )

    def test_dark_steel_on_canvas_and_on_cream(self) -> None:
        """`ReportTable.tsx`'s "Warnings" eyebrow label sits on
        `--surface-cream`, not the canvas — the naive hue-family
        extrapolation from the light steel step passed on canvas (5.18:1)
        but FAILED on cream (4.38:1); this pins both surfaces so that
        regression can't come back unnoticed."""
        canvas = self.dark["--surface-canvas"]
        cream = self.dark["--surface-cream"]
        assert contrast_ratio(self.dark["--text-steel"], canvas) >= TEXT_FLOOR
        assert contrast_ratio(self.dark["--text-steel"], cream) >= TEXT_FLOOR

    def test_dark_danger_on_canvas_and_danger_soft(self) -> None:
        assert (
            contrast_ratio(self.dark["--feedback-danger"], self.dark["--surface-canvas"])
            >= TEXT_FLOOR
        )
        assert (
            contrast_ratio(self.dark["--feedback-danger"], self.dark["--feedback-danger-soft"])
            >= TEXT_FLOOR
        )

    def test_dark_border_hairline_strong_on_canvas_and_page_clears_ui_floor(self) -> None:
        """Non-text UI component contrast (input/button/column-header
        borders) — the pre-issue-07 hue-family extrapolation
        (`#3a3830`) measured 1.55:1 here, well under the 3:1 floor; this
        pins the corrected value (`#6b6862`)."""
        assert (
            contrast_ratio(self.dark["--border-hairline-strong"], self.dark["--surface-canvas"])
            >= UI_FLOOR
        )
        assert (
            contrast_ratio(self.dark["--border-hairline-strong"], self.dark["--surface-page"])
            >= UI_FLOOR
        )

    def test_light_border_hairline_strong_clears_the_ui_floor_too(self) -> None:
        """The same boundary, in the other theme. This token draws the outline
        of every text input, the segmented control and the table's column
        buttons — user interface components under WCAG 1.4.11, needing 3:1,
        not decorative hairlines. It shipped in slice 01 at `#c7c7c7`, which
        is 1.69:1 on canvas: an outline nobody can see. Pinned on all three
        surfaces it actually borders."""
        for surface in ("--surface-canvas", "--surface-page", "--surface-cream"):
            ratio = contrast_ratio(self.light["--border-hairline-strong"], self.light[surface])
            assert ratio >= UI_FLOOR, (
                f"light --border-hairline-strong is {ratio:.2f}:1 on {surface}, "
                f"under the {UI_FLOOR}:1 floor for a UI component boundary"
            )

    def test_dark_danger_is_a_distinct_hue_shifted_step_not_the_light_value_dimmed(
        self,
    ) -> None:
        """architecture.md §7 / the issue: 'the warm accent ... needs a
        genuinely different value on a dark one — not the same hue at
        lower opacity.' Applied here to `feedback-danger`: the dark value
        must be a different literal hex, not the light hex reused."""
        assert self.dark["--feedback-danger"] != self.light["--feedback-danger"]
        assert self.dark["--feedback-danger-soft"] != self.light["--feedback-danger-soft"]

    def test_dark_cream_is_a_distinct_hue_shifted_step_not_the_light_value_dimmed(
        self,
    ) -> None:
        """Same rule applied to the cream accent surface named explicitly
        in the issue text."""
        assert self.dark["--surface-cream"] != self.light["--surface-cream"]
        assert self.dark["--surface-cream-soft"] != self.light["--surface-cream-soft"]
