"""`app/presets.py` unit tests (issue 12).

Level 1 verification per the issue: each preset's `ReportSpec` must validate
and, executed through the real engine against the committed fixture, must
produce the exact shape the issue describes. Reference figures pinned in the
issue brief and already exercised by `test_engine.py`: 14 days, 108 Actors,
103 Mailboxes, whole-window `resolved` = 16372.

No network, no LLM — same `_normalise_dataset(FIXTURE_RAW, WINDOW)` dataset
fixture as `test_engine.py`.
"""

import json

import pytest

from app.engine import execute
from app.presets import build_presets
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_RAW = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
WINDOW = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")

TOTAL_RESOLVED = 16372
NUM_DAYS = 14
NUM_ACTORS = 108
NUM_MAILBOXES = 103


@pytest.fixture
def dataset():
    return _normalise_dataset(FIXTURE_RAW, WINDOW)


def _preset_by_id(preset_id: str):
    match = [p for p in build_presets(WINDOW) if p.id == preset_id]
    assert len(match) == 1, f"expected exactly one preset with id {preset_id!r}"
    return match[0]


class TestDayByActor:
    """The client's verbatim request, and what loads on first paint."""

    def test_produces_fourteen_buckets_by_one_hundred_eight_actors(self, dataset) -> None:
        preset = _preset_by_id("day-by-agent")

        table = execute(preset.spec, dataset)

        buckets = {row.bucket for row in table.rows}
        actors = {row.group_key for row in table.rows}
        assert len(buckets) == NUM_DAYS
        assert len(actors) == NUM_ACTORS
        assert len(table.rows) == NUM_DAYS * NUM_ACTORS

    def test_spec_group_by_is_agent_not_none_or_mailbox(self, dataset) -> None:
        preset = _preset_by_id("day-by-agent")

        assert preset.spec.group_by == "agent"
        assert preset.spec.granularity == "day"


class TestDayByMailbox:
    """The same breakdown as Day by Actor, across the 103 inboxes instead."""

    def test_produces_fourteen_buckets_by_one_hundred_three_mailboxes(self, dataset) -> None:
        preset = _preset_by_id("day-by-mailbox")

        table = execute(preset.spec, dataset)

        buckets = {row.bucket for row in table.rows}
        mailboxes = {row.group_key for row in table.rows}
        assert len(buckets) == NUM_DAYS
        assert len(mailboxes) == NUM_MAILBOXES
        assert len(table.rows) == NUM_DAYS * NUM_MAILBOXES


class TestActorLeaderboard:
    """The whole range collapsed to a single Bucket, grouped by Actor,
    sorted descending — on a Counter (`resolved`), never a Duration Metric
    average (architecture.md §7's minimum-`_count`-threshold gotcha)."""

    def test_produces_one_bucket_with_one_hundred_eight_actors(self, dataset) -> None:
        preset = _preset_by_id("agent-leaderboard")

        table = execute(preset.spec, dataset)

        assert {row.bucket for row in table.rows} == {"total"}
        assert len(table.rows) == NUM_ACTORS
        assert sum(row.values["resolved"] for row in table.rows) == TOTAL_RESOLVED

    def test_sorts_globally_descending_on_the_counter_column(self, dataset) -> None:
        preset = _preset_by_id("agent-leaderboard")
        assert preset.spec.sort is not None
        assert preset.spec.sort.column == "resolved"
        assert preset.spec.sort.direction == "desc"

        table = execute(preset.spec, dataset)

        values = [row.values["resolved"] for row in table.rows]
        assert values == sorted(values, reverse=True)
        # Sanity: a real ranking, not a coincidental already-sorted fixture.
        assert values[0] > values[-1]
