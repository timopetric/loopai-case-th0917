"""Hard rule (AGENTS.md, architecture.md §9): no VITE_* or other build-time
frontend configuration anywhere in the repo. A build-time value would bind an
image to the machine that built it and fail only in production.

This scans for actual *usages* (env-var reads/definitions), not prose that
merely states the rule (this file, AGENTS.md, the architecture docs) —
otherwise the test would fail on its own documentation.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Real usage shapes: reading it in JS/TS, or defining/passing it as a build ARG/ENV.
USAGE_PATTERN = re.compile(
    r"import\.meta\.env\.VITE_|process\.env\.VITE_|^\s*(ARG|ENV)\s+VITE_|^\s*VITE_\w+\s*="
)

# Only the places a build-time value could actually be wired in.
SCAN_PATHS = ["frontend", "Dockerfile", "docker-compose.yml", "Makefile", ".env.example"]


def test_no_vite_env_vars_wired_anywhere() -> None:
    result = subprocess.run(
        ["git", "grep", "-nI", "--untracked", "-e", "VITE_", "--", *SCAN_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    offending = [
        line
        for line in result.stdout.splitlines()
        if USAGE_PATTERN.search(line.split(":", 2)[-1])
    ]

    assert not offending, "found VITE_* usage:\n" + "\n".join(offending)
