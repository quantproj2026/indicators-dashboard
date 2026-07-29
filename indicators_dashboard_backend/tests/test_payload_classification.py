"""Deciding whether an Alpha Vantage body is a success or a failure.

A production bug lived here. The rate-limit markers include the generic words
"premium" and "subscribe", and Alpha Vantage attaches promotional notes using
exactly those words to responses that *also* carry a full series. Because the
markers were tested before checking for data, every indicator was rejected as
rate limited while the same URL returned 97 observations in a browser.

The rule these tests pin down: **observations win over prose.** A body carrying
data succeeded, whatever else it says.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from indicators_dashboard_backend.alpha_vantage import AlphaVantageClient
from indicators_dashboard_backend.config import Settings
from indicators_dashboard_backend.errors import (
    UpstreamInvalidRequestError,
    UpstreamRateLimitError,
)

from .conftest import QUERY_URL, monthly_series

#: The promotional footer Alpha Vantage appends to ordinary successful calls.
PROMO_NOTE = (
    "Thank you for using Alpha Vantage! You may subscribe to any of the premium "
    "plans at https://www.alphavantage.co/premium/ to instantly unlock all "
    "premium endpoints."
)

#: The genuine quota message, returned with no data attached.
QUOTA_NOTE = (
    "Thank you for using Alpha Vantage! Please consider spreading out your free "
    "API requests more sparingly (1 request per second). You may subscribe to any "
    "of the premium plans at https://www.alphavantage.co/premium/ to lift the free "
    "key rate limit (25 requests per day)."
)


@pytest.fixture
async def client():
    av = AlphaVantageClient(
        Settings(
            alpha_vantage_api_key="TEST-KEY",
            min_seconds_between_upstream_calls=0.0,
            retry_backoff_seconds=0.0,
            max_retries=0,
            cache_persist=False,
        )
    )
    try:
        yield av
    finally:
        await av.aclose()


class TestDataWins:
    @respx.mock
    @pytest.mark.parametrize("field", ["Information", "Note"])
    async def test_a_promotional_note_beside_data_is_not_a_rate_limit(
        self, client: AlphaVantageClient, field: str
    ):
        """The exact regression: valid series + a note mentioning premium."""
        payload = {**monthly_series(), field: PROMO_NOTE}
        respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=payload))

        result = await client.fetch({"function": "REAL_GDP"})

        assert len(result["data"]) == 6
        assert result["name"] == "Unemployment Rate"

    @respx.mock
    async def test_even_the_quota_wording_is_ignored_when_data_is_present(
        self, client: AlphaVantageClient
    ):
        payload = {**monthly_series(), "Information": QUOTA_NOTE}
        respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=payload))

        assert len((await client.fetch({"function": "CPI"}))["data"]) == 6

    @respx.mock
    async def test_an_error_message_beside_data_is_also_survivable(
        self, client: AlphaVantageClient
    ):
        payload = {**monthly_series(), "Error Message": "partial revision applied"}
        respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=payload))

        assert len((await client.fetch({"function": "CPI"}))["data"]) == 6


class TestNoDataIsStillAFailure:
    @respx.mock
    async def test_the_quota_message_alone_is_a_rate_limit(
        self, client: AlphaVantageClient
    ):
        respx.get(QUERY_URL).mock(
            return_value=httpx.Response(200, json={"Information": QUOTA_NOTE})
        )
        with pytest.raises(UpstreamRateLimitError):
            await client.fetch({"function": "CPI"})

    @respx.mock
    async def test_the_promotional_message_alone_is_a_rate_limit(
        self, client: AlphaVantageClient
    ):
        """No data and a premium pitch means the endpoint was refused."""
        respx.get(QUERY_URL).mock(
            return_value=httpx.Response(200, json={"Information": PROMO_NOTE})
        )
        with pytest.raises(UpstreamRateLimitError):
            await client.fetch({"function": "CPI"})

    @respx.mock
    async def test_an_empty_data_list_does_not_count_as_data(
        self, client: AlphaVantageClient
    ):
        """`data: []` carries no observations, so a note beside it is fatal."""
        respx.get(QUERY_URL).mock(
            return_value=httpx.Response(
                200, json={"data": [], "Information": QUOTA_NOTE}
            )
        )
        with pytest.raises(UpstreamRateLimitError):
            await client.fetch({"function": "CPI"})

    @respx.mock
    async def test_a_non_quota_error_without_data_is_an_invalid_request(
        self, client: AlphaVantageClient
    ):
        respx.get(QUERY_URL).mock(
            return_value=httpx.Response(
                200, json={"Error Message": "Invalid API call for TREASURY_YIELD."}
            )
        )
        with pytest.raises(UpstreamInvalidRequestError):
            await client.fetch({"function": "TREASURY_YIELD"})


class TestSecretsNeverReachTheLogs:
    def test_the_redaction_filter_scrubs_a_query_string(self):
        """httpx logs the full URL at INFO; the filter is the safety net."""
        from indicators_dashboard_backend.logging_config import scrub

        line = (
            "HTTP Request: GET https://www.alphavantage.co/query"
            "?function=REAL_GDP&apikey=UY4NFWFFEE3N94DW \"HTTP/1.1 200 OK\""
        )
        cleaned = scrub(line)

        assert "UY4NFWFFEE3N94DW" not in cleaned
        assert "***redacted***" in cleaned
        assert "function=REAL_GDP" in cleaned, "non-secret context should survive"

    def test_the_filter_handles_both_spellings_and_casings(self):
        from indicators_dashboard_backend.logging_config import scrub

        assert "secret" not in scrub("?api_key=secret&x=1")
        assert "secret" not in scrub("?APIKEY=secret")

    def test_the_filter_rewrites_log_records(self, caplog):
        import logging

        from indicators_dashboard_backend.logging_config import RedactSecretsFilter

        logger = logging.getLogger("test.redaction")
        logger.addFilter(RedactSecretsFilter())

        with caplog.at_level(logging.INFO, logger="test.redaction"):
            logger.info("calling %s", "https://x.co/query?apikey=TOPSECRET")

        assert "TOPSECRET" not in caplog.text

    def test_httpx_request_logging_is_silenced(self):
        import logging

        from indicators_dashboard_backend.logging_config import configure_logging

        configure_logging()
        assert logging.getLogger("httpx").level >= logging.WARNING
        assert logging.getLogger("httpcore").level >= logging.WARNING
