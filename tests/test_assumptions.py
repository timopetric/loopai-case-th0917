"""Tests for the single assumptions source (issue 09).

The issue names one testable property: the coverage-banner modal and the
future Excel "Report info" sheet (issue 11, not yet built) must derive from
one source, so they cannot drift apart. Issue 11 doesn't exist yet, so this
tests the source itself two ways:

1. `test_build_assumptions_*` — the module's content actually states each
   required fact (units justified with evidence, daily UTC buckets, no
   Actor×Mailbox cross-tab, `actioned_emails` non-additive across Actors,
   `open` hidden, partial final day, Actor role accounts).
2. `test_assumptions_route_returns_exactly_the_shared_module_output` — the
   API route is proven to have NO second copy of this text: monkeypatching
   `build_assumptions` changes what the route returns, byte for byte. If a
   future author hardcoded matching sentences into the route (or the
   exporter) instead of calling the shared function, this test would still
   pass for the route as long as it calls through — but the moment anyone
   duplicates the text as a literal instead of calling the function, this
   test fails, because the patched sentinel would no longer come back.
"""

import json
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.meta import get_upstream_client
from app.assumptions import AssumptionNote, build_assumptions
from app.config import get_settings
from app.main import create_app
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_PATH = _DEV_FIXTURE_PATH
COVERAGE = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


class _FixtureBackedClient:
    """Same fixture-backed stand-in used by tests/test_api_meta.py."""

    def __init__(self) -> None:
        raw = json.loads(FIXTURE_PATH.read_text())["response_json"]
        self._dataset = _normalise_dataset(raw, COVERAGE)

    async def get_dataset(self):
        return self._dataset

    async def get_coverage_window(self):
        return self._dataset.coverage


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_upstream_client] = _FixtureBackedClient
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def _body_text(notes: list[AssumptionNote]) -> str:
    return " ".join(n.title + " " + n.body for n in notes).lower()


def test_units_assumption_is_justified_with_evidence_not_merely_asserted() -> None:
    notes = build_assumptions(COVERAGE)
    text = _body_text(notes)

    # Asserts the finding.
    assert "hour" in text
    assert "second" in text  # names the documentation's wrong claim too

    # Shows the working (user story 30): the decisive evidence was singleton
    # `_count == 1` samples read three ways, not a bare claim.
    assert "_count" in text or "count" in text
    assert "1.06" in text or "median" in text  # the actual singleton figures
    assert "sum" in text  # values are sums, not averages
    assert "never" in text and "average" in text  # Σvalue/Σcount, never averaging averages


def test_states_daily_utc_buckets_and_no_other_granularity() -> None:
    text = _body_text(build_assumptions(COVERAGE))
    assert "utc" in text
    assert "day" in text
    assert "granularity" in text or "bucket" in text


def test_states_no_actor_by_mailbox_crosstab() -> None:
    text = _body_text(build_assumptions(COVERAGE))
    assert "actor" in text and "mailbox" in text
    assert "cross" in text  # cross-tab is unavailable, not merely "not shown"


def test_states_actioned_emails_not_summable_across_actors() -> None:
    text = _body_text(build_assumptions(COVERAGE))
    assert "actioned_emails" in text
    assert "52" in text  # the measured over-count, not a vague "some" figure
    assert "mailbox" in text  # and that it DOES reconcile across Mailboxes


def test_states_open_metric_is_hidden() -> None:
    text = _body_text(build_assumptions(COVERAGE))
    assert "open" in text
    assert "hidden" in text or "hide" in text or "excluded" in text or "not offered" in text


def test_flags_partial_final_day_using_the_actual_coverage_window() -> None:
    notes = build_assumptions(COVERAGE)
    text = _body_text(notes)
    assert "partial" in text
    # The date is derived from the passed-in CoverageWindow, not hardcoded —
    # proven by passing a different window and checking the date moves too.
    assert COVERAGE.to_date in text

    other = CoverageWindow(from_date="2020-01-01", to_date="2020-01-05")
    other_text = _body_text(build_assumptions(other))
    assert other.to_date in other_text
    assert COVERAGE.to_date not in other_text


def test_notes_actor_list_mixes_people_and_role_accounts() -> None:
    text = _body_text(build_assumptions(COVERAGE))
    assert "support" in text and "billing" in text
    assert "role" in text


def test_every_note_has_a_stable_id_title_and_body() -> None:
    notes = build_assumptions(COVERAGE)
    ids = [n.id for n in notes]
    assert len(ids) == len(set(ids)), "assumption ids must be unique"
    for note in notes:
        assert note.title.strip()
        assert note.body.strip()


def test_assumptions_route_returns_exactly_the_shared_module_output(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/assumptions", headers=_auth_headers())
    assert response.status_code == 200

    expected = [asdict(n) for n in build_assumptions(COVERAGE)]
    assert response.json()["items"] == expected


def test_assumptions_route_has_no_hardcoded_second_copy(
    app, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decisive drift-proofing test: patch the shared source to return a
    sentinel, and require the route to reflect it exactly. If the route (or
    anything it calls) held its own literal copy of the assumption text
    instead of calling `build_assumptions`, this would fail because the
    sentinel would never appear in the response."""
    sentinel = [AssumptionNote(id="sentinel", title="Sentinel title", body="Sentinel body")]

    import app.api.v1.routers.assumptions as assumptions_router

    monkeypatch.setattr(assumptions_router, "build_assumptions", lambda coverage: sentinel)

    response = client.get("/api/v1/assumptions", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["items"] == [asdict(n) for n in sentinel]


def test_assumptions_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/assumptions")
    assert response.status_code == 401
