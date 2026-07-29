"""End-to-end HTTP tests against the wired application with a mocked upstream."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from indicators_dashboard_backend.catalog import INDICATORS
from indicators_dashboard_backend.config import Settings
from indicators_dashboard_backend.main import create_app

from .conftest import (
    ERROR_MESSAGE_BODY,
    RATE_LIMIT_BODY,
    FakeUpstream,
    monthly_series,
    series_with_year_of_history,
)

PREFIX = "/api/v1"

#: (path, function, expected forwarded params) for every indicator, defaults applied.
INDICATOR_ROUTES = [
    ("/real-gdp", "REAL_GDP", {"interval": "annual"}),
    ("/real-gdp-per-capita", "REAL_GDP_PER_CAPITA", {}),
    ("/treasury-yield", "TREASURY_YIELD", {"interval": "monthly", "maturity": "10year"}),
    ("/federal-funds-rate", "FEDERAL_FUNDS_RATE", {"interval": "monthly"}),
    ("/cpi", "CPI", {"interval": "monthly"}),
    ("/inflation", "INFLATION", {}),
    ("/retail-sales", "RETAIL_SALES", {}),
    ("/durables", "DURABLES", {}),
    ("/unemployment", "UNEMPLOYMENT", {}),
    ("/nonfarm-payroll", "NONFARM_PAYROLL", {}),
]


# -- system endpoints -------------------------------------------------------


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_key_configured"] is True


def test_health_is_also_mounted_under_the_api_prefix(client: TestClient):
    assert client.get(f"{PREFIX}/health").status_code == 200


def test_root_banner_points_at_the_catalog(client: TestClient):
    body = client.get("/").json()
    assert body["indicators"] == f"{PREFIX}/indicators"
    assert body["overview"] == f"{PREFIX}/indicators/latest"


def test_meta_reports_key_presence_without_the_key(client: TestClient):
    body = client.get(f"{PREFIX}/meta").json()
    assert body["api_key_configured"] is True
    assert body["indicator_count"] == 10
    assert "TEST-KEY-DO-NOT-LOG" not in response_text(client, f"{PREFIX}/meta")
    assert body["cache"]["ttl_seconds"] == 300


def response_text(client: TestClient, path: str) -> str:
    return client.get(path).text


def test_openapi_schema_is_generated(client: TestClient):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path, _function, _params in INDICATOR_ROUTES:
        assert f"{PREFIX}/indicators{path}" in paths


def test_openapi_documents_the_treasury_enums(client: TestClient):
    schema = client.get("/openapi.json").json()
    params = schema["paths"][f"{PREFIX}/indicators/treasury-yield"]["get"]["parameters"]
    by_name = {p["name"]: p for p in params}
    maturity_schema = by_name["maturity"]["schema"]
    ref = maturity_schema.get("$ref") or maturity_schema.get("allOf", [{}])[0].get("$ref", "")
    enum_name = ref.rsplit("/", 1)[-1]
    assert set(schema["components"]["schemas"][enum_name]["enum"]) == {
        "3month",
        "2year",
        "5year",
        "7year",
        "10year",
        "30year",
    }


# -- catalog ----------------------------------------------------------------


def test_catalog_lists_every_indicator(client: TestClient):
    body = client.get(f"{PREFIX}/indicators").json()
    assert len(body) == 10
    assert {item["function"] for item in body} == {s.function for s in INDICATORS.values()}


def test_catalog_advertises_parameters_and_paths(client: TestClient):
    body = {item["slug"]: item for item in client.get(f"{PREFIX}/indicators").json()}

    treasury = body["treasury-yield"]
    assert treasury["path"] == f"{PREFIX}/indicators/treasury-yield"
    names = {p["name"]: p for p in treasury["parameters"]}
    assert set(names) == {"interval", "maturity"}
    assert names["maturity"]["default"] == "10year"

    assert body["unemployment"]["parameters"] == []


def test_catalog_costs_no_upstream_calls(client: TestClient, upstream: FakeUpstream):
    client.get(f"{PREFIX}/indicators")
    assert upstream.call_count == 0


# -- series endpoints -------------------------------------------------------


@pytest.mark.parametrize(("path", "function", "expected"), INDICATOR_ROUTES)
def test_every_indicator_forwards_the_right_parameters(
    client: TestClient, upstream: FakeUpstream, path, function, expected
):
    upstream.default_json(monthly_series())
    response = client.get(f"{PREFIX}/indicators{path}")

    assert response.status_code == 200, response.text
    sent = upstream.last_params()
    assert sent["function"] == function
    for key, value in expected.items():
        assert sent[key] == value
    # Parameters the indicator does not support must not be forwarded.
    for unsupported in {"interval", "maturity"} - set(expected):
        assert unsupported not in sent


@pytest.mark.parametrize(("path", "function", "_expected"), INDICATOR_ROUTES)
def test_every_indicator_returns_the_shared_envelope(
    client: TestClient, upstream: FakeUpstream, path, function, _expected
):
    upstream.default_json(monthly_series())
    body = client.get(f"{PREFIX}/indicators{path}").json()

    assert set(body) == {"indicator", "meta", "latest", "stats", "data"}
    assert body["indicator"]["function"] == function
    assert body["meta"]["source"] == "Alpha Vantage"
    assert body["data"], "expected observations"
    assert set(body["data"][0]) == {"date", "value"}


def test_the_api_key_never_appears_in_a_response(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    response = client.get(f"{PREFIX}/indicators/cpi")
    assert "TEST-KEY-DO-NOT-LOG" not in response.text
    assert "apikey" not in response.text
    # ...but it was sent upstream.
    assert upstream.requests[-1].url.params["apikey"] == "TEST-KEY-DO-NOT-LOG"


def test_selectable_interval_is_forwarded(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(interval="quarterly"))
    client.get(f"{PREFIX}/indicators/real-gdp?interval=quarterly")
    assert upstream.last_params()["interval"] == "quarterly"


def test_selectable_maturity_is_forwarded(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/treasury-yield?interval=daily&maturity=3month")
    sent = upstream.last_params()
    assert (sent["interval"], sent["maturity"]) == ("daily", "3month")


def test_cpi_semiannual_interval_is_accepted(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(interval="semiannual"))
    response = client.get(f"{PREFIX}/indicators/cpi?interval=semiannual")
    assert response.status_code == 200
    assert upstream.last_params()["interval"] == "semiannual"


# -- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/treasury-yield?maturity=1month",  # not offered by Alpha Vantage
        "/treasury-yield?interval=annual",
        "/real-gdp?interval=monthly",
        "/cpi?interval=daily",
        "/federal-funds-rate?interval=quarterly",
        "/unemployment?order=sideways",
        "/unemployment?limit=0",
        "/unemployment?limit=-5",
        "/unemployment?start_date=nonsense",
        "/unemployment?datatype=xml",
    ],
)
def test_invalid_parameters_are_rejected_before_any_upstream_call(
    client: TestClient, upstream: FakeUpstream, url
):
    """Alpha Vantage would silently substitute its default; we refuse instead."""
    response = client.get(f"{PREFIX}/indicators{url}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert upstream.call_count == 0


def test_validation_errors_name_the_offending_field(client: TestClient):
    body = client.get(f"{PREFIX}/indicators/treasury-yield?maturity=1month").json()
    assert body["error"]["details"]["errors"][0]["field"] == "maturity"


def test_unknown_indicator_path_is_404(client: TestClient):
    response = client.get(f"{PREFIX}/indicators/gdp")
    assert response.status_code == 404
    assert "error" in response.json()


# -- presentation parameters ------------------------------------------------


def test_limit_trims_to_the_most_recent_observations(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series(values=[6, 5, 4, 3, 2, 1]))
    body = client.get(f"{PREFIX}/indicators/unemployment?limit=2").json()
    assert body["meta"]["returned"] == 2
    assert body["meta"]["total_available"] == 6
    assert [d["value"] for d in body["data"]] == [6.0, 5.0]  # desc by default


def test_order_asc_reverses_the_series(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(values=[6, 5, 4, 3, 2, 1]))
    body = client.get(f"{PREFIX}/indicators/unemployment?order=asc").json()
    assert body["meta"]["order"] == "asc"
    dates = [d["date"] for d in body["data"]]
    assert dates == sorted(dates)


def test_default_order_is_newest_first(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    body = client.get(f"{PREFIX}/indicators/unemployment").json()
    dates = [d["date"] for d in body["data"]]
    assert dates == sorted(dates, reverse=True)


def test_date_bounds_filter_the_window(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(values=[6, 5, 4, 3, 2, 1]))
    body = client.get(
        f"{PREFIX}/indicators/unemployment?start_date=2026-03-01&end_date=2026-05-01&order=asc"
    ).json()
    assert [d["date"] for d in body["data"]] == ["2026-03-01", "2026-04-01", "2026-05-01"]


def test_filters_do_not_cost_an_extra_upstream_call(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/unemployment")
    client.get(f"{PREFIX}/indicators/unemployment?limit=2&order=asc")
    assert upstream.call_count == 1


def test_latest_is_computed_from_the_full_series_not_the_window(
    client: TestClient, upstream: FakeUpstream
):
    """Narrowing the chart window must not change the headline figure."""
    upstream.default_json(monthly_series(values=[9, 8, 7, 6, 5, 4]))
    unfiltered = client.get(f"{PREFIX}/indicators/unemployment").json()
    windowed = client.get(f"{PREFIX}/indicators/unemployment?limit=2").json()
    assert unfiltered["latest"] == windowed["latest"]


def test_derived_changes_are_present(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(series_with_year_of_history(latest=110.0, year_ago=100.0))
    latest = client.get(f"{PREFIX}/indicators/unemployment").json()["latest"]
    assert latest["value"] == 110.0
    assert latest["change"] is not None
    assert latest["year_over_year_percent"] == pytest.approx(10.0)


def test_missing_observations_are_null_not_dropped(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(values=[4.2, ".", 4.0]))
    body = client.get(f"{PREFIX}/indicators/treasury-yield").json()
    assert body["meta"]["total_available"] == 3
    assert [d["value"] for d in body["data"]] == [4.2, None, 4.0]


def test_stats_describe_the_returned_window(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series(values=[6, 5, 4, 3, 2, 1]))
    stats = client.get(f"{PREFIX}/indicators/unemployment").json()["stats"]
    assert stats == {
        "count": 6,
        "minimum": 1.0,
        "maximum": 6.0,
        "mean": 3.5,
        "first_date": "2026-01-01",
        "last_date": "2026-06-01",
    }


# -- CSV passthrough --------------------------------------------------------


def test_csv_datatype_returns_the_raw_upstream_file(
    client: TestClient, upstream: FakeUpstream
):
    upstream.text("CPI", "timestamp,value\r\n2026-06-01,320.5\r\n")
    response = client.get(f"{PREFIX}/indicators/cpi?datatype=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("timestamp,value")
    assert upstream.last_params()["datatype"] == "csv"


def test_csv_download_carries_a_descriptive_filename(
    client: TestClient, upstream: FakeUpstream
):
    upstream.text("TREASURY_YIELD", "timestamp,value\r\n2026-06-01,4.4\r\n")
    response = client.get(
        f"{PREFIX}/indicators/treasury-yield?datatype=csv&interval=daily&maturity=3month"
    )
    assert "treasury-yield-daily-3month.csv" in response.headers["content-disposition"]


def test_csv_and_json_are_cached_separately(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/durables")
    upstream.text("DURABLES", "timestamp,value\r\n2026-06-01,1\r\n")
    assert client.get(f"{PREFIX}/indicators/durables?datatype=csv").status_code == 200
    assert upstream.call_count == 2


# -- caching ----------------------------------------------------------------


def test_a_repeat_request_is_served_from_cache(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())

    first = client.get(f"{PREFIX}/indicators/cpi").json()
    second = client.get(f"{PREFIX}/indicators/cpi").json()

    assert upstream.call_count == 1
    assert first["meta"]["cached"] is False
    assert second["meta"]["cached"] is True
    assert second["meta"]["stale"] is False


def test_different_parameters_are_cached_independently(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/treasury-yield?maturity=10year")
    client.get(f"{PREFIX}/indicators/treasury-yield?maturity=2year")
    client.get(f"{PREFIX}/indicators/treasury-yield?maturity=10year")
    assert upstream.call_count == 2


def test_refresh_forces_a_live_call(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/cpi")
    body = client.get(f"{PREFIX}/indicators/cpi?refresh=true").json()
    assert upstream.call_count == 2
    assert body["meta"]["cached"] is False


def test_cache_stats_endpoint_tracks_activity(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/cpi")
    client.get(f"{PREFIX}/indicators/cpi")
    stats = client.get(f"{PREFIX}/cache").json()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["entries"] == 1


def test_clearing_the_cache_requires_confirmation(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/cpi")

    unconfirmed = client.delete(f"{PREFIX}/cache").json()
    assert unconfirmed["cleared"] is False

    confirmed = client.delete(f"{PREFIX}/cache?confirm=true").json()
    assert confirmed == {"cleared": True, "entries_removed": 1}

    client.get(f"{PREFIX}/indicators/cpi")
    assert upstream.call_count == 2


# -- upstream failures ------------------------------------------------------


def test_rate_limit_becomes_429_with_the_error_envelope(
    client: TestClient, upstream: FakeUpstream
):
    upstream.json("CPI", RATE_LIMIT_BODY)
    response = client.get(f"{PREFIX}/indicators/cpi")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "upstream_rate_limited"


def test_invalid_upstream_call_becomes_502(client: TestClient, upstream: FakeUpstream):
    upstream.json("CPI", ERROR_MESSAGE_BODY)
    response = client.get(f"{PREFIX}/indicators/cpi")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_invalid_request"


def test_unreachable_upstream_becomes_503(client: TestClient, upstream: FakeUpstream):
    upstream.transport_error("CPI")
    response = client.get(f"{PREFIX}/indicators/cpi")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


def test_a_timeout_becomes_503(client: TestClient, upstream: FakeUpstream):
    upstream.timeout("CPI")
    assert client.get(f"{PREFIX}/indicators/cpi").status_code == 503


def test_malformed_payload_becomes_502(client: TestClient, upstream: FakeUpstream):
    upstream.json("CPI", {"name": "CPI"})
    response = client.get(f"{PREFIX}/indicators/cpi")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_malformed_payload"


def test_a_rate_limit_after_a_success_serves_the_cached_copy(
    client: TestClient, upstream: FakeUpstream
):
    """The dashboard must keep working after the 25-request budget runs out."""
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/cpi")

    # Expire the entry (TTL is 300s, stale grace is a day), then refuse upstream.
    cache = client.app.state.cache
    key = next(iter(cache._entries))
    cache.peek(key).stored_at = time.time() - 3_600
    upstream.json("CPI", RATE_LIMIT_BODY)

    response = client.get(f"{PREFIX}/indicators/cpi")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["stale"] is True
    assert body["meta"]["cached"] is True
    assert body["meta"]["cache_age_seconds"] >= 3_600
    assert body["data"]


def test_a_cached_copy_past_the_grace_window_is_not_served(
    client: TestClient, upstream: FakeUpstream
):
    """Stale-serving has a limit: very old data surfaces the error instead."""
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/cpi")

    cache = client.app.state.cache
    key = next(iter(cache._entries))
    cache.peek(key).stored_at = time.time() - 500_000  # past ttl + 1 day of grace
    upstream.json("CPI", RATE_LIMIT_BODY)

    assert client.get(f"{PREFIX}/indicators/cpi").status_code == 429


def test_a_transport_failure_also_falls_back_to_cache(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/durables")

    cache = client.app.state.cache
    cache.peek(next(iter(cache._entries))).stored_at = time.time() - 3_600
    upstream.transport_error("DURABLES")

    response = client.get(f"{PREFIX}/indicators/durables")
    assert response.status_code == 200
    assert response.json()["meta"]["stale"] is True


def test_the_overview_survives_on_stale_data(client: TestClient, upstream: FakeUpstream):
    """After the daily budget is spent, the dashboard still renders."""
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/latest")

    cache = client.app.state.cache
    for key in list(cache._entries):
        cache.peek(key).stored_at = time.time() - 3_600
    upstream.default_json(RATE_LIMIT_BODY)

    body = client.get(f"{PREFIX}/indicators/latest").json()

    assert body["degraded"] is False
    assert all(item["meta"]["stale"] is True for item in body["indicators"])
    assert all(item["latest"] is not None for item in body["indicators"])


def test_missing_api_key_is_reported_clearly(upstream: FakeUpstream, tmp_path):
    keyless = Settings(
        alpha_vantage_api_key="",
        cache_persist=False,
        cache_dir=tmp_path / "c",
        min_seconds_between_upstream_calls=0.0,
    )
    with TestClient(create_app(keyless)) as client:
        assert client.get("/health").json()["api_key_configured"] is False
        response = client.get(f"{PREFIX}/indicators/cpi")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "api_key_missing"


# -- overview ---------------------------------------------------------------


def test_overview_returns_every_indicator(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    body = client.get(f"{PREFIX}/indicators/latest").json()

    assert body["count"] == 10
    assert body["degraded"] is False
    assert len(body["indicators"]) == 10
    assert {i["indicator"]["slug"] for i in body["indicators"]} == set(INDICATORS)


def test_overview_includes_a_sparkline_in_ascending_order(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series(values=[6, 5, 4, 3, 2, 1]))
    snapshot = client.get(f"{PREFIX}/indicators/latest").json()["indicators"][0]
    dates = [p["date"] for p in snapshot["sparkline"]]
    assert dates == sorted(dates)
    assert snapshot["latest"]["value"] == 6.0


def test_overview_uses_default_parameters_for_each_indicator(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/latest")

    by_function = {r.url.params["function"]: dict(r.url.params) for r in upstream.requests}
    assert by_function["TREASURY_YIELD"]["maturity"] == "10year"
    assert by_function["REAL_GDP"]["interval"] == "annual"
    assert "interval" not in by_function["UNEMPLOYMENT"]


def test_one_failing_indicator_does_not_break_the_overview(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    upstream.json("CPI", RATE_LIMIT_BODY)

    body = client.get(f"{PREFIX}/indicators/latest").json()

    assert body["degraded"] is True
    by_slug = {i["indicator"]["slug"]: i for i in body["indicators"]}
    assert by_slug["cpi"]["error"]["code"] == "upstream_rate_limited"
    assert by_slug["cpi"]["latest"] is None
    # The failing indicator still carries usable metadata for the card.
    assert by_slug["cpi"]["indicator"]["short_name"] == "CPI"
    # Everything else loaded.
    assert by_slug["unemployment"]["latest"]["value"] == 4.2
    assert by_slug["unemployment"]["error"] is None


def test_overview_shares_the_cache_with_the_series_endpoints(
    client: TestClient, upstream: FakeUpstream
):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/latest")
    calls_after_overview = upstream.call_count

    client.get(f"{PREFIX}/indicators/cpi")
    assert upstream.call_count == calls_after_overview


def test_overview_costs_one_call_per_indicator(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    client.get(f"{PREFIX}/indicators/latest")
    assert upstream.call_count == 10
    client.get(f"{PREFIX}/indicators/latest")
    assert upstream.call_count == 10, "second overview must be fully cached"


# -- CORS -------------------------------------------------------------------


def test_cors_allows_the_dashboard_origin(client: TestClient, upstream: FakeUpstream):
    upstream.default_json(monthly_series())
    response = client.get(
        f"{PREFIX}/indicators/cpi", headers={"Origin": "http://localhost:3000"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_is_answered(client: TestClient):
    response = client.options(
        f"{PREFIX}/indicators/cpi",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "GET" in response.headers["access-control-allow-methods"]
