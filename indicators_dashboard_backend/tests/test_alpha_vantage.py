"""Client behaviour, with emphasis on Alpha Vantage's HTTP-200 error bodies."""

from __future__ import annotations

import httpx
import pytest
import respx

from indicators_dashboard_backend.alpha_vantage import (
    AlphaVantageClient,
    UpstreamThrottle,
    redact,
)
from indicators_dashboard_backend.config import Settings
from indicators_dashboard_backend.errors import (
    ApiKeyMissingError,
    UpstreamInvalidRequestError,
    UpstreamPayloadError,
    UpstreamRateLimitError,
    UpstreamUnavailableError,
)

from .conftest import ERROR_MESSAGE_BODY, QUERY_URL, RATE_LIMIT_BODY, monthly_series

PARAMS = {"function": "UNEMPLOYMENT"}


def make_settings(**overrides) -> Settings:
    base = dict(
        alpha_vantage_api_key="SECRET-KEY",
        min_seconds_between_upstream_calls=0.0,
        retry_backoff_seconds=0.0,
        max_retries=1,
        cache_persist=False,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
async def client():
    av = AlphaVantageClient(make_settings())
    try:
        yield av
    finally:
        await av.aclose()


# -- happy path -------------------------------------------------------------


@respx.mock
async def test_fetch_returns_the_payload(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=monthly_series()))
    payload = await client.fetch(PARAMS)
    assert payload["name"] == "Unemployment Rate"
    assert len(payload["data"]) == 6


@respx.mock
async def test_the_api_key_is_attached_to_the_request(client: AlphaVantageClient):
    route = respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=monthly_series()))
    await client.fetch(PARAMS)
    assert route.calls.last.request.url.params["apikey"] == "SECRET-KEY"


@respx.mock
async def test_json_datatype_is_forced_for_the_json_path(client: AlphaVantageClient):
    route = respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=monthly_series()))
    await client.fetch({**PARAMS, "datatype": "csv"})
    assert route.calls.last.request.url.params["datatype"] == "json"


# -- HTTP-200 error bodies --------------------------------------------------


@respx.mock
async def test_rate_limit_body_becomes_a_rate_limit_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=RATE_LIMIT_BODY))
    with pytest.raises(UpstreamRateLimitError) as excinfo:
        await client.fetch(PARAMS)
    assert excinfo.value.status_code == 429


@respx.mock
async def test_note_style_throttle_body_becomes_a_rate_limit_error(client: AlphaVantageClient):
    body = {
        "Note": (
            "Thank you for using Alpha Vantage! Our standard API call frequency is "
            "5 calls per minute and 500 calls per day."
        )
    }
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(UpstreamRateLimitError):
        await client.fetch(PARAMS)


@respx.mock
async def test_error_message_body_becomes_an_invalid_request_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=ERROR_MESSAGE_BODY))
    with pytest.raises(UpstreamInvalidRequestError) as excinfo:
        await client.fetch(PARAMS)
    assert excinfo.value.status_code == 502


@respx.mock
async def test_informational_note_alongside_data_is_not_fatal(client: AlphaVantageClient):
    """A non-quota `Information` note with data attached should still succeed."""
    payload = {**monthly_series(), "Information": "This series was revised."}
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=payload))
    assert len(await client.fetch(PARAMS)) >= 1


@respx.mock
async def test_missing_data_key_is_a_payload_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json={"name": "x"}))
    with pytest.raises(UpstreamPayloadError):
        await client.fetch(PARAMS)


@respx.mock
async def test_non_list_data_is_a_payload_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json={"data": {"a": 1}}))
    with pytest.raises(UpstreamPayloadError):
        await client.fetch(PARAMS)


@respx.mock
async def test_non_json_body_is_a_payload_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, text="<html>nope</html>"))
    with pytest.raises(UpstreamPayloadError):
        await client.fetch(PARAMS)


