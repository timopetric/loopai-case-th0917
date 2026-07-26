"""Issue 01 (frontend-rework) acceptance criterion: Instrument Serif, Inter
and JetBrains Mono are self-hosted and bundled in the image, with no request
to any external host at runtime. A CDN link would add an external runtime
dependency that behaves differently in production than in development —
the exact class of mistake the no-build-time-configuration rule exists to
prevent (PRD, "Fonts are self-hosted and bundled").

These tests work at two levels, mirroring test_dev_fixture_ships_in_image.py
and test_spa_static_mount.py:
- source level (always runs): the font binaries are vendored as real files
  and nothing in frontend/ source reaches for an external font/CDN host.
- built level (skipped if frontend/dist doesn't exist): the fingerprinted
  font files actually land in the built assets, proving Vite bundled them
  rather than them being dead files only referenced by nothing.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

# The woff2 magic bytes ("wOF2"), so we know these are real font binaries
# and not empty files or stray text (e.g. a 404 page saved with a font
# extension).
WOFF2_MAGIC = b"wOF2"

FONT_FILES = [
    "instrument-serif-regular.woff2",
    "instrument-serif-italic.woff2",
    "inter-variable.woff2",
    "jetbrains-mono-variable.woff2",
]

# Hosts a font or generic CDN could be fetched from. If any of these appear
# in frontend source (outside node_modules/dist), a font or other asset is
# being loaded over the network at runtime instead of being bundled.
EXTERNAL_HOST_PATTERN = re.compile(
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net|unpkg\.com|"
    r"cdnjs\.cloudflare\.com|jsdelivr\.net"
)


def _font_dir() -> Path:
    return FRONTEND_SRC / "assets" / "fonts"


def test_all_three_font_families_are_vendored_as_real_woff2_files() -> None:
    font_dir = _font_dir()
    assert font_dir.is_dir(), f"expected vendored fonts under {font_dir}"

    for filename in FONT_FILES:
        path = font_dir / filename
        assert path.is_file(), f"missing vendored font file {path}"
        assert path.stat().st_size > 1000, f"{path} is suspiciously small for a font binary"
        with path.open("rb") as handle:
            header = handle.read(4)
        assert header == WOFF2_MAGIC, f"{path} does not look like a real woff2 file"


def test_no_frontend_source_references_an_external_font_or_cdn_host() -> None:
    result = subprocess.run(
        ["git", "grep", "-nIE", EXTERNAL_HOST_PATTERN.pattern, "--", "frontend"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    # git grep exits 1 when there are no matches, which is the passing case.
    offending = [line for line in result.stdout.splitlines() if line.strip()]
    assert not offending, "found external font/CDN host reference(s):\n" + "\n".join(offending)


@pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(),
    reason="requires a built frontend/dist (run `make frontend` build first)",
)
def test_built_assets_include_the_bundled_font_files() -> None:
    dist_assets = FRONTEND_DIST / "assets"
    assert dist_assets.is_dir(), f"expected {dist_assets} from the Vite build"

    shipped = {path.suffix for path in dist_assets.iterdir()}
    assert ".woff2" in shipped, (
        f"no .woff2 files found in {dist_assets} — Vite did not fingerprint the vendored fonts"
    )

    woff2_files = list(dist_assets.glob("*.woff2"))
    assert len(woff2_files) >= len(FONT_FILES), (
        f"expected at least {len(FONT_FILES)} bundled font files in {dist_assets}, "
        f"found {[p.name for p in woff2_files]}"
    )
