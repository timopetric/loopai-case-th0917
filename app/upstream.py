"""The only module that talks to the upstream reporting API (architecture.md §3, §10).

Fetches the **entire Coverage Window** on every cache miss and memoises that
single normalised :class:`Dataset` in-process for five minutes (ADR-0001). The
cache key is the Coverage Window itself, read from the upstream's undocumented
``GET /health`` route and memoised on the same interval, falling back to a
hardcoded window only when that route is unreachable.

Normalises units here and nowhere else: duration metrics arrive as *sums*
expressed in **hours**, each with a ``_count`` companion, despite the vendor
docs claiming seconds (api-report-fresh.md §6). Raw upstream shapes must never
escape this module — everything downstream sees the normalised types below.
"""

import json
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
from loguru import logger

from app.config import Settings, get_settings

CACHE_TTL_SECONDS = 300  # 5 minutes (ADR-0001), shared by the window and dataset caches.

# Hardcoded fallback (ADR-0001) — used ONLY when GET /health is unreachable.
_FALLBACK_COVERAGE = ("2026-07-10", "2026-07-23")

# ADR-0003's narrow exception: DEV_FAKE_UPSTREAM serves this committed fixture
# instead of calling out. Honoured only in a development environment
# (app/config.py's Settings validator refuses to start otherwise).
#
# Lives under app/, NOT tests/: this path must resolve inside the built
# Docker image, and the Dockerfile only COPYs `app/` (+ the built frontend) —
# `tests/` is excluded by .dockerignore. Tests import this same constant
# rather than keeping a second copy of the 1.2 MB blob (see
# tests/test_dev_fixture_ships_in_image.py, which pins this location so the
# fixture can't quietly migrate back under tests/).
_DEV_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "dev_fixtures" / "resp-full-unscoped-latest.json"
)

# The 7 Duration Metrics (CONTEXT.md): sums expressed in hours, each with a
# `_count` companion. `replies_to_resolve` also carries a `_count` but is a
# plain sum of replies, not an hours quantity.
_DURATION_METRIC_KEYS = (
    "resolve_time",
    "response_time",
    "time_to_first_reply",
    "resolve_time_business_hours",
    "response_time_business_hours",
    "time_to_first_reply_business_hours",
    "handle_time",
)
_SUM_METRIC_KEYS = ("replies_to_resolve",)
_COUNTER_METRIC_KEYS = (
    "actioned_emails",
    "resolved",
    "new_tickets",
    "replies",
    "new_emails",
    "sla_breaches",
)
# `open` is always zero (api-report-fresh.md §5.4/§6.5) — carried in the
# normalised Dataset for completeness but excluded from the metric catalogue.
_DEAD_METRIC_KEYS = ("open",)

_ALL_METRIC_KEYS = (
    _COUNTER_METRIC_KEYS + _DURATION_METRIC_KEYS + _SUM_METRIC_KEYS + _DEAD_METRIC_KEYS
)
_COUNT_COMPANION_KEYS = _DURATION_METRIC_KEYS + _SUM_METRIC_KEYS


@dataclass(frozen=True)
class CoverageWindow:
    """The absolute date range for which upstream data exists (CONTEXT.md)."""

    from_date: str  # ISO date, e.g. "2026-07-10"
    to_date: str  # ISO date, inclusive, e.g. "2026-07-23"


@dataclass(frozen=True)
class MetricInfo:
    """One entry of the metric catalogue exposed by the metadata route."""

    key: str
    kind: Literal["counter", "duration", "sum"]
    unit: Literal["count", "hours", "replies"]


METRIC_CATALOGUE: tuple[MetricInfo, ...] = tuple(
    [MetricInfo(key=key, kind="counter", unit="count") for key in _COUNTER_METRIC_KEYS]
    + [MetricInfo(key=key, kind="duration", unit="hours") for key in _DURATION_METRIC_KEYS]
    + [MetricInfo(key=key, kind="sum", unit="replies") for key in _SUM_METRIC_KEYS]
)


@dataclass(frozen=True)
class EntityBreakdown:
    """One `actors[]` or `mailbox[]` entry, normalised (api-report-fresh.md §4.3)."""

    id: str
    name: str
    metrics: dict[str, list[float]]  # metric key -> per-bucket values
    counts: dict[str, list[float]]  # duration/sum metric key -> per-bucket `_count`


@dataclass(frozen=True)
class Dataset:
    """The whole normalised Coverage Window, as returned by `get_dataset()`.

    Raw upstream shapes stop here: everything downstream — engine, exporters,
    the Assistant — sees this type and nothing about the wire format.
    """

    coverage: CoverageWindow
    ticks: list[str]
    metrics: dict[str, list[float]]  # top-level metric arrays
    counts: dict[str, list[float]]  # top-level `_count` companions
    actors: list[EntityBreakdown]
    mailboxes: list[EntityBreakdown]


