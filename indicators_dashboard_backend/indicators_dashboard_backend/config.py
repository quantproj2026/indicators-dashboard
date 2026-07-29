"""Application settings, loaded from the environment and the local ``.env`` file."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# <repo>/indicators_dashboard_backend/ -- the directory holding .env and pyproject.toml.
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden with an environment variable of the same name
    (case-insensitive). ``ALPHA_VANTAGE_API_KEY`` is the only required one and is
    read from ``indicators_dashboard_backend/.env``.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Upstream -----------------------------------------------------------
    alpha_vantage_api_key: str = Field(
        default="",
        description="Alpha Vantage API key. Never leaves the backend process.",
    )
    alpha_vantage_base_url: str = Field(
        default="https://www.alphavantage.co/query",
        description="Alpha Vantage query endpoint.",
    )
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Retries for transport errors and 5xx responses (not for rate limits).",
    )
    retry_backoff_seconds: float = Field(default=0.75, ge=0)

    # -- Upstream politeness -------------------------------------------------
    # The free Alpha Vantage tier allows 25 requests/day and asks for no more
    # than ~1 request/second. We serialise outbound calls and space them out.
    min_seconds_between_upstream_calls: float = Field(default=1.1, ge=0)
    max_concurrent_upstream_calls: int = Field(default=1, ge=1, le=16)

    # -- Cache ---------------------------------------------------------------
    cache_ttl_seconds: int = Field(
        default=6 * 60 * 60,
        ge=0,
        description=(
            "How long a successful upstream response stays fresh. Economic series "
            "update monthly/quarterly, so a long TTL costs nothing and protects the "
            "25 requests/day free-tier budget."
        ),
    )
    cache_max_entries: int = Field(default=512, ge=1)
    cache_stale_grace_seconds: int = Field(
        default=14 * 24 * 60 * 60,
        ge=0,
        description=(
            "How long an expired entry may still be served when the upstream is "
            "unavailable or rate limited. Set to 0 to disable stale-while-error."
        ),
    )
    cache_persist: bool = Field(
        default=True,
        description="Persist the cache to disk so restarts do not burn the daily quota.",
    )
    cache_dir: Path = Field(default=PROJECT_ROOT / ".cache")

    # -- HTTP API ------------------------------------------------------------
    api_prefix: str = Field(default="/api/v1")
    # `NoDecode` is load-bearing. Without it pydantic-settings treats a
    # list-typed field as "complex" and runs `json.loads` on the raw environment
    # value *inside the env source*, before any validator on this class gets a
    # look. An ordinary `CORS_ORIGINS=https://app.example.com` would then abort
    # the process at import time with a JSONDecodeError. NoDecode hands the raw
    # string to `_split_origins` below instead.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Comma-separated list of allowed browser origins.",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept ``a,b``, a single origin, or a JSON array.

        Because of ``NoDecode`` above, parsing the JSON form is this method's
        job -- pydantic-settings no longer does it.
        """
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return []

        if stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "CORS_ORIGINS looks like a JSON array but could not be parsed. "
                    "A comma-separated list is easier and also accepted, e.g. "
                    "https://app.example.com,https://www.example.com"
                ) from exc

        return [origin.strip() for origin in stripped.split(",") if origin.strip()]

    @field_validator("api_prefix")
    @classmethod
    def _normalise_prefix(cls, value: str) -> str:
        value = "/" + value.strip("/")
        return "" if value == "/" else value

    @property
    def has_api_key(self) -> bool:
        return bool(self.alpha_vantage_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
