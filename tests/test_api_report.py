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
    def __init__(self) -> None:
        raw = json.loads(FIXTURE_PATH.read_text())["response_json"]
        self._dataset = _normalise_dataset(
            raw, CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")
        )

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
