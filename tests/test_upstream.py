"""`upstream.py` unit tests (issue 03).

`upstream.UpstreamClient` is tested directly, against `httpx.MockTransport` —
httpx's own supported test seam, not a patch of the HTTP library itself. This
lets us exercise the real request/response/caching code path offline. API-level
tests (`test_api.py`) instead override the FastAPI dependency, per
architecture.md §3 / the issue brief.
"""

import json

import httpx
import pytest

from app.config import Settings
from app.upstream import _DEV_FIXTURE_PATH, METRIC_CATALOGUE, CoverageWindow, UpstreamClient

# The same file `DEV_FAKE_UPSTREAM` serves at runtime (app/dev_fixtures/) —
# one committed copy, read by both consumers (see
# tests/test_dev_fixture_ships_in_image.py for why it lives under app/).
FIXTURE_PATH = _DEV_FIXTURE_PATH
FIXTURE = json.loads(FIXTURE_PATH.read_text())["response_json"]

HEALTH_OK = {
    "ok": True,
    "service": "reporting-stats-api",
    "endpoint": "POST /reporting_api/v1/reporting/stats/json",
    "coverage": {"from": "2026-07-10", "to": "2026-07-23"},
}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _client(handler, **settings_overrides) -> UpstreamClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://upstream.test")
    return UpstreamClient(_settings(**settings_overrides), http_client=http_client)


def _handler(*, health=HEALTH_OK, stats=FIXTURE, calls: list[str] | None = None):
    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if request.url.path == "/health":
            if health is None:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, json=health)
        if request.url.path.endswith("/stats/json"):
            return httpx.Response(200, json=stats)
        return httpx.Response(404)

    return handle


class TestCoverageWindow:
    async def test_parses_coverage_window_from_the_health_route(self):
        client = _client(_handler())

        window = await client.get_coverage_window()

        assert window == CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")

    async def test_falls_back_to_the_hardcoded_window_when_health_is_unreachable(self):
        client = _client(_handler(health=None))

        window = await client.get_coverage_window()

        assert window == CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")


class TestDatasetCaching:
    async def test_a_second_call_within_five_minutes_does_not_refetch(self):
        calls: list[str] = []
        client = _client(_handler(calls=calls))

        await client.get_dataset()
        first_call_count = len([c for c in calls if c.endswith("/stats/json")])
        await client.get_dataset()
        second_call_count = len([c for c in calls if c.endswith("/stats/json")])

        assert first_call_count == 1
        assert second_call_count == 1  # unchanged: no second fetch


class TestHoursNormalisation:
    """Pins the semantics from api-report-fresh.md §6, not just pass-through:
    a Duration Metric is (a) catalogued as hours, (b) a per-bucket SUM — never
    an average — reconciling exactly across all 108 Actors, and (c) paired
    with a `_count` companion whose count-weighted mean lands on the window
    figure the investigation measured. Getting the unit wrong (seconds) or
    the aggregation wrong (mean-of-means) would each fail this loudly."""

    DURATION_METRICS = (
        "resolve_time",
        "response_time",
        "time_to_first_reply",
        "handle_time",
    )
    # Window-level count-weighted means measured directly from the fixture
    # (api-report-fresh.md §6.2/§6.5) — only plausible if the unit is hours.
    # As seconds these would read ~41328h/~126139h; as minutes ~689h/~2102h.
    EXPECTED_WINDOW_MEAN_HOURS = {
        "resolve_time": 11.482,
        "response_time": 35.039,
        "time_to_first_reply": 40.204,
        "handle_time": 0.0133,
    }

    def test_catalogue_declares_duration_metrics_as_hours(self) -> None:
        by_key = {m.key: m for m in METRIC_CATALOGUE}

        for key in self.DURATION_METRICS:
            assert by_key[key].kind == "duration"
            assert by_key[key].unit == "hours"

    async def test_a_duration_metric_is_a_sum_reconciling_exactly_across_actors(self) -> None:
        """api-report-fresh.md §6.1: Σ over all 108 Actors == the top-level
        value, per bucket, to the last bit — proof it is a sum, not a mean
        (a per-bucket average could never be reconstructed by summing 100+
        per-actor numbers back up to the same figure)."""
        client = _client(_handler())

        dataset = await client.get_dataset()

        for metric in self.DURATION_METRICS:
            n_buckets = len(dataset.metrics[metric])
            actor_totals = [
                sum(actor.metrics[metric][i] for actor in dataset.actors)
                for i in range(n_buckets)
            ]
            assert actor_totals == pytest.approx(dataset.metrics[metric], abs=1e-6), (
                f"{metric}: Σactors != top-level — this metric is not being "
                "treated as a per-bucket sum"
            )

    async def test_duration_metric_count_weighted_mean_matches_hours_not_seconds(self) -> None:
        """Σvalue / Σcount over the whole window (api-report-fresh.md §6.5) —
        the count-weighted mean the `_count` companion exists to make
        possible, never a mean of per-bucket averages."""
        client = _client(_handler())

        dataset = await client.get_dataset()

        for metric, expected_hours in self.EXPECTED_WINDOW_MEAN_HOURS.items():
            total_value = sum(dataset.metrics[metric])
            total_count = sum(dataset.counts[metric])
            count_weighted_mean = total_value / total_count

            assert count_weighted_mean == pytest.approx(expected_hours, abs=0.01)


class TestDevFakeUpstream:
    async def test_dev_fake_upstream_serves_the_fixture_without_any_http_call(self):
        """ADR-0003: when the flag is set (in a development environment — the
        Settings validator enforces that, tested in test_config.py), the
        committed fixture is served and upstream is never called at all."""
        calls: list[str] = []
        client = _client(_handler(calls=calls), environment="local", dev_fake_upstream=True)

        dataset = await client.get_dataset()
        window = await client.get_coverage_window()

        assert calls == []  # no HTTP call of any kind, not health, not stats
        assert len(dataset.actors) == 108
        assert len(dataset.mailboxes) == 103
        assert dataset.metrics["resolved"] == pytest.approx(FIXTURE["resolved"])
        assert window == CoverageWindow(from_date="2026-07-10", to_date="2026-07-23")
