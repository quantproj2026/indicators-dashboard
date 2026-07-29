"""Turns raw Alpha Vantage payloads into the API's response envelope.

Responsibilities, in order:

1. Build the upstream parameter set from an :class:`~.catalog.IndicatorSpec`.
2. Fetch through the cache (see :mod:`.cache`) so the daily quota is respected.
3. Normalise the payload -- parse dates, coerce ``"."`` placeholders to ``None``,
   sort ascending.
4. Derive headline figures (latest, prior, year-over-year) and window statistics.
5. Apply the caller's date/limit/order filters and emit the response model.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .alpha_vantage import AlphaVantageClient, redact
from .cache import CacheResult, TTLCache, make_key
from .catalog import (
    INDICATORS,
    Frequency,
    IndicatorSpec,
    SortOrder,
)
from .errors import UpstreamError, UpstreamPayloadError
from .schemas import (
    IndicatorIdentityOut,
    IndicatorSeriesOut,
    IndicatorSnapshotOut,
    LatestOut,
    ObservationOut,
    OverviewOut,
    SeriesMetaOut,
    SeriesStatsOut,
)

logger = logging.getLogger(__name__)

#: Values Alpha Vantage uses for "no observation at this date".
_MISSING_VALUE_TOKENS = {".", "", "-", "n/a", "na", "null", "none"}

#: How far from an exact one-year offset a "year ago" match may sit, per frequency.
_YOY_TOLERANCE_DAYS: Mapping[Frequency, int] = {
    Frequency.DAILY: 10,
    Frequency.WEEKLY: 14,
    Frequency.MONTHLY: 20,
    Frequency.QUARTERLY: 50,
    Frequency.SEMIANNUAL: 100,
    Frequency.ANNUAL: 200,
}

#: Observations kept on an overview card for its sparkline.
SPARKLINE_POINTS = 36


class Observation:
    """A parsed observation. Lighter than the Pydantic model for internal maths."""

    __slots__ = ("date", "value")

    def __init__(self, obs_date: date, value: float | None) -> None:
        self.date = obs_date
        self.value = value

    def to_out(self) -> ObservationOut:
        return ObservationOut(date=self.date, value=self.value)


def _parse_value(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if text.lower() in _MISSING_VALUE_TOKENS:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _parse_date(raw: object) -> date | None:
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_observations(payload: Mapping[str, Any]) -> list[Observation]:
    """Extract observations from a payload, sorted oldest to newest.

    Rows with an unparseable date are dropped; rows with an unparseable value are
    kept with ``value=None`` so gaps stay visible in the chart.
    """
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise UpstreamPayloadError("Alpha Vantage payload has no `data` list.")

    observations: list[Observation] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        obs_date = _parse_date(row.get("date"))
        if obs_date is None:
            continue
        observations.append(Observation(obs_date, _parse_value(row.get("value"))))

    observations.sort(key=lambda o: o.date)
    return observations


def _shift_one_year(anchor: date) -> date:
    try:
        return anchor.replace(year=anchor.year - 1)
    except ValueError:  # 29 February
        return anchor.replace(year=anchor.year - 1, day=28)


def _find_year_ago(
    observations: Sequence[Observation], anchor: date, frequency: Frequency
) -> Observation | None:
    """Find the observation closest to one year before ``anchor``.

    Matching by date rather than by index keeps the result correct even when the
    series has gaps (common in daily Treasury data around holidays).
    """
    target = _shift_one_year(anchor)
    tolerance = _YOY_TOLERANCE_DAYS.get(frequency, 20)
    best: Observation | None = None
    best_distance = tolerance + 1
    for obs in observations:
        if obs.value is None:
            continue
        distance = abs((obs.date - target).days)
        if distance <= tolerance and distance < best_distance:
            best, best_distance = obs, distance
    return best


def _percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 4)


def build_latest(
    observations: Sequence[Observation], frequency: Frequency
) -> LatestOut | None:
    """Compute the headline block from the tail of an ascending series."""
    valued = [o for o in observations if o.value is not None]
    if not valued:
        return None

    latest = valued[-1]
    assert latest.value is not None
    previous = valued[-2] if len(valued) >= 2 else None
    year_ago = _find_year_ago(valued[:-1], latest.date, frequency)

    change = change_pct = None
    if previous is not None and previous.value is not None:
        change = round(latest.value - previous.value, 6)
        change_pct = _percent_change(latest.value, previous.value)

    yoy = yoy_pct = None
    if year_ago is not None and year_ago.value is not None:
        yoy = round(latest.value - year_ago.value, 6)
        yoy_pct = _percent_change(latest.value, year_ago.value)

    return LatestOut(
        date=latest.date,
        value=latest.value,
        previous_date=previous.date if previous else None,
        previous_value=previous.value if previous else None,
        change=change,
        change_percent=change_pct,
        year_ago_date=year_ago.date if year_ago else None,
        year_ago_value=year_ago.value if year_ago else None,
        year_over_year_change=yoy,
        year_over_year_percent=yoy_pct,
    )


def build_stats(observations: Sequence[Observation]) -> SeriesStatsOut:
    values = [o.value for o in observations if o.value is not None]
    if not observations:
        return SeriesStatsOut(count=0)
    return SeriesStatsOut(
        count=len(observations),
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        mean=round(sum(values) / len(values), 6) if values else None,
        first_date=min(o.date for o in observations),
        last_date=max(o.date for o in observations),
    )


def _apply_filters(
    observations: Sequence[Observation],
    *,
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
) -> list[Observation]:
    """Filter by date range, then keep the ``limit`` most recent observations."""
    selected: Iterable[Observation] = observations
    if start_date is not None:
        selected = (o for o in selected if o.date >= start_date)
    if end_date is not None:
        selected = (o for o in selected if o.date <= end_date)
    result = list(selected)
    if limit is not None and limit < len(result):
        result = result[-limit:]
    return result


class IndicatorService:
    """Application service backing every indicator endpoint."""

    def __init__(self, client: AlphaVantageClient, cache: TTLCache) -> None:
        self._client = client
        self._cache = cache

    # -- fetching -----------------------------------------------------------

    async def _fetch_payload(
        self, params: Mapping[str, str], *, force_refresh: bool = False
    ) -> CacheResult[dict[str, Any]]:
        key = make_key("json", *(f"{k}={params[k]}" for k in sorted(params)))
        return await self._cache.get_or_fetch(
            key,
            lambda: self._client.fetch(params),
            serialize=lambda payload: payload,  # already JSON-compatible
            force_refresh=force_refresh,
        )

    async def fetch_csv(
        self,
        spec: IndicatorSpec,
        *,
        interval: str | None = None,
        maturity: str | None = None,
        force_refresh: bool = False,
    ) -> str:
        """Return the upstream CSV representation of a series."""
        params = spec.upstream_params(interval=interval, maturity=maturity)
        key = make_key("csv", *(f"{k}={params[k]}" for k in sorted(params)))
        result = await self._cache.get_or_fetch(
            key,
            lambda: self._client.fetch_csv(params),
            serialize=lambda text: text,
            force_refresh=force_refresh,
        )
        return result.value

    # -- series -------------------------------------------------------------

    async def get_series(
        self,
        spec: IndicatorSpec,
        *,
        interval: str | None = None,
        maturity: str | None = None,
        limit: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        order: SortOrder = SortOrder.DESC,
        force_refresh: bool = False,
    ) -> IndicatorSeriesOut:
        """Fetch, normalise, and package one indicator's time series."""
        params = spec.upstream_params(interval=interval, maturity=maturity)
        result = await self._fetch_payload(params, force_refresh=force_refresh)
        payload = result.value

        observations = parse_observations(payload)
        frequency = spec.frequency_for(params.get("interval"))
        latest = build_latest(observations, frequency)

        window = _apply_filters(
            observations, start_date=start_date, end_date=end_date, limit=limit
        )
        emitted = window if order is SortOrder.ASC else list(reversed(window))

        return IndicatorSeriesOut(
            indicator=self._identity(spec, payload, params, frequency),
            meta=self._meta(spec, params, result, order, len(window), len(observations)),
            latest=latest,
            stats=build_stats(window),
            data=[o.to_out() for o in emitted],
        )

    async def get_snapshot(
        self,
        spec: IndicatorSpec,
        *,
        sparkline_points: int = SPARKLINE_POINTS,
        force_refresh: bool = False,
    ) -> IndicatorSnapshotOut:
        """Headline figures for one indicator, using its default parameters.

        Never raises for upstream problems -- a failure is reported inside the
        snapshot so one bad indicator cannot blank the whole overview grid.
        """
        params = spec.upstream_params()
        frequency = spec.frequency_for(params.get("interval"))
        identity_fallback = IndicatorIdentityOut(
            slug=spec.slug,
            function=spec.function,
            name=spec.name,
            short_name=spec.short_name,
            unit=spec.unit,
            unit_short=spec.unit_short,
            category=spec.category,
            frequency=frequency,
            interval=params.get("interval"),
            maturity=params.get("maturity"),
            higher_is_better=spec.higher_is_better,
        )

        try:
            result = await self._fetch_payload(params, force_refresh=force_refresh)
        except UpstreamError as exc:
            logger.warning("Overview: %s unavailable (%s)", spec.slug, exc.code)
            from .schemas import ErrorDetail

            return IndicatorSnapshotOut(
                indicator=identity_fallback,
                error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details or None),
            )

        payload = result.value
        observations = parse_observations(payload)
        window = observations[-sparkline_points:] if sparkline_points > 0 else []

        return IndicatorSnapshotOut(
            indicator=self._identity(spec, payload, params, frequency),
            latest=build_latest(observations, frequency),
            sparkline=[o.to_out() for o in window],
            meta=self._meta(
                spec, params, result, SortOrder.ASC, len(window), len(observations)
            ),
        )

    async def get_overview(self, *, force_refresh: bool = False) -> OverviewOut:
        """Snapshots for the whole catalog, fetched concurrently."""
        snapshots = await asyncio.gather(
            *(
                self.get_snapshot(spec, force_refresh=force_refresh)
                for spec in INDICATORS.values()
            )
        )
        return OverviewOut(
            generated_at=datetime.now(timezone.utc),
            count=len(snapshots),
            degraded=any(s.error is not None for s in snapshots),
            indicators=list(snapshots),
        )

    # -- assembly helpers ---------------------------------------------------

    @staticmethod
    def _identity(
        spec: IndicatorSpec,
        payload: Mapping[str, Any],
        params: Mapping[str, str],
        frequency: Frequency,
    ) -> IndicatorIdentityOut:
        upstream_name = payload.get("name")
        upstream_unit = payload.get("unit")
        return IndicatorIdentityOut(
            slug=spec.slug,
            function=spec.function,
            name=str(upstream_name) if upstream_name else spec.name,
            short_name=spec.short_name,
            unit=str(upstream_unit) if upstream_unit else spec.unit,
            unit_short=spec.unit_short,
            category=spec.category,
            frequency=frequency,
            interval=params.get("interval"),
            maturity=params.get("maturity"),
            higher_is_better=spec.higher_is_better,
        )

    @staticmethod
    def _meta(
        spec: IndicatorSpec,
        params: Mapping[str, str],
        result: CacheResult[Any],
        order: SortOrder,
        returned: int,
        total: int,
    ) -> SeriesMetaOut:
        return SeriesMetaOut(
            function=spec.function,
            parameters=redact(params),
            order=order,
            returned=returned,
            total_available=total,
            fetched_at=datetime.fromtimestamp(result.stored_at, tz=timezone.utc),
            cached=result.cached,
            stale=result.stale,
            cache_age_seconds=round(result.age_seconds, 3),
        )
