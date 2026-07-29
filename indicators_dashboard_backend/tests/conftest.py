"""Shared fixtures.

Every test runs against a fully wired application with the Alpha Vantage host
mocked by :class:`FakeUpstream`, so nothing here consumes the real 25-requests
per-day quota.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from indicators_dashboard_backend.config import Settings
from indicators_dashboard_backend.main import create_app

QUERY_URL = "https://www.alphavantage.co/query"

# A rate-limit body, copied from a live free-tier response. Note the HTTP 200.
RATE_LIMIT_BODY = {
    "Information": (
        "Thank you for using Alpha Vantage! Please consider spreading out your free "
        "API requests more sparingly (1 request per second). You may subscribe to any "
        "of the premium plans at https://www.alphavantage.co/premium/ to lift the free "
        "key rate limit (25 requests per day)."
    )
}

ERROR_MESSAGE_BODY = {
    "Error Message": (
        "Invalid API call. Please retry or visit the documentation "
        "(https://www.alphavantage.co/documentation/) for TREASURY_YIELD."
    )
}


def monthly_series(
    *,
    name: str = "Unemployment Rate",
    unit: str = "percent",
    interval: str = "monthly",
    values: list[float | str] | None = None,
    start: date = date(2026, 6, 1),
) -> dict[str, Any]:
    """Build an Alpha Vantage payload: newest first, one observation per month."""
    values = values if values is not None else [4.2, 4.3, 4.3, 4.1, 4.0, 3.9]
    data = []
    cursor = start
    for value in values:
        data.append({"date": cursor.isoformat(), "value": str(value)})
        # Step back one month.
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    return {"name": name, "interval": interval, "unit": unit, "data": data}


def series_with_year_of_history(
    *, latest: float, year_ago: float, months: int = 14
) -> dict[str, Any]:
    """A monthly payload where the observation 12 periods back is ``year_ago``."""
    values: list[float | str] = [latest]
    for index in range(1, months):
        values.append(year_ago if index == 12 else round(latest - index * 0.01, 4))
    return monthly_series(values=values)


class FakeUpstream:
    """Records outbound calls and answers them from a per-``function`` script."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._responses: dict[str, Callable[[httpx.Request], httpx.Response]] = {}
        self._default: Callable[[httpx.Request], httpx.Response] | None = None

    # -- scripting ----------------------------------------------------------

    def json(self, function: str, payload: dict[str, Any], *, status_code: int = 200) -> None:
        self._responses[function] = lambda _req: httpx.Response(status_code, json=payload)

    def text(self, function: str, body: str, *, content_type: str = "text/csv") -> None:
        self._responses[function] = lambda _req: httpx.Response(
            200, text=body, headers={"content-type": content_type}
        )

    def status(self, function: str, status_code: int) -> None:
        self._responses[function] = lambda _req: httpx.Response(status_code, text="upstream error")

    def transport_error(self, function: str) -> None:
        def _raise(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        self._responses[function] = _raise

    def timeout(self, function: str) -> None:
        def _raise(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        self._responses[function] = _raise

    def default_json(self, payload: dict[str, Any]) -> None:
        self._default = lambda _req: httpx.Response(200, json=payload)

    # -- introspection ------------------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def calls_for(self, function: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.params.get("function") == function]

    def last_params(self) -> dict[str, str]:
        return dict(self.requests[-1].url.params)

    # -- respx handler ------------------------------------------------------

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        function = request.url.params.get("function", "")
        handler = self._responses.get(function, self._default)
        if handler is None:
            return httpx.Response(200, json=monthly_series())
        return handler(request)


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Test settings: real-looking, but with no network politeness delays."""
    return Settings(
        alpha_vantage_api_key="TEST-KEY-DO-NOT-LOG",
        cache_ttl_seconds=300,
        cache_stale_grace_seconds=86_400,
        cache_persist=False,
        cache_dir=tmp_path / "cache",
        min_seconds_between_upstream_calls=0.0,
        retry_backoff_seconds=0.0,
        max_retries=1,
        request_timeout_seconds=5.0,
    )


@pytest.fixture
def upstream() -> Iterator[FakeUpstream]:
    fake = FakeUpstream()
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=fake)
        yield fake


@pytest.fixture
def client(settings: Settings, upstream: FakeUpstream) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_client(upstream: FakeUpstream):
    """Factory for a client bound to custom settings."""

    def _factory(custom: Settings) -> TestClient:
        return TestClient(create_app(custom))

    return _factory
