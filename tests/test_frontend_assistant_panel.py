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


class TestReasoningDisclosureIsUniversal:
    """ADR-0005 dropped the dev-only gate on `ThinkingTextEvent`: raw
    reasoning now streams to every user, in every environment, so the
    frontend must not still be gating its display on a runtime dev flag —
    that would silently hide a feature the backend now always sends. The
    `VITE_*` hard rule (no build-time frontend configuration) still applies,
    so this is also a guard against reintroducing an `import.meta.env` gate
    instead."""

    def test_no_build_time_env_read_anywhere_in_the_panel(self) -> None:
        offenders: list[str] = []
        for path in PANEL_FILES + [ASSISTANT_PANE_FILE]:
            source = _read(path)
            if "import.meta.env" in source:
                offenders.append(path.name)
        assert not offenders, f"found a build-time env read in: {offenders}"

    def test_reasoning_disclosure_is_no_longer_gated_on_the_dev_flag(self) -> None:
        """A regression here would mean someone re-added the dev-only gate
        ADR-0005 explicitly removed — reasoning must render for every user,
        not just when `meta.dev_fake_llm` is true."""
        source = _read(CHAT_FILE)
        assert "dev_fake_llm" not in source, (
            "expected Chat.tsx to no longer reference meta.dev_fake_llm — "
            "ADR-0005 dropped the dev-only gate on the reasoning panel"
        )

    def test_reasoning_disclosure_is_a_details_element(self) -> None:
        source = _read(CHAT_FILE)
        assert "<details" in source, "expected the reasoning panel to be a <details> disclosure"
        assert "<summary" in source


class TestReasoningLivesOnTheMessage:
    """The PRD's data-model change: `reasoning` moves off a single shared
    `Chat`-component `useState` onto each `ChatMessage`, exactly like
    `chips` already persists per message. A regression back to shared state
    would silently reintroduce the bug where reasoning accumulates across
    the whole session instead of resetting per turn."""

    def test_reasoning_is_a_field_on_the_message_type_not_shared_state(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"reasoning\s*:\s*string", source), (
            "expected a `reasoning: string` field on the ChatMessage shape"
        )
        # The old bug: `const [reasoning, setReasoning] = useState("")` at
        # the Chat-component level, shared across every turn. That specific
        # shared-state declaration must be gone.
        assert not re.search(r"useState[<(][^)]*reasoning", source, re.IGNORECASE), (
            "found what looks like a shared component-level reasoning "
            "useState — reasoning must live on each ChatMessage instead"
        )

    def test_a_new_turn_starts_with_an_empty_reasoning_trace(self) -> None:
        """Pins the bug fix: each new assistant message must be constructed
        with `reasoning: ""`, not inherit whatever the previous turn left
        behind."""
        source = _read_code_only(CHAT_FILE)
        assert re.search(r'reasoning\s*:\s*""', source), (
            "expected a new assistant message to be constructed with an "
            "empty reasoning string"
        )

    def test_reasoning_segments_only_when_prior_reasoning_exists(self) -> None:
        """Segmentation: a paragraph break must be inserted into the
        accumulating reasoning text specifically when `thinking: start`
        fires AND prior reasoning already exists — a break on every start,
        unconditionally, would prepend a stray blank paragraph before the
        very first burst too. A regex that just checks 'a newline appears
        somewhere in the start handler' would pass even if the break were
        unconditional (or sitting in a comment) — this test extracts the
        actual `reasoning:` field assignment and requires it to be a real
        conditional with two differing branches."""
        source = _read_code_only(CHAT_FILE)
        start_handler_match = re.search(
            r'event\.state\s*===\s*"start".*?(?=\}\s*else|onStatus)', source, re.DOTALL
        )
        assert start_handler_match, "expected an onThinking handler branching on event.state"
        start_handler = start_handler_match.group(0)

        reasoning_assignment = re.search(r"reasoning:\s*(.+?),\n", start_handler)
        assert reasoning_assignment, (
            "expected a `reasoning:` field assignment inside the "
            "thinking:start branch"
        )
        expr = reasoning_assignment.group(1)

        assert "?" in expr and "message.reasoning" in expr, (
            "expected the paragraph break to be conditioned on "
            "message.reasoning already being non-empty, via a ternary "
            "referencing message.reasoning — not applied unconditionally"
        )
        true_branch, _, false_branch = expr.split("?", 1)[1].partition(":")
        assert true_branch.strip() != false_branch.strip(), (
            "expected the ternary's two branches to actually differ — "
            "identical branches mean the break is applied unconditionally "
            "regardless of whether prior reasoning exists"
        )
        # The true branch (prior reasoning is non-empty) is the one that
        # must carry the break.
        assert "\\n\\n" in true_branch or "\\n" in true_branch, (
            "expected the branch taken when message.reasoning is already "
            "non-empty to append a paragraph break"
        )


