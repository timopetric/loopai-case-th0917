"""Issue 02 (frontend-rework): the three-pane workspace shell.

Source-level structural guards, mirroring `test_no_build_time_frontend_config.py`
and `test_frontend_fonts_bundled.py` — there is no JS test runner in this repo
(AGENTS.md/CLAUDE.md), so behaviour that can be pinned from the source tree
(what got split out of `App.tsx`, what got removed, what vocabulary survives)
is checked here; anything that can only be seen by actually running the app
(controls visibly moving as the Assistant streams a `spec` event) is a
level-2 browser check, not something these tests pretend to cover.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

WORKSPACE_DIR = FRONTEND_SRC / "workspace"
STORE_FILE = FRONTEND_SRC / "store" / "reportSpecStore.ts"
APP_FILE = FRONTEND_SRC / "App.tsx"

PANE_FILES = {
    "header": WORKSPACE_DIR / "Header.tsx",
    "builder": WORKSPACE_DIR / "BuilderPane.tsx",
    "report": WORKSPACE_DIR / "ReportPane.tsx",
    "assistant": WORKSPACE_DIR / "AssistantPane.tsx",
    "shell": WORKSPACE_DIR / "WorkspaceShell.tsx",
}


def _read(path: Path) -> str:
    assert path.is_file(), f"expected {path} to exist"
    return path.read_text()


def test_app_is_split_into_a_shell_header_and_three_panes() -> None:
    for name, path in PANE_FILES.items():
        assert path.is_file(), f"expected the {name} pane/shell at {path}"
    assert STORE_FILE.is_file(), f"expected the Report Spec store at {STORE_FILE}"


def test_app_tsx_is_reduced_to_the_auth_gate() -> None:
    """The 689-line monolith (builder + report + chat + header all inline)
    is what this issue removes. `App.tsx` should now hold only the sign-in
    gate and mounting the workspace shell — none of the builder fieldsets,
    the table, the chart or the chat markup that used to live here."""
    source = _read(APP_FILE)
    line_count = len(source.splitlines())
    assert line_count <= 60, (
        f"App.tsx is {line_count} lines — expected a thin auth-gate shell, "
        "not the old monolith"
    )

    # Telltale markup that must have moved OUT of App.tsx into the panes.
    for leftover in [
        "<legend>Metrics",
        "<legend>Date range",
        "Download CSV",
        "Download Excel",
        "<Chat ",
        "<ReportTable ",
        "<Chart ",
    ]:
        assert leftover not in source, f"found pane markup still in App.tsx: {leftover!r}"


def test_no_pane_imports_a_sibling_panes_module() -> None:
    """'no pane holding another pane's state' (issue acceptance criteria) —
    checked at the import level: a pane may import the shared store and
    shared lib modules, but never reach into a sibling pane file directly,
    which is how prop-drilled/duplicated state creeps back in."""
    sibling_names = {name: path.stem for name, path in PANE_FILES.items() if name != "shell"}

    for name, path in PANE_FILES.items():
        if name == "shell":
            continue  # the shell is explicitly allowed to compose the panes
        source = _read(path)
        for other_name, other_stem in sibling_names.items():
            if other_name == name:
                continue
            assert f"./{other_stem}" not in source and f'"{other_stem}"' not in source, (
                f"{path.name} appears to import sibling pane {other_stem} directly"
            )


def test_single_report_spec_store_is_shared_by_a_control_edit_and_the_assistant() -> None:
    """architecture.md §7 / the issue: one Zustand store, and both a human
    control edit (BuilderPane) and an Assistant `spec` event (AssistantPane/
    Chat) must update it through the SAME path — checked here as both
    referencing the same store module."""
    store_source = _read(STORE_FILE)
    assert re.search(r"from\s+[\"']zustand[\"']", store_source), (
        "expected the store to be built on zustand"
    )
    assert re.search(r"create[<(]", store_source), "expected zustand's create() to build the store"

    builder_source = _read(PANE_FILES["builder"])
    assert "reportSpecStore" in builder_source, "BuilderPane does not use the shared spec store"

    # The Assistant pane may delegate to Chat.tsx directly, which is fine —
    # what matters is that whichever file drives the Assistant's `spec`
    # events reaches the same store module, not a separate copy.
    assistant_source = _read(PANE_FILES["assistant"])
    chat_source = _read(FRONTEND_SRC / "Chat.tsx")
    assert "reportSpecStore" in assistant_source or "reportSpecStore" in chat_source, (
        "neither AssistantPane nor Chat.tsx uses the shared spec store"
    )


def test_developer_status_line_is_gone() -> None:
    """PRD / issue: 'The developer status line currently rendered to users
    is removed.' That was `<p>Backend status: {status}</p>` in the old
    `App.tsx`."""
    offending = []
    for path in FRONTEND_SRC.rglob("*.tsx"):
        text = path.read_text()
        if "Backend status" in text:
            offending.append(str(path))
    assert not offending, f"developer status line still present in: {offending}"


def test_side_panes_expose_a_collapse_control() -> None:
    """'Both side panes can be collapsed and restored' (acceptance
    criteria) — checked as each pane (or its shell wiring) exposing a
    collapse/expand affordance."""
    for name in ("builder", "assistant"):
        source = _read(PANE_FILES[name])
        shell_source = _read(PANE_FILES["shell"])
        combined = source + shell_source
        assert re.search(r"ollapse", combined), (
            f"no collapse/expand control found for the {name} pane"
        )


def test_no_unqualified_agent_in_user_visible_copy() -> None:
    """CONTEXT.md: 'agent' is banned as an unqualified term in UI copy; the
    wire value `\"agent\"` in `group_by` is correct and must not change. This
    checks the specific known offenders (plain-English example copy in the
    chat panel) rather than acting as a general-purpose parser of JSX text
    nodes vs. code."""
    offending = []
    for path in FRONTEND_SRC.rglob("*.tsx"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if "by agent" in line.lower():
                offending.append(f"{path}:{lineno}: {line.strip()}")

    assert not offending, "unqualified 'agent' found in user-visible copy:\n" + "\n".join(
        offending
    )
