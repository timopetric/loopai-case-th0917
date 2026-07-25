"""Regression test for a real bug: `DEV_FAKE_UPSTREAM`'s fixture must resolve
inside the built Docker image, or Level 2 of the verification ladder
(`make run` with `DEV_FAKE_UPSTREAM=1`, architecture.md §12) fails with a
missing-file error.

The fixture originally lived under `tests/fixtures/`, which `.dockerignore`
excludes and which the Dockerfile never `COPY`s. This test pins the fixture
inside `app/`, the one directory tree the Dockerfile actually ships, and
parses the Dockerfile's own `COPY` lines rather than hardcoding "app" — so a
future change to what the image ships is what this test tracks, not a
duplicated assumption about it.
"""

import re
from pathlib import Path

from app.upstream import _DEV_FIXTURE_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _runtime_stage_copy_sources() -> list[Path]:
    """Directories/files the runtime (final) Docker stage COPYs from the
    build context — i.e. what actually ends up in the shipped image, as
    opposed to the frontend-build stage's own inputs."""
    text = DOCKERFILE.read_text()
    # Only look at COPY instructions that pull from the build context (no
    # `--from=`), which excludes the multi-stage frontend artifact copy.
    sources = []
    for line in text.splitlines():
        match = re.match(r"\s*COPY\s+(?!--from=)(\S+)\s+\S+\s*$", line)
        if match:
            sources.append((REPO_ROOT / match.group(1).rstrip("/")).resolve())
    return sources


def test_dockerfile_actually_copies_the_directory_the_fixture_lives_in() -> None:
    copy_sources = _runtime_stage_copy_sources()
    assert copy_sources, "expected at least one COPY instruction in the Dockerfile"

    assert any(
        _DEV_FIXTURE_PATH.is_relative_to(source) for source in copy_sources
    ), (
        f"{_DEV_FIXTURE_PATH} is not under any directory the Dockerfile COPYs "
        f"({copy_sources}) — DEV_FAKE_UPSTREAM would 404 in the built image"
    )


def test_dev_fixture_directory_is_not_dockerignored() -> None:
    ignore_patterns = [
        line.strip()
        for line in DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    relative = _DEV_FIXTURE_PATH.relative_to(REPO_ROOT)

    # A literal, un-negated "tests" (or a parent of the fixture) entry would
    # silently drop it from the build context even if the Dockerfile COPYs it.
    for pattern in ignore_patterns:
        if pattern.startswith("!"):
            continue
        assert str(relative) != pattern and not str(relative).startswith(pattern + "/"), (
            f".dockerignore pattern {pattern!r} would exclude {relative}"
        )


def test_dev_fixture_path_is_under_app_not_tests() -> None:
    """The narrower, direct assertion: this is a dev-only runtime path
    (ADR-0003's one exception), so it belongs under `app/`, not `tests/`."""
    app_dir = (REPO_ROOT / "app").resolve()
    tests_dir = (REPO_ROOT / "tests").resolve()

    assert _DEV_FIXTURE_PATH.is_relative_to(app_dir)
    assert not _DEV_FIXTURE_PATH.is_relative_to(tests_dir)


def test_dev_fixture_file_exists_at_the_resolved_path() -> None:
    assert _DEV_FIXTURE_PATH.is_file()
