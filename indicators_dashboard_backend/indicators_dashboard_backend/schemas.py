"""Pydantic models describing the public JSON contract.

Every indicator endpoint returns the same envelope -- ``indicator`` (what the
series is), ``meta`` (how it was fetched), ``latest`` (pre-computed headline
figures), and ``data`` (the observations) -- so the frontend can render any
indicator with a single code path.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .catalog import Category, Frequency, IndicatorSpec, SortOrder


class ObservationOut(BaseModel):
    """A single point of the time series."""

    model_config = ConfigDict(json_schema_extra={"example": {"date": "2026-06-01", "value": 4.2}})

    date: date
    value: float | None = Field(
        default=None,
        description="Observed value, or null when the source reported no data (`.`).",
    )


class ParameterOut(BaseModel):
    """An optional query parameter supported by an indicator."""

    name: str
    allowed: list[str]
    default: str
    description: str


class IndicatorSummaryOut(BaseModel):
    """Catalog entry: static metadata, no observations."""

    slug: str
    function: str = Field(description="The Alpha Vantage `function` this endpoint proxies.")
    name: str
    short_name: str
    description: str
    unit: str
    unit_short: str
    category: Category
    frequency: Frequency = Field(description="Release cadence under the default parameters.")
    higher_is_better: bool | None = Field(
        default=None,
        description="Whether a rising value is generally read as favourable. Null when ambiguous.",
    )
    default_window: int = Field(description="Suggested number of observations for a default chart.")
    parameters: list[ParameterOut]
    path: str = Field(description="Path of this indicator's series endpoint.")
    source_note: str

    @classmethod
    def from_spec(cls, spec: IndicatorSpec, *, api_prefix: str) -> "IndicatorSummaryOut":
        return cls(
            slug=spec.slug,
            function=spec.function,
            name=spec.name,
            short_name=spec.short_name,
            description=spec.description,
            unit=spec.unit,
            unit_short=spec.unit_short,
            category=spec.category,
            frequency=spec.default_frequency,
            higher_is_better=spec.higher_is_better,
            default_window=spec.default_window,
            parameters=[
                ParameterOut(
                    name=p.name,
                    allowed=list(p.allowed),
                    default=p.default,
                    description=p.description,
                )
                for p in spec.parameters
            ],
            path=f"{api_prefix}/indicators/{spec.slug}",
            source_note=spec.source_note,
        )


class IndicatorIdentityOut(BaseModel):
    """Which series this payload holds, including resolved parameters."""

    slug: str
    function: str
    name: str = Field(description="Series name as reported by Alpha Vantage.")
    short_name: str
    unit: str
    unit_short: str
    category: Category
    frequency: Frequency
    interval: str | None = Field(default=None, description="Resolved `interval`, if supported.")
    maturity: str | None = Field(default=None, description="Resolved `maturity`, if supported.")
    higher_is_better: bool | None = None


class LatestOut(BaseModel):
    """Headline figures derived from the tail of the series."""

    date: date
    value: float
    previous_date: date | None = None
    previous_value: float | None = None
    change: float | None = Field(
        default=None, description="Absolute change against the previous observation."
    )
    change_percent: float | None = Field(
        default=None, description="Percent change against the previous observation."
    )
    year_ago_date: date | None = None
    year_ago_value: float | None = None
    year_over_year_change: float | None = None
    year_over_year_percent: float | None = None


class SeriesStatsOut(BaseModel):
    """Descriptive statistics over the returned window."""

    count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    first_date: date | None = None
    last_date: date | None = None


class SeriesMetaOut(BaseModel):
    """How this payload was produced."""

    source: str = "Alpha Vantage"
    source_url: str = "https://www.alphavantage.co/documentation/#economic-indicators"
    function: str
    parameters: dict[str, str] = Field(
        description="Exact parameters forwarded upstream, minus the API key."
    )
    order: SortOrder
    returned: int = Field(description="Observations in `data` after filtering and limiting.")
    total_available: int = Field(description="Observations returned by the upstream before filtering.")
    fetched_at: datetime = Field(description="When the upstream response was retrieved (UTC).")
    cached: bool = Field(description="True when served from the backend cache.")
    stale: bool = Field(
        default=False,
        description="True when a cached copy was served because the upstream was unavailable.",
    )
    cache_age_seconds: float = Field(default=0.0, ge=0)


class IndicatorSeriesOut(BaseModel):
    """The full response returned by every indicator endpoint."""

    indicator: IndicatorIdentityOut
    meta: SeriesMetaOut
    latest: LatestOut | None = None
    stats: SeriesStatsOut
    data: list[ObservationOut]


class IndicatorSnapshotOut(BaseModel):
    """One indicator's headline figures, for the dashboard overview grid."""

    indicator: IndicatorIdentityOut
    latest: LatestOut | None = None
    #: Small tail of the series so cards can draw a sparkline without a second call.
    sparkline: list[ObservationOut] = Field(default_factory=list)
    meta: SeriesMetaOut | None = None
    error: "ErrorDetail | None" = Field(
        default=None,
        description="Set when this indicator could not be fetched; other entries are unaffected.",
    )


class OverviewOut(BaseModel):
    """Latest values for every indicator in the catalog."""

    generated_at: datetime
    count: int
    degraded: bool = Field(
        description="True when at least one indicator failed to load.",
    )
    indicators: list[IndicatorSnapshotOut]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    """The body returned for every non-2xx response."""

    error: ErrorDetail


class CacheStatsOut(BaseModel):
    entries: int
    hits: int
    misses: int
    stale_hits: int
    evictions: int
    hit_rate: float
    ttl_seconds: int
    stale_grace_seconds: int
    persisted: bool


class ServiceMetaOut(BaseModel):
    """Operational metadata, useful for the dashboard footer and for debugging."""

    name: str
    version: str
    upstream: str
    api_key_configured: bool = Field(
        description="Whether a key is present. The key itself is never exposed."
    )
    indicator_count: int
    api_prefix: str
    cache: CacheStatsOut


class HealthOut(BaseModel):
    status: str
    version: str
    api_key_configured: bool


IndicatorSnapshotOut.model_rebuild()
