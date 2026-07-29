"""Health, service metadata, and cache administration endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from .. import __version__
from ..catalog import INDICATORS
from ..dependencies import CacheDep, SettingsDep
from ..schemas import CacheStatsOut, HealthOut, ServiceMetaOut

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Liveness probe",
    description="Cheap check that the process is up. Never contacts Alpha Vantage.",
)
async def health(settings: SettingsDep) -> HealthOut:
    return HealthOut(
        status="ok",
        version=__version__,
        api_key_configured=settings.has_api_key,
    )


meta_router = APIRouter(tags=["system"])


@meta_router.get(
    "/meta",
    response_model=ServiceMetaOut,
    summary="Service metadata and cache statistics",
    description=(
        "Operational detail for the dashboard footer and for debugging. "
        "Reports only whether an API key is configured -- never its value."
    ),
)
async def service_meta(settings: SettingsDep, cache: CacheDep) -> ServiceMetaOut:
    return ServiceMetaOut(
        name="indicators-dashboard-backend",
        version=__version__,
        upstream=settings.alpha_vantage_base_url,
        api_key_configured=settings.has_api_key,
        indicator_count=len(INDICATORS),
        api_prefix=settings.api_prefix,
        cache=CacheStatsOut(**cache.snapshot_stats()),
    )


@meta_router.get(
    "/cache",
    response_model=CacheStatsOut,
    summary="Cache statistics",
)
async def cache_stats(cache: CacheDep) -> CacheStatsOut:
    return CacheStatsOut(**cache.snapshot_stats())


@meta_router.delete(
    "/cache",
    summary="Clear the cached upstream responses",
    description=(
        "Drops every cached payload from memory and disk. The next request for "
        "each series will spend one of the 25 daily upstream calls."
    ),
)
async def clear_cache(
    cache: CacheDep,
    confirm: Annotated[
        bool,
        Query(description="Must be true. Guards against an accidental quota-burning clear."),
    ] = False,
) -> dict[str, object]:
    if not confirm:
        return {
            "cleared": False,
            "entries": len(cache),
            "message": "Pass ?confirm=true to clear the cache.",
        }
    removed = await cache.clear()
    return {"cleared": True, "entries_removed": removed}
