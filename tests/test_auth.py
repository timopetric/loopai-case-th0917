"""Auth-gate tests (issue 02).

Structural on purpose: `_api_v1_routes` enumerates every route FastAPI has
registered under `/api/v1` rather than hardcoding one path, so a route added
in a later slice is protected automatically — the no-key case is what would
catch an auth dependency that was never attached to the router.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.config import get_settings
from app.main import create_app

_PATH_PARAM = re.compile(r"\{[^{}]+\}")

# FastAPI 0.140's aggregate/include_router is lazily resolved (`_IncludedRouter`),
# so `app.routes` no longer flattens into concrete `APIRoute`s. The OpenAPI
# schema is the stable, version-agnostic place every registered path and
# method actually shows up — the same place Swagger itself reads from — so
# enumerate routes from there instead of walking internal router state.
def _api_v1_routes(app) -> list[tuple[str, str]]:
    schema = app.openapi()
    return [
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        if path.startswith("/api/v1")
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    ]


def _concrete_path(path: str) -> str:
    """Fill in any path params with a placeholder so later routes with, say,
    `/api/v1/report/{id}` are still requestable by this generic test."""
    return _PATH_PARAM.sub("test", path)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def test_every_api_v1_route_rejects_a_request_with_no_key(client: TestClient, app) -> None:
    routes = _api_v1_routes(app)
    assert routes, "expected at least one /api/v1 route to exist"

    for method, path in routes:
        response = client.request(method, _concrete_path(path))
        assert response.status_code == 401, f"{method} {path} was not protected"


def test_every_api_v1_route_rejects_the_wrong_key(client: TestClient, app) -> None:
    routes = _api_v1_routes(app)

    for method, path in routes:
        response = client.request(
            method,
            _concrete_path(path),
            headers={"X-API-Key": "definitely-wrong"},
        )
        assert response.status_code == 401, f"{method} {path} accepted a wrong key"


def test_session_route_succeeds_with_the_correct_key(client: TestClient) -> None:
    settings = get_settings()

    response = client.get("/api/v1/session", headers={"X-API-Key": settings.app_api_key})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_auth_dependency_is_attached_at_the_router_level_not_per_route() -> None:
    """The dependency must live on the aggregate router's `dependencies=[...]`
    so a route added later inherits it without anyone remembering to add it
    per-endpoint (architecture.md §3)."""
    names = {dependency.dependency.__name__ for dependency in api_router.dependencies}

    assert "require_api_key" in names


def test_wrong_key_error_body_never_echoes_the_submitted_or_configured_key(
    client: TestClient,
) -> None:
    settings = get_settings()
    submitted = "definitely-wrong-key"

    response = client.get("/api/v1/session", headers={"X-API-Key": submitted})

    assert submitted not in response.text
    assert settings.app_api_key not in response.text
