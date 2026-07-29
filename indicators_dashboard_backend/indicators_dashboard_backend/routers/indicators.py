"""REST endpoints proxying the Alpha Vantage economic indicators.

Every indicator listed at
https://www.alphavantage.co/documentation/#economic-indicators gets its own
route, declared explicitly rather than generated from the catalog, so the
OpenAPI schema carries the real enum of allowed ``interval``/``maturity`` values
and ``/docs`` is self-documenting.

All routes share:

* the response envelope :class:`~..schemas.IndicatorSeriesOut`;
* the presentation parameters in :class:`~..dependencies.SeriesQuery`
  (``limit``, ``start_date``, ``end_date``, ``order``, ``datatype``, ``refresh``);
* the API key, which is attached inside the backend and never reaches the client.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from ..catalog import (
    INDICATORS,
    CpiInterval,
    DataType,
    FederalFundsInterval,
    IndicatorSpec,
    RealGdpInterval,
    TreasuryInterval,
    TreasuryMaturity,
    get_spec,
)
from ..dependencies import SeriesQueryDep, ServiceDep, SettingsDep
from ..schemas import (
    ErrorResponse,
    IndicatorSeriesOut,
    IndicatorSummaryOut,
    OverviewOut,
)

router = APIRouter(prefix="/indicators", tags=["indicators"])

#: Documented failure modes shared by every series endpoint.
_SERIES_RESPONSES: dict[int | str, dict] = {
    429: {
        "model": ErrorResponse,
        "description": (
            "Alpha Vantage rate limit reached (the free tier allows 25 requests "
            "per day) and no cached copy was available to serve instead."
        ),
    },
    502: {"model": ErrorResponse, "description": "Alpha Vantage returned an unusable response."},
    503: {"model": ErrorResponse, "description": "Alpha Vantage could not be reached."},
}

_CSV_RESPONSE_DOC = {
    "content": {
        "application/json": {},
        "text/csv": {"schema": {"type": "string"}},
    },
    "description": "The time series. Returns `text/csv` when `datatype=csv`.",
}


async def _series(
    spec: IndicatorSpec,
    service: ServiceDep,
    query: SeriesQueryDep,
    *,
    interval: str | None = None,
    maturity: str | None = None,
) -> IndicatorSeriesOut | Response:
    """Shared body for the per-indicator routes."""
    if query.datatype is DataType.CSV:
        csv_text = await service.fetch_csv(
            spec, interval=interval, maturity=maturity, force_refresh=query.refresh
        )
        filename = "-".join(
            part for part in (spec.slug, interval, maturity) if part
        )
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{filename}.csv"'},
        )

    return await service.get_series(
        spec,
        interval=interval,
        maturity=maturity,
        limit=query.limit,
        start_date=query.start_date,
        end_date=query.end_date,
        order=query.order,
        force_refresh=query.refresh,
    )


# ---------------------------------------------------------------------------
# Catalog and overview. Declared before the per-indicator routes.
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[IndicatorSummaryOut],
    summary="List every available indicator",
    description=(
        "Static catalog of the ten Alpha Vantage economic indicators, including "
        "each one's supported parameters, allowed values, and defaults. Contacts "
        "no upstream service, so it is always fast and always available."
    ),
)
async def list_indicators(settings: SettingsDep) -> list[IndicatorSummaryOut]:
    return [
        IndicatorSummaryOut.from_spec(spec, api_prefix=settings.api_prefix)
        for spec in INDICATORS.values()
    ]


@router.get(
    "/latest",
    response_model=OverviewOut,
    summary="Latest value for every indicator",
    description=(
        "One batched call powering the dashboard's overview grid: the newest "
        "observation for each indicator using its default parameters, plus the "
        "period-over-period and year-over-year changes and a short sparkline "
        "series.\n\n"
        "Indicators are fetched concurrently and failures are isolated -- an "
        "indicator that cannot be loaded reports an `error` object while the "
        "rest return normally, and `degraded` flags that this happened."
    ),
)
async def latest_overview(
    service: ServiceDep,
    refresh: Annotated[
        bool,
        Query(
            description=(
                "Bypass the cache for every indicator. This costs one upstream "
                "request per indicator against a 25/day budget."
            )
        ),
    ] = False,
) -> OverviewOut:
    return await service.get_overview(force_refresh=refresh)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@router.get(
    "/real-gdp",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Real GDP",
    description="Annual or quarterly real Gross Domestic Product of the United States.",
)
async def real_gdp(
    service: ServiceDep,
    query: SeriesQueryDep,
    interval: Annotated[
        RealGdpInterval, Query(description="Sampling frequency of the GDP series.")
    ] = RealGdpInterval.ANNUAL,
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("real-gdp"), service, query, interval=interval.value)


@router.get(
    "/real-gdp-per-capita",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Real GDP per capita",
    description=(
        "Quarterly real GDP per capita in chained 2012 dollars. Alpha Vantage "
        "publishes this series at a single frequency, so it takes no `interval`."
    ),
)
async def real_gdp_per_capita(
    service: ServiceDep, query: SeriesQueryDep
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("real-gdp-per-capita"), service, query)


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------


@router.get(
    "/treasury-yield",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Treasury yield",
    description=(
        "U.S. Treasury constant-maturity yield. Both `interval` and `maturity` "
        "are selectable; unsupported values are rejected with 422 rather than "
        "forwarded, because Alpha Vantage silently substitutes its default."
    ),
)
async def treasury_yield(
    service: ServiceDep,
    query: SeriesQueryDep,
    interval: Annotated[
        TreasuryInterval, Query(description="Sampling frequency of the yield series.")
    ] = TreasuryInterval.MONTHLY,
    maturity: Annotated[
        TreasuryMaturity, Query(description="Constant maturity of the security.")
    ] = TreasuryMaturity.Y10,
) -> IndicatorSeriesOut | Response:
    return await _series(
        get_spec("treasury-yield"),
        service,
        query,
        interval=interval.value,
        maturity=maturity.value,
    )


@router.get(
    "/federal-funds-rate",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Federal funds rate",
    description="Daily, weekly, or monthly effective federal funds rate.",
)
async def federal_funds_rate(
    service: ServiceDep,
    query: SeriesQueryDep,
    interval: Annotated[
        FederalFundsInterval, Query(description="Sampling frequency of the policy rate.")
    ] = FederalFundsInterval.MONTHLY,
) -> IndicatorSeriesOut | Response:
    return await _series(
        get_spec("federal-funds-rate"), service, query, interval=interval.value
    )


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------


@router.get(
    "/cpi",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Consumer Price Index",
    description="Monthly or semiannual CPI for all urban consumers.",
)
async def cpi(
    service: ServiceDep,
    query: SeriesQueryDep,
    interval: Annotated[
        CpiInterval, Query(description="Sampling frequency of the price index.")
    ] = CpiInterval.MONTHLY,
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("cpi"), service, query, interval=interval.value)


@router.get(
    "/inflation",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Inflation",
    description="Annual U.S. consumer-price inflation. Published annually only.",
)
async def inflation(service: ServiceDep, query: SeriesQueryDep) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("inflation"), service, query)


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------


@router.get(
    "/retail-sales",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Retail sales",
    description="Monthly advance retail sales for U.S. retail trade.",
)
async def retail_sales(
    service: ServiceDep, query: SeriesQueryDep
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("retail-sales"), service, query)


@router.get(
    "/durables",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Durable goods orders",
    description="Monthly manufacturers' new orders for durable goods.",
)
async def durables(service: ServiceDep, query: SeriesQueryDep) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("durables"), service, query)


# ---------------------------------------------------------------------------
# Labor
# ---------------------------------------------------------------------------


@router.get(
    "/unemployment",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Unemployment rate",
    description="Monthly U.S. unemployment rate, seasonally adjusted.",
)
async def unemployment(
    service: ServiceDep, query: SeriesQueryDep
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("unemployment"), service, query)


@router.get(
    "/nonfarm-payroll",
    response_model=IndicatorSeriesOut,
    responses={200: _CSV_RESPONSE_DOC, **_SERIES_RESPONSES},
    summary="Nonfarm payroll",
    description="Monthly total U.S. nonfarm payroll employment.",
)
async def nonfarm_payroll(
    service: ServiceDep, query: SeriesQueryDep
) -> IndicatorSeriesOut | Response:
    return await _series(get_spec("nonfarm-payroll"), service, query)