@respx.mock
async def test_json_array_body_is_a_payload_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    with pytest.raises(UpstreamPayloadError):
        await client.fetch(PARAMS)


# -- transport failures -----------------------------------------------------


@respx.mock
async def test_server_errors_are_retried_then_reported_unavailable(client: AlphaVantageClient):
    route = respx.get(QUERY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamUnavailableError):
        await client.fetch(PARAMS)
    assert route.call_count == 2  # max_retries=1 -> 2 attempts


@respx.mock
async def test_a_retry_can_succeed(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json=monthly_series()),
        ]
    )
    payload = await client.fetch(PARAMS)
    assert len(payload["data"]) == 6


@respx.mock
async def test_connection_errors_are_reported_unavailable(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamUnavailableError):
        await client.fetch(PARAMS)


@respx.mock
async def test_timeouts_are_reported_unavailable(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamUnavailableError):
        await client.fetch(PARAMS)


@respx.mock
async def test_http_429_is_a_rate_limit_error(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(UpstreamRateLimitError):
        await client.fetch(PARAMS)


@respx.mock
async def test_client_errors_are_not_retried(client: AlphaVantageClient):
    route = respx.get(QUERY_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(UpstreamInvalidRequestError):
        await client.fetch(PARAMS)
    assert route.call_count == 1


async def test_missing_api_key_raises_before_any_request():
    av = AlphaVantageClient(make_settings(alpha_vantage_api_key=""))
    try:
        with pytest.raises(ApiKeyMissingError):
            await av.fetch(PARAMS)
    finally:
        await av.aclose()


# -- CSV --------------------------------------------------------------------


@respx.mock
async def test_fetch_csv_returns_raw_text(client: AlphaVantageClient):
    csv = "timestamp,value\r\n2026-06-01,4.2\r\n"
    respx.get(QUERY_URL).mock(
        return_value=httpx.Response(200, text=csv, headers={"content-type": "text/csv"})
    )
    assert await client.fetch_csv(PARAMS) == csv


@respx.mock
async def test_fetch_csv_detects_a_json_rate_limit_body(client: AlphaVantageClient):
    """Rate limits are returned as JSON even when CSV was requested."""
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=RATE_LIMIT_BODY))
    with pytest.raises(UpstreamRateLimitError):
        await client.fetch_csv(PARAMS)


@respx.mock
async def test_fetch_csv_rejects_an_empty_body(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, text="   "))
    with pytest.raises(UpstreamPayloadError):
        await client.fetch_csv(PARAMS)


@respx.mock
async def test_csv_datatype_is_requested(client: AlphaVantageClient):
    route = respx.get(QUERY_URL).mock(return_value=httpx.Response(200, text="a,b\n1,2\n"))
    await client.fetch_csv(PARAMS)
    assert route.calls.last.request.url.params["datatype"] == "csv"


# -- secret hygiene ---------------------------------------------------------


def test_redact_strips_the_api_key():
    assert redact({"function": "CPI", "apikey": "SECRET"}) == {"function": "CPI"}


@respx.mock
async def test_error_details_never_carry_the_api_key(client: AlphaVantageClient):
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=RATE_LIMIT_BODY))
    with pytest.raises(UpstreamRateLimitError) as excinfo:
        await client.fetch({"function": "CPI", "interval": "monthly"})
    rendered = repr(excinfo.value.to_payload())
    assert "SECRET-KEY" not in rendered
    assert "apikey" not in rendered


# -- throttle ---------------------------------------------------------------


async def test_throttle_spaces_out_consecutive_calls():
    import time

    throttle = UpstreamThrottle(min_interval=0.05)
    start = time.monotonic()
    for _ in range(3):
        async with throttle:
            pass
    assert time.monotonic() - start >= 0.10  # first is free, next two wait


async def test_throttle_serialises_concurrent_callers():
    import asyncio

    throttle = UpstreamThrottle(min_interval=0.0, max_concurrency=1)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with throttle:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(worker() for _ in range(5)))
    assert peak == 1
