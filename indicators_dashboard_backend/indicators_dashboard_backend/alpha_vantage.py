"""Thin, defensive client for the Alpha Vantage economic-indicator endpoints.

Two things make this upstream awkward and drive the design here:

1. **Errors arrive as HTTP 200.** Rate limits, invalid calls, and premium-only
   endpoints all return status 200 with an ``Information``, ``Note``, or
   ``Error Message`` field. The status code cannot be trusted; the body must be
   inspected. :meth:`AlphaVantageClient.fetch` maps each case onto a distinct
   exception so the API can answer 429 vs 502 correctly.
2. **The free tier allows 25 requests/day** and asks for at most one request per
   second. Outbound calls are therefore serialised and spaced by
   :class:`UpstreamThrottle`, and everything above this layer is cached.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Final, Mapping

import httpx

from .config import Settings
from .errors import (
    ApiKeyMissingError,
    UpstreamInvalidRequestError,
    UpstreamPayloadError,
    UpstreamRateLimitError,
    UpstreamUnavailableError,
)

logger = logging.getLogger(__name__)

#: Body keys Alpha Vantage uses to report problems while still returning HTTP 200.
_ERROR_KEY: Final = "Error Message"
_NOTE_KEY: Final = "Note"
_INFORMATION_KEY: Final = "Information"

#: Substrings that identify a quota/throttle message inside those fields.
_RATE_LIMIT_MARKERS: Final = (
    "rate limit",
    "requests per day",
    "api call frequency",
    "calls per minute",
    "higher api call volume",
    "spreading out your free api requests",
    "premium",
    "subscribe",
)

#: Keys that a well-formed economic-indicator payload always contains.
_REQUIRED_PAYLOAD_KEYS: Final = ("data",)


def _looks_like_rate_limit(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


def redact(params: Mapping[str, Any]) -> dict[str, Any]:
    """Copy ``params`` with the API key removed, safe for logs and responses."""
    return {k: v for k, v in params.items() if k != "apikey"}


class UpstreamThrottle:
    """Serialises outbound calls and enforces a minimum gap between them."""

    def __init__(self, *, min_interval: float, max_concurrency: int = 1) -> None:
        self.min_interval = max(0.0, min_interval)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._gate = asyncio.Lock()
        self._last_call: float = 0.0

    async def __aenter__(self) -> "UpstreamThrottle":
        await self._semaphore.acquire()
        try:
            async with self._gate:
                if self.min_interval > 0:
                    wait = self.min_interval - (time.monotonic() - self._last_call)
                    if wait > 0:
                        await asyncio.sleep(wait)
                self._last_call = time.monotonic()
        except BaseException:
            self._semaphore.release()
            raise
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        self._semaphore.release()


class AlphaVantageClient:
    """Performs the actual HTTP calls to ``https://www.alphavantage.co/query``.

    The client owns a single :class:`httpx.AsyncClient` for connection reuse and
    is safe to share across requests. The API key is injected here and never
    appears in a response body, an error message, or a log line.
    """

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            headers={"User-Agent": "indicators-dashboard-backend/1.0 (+httpx)"},
            follow_redirects=True,
        )
        self._throttle = UpstreamThrottle(
            min_interval=settings.min_seconds_between_upstream_calls,
            max_concurrency=settings.max_concurrent_upstream_calls,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- public API ---------------------------------------------------------

    async def fetch(self, params: Mapping[str, str]) -> dict[str, Any]:
        """Call the upstream and return the parsed JSON payload.

        Args:
            params: Query parameters *without* ``apikey`` or ``datatype``.

        Raises:
            ApiKeyMissingError: no key configured.
            UpstreamRateLimitError: free-tier quota exhausted.
            UpstreamInvalidRequestError: the upstream rejected the call.
            UpstreamPayloadError: the response was not a valid indicator series.
            UpstreamUnavailableError: transport failure, timeout, or 5xx.
        """
        response = await self._request({**params, "datatype": "json"})

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamPayloadError(
                "Alpha Vantage returned a body that is not valid JSON.",
                details={"parameters": redact(params)},
            ) from exc

        if not isinstance(payload, dict):
            raise UpstreamPayloadError(
                "Alpha Vantage returned an unexpected JSON structure.",
                details={"parameters": redact(params)},
            )

        self._raise_for_payload_errors(payload, params)

        missing = [key for key in _REQUIRED_PAYLOAD_KEYS if key not in payload]
        if missing:
            raise UpstreamPayloadError(
                "Alpha Vantage response is missing the time-series data.",
                details={"parameters": redact(params), "missing_keys": missing},
            )
        if not isinstance(payload["data"], list):
            raise UpstreamPayloadError(
                "Alpha Vantage returned a non-list `data` field.",
                details={"parameters": redact(params)},
            )
        return payload

    async def fetch_csv(self, params: Mapping[str, str]) -> str:
        """Call the upstream with ``datatype=csv`` and return the raw CSV text."""
        response = await self._request({**params, "datatype": "csv"})
        text = response.text

        # A rate-limited "CSV" request still comes back as a JSON error body.
        stripped = text.lstrip()
        if stripped.startswith("{"):
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                self._raise_for_payload_errors(payload, params)
            raise UpstreamPayloadError(
                "Alpha Vantage returned JSON where CSV was requested.",
                details={"parameters": redact(params)},
            )
        if not stripped:
            raise UpstreamPayloadError(
                "Alpha Vantage returned an empty CSV body.",
                details={"parameters": redact(params)},
            )
        return text

    # -- internals ----------------------------------------------------------

    def _raise_for_payload_errors(
        self, payload: Mapping[str, Any], params: Mapping[str, str]
    ) -> None:
        """Translate Alpha Vantage's HTTP-200 error bodies into exceptions.

        Observations win over prose. Alpha Vantage attaches promotional notes --
        which mention "premium" and "subscribe", two of our quota markers -- to
        responses that also carry a full series. Testing the markers before
        testing for data therefore rejected perfectly good payloads as rate
        limited, on every indicator, even with a brand-new key. A body that
        contains observations succeeded, whatever else it says.
        """
        details = {"parameters": redact(params)}

        rows = payload.get("data")
        has_data = isinstance(rows, list) and len(rows) > 0

        for key in (_ERROR_KEY, _NOTE_KEY, _INFORMATION_KEY):
            if key not in payload:
                continue
            message = str(payload[key])

            if has_data:
                # Informational only: the series is present and usable.
                logger.info("Alpha Vantage note alongside data: %s", message[:300])
                continue

            if _looks_like_rate_limit(message):
                raise UpstreamRateLimitError(message, details=details)

            raise UpstreamInvalidRequestError(
                f"Alpha Vantage rejected the request: {message}"
                if key == _ERROR_KEY
                else message,
                details=details,
            )

    async def _request(self, params: Mapping[str, str]) -> httpx.Response:
        if not self._settings.has_api_key:
            raise ApiKeyMissingError()

        query = {**params, "apikey": self._settings.alpha_vantage_api_key}
        attempts = self._settings.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            async with self._throttle:
                try:
                    response = await self._client.get(
                        self._settings.alpha_vantage_base_url, params=query
                    )
                except httpx.TimeoutException as exc:
                    last_error = exc
                    logger.warning(
                        "Alpha Vantage timeout (attempt %d/%d) for %s",
                        attempt,
                        attempts,
                        redact(params),
                    )
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "Alpha Vantage transport error (attempt %d/%d): %s",
                        attempt,
                        attempts,
                        exc,
                    )
                else:
                    if response.status_code == 429:
                        raise UpstreamRateLimitError(
                            "Alpha Vantage rate limit reached. The free tier allows "
                            "25 requests per day.",
                            details={"parameters": redact(params)},
                        )
                    if response.status_code >= 500:
                        last_error = httpx.HTTPStatusError(
                            f"Upstream returned {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                        logger.warning(
                            "Alpha Vantage %d (attempt %d/%d)",
                            response.status_code,
                            attempt,
                            attempts,
                        )
                    elif response.status_code >= 400:
                        raise UpstreamInvalidRequestError(
                            f"Alpha Vantage returned HTTP {response.status_code}.",
                            details={"parameters": redact(params)},
                        )
                    else:
                        return response

            if attempt < attempts and self._settings.retry_backoff_seconds > 0:
                await asyncio.sleep(self._settings.retry_backoff_seconds * attempt)

        raise UpstreamUnavailableError(
            "Could not reach Alpha Vantage after "
            f"{attempts} attempt(s): {type(last_error).__name__}.",
            details={"parameters": redact(params)},
        ) from last_error