def _normalise_entity(raw: dict, *, id_key: str) -> EntityBreakdown:
    return EntityBreakdown(
        id=raw[id_key],
        name=raw["name"],
        metrics={key: raw[key] for key in _ALL_METRIC_KEYS if key in raw},
        counts={key: raw[f"{key}_count"] for key in _COUNT_COMPANION_KEYS if f"{key}_count" in raw},
    )


def _normalise_dataset(raw: dict, coverage: CoverageWindow) -> Dataset:
    """Turn one raw upstream response body into a :class:`Dataset`.

    Duration values are NOT divided or multiplied — the raw number already
    IS hours (api-report-fresh.md §6.2). "Normalising" here means: build the
    typed shape and never let downstream code apply its own conversion.
    """
    return Dataset(
        coverage=coverage,
        ticks=raw["ticks"],
        metrics={key: raw[key] for key in _ALL_METRIC_KEYS if key in raw},
        counts={key: raw[f"{key}_count"] for key in _COUNT_COMPANION_KEYS if f"{key}_count" in raw},
        actors=[_normalise_entity(a, id_key="user_id") for a in raw["actors"]],
        mailboxes=[_normalise_entity(m, id_key="mailbox_id") for m in raw["mailbox"]],
    )


class UpstreamClient:
    """Thin live client + the 5-minute in-process memo described above.

    `http_client` is an injectable seam: production code lets it default to a
    real `httpx.AsyncClient`; tests pass one built on `httpx.MockTransport`
    (httpx's own offline test transport) so the real request/normalise/cache
    code path is exercised without touching the network or patching the HTTP
    library itself.
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(
            base_url=settings.upstream_base_url, timeout=10.0
        )
        self._window_cache: tuple[CoverageWindow, float] | None = None
        self._dataset_cache: tuple[Dataset, float] | None = None

    async def get_coverage_window(self) -> CoverageWindow:
        """The Coverage Window, read from `/health` and memoised 5 minutes.

        Falls back to the hardcoded window (ADR-0001) whenever `/health` is
        unreachable, unparseable, or missing the field we need — a partial
        outage of the undocumented route must never take the app down.
        """
        if self._settings.dev_fake_upstream:
            return CoverageWindow(*_FALLBACK_COVERAGE)

        if self._window_cache is not None:
            window, fetched_at = self._window_cache
            if time.monotonic() - fetched_at < CACHE_TTL_SECONDS:
                return window

        window = await self._fetch_coverage_window()
        self._window_cache = (window, time.monotonic())
        return window

    async def _fetch_coverage_window(self) -> CoverageWindow:
        try:
            response = await self._http.get("/health")
            response.raise_for_status()
            coverage = response.json()["coverage"]
            return CoverageWindow(from_date=coverage["from"], to_date=coverage["to"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "upstream /health unreachable or unparseable ({}); "
                "falling back to the hardcoded coverage window",
                exc,
            )
            return CoverageWindow(*_FALLBACK_COVERAGE)

    async def get_dataset(self) -> Dataset:
        """The whole Coverage Window, normalised and memoised 5 minutes.

        The cache key is the Coverage Window itself (ADR-0001): a second call
        within the TTL for the same window is served from memory with no
        upstream fetch at all.
        """
        if self._settings.dev_fake_upstream:
            return await self._load_dev_fixture()

        window = await self.get_coverage_window()

        if self._dataset_cache is not None:
            dataset, fetched_at = self._dataset_cache
            if dataset.coverage == window and time.monotonic() - fetched_at < CACHE_TTL_SECONDS:
                return dataset

        dataset = await self._fetch_dataset(window)
        self._dataset_cache = (dataset, time.monotonic())
        return dataset

    async def _fetch_dataset(self, window: CoverageWindow) -> Dataset:
        response = await self._http.post(
            "/reporting_api/v1/reporting/stats/json",
            json={
                "from_date": f"{window.from_date}T00:00:00Z",
                "to_date": f"{window.to_date}T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {self._settings.upstream_token}"},
        )
        response.raise_for_status()
        return _normalise_dataset(response.json(), window)

    async def _load_dev_fixture(self) -> Dataset:
        raw = json.loads(_DEV_FIXTURE_PATH.read_text())["response_json"]
        return _normalise_dataset(raw, CoverageWindow(*_FALLBACK_COVERAGE))


@lru_cache
def get_upstream_client() -> UpstreamClient:
    """Process-wide singleton — the FastAPI dependency-override seam for tests.

    A singleton (rather than one instance per request) is what makes the
    5-minute memo actually memoise across requests.
    """
    return UpstreamClient(get_settings())
