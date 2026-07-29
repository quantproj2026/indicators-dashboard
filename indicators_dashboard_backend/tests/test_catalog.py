"""The catalog must match the published Alpha Vantage parameter surface exactly."""

from __future__ import annotations

import pytest

from indicators_dashboard_backend.catalog import (
    INDICATORS,
    INDICATORS_BY_FUNCTION,
    Frequency,
    get_spec,
)
from indicators_dashboard_backend.errors import IndicatorNotFoundError

#: Every function documented under "Economic Indicators".
EXPECTED_FUNCTIONS = {
    "REAL_GDP",
    "REAL_GDP_PER_CAPITA",
    "TREASURY_YIELD",
    "FEDERAL_FUNDS_RATE",
    "CPI",
    "INFLATION",
    "RETAIL_SALES",
    "DURABLES",
    "UNEMPLOYMENT",
    "NONFARM_PAYROLL",
}


def test_every_documented_indicator_is_present():
    assert set(INDICATORS_BY_FUNCTION) == EXPECTED_FUNCTIONS


def test_slugs_are_unique_and_url_safe():
    slugs = [spec.slug for spec in INDICATORS.values()]
    assert len(slugs) == len(set(slugs))
    assert all(slug == slug.lower() and " " not in slug for slug in slugs)


@pytest.mark.parametrize(
    ("slug", "allowed", "default"),
    [
        ("real-gdp", ("annual", "quarterly"), "annual"),
        ("treasury-yield", ("daily", "weekly", "monthly"), "monthly"),
        ("federal-funds-rate", ("daily", "weekly", "monthly"), "monthly"),
        ("cpi", ("monthly", "semiannual"), "monthly"),
    ],
)
def test_interval_parameters_match_the_documentation(slug, allowed, default):
    spec = get_spec(slug)
    assert spec.interval is not None
    assert spec.interval.allowed == allowed
    assert spec.interval.default == default


def test_treasury_maturities_match_the_documentation():
    spec = get_spec("treasury-yield")
    assert spec.maturity is not None
    assert spec.maturity.allowed == ("3month", "2year", "5year", "7year", "10year", "30year")
    assert spec.maturity.default == "10year"


@pytest.mark.parametrize(
    "slug",
    [
        "real-gdp-per-capita",
        "inflation",
        "retail-sales",
        "durables",
        "unemployment",
        "nonfarm-payroll",
    ],
)
def test_single_frequency_indicators_take_no_parameters(slug):
    spec = get_spec(slug)
    assert spec.parameters == ()
    assert spec.upstream_params() == {"function": spec.function}


def test_upstream_params_drop_unsupported_arguments():
    """A maturity passed to a series that has none must not reach the upstream.

    Alpha Vantage silently ignores unknown parameters, which would let two
    different requests collapse onto one mislabelled cache entry.
    """
    spec = get_spec("unemployment")
    assert spec.upstream_params(interval="daily", maturity="30year") == {
        "function": "UNEMPLOYMENT"
    }


def test_upstream_params_fill_in_defaults():
    assert get_spec("treasury-yield").upstream_params() == {
        "function": "TREASURY_YIELD",
        "interval": "monthly",
        "maturity": "10year",
    }
    assert get_spec("treasury-yield").upstream_params(interval="daily", maturity="3month") == {
        "function": "TREASURY_YIELD",
        "interval": "daily",
        "maturity": "3month",
    }


def test_frequency_resolution_tracks_the_interval():
    spec = get_spec("real-gdp")
    assert spec.frequency_for(None) is Frequency.ANNUAL
    assert spec.frequency_for("quarterly") is Frequency.QUARTERLY
    assert spec.frequency_for("nonsense") is Frequency.ANNUAL


def test_unknown_slug_raises_with_the_available_list():
    with pytest.raises(IndicatorNotFoundError) as excinfo:
        get_spec("gdp")
    payload = excinfo.value.to_payload()
    assert payload["error"]["code"] == "indicator_not_found"
    assert "real-gdp" in payload["error"]["details"]["available"]
