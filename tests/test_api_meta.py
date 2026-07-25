"""API-level test for the metadata route (issue 03).

`upstream` is faked via FastAPI dependency override, built directly from the
committed fixture — no HTTP library mocked, no network. This exercises the
seam architecture.md §3 names explicitly: routes depend on
`get_upstream_client`, and tests override that dependency.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.meta import get_upstream_client
from app.config import get_settings
from app.main import create_app
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

# Same committed file DEV_FAKE_UPSTREAM serves at runtime — one copy, not a
# duplicate under tests/ (see tests/test_dev_fixture_ships_in_image.py).
FIXTURE_PATH = _DEV_FIXTURE_PATH


class _FixtureBackedClient:
    """A stand-in for `UpstreamClient` that never touches the network,
    returning the normalised fixture dataset every time."""

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


def test_meta_route_shape_and_real_fixture_numbers(client: TestClient) -> None:
    response = client.get("/api/v1/meta", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()

    assert body["coverage_window"] == {"from_date": "2026-07-10", "to_date": "2026-07-23"}
    assert len(body["actors"]) == 108
    assert len(body["mailboxes"]) == 103
    assert body["dev_fake_upstream"] is False

    metric_keys = {m["key"] for m in body["metrics"]}
    assert "open" not in metric_keys  # the always-empty metric must not be offered
    assert "resolved" in metric_keys
    assert "resolve_time" in metric_keys


def test_meta_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/meta")

    assert response.status_code == 401
