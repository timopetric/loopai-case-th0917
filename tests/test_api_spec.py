"""API-level test for `GET /api/v1/spec` (issue 13).

Proves the round trip through REAL HTTP query-string parsing (Starlette's
`request.query_params`), not just the in-process `encode_spec`/`decode_spec`
calls `tests/test_spec_url.py` exercises directly. `upstream` is faked via
FastAPI dependency override from the committed fixture — same pattern as
`test_api_meta.py` and `test_api_report.py`, no network.
"""

import json
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers.meta import get_upstream_client
from app.config import get_settings
from app.main import create_app
from app.models import Metric, ReportSpec, SortSpec
from app.presets import DEFAULT_PRESET_ID, build_presets
from app.spec_url import encode_spec
from app.upstream import _DEV_FIXTURE_PATH, CoverageWindow, _normalise_dataset

FIXTURE_PATH = _DEV_FIXTURE_PATH
COVERAGE = CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


class _FixtureBackedClient:
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


def _default_spec() -> ReportSpec:
    return next(
        p.spec for p in build_presets(COVERAGE) if p.id == DEFAULT_PRESET_ID
    )


def test_a_fully_populated_spec_survives_a_round_trip_through_real_query_params(
    client: TestClient,
) -> None:
    spec = ReportSpec(
        metrics=[Metric.RESOLVED, Metric.NEW_TICKETS],
        date_from="2026-07-11",
        date_to="2026-07-20",
        granularity="total",
        group_by="mailbox",
        duration_display="total",
        sort=SortSpec(column="resolved", direction="asc"),
        columns_order=["new_tickets", "resolved"],
        layout="pivot",
        chart_metric=Metric.NEW_TICKETS,
    )

    query = urlencode(encode_spec(spec))
    response = client.get(f"/api/v1/spec?{query}", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == []
    assert ReportSpec(**body["spec"]) == spec


def test_no_query_params_returns_the_default_report_with_no_warning(client: TestClient) -> None:
    response = client.get("/api/v1/spec", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == []
    assert ReportSpec(**body["spec"]) == _default_spec()


def test_an_invalid_link_falls_back_to_the_default_report_with_a_warning(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/spec",
        params={"metrics": "not_a_real_metric", "date_from": "2026-07-10", "date_to": "2026-07-23"},
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert ReportSpec(**body["spec"]) == _default_spec()
    assert len(body["warnings"]) == 1


def test_a_stale_link_outside_a_moved_coverage_window_still_decodes(
    client: TestClient,
) -> None:
    """`decode_spec` only enforces `ReportSpec`'s OWN validators (ordering,
    enum membership) — it has no way to know the real Coverage Window, which
    is only known at report-execution time (architecture.md §2). A spec
    whose dates have drifted outside a moved window is not this route's
    "invalid" case; it decodes successfully here and is refused later, by
    `POST /api/v1/report`, exactly like any other out-of-window request
    (issue 08) — see `test_api_report.py::TestCoverageValidation`."""
    response = client.get(
        "/api/v1/spec",
        params={"metrics": "resolved", "date_from": "2020-01-01", "date_to": "2020-01-05"},
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == []
    assert body["spec"]["date_from"] == "2020-01-01"


def test_spec_route_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/spec")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        # Unknown metric.
        {"metrics": "not_a_real_metric", "date_from": "2026-07-10", "date_to": "2026-07-23"},
        # Bad enum value.
        {
            "metrics": "resolved",
            "date_from": "2026-07-10",
            "date_to": "2026-07-23",
            "granularity": "fortnight",
        },
        # Inverted date range.
        {"metrics": "resolved", "date_from": "2026-07-23", "date_to": "2026-07-10"},
        # sort_column naming a metric that isn't selected.
        {
            "metrics": "resolved",
            "date_from": "2026-07-10",
            "date_to": "2026-07-23",
            "sort_column": "new_tickets",
        },
        # chart_metric naming a metric that isn't selected.
        {
            "metrics": "resolved",
            "date_from": "2026-07-10",
            "date_to": "2026-07-23",
            "chart_metric": "new_tickets",
        },
        # Missing required field entirely.
        {"date_from": "2026-07-10", "date_to": "2026-07-23"},
    ],
    ids=[
        "unknown-metric",
        "bad-enum",
        "inverted-dates",
        "sort-column-not-selected",
        "chart-metric-not-selected",
        "missing-metrics",
    ],
)
def test_a_hostile_hand_edited_query_string_falls_back_to_the_default_with_a_warning(
    client: TestClient, params: dict[str, str]
) -> None:
    """The decisive negative case (issue 13): a hand-edited or hostile query
    string — the untrusted input path a shared link is — must never come
    back as a 4xx/5xx and must never come back as a partially-applied spec.
    It always comes back 200, with the DEFAULT spec exactly, and exactly one
    Warning explaining the fallback."""
    response = client.get("/api/v1/spec", params=params, headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert ReportSpec(**body["spec"]) == _default_spec()
    assert len(body["warnings"]) == 1
    assert body["warnings"][0]  # non-empty, human-readable
