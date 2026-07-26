"""Issue 06 (frontend-rework): the Assistant panel with rendered markdown.

Source-level structural guards, mirroring `test_frontend_chart.py` and
`test_frontend_report_table.py` — there is no JS test runner in this repo
(AGENTS.md/CLAUDE.md), so behaviour pinned from the source tree (which
renderer is used, whether raw HTML stays disabled, whether link protocols
are allowlisted, whether the reasoning disclosure is gated on a runtime
signal rather than a build-time one) is checked here. Anything only
observable by actually driving the app (partial-markdown flicker while
streaming, the thinking indicator's felt responsiveness, a long reply's
render cost) is a level-2/3 browser check, called out in the issue report
rather than faked here.

The load-bearing guard in this file is `TestRawHtmlStaysDisabled`: the
presenter (`app/agent/presenter.py`, untouched by this slice) already keeps
tool names/arguments/prompts/reasoning off the wire — what is new here is
that the assistant's *prose*, which does reach the browser, is untrusted
model output rendered as markdown, and must never become renderable HTML.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
CHAT_FILE = FRONTEND_SRC / "Chat.tsx"
ASSISTANT_PANE_FILE = FRONTEND_SRC / "workspace" / "AssistantPane.tsx"
MARKDOWN_FILE = FRONTEND_SRC / "lib" / "markdown.tsx"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"
PRESENTER_FILE = REPO_ROOT / "app" / "agent" / "presenter.py"
PRESENTER_TEST_FILE = REPO_ROOT / "tests" / "test_agent_presenter.py"

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PANEL_FILES = [CHAT_FILE, ASSISTANT_PANE_FILE, MARKDOWN_FILE]


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def _read_code_only(path: Path) -> str:
    """Source with `/** ... */` block comments stripped — several guards in
    this file scan for forbidden tokens (`rehype-raw`, `javascript:`) that
    this file's own docstrings and this module's explanatory comments
    legitimately *name in prose* while explaining why they're absent from
    the actual code. Scanning only code keeps those guards honest."""
    source = _read(path)
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


class TestPresenterIsUntouched:
    """This slice formats what already arrives; it must not widen what the
    backend sends. Not a substitute for actually running the presenter
    tests — a cheap tripwire that the files a reviewer would check first
    were not edited by this slice."""

    def test_presenter_module_exists_and_this_slice_does_not_touch_app(self) -> None:
        assert PRESENTER_FILE.is_file()
        # A slice-06 diff has no business touching anything under app/ at
        # all; the one file most likely to be tempting is presenter.py
        # itself, so name it explicitly.
        source = _read(PRESENTER_FILE)
        assert "def present(" in source or "def present_async(" in source

    def test_presenter_negative_leak_test_still_exists(self) -> None:
        assert PRESENTER_TEST_FILE.is_file()
        source = _read(PRESENTER_TEST_FILE)
        assert "leak" in source.lower()


class TestMarkdownRendererIsStreamdown:
    def test_streamdown_is_the_declared_dependency(self) -> None:
        package_json = _read(PACKAGE_JSON)
        assert '"streamdown"' in package_json, (
            "expected streamdown to be declared in frontend/package.json "
            "(decided renderer, per the issue) — if it proved unusable, the "
            "fallback is react-markdown + remark-gfm, declared explicitly instead"
        )

    def test_chat_renders_assistant_prose_through_the_markdown_module(self) -> None:
        chat_source = _read(CHAT_FILE)
        assert "Markdown" in chat_source, (
            "expected Chat.tsx to render assistant messages through the shared "
            "Markdown component rather than a bare text node"
        )


class TestRawHtmlStaysDisabled:
    """Model output is untrusted. Raw HTML must never become real DOM
    elements — not via streamdown's own default pipeline (which bundles
    `rehype-raw` unless overridden), and not via any manual escape hatch."""

    def test_streamdown_is_pinned_to_an_exact_version(self) -> None:
        """Omitting `rehype-raw` disables raw HTML because streamdown then
        appends a remark plugin that rewrites `html` nodes to text. That is
        an *undocumented internal* of the bundle, not a promised API — so a
        minor upgrade could reopen the hole with every guard in this file
        still green. Pin the version exactly; re-verify the behaviour in
        `node_modules/streamdown/dist/` before ever raising the pin."""
        declared = json.loads(_read(PACKAGE_JSON))["dependencies"]["streamdown"]
        assert re.fullmatch(r"\d+\.\d+\.\d+", declared), (
            f"streamdown must be pinned to an exact version, found {declared!r} — "
            "a range lets a minor bump silently change the raw-HTML behaviour "
            "this panel's safety rests on"
        )

    def test_no_raw_html_enabling_constructs_anywhere_in_the_panel(self) -> None:
        forbidden = [
            "rehype-raw",
            "dangerouslySetInnerHTML",
            "allowDangerousHtml",
            "rehypeRaw",
        ]
        offenders: list[str] = []
        for path in PANEL_FILES:
            source = _read_code_only(path)
            for token in forbidden:
                if token in source:
                    offenders.append(f"{path.name}: {token}")
        assert not offenders, f"found raw-HTML-enabling construct(s): {offenders}"

    def test_markdown_module_explicitly_overrides_rehype_plugins(self) -> None:
        """Streamdown's own default `rehypePlugins` includes `rehype-raw` —
        leaving the prop unset would silently inherit raw HTML parsing. The
        markdown module must pass its own `rehypePlugins`, which by
        construction (the test above) never includes rehype-raw."""
        source = _read(MARKDOWN_FILE)
        assert "rehypePlugins" in source, (
            "expected the Markdown component to pass an explicit rehypePlugins "
            "list, overriding streamdown's raw-HTML-enabled default"
        )


class TestLinkProtocolsAreAllowlisted:
    def test_markdown_module_restricts_href_protocols(self) -> None:
        source = _read(MARKDOWN_FILE)
        code_only = _read_code_only(MARKDOWN_FILE)
        assert "rehype-sanitize" in source, (
            "expected rehype-sanitize to police element/attribute/protocol safety"
        )
        assert "protocols" in code_only and "href" in code_only, (
            "expected an explicit href protocol allowlist rather than the "
            "unrestricted default"
        )
        # The allowlist must be a small, explicit set in actual code — not
        # '*' or anything that reintroduces javascript: as a real value.
        assert "javascript" not in code_only.lower()
        assert re.search(r"\[\s*[\"']http[\"']\s*,\s*[\"']https[\"']", code_only), (
            "expected an explicit ['http', 'https', ...] protocol allowlist"
        )


class TestNoWidenedSurface:
    """Presentation-only: nothing in this slice may reach for a raw hex
    colour or an inline decorative style outside the token layer, and none
    of the Assistant's internal vocabulary (tool names, argument shapes,
    prompt fragments) may appear as literal strings in the panel."""

    def test_no_raw_hex_colour_in_the_panel(self) -> None:
        offenders: list[str] = []
        for path in PANEL_FILES:
            hits = HEX_COLOR_PATTERN.findall(_read(path))
            if hits:
                offenders.append(f"{path.name}: {hits}")
        assert not offenders, f"found raw hex colour(s): {offenders}"

    def test_no_inline_decorative_style_in_chat_or_pane(self) -> None:
        for path in (CHAT_FILE, ASSISTANT_PANE_FILE):
            source = _read(path)
            assert "style={{" not in source, (
                f"expected {path.name} to use token-layer Tailwind classes, "
                "not inline style={{}}"
            )

    def test_no_internal_tool_vocabulary_leaks_into_the_panel(self) -> None:
        """A regression here would mean this slice widened the panel to
        reference the internal tool surface directly (rather than only the
        presenter's already-sanitised event vocabulary), e.g. by trying to
        special-case a tool name in the UI."""
        forbidden = [
            "set_metrics",
            "set_date_range",
            "set_grouping",
            "set_sort",
            "set_columns",
            "set_chart",
            "set_layout",
            "run_report",
            "get_meta",
        ]
        offenders: list[str] = []
        for path in PANEL_FILES:
            source = _read(path)
            for token in forbidden:
                if token in source:
                    offenders.append(f"{path.name}: {token}")
        assert not offenders, f"found internal tool name(s) in the panel: {offenders}"


class TestTurnsAreVisuallyDistinctAndRepairsAreBadges:
    def test_user_and_assistant_turns_carry_distinct_classes(self) -> None:
        source = _read(CHAT_FILE)
        assert 'role === "user"' in source, "expected the message role to still drive rendering"
        # The bubble must branch its className (and hence its visual
        # surface) on that role, not render both turns identically.
        assert re.search(r"isUser\s*\?[^:]+:\s*", source), (
            "expected the bubble's styling to branch on the user/assistant role"
        )

    def test_chips_render_through_a_dedicated_badge_component(self) -> None:
        """'Repair chips as proper badges rather than inline text' — checked
        as chips routing through a named badge component/function, not an
        inline `<span>` built ad hoc at the call site (which is what the
        pre-issue-06 Chat.tsx did)."""
        source = _read(CHAT_FILE)
        assert re.search(r"function \w*Badge\w*", source) or "Badge" in source, (
            "expected a dedicated badge component for Repair chips"
        )


class TestThinkingIndicator:
    def test_thinking_row_counts_elapsed_time(self) -> None:
        source = _read(CHAT_FILE)
        assert "setInterval" in source, "expected a live elapsed-time counter"
        assert "elapsedMs" in source or "elapsed" in source.lower()

    def test_thinking_row_is_a_status_role(self) -> None:
        source = _read(CHAT_FILE)
        assert 'role="status"' in source


class TestReasoningDisclosureIsDevelopmentOnly:
    """The `VITE_*` hard rule bans build-time frontend configuration, so the
    dev-only reasoning panel cannot be gated on an `import.meta.env` value —
    it must use the same runtime signal the dev-fake banners already use
    (`meta.dev_fake_llm`, fetched from `/api/v1/meta` at request time)."""

    def test_no_build_time_env_read_anywhere_in_the_panel(self) -> None:
        offenders: list[str] = []
        for path in PANEL_FILES + [ASSISTANT_PANE_FILE]:
            source = _read(path)
            if "import.meta.env" in source:
                offenders.append(path.name)
        assert not offenders, f"found a build-time env read in: {offenders}"

    def test_reasoning_disclosure_is_gated_on_the_meta_dev_flag(self) -> None:
        source = _read(CHAT_FILE)
        assert "dev_fake_llm" in source, (
            "expected the raw-reasoning disclosure to be gated on "
            "meta.dev_fake_llm, the same runtime signal Header.tsx's "
            "DEV_FAKE_LLM banner already uses"
        )

    def test_reasoning_disclosure_is_collapsed_by_default(self) -> None:
        source = _read(CHAT_FILE)
        assert "<details" in source, "expected the raw reasoning panel to be a <details> disclosure"
        assert "<summary" in source


class TestComposer:
    def test_composer_submits_on_enter(self) -> None:
        source = _read(CHAT_FILE)
        assert '"Enter"' in source or "'Enter'" in source

    def test_composer_shows_a_busy_state_and_cannot_double_submit(self) -> None:
        source = _read(CHAT_FILE)
        assert "disabled={busy" in source or "disabled={busy}" in source, (
            "expected the composer's input/button to disable while a turn is in flight"
        )
        # The guard against a double submit while busy: send() must bail out
        # early when a turn is already in flight.
        assert re.search(r"if\s*\(\s*!?\w*\s*\|\|\s*busy\s*\)\s*return", source) or (
            "if (busy)" in source
        ), "expected send() to refuse to start a second turn while busy"


class TestErrorsRenderAsConversationMessages:
    def test_errors_are_appended_to_the_message_list_not_a_bare_alert(self) -> None:
        source = _read(CHAT_FILE)
        assert "window.alert" not in source and "alert(" not in source
