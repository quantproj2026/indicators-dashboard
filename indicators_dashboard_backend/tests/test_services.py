"""Normalisation and the derived headline figures."""

from __future__ import annotations

from datetime import date

import pytest

from indicators_dashboard_backend.catalog import Frequency
from indicators_dashboard_backend.errors import UpstreamPayloadError
from indicators_dashboard_backend.services import (
    Observation,
    _apply_filters,
    build_latest,
    build_stats,
    parse_observations,
)


def obs(day: str, value: float | None) -> Observation:
    return Observation(date.fromisoformat(day), value)


# -- parsing ----------------------------------------------------------------


def test_observations_are_sorted_oldest_first():
    payload = {
        "data": [
            {"date": "2026-03-01", "value": "3"},
            {"date": "2026-01-01", "value": "1"},
            {"date": "2026-02-01", "value": "2"},
        ]
    }
    parsed = parse_observations(payload)
    assert [o.date.month for o in parsed] == [1, 2, 3]
    assert [o.value for o in parsed] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("token", [".", "", "-", "n/a", "NA", "null", "None"])
def test_missing_value_tokens_become_null(token):
    """Alpha Vantage writes `.` for holidays in the daily Treasury series."""
    parsed = parse_observations({"data": [{"date": "2026-01-01", "value": token}]})
    assert parsed[0].value is None


def test_thousands_separators_are_tolerated():
    parsed = parse_observations({"data": [{"date": "2026-01-01", "value": "1,234.5"}]})
    assert parsed[0].value == 1234.5


def test_numeric_values_are_accepted_unquoted():
    parsed = parse_observations({"data": [{"date": "2026-01-01", "value": 7}]})
    assert parsed[0].value == 7.0


def test_rows_with_unparseable_dates_are_dropped():
    payload = {
        "data": [
            {"date": "not-a-date", "value": "1"},
            {"date": "2026-01-01", "value": "2"},
        ]
    }
    assert len(parse_observations(payload)) == 1


def test_short_date_formats_are_accepted():
    parsed = parse_observations({"data": [{"date": "2026", "value": "1"}]})
    assert parsed[0].date == date(2026, 1, 1)


def test_non_mapping_rows_are_skipped():
    parsed = parse_observations({"data": ["junk", {"date": "2026-01-01", "value": "1"}]})
    assert len(parsed) == 1


def test_a_missing_data_list_raises():
    with pytest.raises(UpstreamPayloadError):
        parse_observations({"name": "x"})


# -- latest -----------------------------------------------------------------


def test_latest_reports_period_over_period_change():
    series = [obs("2026-01-01", 4.0), obs("2026-02-01", 4.5)]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.value == 4.5
    assert latest.previous_value == 4.0
    assert latest.change == pytest.approx(0.5)
    assert latest.change_percent == pytest.approx(12.5)


def test_latest_reports_year_over_year_change():
    series = [obs(f"2025-{m:02d}-01", 100.0) for m in range(1, 13)]
    series.append(obs("2026-01-01", 110.0))
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.year_ago_date == date(2025, 1, 1)
    assert latest.year_over_year_change == pytest.approx(10.0)
    assert latest.year_over_year_percent == pytest.approx(10.0)


def test_year_ago_is_matched_by_date_not_by_index():
    """With gaps in the series, index arithmetic would pick the wrong month."""
    series = [
        obs("2025-01-01", 50.0),
        obs("2025-02-01", 51.0),
        # months 3..11 missing
        obs("2025-12-01", 59.0),
        obs("2026-01-01", 60.0),
    ]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.year_ago_date == date(2025, 1, 1)
    assert latest.year_over_year_change == pytest.approx(10.0)


def test_year_ago_is_omitted_when_nothing_falls_in_range():
    series = [obs("2026-01-01", 1.0), obs("2026-02-01", 2.0)]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.year_ago_value is None
    assert latest.year_over_year_percent is None


def test_null_observations_are_skipped_when_picking_the_latest():
    series = [obs("2026-01-01", 4.0), obs("2026-02-01", None)]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.date == date(2026, 1, 1)
    assert latest.value == 4.0


def test_latest_is_none_for_an_all_null_series():
    assert build_latest([obs("2026-01-01", None)], Frequency.MONTHLY) is None
    assert build_latest([], Frequency.MONTHLY) is None


def test_percent_change_is_none_when_the_base_is_zero():
    series = [obs("2026-01-01", 0.0), obs("2026-02-01", 1.0)]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.change == pytest.approx(1.0)
    assert latest.change_percent is None


def test_percent_change_uses_the_magnitude_of_a_negative_base():
    """Going from -2 to -1 is an improvement, so the percentage must be positive."""
    series = [obs("2026-01-01", -2.0), obs("2026-02-01", -1.0)]
    latest = build_latest(series, Frequency.MONTHLY)
    assert latest.change_percent == pytest.approx(50.0)


def test_annual_series_match_the_previous_year_as_year_ago():
    series = [obs("2024-01-01", 2.0), obs("2025-01-01", 3.0)]
    latest = build_latest(series, Frequency.ANNUAL)
    assert latest.year_ago_date == date(2024, 1, 1)


def test_leap_day_anchor_does_not_crash():
    series = [obs("2023-02-28", 1.0), obs("2024-02-29", 2.0)]
    latest = build_latest(series, Frequency.DAILY)
    assert latest.year_ago_date == date(2023, 2, 28)


# -- stats ------------------------------------------------------------------


def test_stats_ignore_nulls_but_count_every_row():
    series = [obs("2026-01-01", 1.0), obs("2026-02-01", None), obs("2026-03-01", 3.0)]
    stats = build_stats(series)
    assert stats.count == 3
    assert (stats.minimum, stats.maximum, stats.mean) == (1.0, 3.0, 2.0)
    assert stats.first_date == date(2026, 1, 1)
    assert stats.last_date == date(2026, 3, 1)


def test_stats_of_an_empty_window():
    stats = build_stats([])
    assert stats.count == 0
    assert stats.minimum is None


def test_stats_of_an_all_null_window():
    stats = build_stats([obs("2026-01-01", None)])
    assert stats.count == 1
    assert stats.mean is None


# -- filtering --------------------------------------------------------------


SERIES = [obs(f"2026-{m:02d}-01", float(m)) for m in range(1, 13)]


def test_limit_keeps_the_most_recent_observations():
    result = _apply_filters(SERIES, start_date=None, end_date=None, limit=3)
    assert [o.value for o in result] == [10.0, 11.0, 12.0]


def test_date_bounds_are_inclusive():
    result = _apply_filters(
        SERIES, start_date=date(2026, 3, 1), end_date=date(2026, 5, 1), limit=None
    )
    assert [o.value for o in result] == [3.0, 4.0, 5.0]


def test_limit_is_applied_after_the_date_filter():
    result = _apply_filters(SERIES, start_date=None, end_date=date(2026, 6, 1), limit=2)
    assert [o.value for o in result] == [5.0, 6.0]


def test_a_limit_larger_than_the_series_is_harmless():
    assert len(_apply_filters(SERIES, start_date=None, end_date=None, limit=999)) == 12


def test_an_empty_range_yields_nothing():
    result = _apply_filters(
        SERIES, start_date=date(2027, 1, 1), end_date=date(2027, 2, 1), limit=None
    )
    assert result == []
