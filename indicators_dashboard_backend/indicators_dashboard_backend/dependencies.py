"""FastAPI dependencies: shared singletons and the query parameters every
indicator endpoint accepts on top of the upstream's own."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, Query, Request

from .alpha_vantage import AlphaVantageClient
from .cache import TTLCache
from .catalog import DataType, SortOrder
from .config import Settings, get_settings
from .services import IndicatorService


def get_app_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    return settings if settings is not None else get_settings()


def get_cache(request: Request) -> TTLCache:
    return request.app.state.cache


def get_client(request: Request) -> AlphaVantageClient:
    return request.app.state.client


def get_service(request: Request) -> IndicatorService:
    return request.app.state.service


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CacheDep = Annotated[TTLCache, Depends(get_cache)]
ServiceDep = Annotated[IndicatorService, Depends(get_service)]


@dataclass(slots=True)
class SeriesQuery:
    """Presentation options applied after the upstream response is fetched.

    These are additions on top of the Alpha Vantage parameter set. They only
    affect how the cached payload is sliced, so using them never costs an
    upstream request.
    """

    limit: int | None
    start_date: date | None
    end_date: date | None
    order: SortOrder
    datatype: DataType
    refresh: bool


def series_query(
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=20_000,
            description="Keep only the most recent N observations after date filtering.",
        ),
    ] = None,
    start_date: Annotated[
        date | None,
        Query(description="Drop observations before this date (inclusive, YYYY-MM-DD)."),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Drop observations after this date (inclusive, YYYY-MM-DD)."),
    ] = None,
    order: Annotated[
        SortOrder,
        Query(description="Order of `data`: newest first (`desc`) or oldest first (`asc`)."),
    ] = SortOrder.DESC,
    datatype: Annotated[
        DataType,
        Query(
            description=(
                "Upstream `datatype`. `json` returns the standard envelope; "
                "`csv` streams Alpha Vantage's CSV file unchanged."
            )
        ),
    ] = DataType.JSON,
    refresh: Annotated[
        bool,
        Query(
            description=(
                "Bypass the backend cache and force a live upstream call. "
                "Use sparingly: the free tier allows 25 requests per day."
            )
        ),
    ] = False,
) -> SeriesQuery:
    return SeriesQuery(
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        order=order,
        datatype=datatype,
        refresh=refresh,
    )


SeriesQueryDep = Annotated[SeriesQuery, Depends(series_query)]
