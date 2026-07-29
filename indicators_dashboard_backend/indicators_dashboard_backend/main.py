"""Application factory, wiring, and error handling.

Run with::

    poetry run uvicorn indicators_dashboard_backend.main:app --reload

Interactive documentation is served at ``/docs``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .alpha_vantage import AlphaVantageClient
from .cache import TTLCache
from .catalog import INDICATORS
from .config import Settings, get_settings
from .errors import IndicatorNotFoundError, UpstreamError
from .routers import indicators as indicators_router
from .routers import system as system_router
from .services import IndicatorService

logger = logging.getLogger(__name__)

# Starlette renamed this constant and deprecated the old name; reading the old one
# even as a getattr default emits a warning, so probe before touching it.
_UNPROCESSABLE: int = (
    status.HTTP_422_UNPROCESSABLE_CONTENT
    if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT")
    else 422
)

DESCRIPTION = """
A typed REST facade over the [Alpha Vantage economic indicators](
https://www.alphavantage.co/documentation/#economic-indicators).

**What this service adds over calling Alpha Vantage directly**

* **The API key stays server-side.** It is attached to the outbound request and
  never appears in a response body, an error payload, or a log line.
* **One consistent envelope** for all ten indicators -- `indicator`, `meta`,
  `latest`, `stats`, `data` -- so a client renders any series with one code path.
* **Derived headline figures**: period-over-period and year-over-year change are
  computed server-side, with year-ago matching done by date so gaps in daily
  series do not skew the result.
* **Quota protection.** The free Alpha Vantage tier allows 25 requests per day
  and signals exhaustion with HTTP 200 plus an `Information` field. Responses are
  cached (on disk as well as in memory), identical concurrent requests are
  collapsed into one upstream call, and a cached copy is served -- flagged
  `meta.stale` -- when the upstream is unavailable.
* **Strict parameter validation.** Alpha Vantage silently substitutes its default
  for an unrecognised `maturity`; this API rejects it with 422 instead.
"""

TAGS_METADATA = [
    {
        "name": "indicators",
        "description": "The ten economic indicators, plus the catalog and overview endpoints.",
    },
    {"name": "system", "description": "Health, service metadata, and cache administration."},
]


def _build_state(app: FastAPI, settings: Settings) -> None:
    cache = TTLCache(
        ttl_seconds=settings.cache_ttl_seconds,
        max_entries=settings.cache_max_entries,
        stale_grace_seconds=settings.cache_stale_grace_seconds,
        persist_dir=settings.cache_dir if settings.cache_persist else None,
    )
    client = AlphaVantageClient(settings)
    app.state.settings = settings
    app.state.cache = cache
    app.state.client = client
    app.state.service = IndicatorService(client, cache)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if not settings.has_api_key:
        logger.warning(
            "ALPHA_VANTAGE_API_KEY is not set. Indicator endpoints will return 500 "
            "until a key is added to indicators_dashboard_backend/.env."
        )
    logger.info(
        "Indicators Dashboard API %s ready: %d indicators, cache TTL %ds%s",
        __version__,
        len(INDICATORS),
        settings.cache_ttl_seconds,
        f", persisted to {settings.cache_dir}" if settings.cache_persist else "",
    )
    try:
        yield
    finally:
        await app.state.client.aclose()


def jsonable_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """Reduce pydantic's error list to a JSON-safe, client-friendly form."""
    reduced: list[dict[str, object]] = []
    for error in exc.errors():
        reduced.append(
            {
                "field": ".".join(str(part) for part in error.get("loc", ())[1:]) or "request",
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "value_error"),
            }
        )
    return reduced


def _register_error_handlers(app: FastAPI) -> None:
    """Render every failure with the same ``{"error": {...}}`` shape."""

    @app.exception_handler(UpstreamError)
    async def _upstream(_: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(IndicatorNotFoundError)
    async def _not_found(_: Request, exc: IndicatorNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=_UNPROCESSABLE,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "One or more query parameters are invalid.",
                    "details": {"errors": jsonable_errors(exc)},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                }
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the detail, return none of it: internals must not leak to clients.
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The server encountered an unexpected error.",
                }
            },
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully wired application instance."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Indicators Dashboard API",
        description=DESCRIPTION,
        version=__version__,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
        license_info={"name": "MIT"},
    )
    _build_state(app, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,
    )

    _register_error_handlers(app)

    # Health lives at the root so container probes need no prefix knowledge,
    # and again under the API prefix for clients that only know the prefix.
    app.include_router(system_router.router)
    app.include_router(system_router.router, prefix=settings.api_prefix, include_in_schema=False)
    app.include_router(system_router.meta_router, prefix=settings.api_prefix)
    app.include_router(indicators_router.router, prefix=settings.api_prefix)

    @app.get("/", tags=["system"], summary="Service banner")
    async def root() -> dict[str, object]:
        return {
            "name": "Indicators Dashboard API",
            "version": __version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "indicators": f"{settings.api_prefix}/indicators",
            "overview": f"{settings.api_prefix}/indicators/latest",
            "upstream": "Alpha Vantage economic indicators",
        }

    return app


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

#: Module-level instance for ``uvicorn indicators_dashboard_backend.main:app``.
app = create_app()
