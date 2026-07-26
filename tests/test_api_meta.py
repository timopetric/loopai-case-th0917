"""API-level test for the metadata route (issue 03; presets added issue 12).

`upstream` is faked via FastAPI dependency override, built directly from the
committed fixture — no HTTP library mocked, no network. This exercises the
seam architecture.md §3 names explicitly: routes depend on
`get_upstream_client`, and tests override that dependency.

`test_meta_route_has_no_hardcoded_second_copy_of_presets` is issue 12's
sentinel test, the same drift-proofing pattern issue 09 established in
`test_assumptions.py`: monkeypatch the shared source (`build_presets`) to
return a sentinel and require the route to reflect it exactly. A test that
only checked the three expected preset ids were present would still pass
against a route holding its own hardcoded copy of the presets — this one
would not, because the sentinel could only come back if the route actually
calls through.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.meta import get_upstream_client
from app.config import get_settings
from app.main import create_app
from app.models import Metric, ReportSpec
from app.presets import Preset
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


def test_meta_route_carries_the_three_presets_with_the_real_coverage_window(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/meta", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()

    preset_ids = [p["id"] for p in body["presets"]]
    assert preset_ids == ["day-by-agent", "day-by-mailbox", "agent-leaderboard"]

    day_by_agent = body["presets"][0]
    assert day_by_agent["spec"]["date_from"] == "2026-07-10"
    assert day_by_agent["spec"]["date_to"] == "2026-07-23"
    assert day_by_agent["spec"]["group_by"] == "agent"

    leaderboard = body["presets"][2]
    assert leaderboard["spec"]["granularity"] == "total"
    assert leaderboard["spec"]["sort"] == {"column": "resolved", "direction": "desc"}


def test_meta_route_has_no_hardcoded_second_copy_of_presets(
    app, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decisive drift-proofing test (issue 12, mirroring issue 09's
    `test_assumptions_route_has_no_hardcoded_second_copy`): patch the shared
    source to return a sentinel preset, and require the route to reflect it
    exactly. If the route (or `App.tsx`, checked separately) held its own
    copy of the preset definitions instead of calling `build_presets`, this
    would fail — the sentinel could never appear in the response."""
    sentinel = [
        Preset(
            id="sentinel",
            label="Sentinel preset",
            spec=ReportSpec(
                metrics=[Metric.RESOLVED],
                date_from="2026-07-10",
                date_to="2026-07-23",
            ),
        )
    ]

    import app.api.v1.routers.meta as meta_router

    monkeypatch.setattr(meta_router, "build_presets", lambda coverage: sentinel)

    response = client.get("/api/v1/meta", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()

    assert len(body["presets"]) == 1
    assert body["presets"][0]["id"] == "sentinel"
    assert body["presets"][0]["label"] == "Sentinel preset"
    assert body["presets"][0]["spec"]["metrics"] == ["resolved"]
