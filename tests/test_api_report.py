"""API-level test for the report route (issue 04).

`upstream` is faked via FastAPI dependency override, built from the committed
fixture — same pattern as `test_api_meta.py`, no HTTP library mocked, no
network.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.meta import get_upstream_client
from app.config import get_settings
from app.main import create_app
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_PATH = _DEV_FIXTURE_PATH


class _FixtureBackedClient:
    """Also counts `get_dataset()` calls (issue 08) — the full-window fetch
    that stands in for "reaching the upstream" in these tests. `get_dataset()`
    takes no date arguments at all (ADR-0001: always the whole Coverage
    Window, sliced locally), so a request's dates can never reach it, in
    range or out — that's why the coverage guard lives in `engine.execute()`,
    not in whether this route decides to call `get_dataset()` at all. See
    `test_engine.py::TestCoverageValidation` for the test that actually
    proves the property that matters: `execute()` refuses an out-of-range
    spec rather than silently returning a zero-filled table."""

    def __init__(self) -> None:
        raw = json.loads(FIXTURE_PATH.read_text())["response_json"]
        self._dataset = _normalise_dataset(
            raw, CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")
        )
        self.get_dataset_calls = 0

    async def get_dataset(self):
        self.get_dataset_calls += 1
        return self._dataset

    async def get_coverage_window(self):
        return self._dataset.coverage


@pytest.fixture
def fixture_client() -> _FixtureBackedClient:
    return _FixtureBackedClient()


@pytest.fixture
def app(fixture_client):
    application = create_app()
    application.dependency_overrides[get_upstream_client] = lambda: fixture_client
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def _spec(**overrides) -> dict:
    body = dict(
        metrics=["resolved"],
        date_from="2026-07-10",
        date_to="2026-07-23",
        granularity="day",
        group_by="agent",
    )
    body.update(overrides)
    return body


def test_report_route_returns_a_table_with_real_fixture_totals(client: TestClient) -> None:
    response = client.post("/api/v1/report", json=_spec(), headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()

    assert body["totals"]["resolved"] == 16372
    assert len(body["rows"]) == 14 * 108
    assert body["columns"] == [
        {"key": "resolved", "label": "Resolved", "kind": "counter", "unit": "count"}
    ]


def test_report_route_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/report", json=_spec())

    assert response.status_code == 401


def test_report_route_grouped_by_mailbox_reconciles_to_the_same_total(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/report", json=_spec(group_by="mailbox"), headers=_auth_headers()
    )

    assert response.status_code == 200
    assert response.json()["totals"]["resolved"] == 16372


def test_report_route_rejects_an_invalid_spec(client: TestClient) -> None:
    response = client.post(
        "/api/v1/report", json=_spec(date_from="2026-07-23", date_to="2026-07-10"),
        headers=_auth_headers(),
    )

    assert response.status_code == 422


class TestCoverageValidation:
    """API-level coverage of issue 08: the route translates `engine.execute`'s
    `CoverageRefusedError` into a 422 carrying the real Coverage Window, and
    a clamped range's Warning survives the round trip through the route."""

    def test_a_partially_overlapping_range_is_clamped_with_a_warning(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/report",
            json=_spec(date_from="2026-07-05", date_to="2026-07-12", group_by="none"),
            headers=_auth_headers(),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["warnings"]) == 1
        assert "2026-07-10" in body["warnings"][0]
        assert "2026-07-12" in body["warnings"][0]
        # The table itself reflects the clamped range, not the request as sent.
        assert [row["bucket"] for row in body["rows"]] == [
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
        ]

    def test_a_zero_overlap_range_is_refused_carrying_the_real_coverage_window(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/report",
            json=_spec(date_from="2026-06-01", date_to="2026-06-30"),
            headers=_auth_headers(),
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["coverage"] == {"from_date": "2026-07-10", "to_date": "2026-07-23"}

    def test_a_refused_request_never_carries_its_dates_into_the_upstream_fetch(
        self, client: TestClient, fixture_client: _FixtureBackedClient
    ) -> None:
        """`get_dataset()` (the fetch a real `UpstreamClient` would make) is
        called for a refused request exactly as it is for any other — it
        takes no date arguments at all (ADR-0001), so the requested range
        never reaches it either way. The property this issue actually
        guards against is a bad *answer*, not an extra HTTP call — the
        response here is still a 422 refusal, not a zero-filled 200, which
        is what `test_engine.py::TestCoverageValidation` proves directly at
        the unit level."""
        response = client.post(
            "/api/v1/report",
            json=_spec(date_from="2026-06-01", date_to="2026-06-30"),
            headers=_auth_headers(),
        )

        assert response.status_code == 422
        assert fixture_client.get_dataset_calls == 1

    def test_a_clamped_in_range_request_still_reaches_the_upstream_normally(
        self, client: TestClient, fixture_client: _FixtureBackedClient
    ) -> None:
        """A clamp is not a refusal — the (clamped) request still executes
        against real data, fetched the same way as any other request."""
        response = client.post(
            "/api/v1/report",
            json=_spec(date_from="2026-07-05", date_to="2026-07-12"),
            headers=_auth_headers(),
        )

        assert response.status_code == 200
        assert fixture_client.get_dataset_calls == 1