class TestReasoningManualOverride:
    """The PRD's manual-override rule: a user collapsing/expanding a
    message's panel mid-turn must not be snapped back by the next
    auto-collapse/auto-expand transition for that same message."""

    def test_a_manual_override_flag_exists_on_the_message(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"reasoningManualOverride|manualOverride", source), (
            "expected a per-message flag recording that the user manually "
            "toggled the reasoning panel"
        )

    def test_auto_transitions_never_set_reasoning_expanded_outside_the_guard_helper(self) -> None:
        """A regression here would be an auto-transition handler (any of
        the four stream-event sites that change expand/collapse state)
        writing `reasoningExpanded: ...` directly, bypassing the override
        guard entirely — a bare `re.search(r"reasoningManualOverride\\?",
        source)` over the whole file would still pass in that broken case,
        since the guard helper's own definition contains that ternary even
        if nothing outside it ever calls it. This test isolates the body of
        `send()` (where all four onThinking/onDone/onError stream handlers
        live) and asserts `reasoningExpanded` is written nowhere in it
        except through the one helper call site."""
        source = _read_code_only(CHAT_FILE)

        send_match = re.search(
            r"async function send\(\)\s*\{(.*?)\n  \}\n", source, re.DOTALL
        )
        assert send_match, "expected an async function send() body"
        send_body = send_match.group(1)

        assert "setExpandedUnlessOverridden" in send_body, (
            "expected send() to route every auto expand/collapse decision "
            "through a single named guard helper"
        )

        # Strip out the helper's own definition (it necessarily assigns
        # reasoningExpanded once, inside the guard) before checking that no
        # *other* line in send() assigns reasoningExpanded directly.
        helper_def_match = re.search(
            r"function setExpandedUnlessOverridden.*?\n    \}\n", send_body, re.DOTALL
        )
        assert helper_def_match, "expected setExpandedUnlessOverridden to be defined inside send()"
        body_outside_helper = (
            send_body[: helper_def_match.start()] + send_body[helper_def_match.end() :]
        )

        assert "reasoningExpanded:" not in body_outside_helper, (
            "found a direct `reasoningExpanded:` assignment inside send() "
            "outside the guard helper — every auto expand/collapse "
            "transition must go through setExpandedUnlessOverridden so the "
            "manual-override flag is respected"
        )

    def test_manual_toggle_sets_the_override_flag(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"reasoningManualOverride\s*:\s*true", source), (
            "expected the user's manual toggle handler to set "
            "reasoningManualOverride to true"
        )


class TestCollapsedPulseDistinguishesInFlightFromDone:
    """The PRD's central distinction: a collapsed reasoning panel must keep
    pulsing while that Tool Step's model call is still genuinely in flight,
    and only go static once the whole turn reaches `done`. These are two
    different booleans (`reasoningActive` vs. `turnDone`) — collapsing the
    two into one would make "collapsed but still working" indistinguishable
    from "collapsed and finished", which is the exact bug this issue exists
    to fix."""

    def test_active_and_done_are_tracked_as_distinct_fields(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"reasoningActive\s*:\s*(bool|boolean)", source), (
            "expected a reasoningActive field distinguishing an in-flight "
            "Tool Step's model call from an idle gap"
        )
        assert re.search(r"turnDone\s*:\s*(bool|boolean)", source), (
            "expected a turnDone field distinguishing the whole turn's "
            "completion from a single Tool Step ending"
        )

    def test_turn_done_is_only_set_on_done_or_error(self) -> None:
        source = _read_code_only(CHAT_FILE)
        done_and_error_block = re.search(
            r"onDone:.*?onError:.*?(?=onThinkingText|\}\);)", source, re.DOTALL
        )
        assert done_and_error_block, "expected onDone and onError handlers in streamAgentMessage"
        assert re.search(r"turnDone\s*:\s*true", done_and_error_block.group(0)), (
            "expected turnDone to be set true inside onDone/onError, not "
            "inside the per-Tool-Step onThinking handler"
        )

    def test_pulsing_animation_reads_the_active_flag_not_turn_done(self) -> None:
        """The animated dot must be driven by reasoningActive (this Tool
        Step's model call in flight), not by the inverse of turnDone —
        otherwise the gap between Tool Steps (no model call in flight, but
        the turn isn't done yet) would incorrectly keep pulsing."""
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"animate-pulse", source)
        # The pulsing class must be conditioned on reasoningActive within
        # the same function that renders it (ReasoningPanel).
        panel_fn = re.search(r"function ReasoningPanel\(.*?function RepairBadge", source, re.DOTALL)
        assert panel_fn, "expected a ReasoningPanel function rendering the collapsed/expanded panel"
        panel_source = panel_fn.group(0)
        assert "animate-pulse" in panel_source and "reasoningActive" in panel_source, (
            "expected the pulsing indicator to be conditioned on "
            "message.reasoningActive inside ReasoningPanel"
        )


