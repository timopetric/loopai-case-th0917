"""The health probe is unauthenticated liveness — issue 01 acceptance criterion."""

from fastapi.testclient import TestClient


def test_healthz_returns_ok_without_auth(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_ignores_bogus_api_key(client: TestClient) -> None:
    """The probe must stay reachable even with a garbage/absent key header —
    it is infra-facing, not app-facing (PLAYBOOK.md §7)."""
    response = client.get("/healthz", headers={"X-API-Key": "definitely-wrong"})

    assert response.status_code == 200
