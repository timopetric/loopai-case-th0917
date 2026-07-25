"""The SPA is served from the backend's own origin, with a fallback to
index.html for client-side deep links — but unmatched /api paths must 404,
never silently return the SPA shell (issue 01 acceptance criteria)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

pytestmark = pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(),
    reason="requires a built frontend/dist (run `make frontend` build first)",
)


@pytest.fixture
def spa_client() -> TestClient:
    return TestClient(create_app())


def test_root_serves_the_frontend_shell(spa_client: TestClient) -> None:
    response = spa_client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<div id=\"root\">" in response.text


def test_deep_link_falls_back_to_index_html(spa_client: TestClient) -> None:
    response = spa_client.get("/some/deep/client-side/route")

    assert response.status_code == 200
    assert "<div id=\"root\">" in response.text


def test_unmatched_api_path_is_a_404_not_the_spa_shell(spa_client: TestClient) -> None:
    response = spa_client.get("/api/v1/definitely-not-a-route")

    assert response.status_code == 404