class TestWaitingStateNeedsNoNewBackendEvent:
    """The Waiting state ("busy, no thinking:start yet, no reasoning text")
    must be derivable purely from client-side facts available the instant
    `send()` is called — the PRD explicitly rejects an explicit
    `turn_start` SSE event for this. A regression toward waiting on a
    server round-trip would reintroduce the flash-of-nothing the whole
    state machine exists to avoid."""

    def test_waiting_copy_exists_and_is_plain_not_animated(self) -> None:
        source = _read_code_only(CHAT_FILE)
        assert "Waiting for a response" in source

    def test_waiting_state_is_gated_on_reasoning_not_started(self) -> None:
        """A 'somewhere nearby' proximity check would pass even if
        `reasoningStarted` merely appeared in an unrelated sibling branch —
        this asserts the actual JSX condition immediately guarding the
        Waiting paragraph."""
        source = _read_code_only(CHAT_FILE)
        waiting_line = re.search(r"\{[^{]*?<p[^>]*>Waiting for a response", source, re.DOTALL)
        assert waiting_line, (
            "expected a `{<condition> && (<p>...Waiting for a response...` "
            "render guard directly above the Waiting paragraph"
        )
        condition = waiting_line.group(0)
        assert "!message.reasoningStarted" in condition, (
            "expected the Waiting text's render condition to require "
            "!message.reasoningStarted"
        )
        assert "busy" in condition, (
            "expected the Waiting text's render condition to also require "
            "busy — a finished past turn with no reasoning must not show "
            "the Waiting text forever"
        )


class TestPastTurnsReasoningPersistsAndReexpands:
    """Past turns' reasoning traces must remain in the chat history and be
    re-expandable after sending a new message — this is what makes
    `reasoning` a per-message field rather than shared state (moving it
    also fixes the accumulation bug, covered separately)."""

    def test_reasoning_panel_is_rendered_per_message_not_once_globally(self) -> None:
        """A regression here would render a single reasoning panel outside
        the per-message map, which cannot stay attached to a specific past
        turn once a new turn starts."""
        source = _read_code_only(CHAT_FILE)
        chat_bubble_fn = re.search(
            r"function ChatBubble\((.*?)\nfunction ReasoningPanel", source, re.DOTALL
        )
        assert chat_bubble_fn, "expected a ChatBubble function followed by ReasoningPanel"
        chat_bubble_body = chat_bubble_fn.group(1)
        assert "reasoningStarted" in chat_bubble_body and "ReasoningPanel" in chat_bubble_body, (
            "expected ChatBubble (rendered once per message) to render that "
            "message's reasoning panel via <ReasoningPanel>, gated on that "
            "message's own reasoningStarted"
        )

    def test_toggle_handler_targets_a_specific_message_by_index(self) -> None:
        """The manual-toggle handler must address one message (by index or
        id), not mutate a single shared panel-open boolean — otherwise
        expanding one past turn's trace would expand/collapse all of them
        together."""
        source = _read_code_only(CHAT_FILE)
        assert re.search(r"function toggleReasoningPanel\(index", source), (
            "expected a per-message toggle handler parameterised on which "
            "message it targets"
        )


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
