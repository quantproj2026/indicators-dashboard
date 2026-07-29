"""The catalog of Alpha Vantage economic indicators exposed by this API.

Mirrors https://www.alphavantage.co/documentation/#economic-indicators -- one
:class:`IndicatorSpec` per ``function``, describing which optional parameters the
upstream accepts, their allowed values, and their defaults. Everything else in
the backend (routing, validation, OpenAPI metadata, the frontend catalog
endpoint) is derived from this module, so adding an indicator means adding one
entry here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RealGdpInterval(StrEnum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class TreasuryInterval(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class FederalFundsInterval(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CpiInterval(StrEnum):
    MONTHLY = "monthly"
    SEMIANNUAL = "semiannual"


class TreasuryMaturity(StrEnum):
    M3 = "3month"
    Y2 = "2year"
    Y5 = "5year"
    Y7 = "7year"
    Y10 = "10year"
    Y30 = "30year"


class DataType(StrEnum):
    """Upstream ``datatype`` parameter: JSON objects or a CSV file."""

    JSON = "json"
    CSV = "csv"


class SortOrder(StrEnum):
    """Ordering of the returned observations. Not an upstream parameter."""

    DESC = "desc"
    ASC = "asc"


class Category(StrEnum):
    """Grouping used by the dashboard to lay out the overview grid."""

    OUTPUT = "output"
    RATES = "rates"
    PRICES = "prices"
    LABOR = "labor"
    DEMAND = "demand"


class Frequency(StrEnum):
    """Native release cadence of the series, used for labelling and YoY maths."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


#: How many observations make up one year, per frequency. Used for YoY change.
OBSERVATIONS_PER_YEAR: Mapping[Frequency, int] = MappingProxyType(
    {
        Frequency.DAILY: 252,
        Frequency.WEEKLY: 52,
        Frequency.MONTHLY: 12,
        Frequency.QUARTERLY: 4,
        Frequency.SEMIANNUAL: 2,
        Frequency.ANNUAL: 1,
    }
)


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One optional query parameter accepted by an indicator."""

    name: str
    allowed: tuple[str, ...]
    default: str
    description: str


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Everything the backend knows about a single economic indicator."""

    slug: str
    function: str
    name: str
    short_name: str
    description: str
    unit: str
    unit_short: str
    category: Category
    #: Frequency when queried with the default parameters.
    default_frequency: Frequency
    #: Maps each ``interval`` value to the resulting release frequency.
    frequency_by_interval: Mapping[str, Frequency] = field(default_factory=dict)
    interval: ParameterSpec | None = None
    maturity: ParameterSpec | None = None
    #: A rise in this series is generally read as good news for the economy.
    higher_is_better: bool | None = None
    #: Sensible number of observations for the dashboard's default chart window.
    default_window: int = 120
    source_note: str = ""

    @property
    def parameters(self) -> tuple[ParameterSpec, ...]:
        return tuple(p for p in (self.interval, self.maturity) if p is not None)

    def frequency_for(self, interval: str | None) -> Frequency:
        if interval is None:
            return self.default_frequency
        return self.frequency_by_interval.get(interval, self.default_frequency)

    def upstream_params(
        self, *, interval: str | None = None, maturity: str | None = None
    ) -> dict[str, str]:
        """Build the ``function``/``interval``/``maturity`` triple for the upstream call.

        Parameters the indicator does not support are dropped rather than passed
        through, because Alpha Vantage silently ignores unknown values (a bad
        ``maturity`` quietly returns the 10-year series) and that would poison
        the cache with mislabelled data.
        """
        params: dict[str, str] = {"function": self.function}
        if self.interval is not None:
            params["interval"] = interval or self.interval.default
        if self.maturity is not None:
            params["maturity"] = maturity or self.maturity.default
        return params


_REAL_GDP = IndicatorSpec(
    slug="real-gdp",
    function="REAL_GDP",
    name="Real Gross Domestic Product",
    short_name="Real GDP",
    description=(
        "Inflation-adjusted value of all goods and services produced in the United "
        "States, the broadest single measure of economic output."
    ),
    unit="billions of dollars",
    unit_short="$B",
    category=Category.OUTPUT,
    default_frequency=Frequency.ANNUAL,
    frequency_by_interval={
        "annual": Frequency.ANNUAL,
        "quarterly": Frequency.QUARTERLY,
    },
    interval=ParameterSpec(
        name="interval",
        allowed=tuple(v.value for v in RealGdpInterval),
        default=RealGdpInterval.ANNUAL.value,
        description="Sampling frequency of the GDP series.",
    ),
    higher_is_better=True,
    default_window=60,
    source_note="U.S. Bureau of Economic Analysis, retrieved from FRED.",
)

_REAL_GDP_PER_CAPITA = IndicatorSpec(
    slug="real-gdp-per-capita",
    function="REAL_GDP_PER_CAPITA",
    name="Real Gross Domestic Product per Capita",
    short_name="Real GDP / Capita",
    description=(
        "Quarterly real GDP divided by population, in chained 2012 dollars -- a "
        "proxy for average material living standards."
    ),
    unit="chained 2012 dollars",
    unit_short="$",
    category=Category.OUTPUT,
    default_frequency=Frequency.QUARTERLY,
    higher_is_better=True,
    default_window=80,
    source_note="U.S. Bureau of Economic Analysis, retrieved from FRED.",
)

_TREASURY_YIELD = IndicatorSpec(
    slug="treasury-yield",
    function="TREASURY_YIELD",
    name="Treasury Yield",
    short_name="Treasury Yield",
    description=(
        "Daily, weekly, or monthly yield on U.S. Treasury securities at a fixed "
        "constant maturity, quoted on an investment basis."
    ),
    unit="percent",
    unit_short="%",
    category=Category.RATES,
    default_frequency=Frequency.MONTHLY,
    frequency_by_interval={
        "daily": Frequency.DAILY,
        "weekly": Frequency.WEEKLY,
        "monthly": Frequency.MONTHLY,
    },
    interval=ParameterSpec(
        name="interval",
        allowed=tuple(v.value for v in TreasuryInterval),
        default=TreasuryInterval.MONTHLY.value,
        description="Sampling frequency of the yield series.",
    ),
    maturity=ParameterSpec(
        name="maturity",
        allowed=tuple(v.value for v in TreasuryMaturity),
        default=TreasuryMaturity.Y10.value,
        description="Constant maturity of the Treasury security.",
    ),
    default_window=240,
    source_note="Board of Governors of the Federal Reserve System, retrieved from FRED.",
)

_FEDERAL_FUNDS_RATE = IndicatorSpec(
    slug="federal-funds-rate",
    function="FEDERAL_FUNDS_RATE",
    name="Effective Federal Funds Rate",
    short_name="Fed Funds Rate",
    description=(
        "The interest rate at which depository institutions lend reserve balances "
        "overnight -- the Federal Reserve's primary policy rate."
    ),
    unit="percent",
    unit_short="%",
    category=Category.RATES,
    default_frequency=Frequency.MONTHLY,
    frequency_by_interval={
        "daily": Frequency.DAILY,
        "weekly": Frequency.WEEKLY,
        "monthly": Frequency.MONTHLY,
    },
    interval=ParameterSpec(
        name="interval",
        allowed=tuple(v.value for v in FederalFundsInterval),
        default=FederalFundsInterval.MONTHLY.value,
        description="Sampling frequency of the policy-rate series.",
    ),
    default_window=240,
    source_note="Board of Governors of the Federal Reserve System, retrieved from FRED.",
)

_CPI = IndicatorSpec(
    slug="cpi",
    function="CPI",
    name="Consumer Price Index for all Urban Consumers",
    short_name="CPI",
    description=(
        "Index of the average price paid by urban consumers for a market basket of "
        "goods and services. The headline inflation gauge."
    ),
    unit="index 1982-1984=100",
    unit_short="idx",
    category=Category.PRICES,
    default_frequency=Frequency.MONTHLY,
    frequency_by_interval={
        "monthly": Frequency.MONTHLY,
        "semiannual": Frequency.SEMIANNUAL,
    },
    interval=ParameterSpec(
        name="interval",
        allowed=tuple(v.value for v in CpiInterval),
        default=CpiInterval.MONTHLY.value,
        description="Sampling frequency of the price index.",
    ),
    default_window=180,
    source_note="U.S. Bureau of Labor Statistics, retrieved from FRED.",
)

_INFLATION = IndicatorSpec(
    slug="inflation",
    function="INFLATION",
    name="Inflation - US Consumer Prices",
    short_name="Inflation",
    description=(
        "Annual percentage change in U.S. consumer prices, the year-over-year "
        "counterpart to the CPI level series."
    ),
    unit="percent",
    unit_short="%",
    category=Category.PRICES,
    default_frequency=Frequency.ANNUAL,
    higher_is_better=False,
    default_window=60,
    source_note="World Bank / U.S. Bureau of Labor Statistics, retrieved from FRED.",
)

_RETAIL_SALES = IndicatorSpec(
    slug="retail-sales",
    function="RETAIL_SALES",
    name="Advance Retail Sales: Retail Trade",
    short_name="Retail Sales",
    description=(
        "Monthly advance estimate of receipts at U.S. retail and food-service "
        "firms, the earliest read on household demand."
    ),
    unit="millions of dollars",
    unit_short="$M",
    category=Category.DEMAND,
    default_frequency=Frequency.MONTHLY,
    higher_is_better=True,
    default_window=180,
    source_note="U.S. Census Bureau, retrieved from FRED.",
)

_DURABLES = IndicatorSpec(
    slug="durables",
    function="DURABLES",
    name="Manufacturers' New Orders: Durable Goods",
    short_name="Durable Goods",
    description=(
        "New orders placed with manufacturers for goods expected to last three or "
        "more years -- a forward-looking read on capital spending."
    ),
    unit="millions of dollars",
    unit_short="$M",
    category=Category.DEMAND,
    default_frequency=Frequency.MONTHLY,
    higher_is_better=True,
    default_window=180,
    source_note="U.S. Census Bureau, retrieved from FRED.",
)

_UNEMPLOYMENT = IndicatorSpec(
    slug="unemployment",
    function="UNEMPLOYMENT",
    name="Unemployment Rate",
    short_name="Unemployment",
    description=(
        "Share of the civilian labor force that is jobless and actively seeking "
        "work, seasonally adjusted."
    ),
    unit="percent",
    unit_short="%",
    category=Category.LABOR,
    default_frequency=Frequency.MONTHLY,
    higher_is_better=False,
    default_window=180,
    source_note="U.S. Bureau of Labor Statistics, retrieved from FRED.",
)

_NONFARM_PAYROLL = IndicatorSpec(
    slug="nonfarm-payroll",
    function="NONFARM_PAYROLL",
    name="Total Nonfarm Payroll",
    short_name="Nonfarm Payroll",
    description=(
        "Total number of U.S. workers excluding farm employees, private household "
        "staff, and non-profit employees. The headline monthly jobs number."
    ),
    unit="thousands of persons",
    unit_short="K",
    category=Category.LABOR,
    default_frequency=Frequency.MONTHLY,
    higher_is_better=True,
    default_window=180,
    source_note="U.S. Bureau of Labor Statistics, retrieved from FRED.",
)


#: Registry keyed by URL slug, in the order the dashboard displays them.
INDICATORS: Mapping[str, IndicatorSpec] = MappingProxyType(
    {
        spec.slug: spec
        for spec in (
            _REAL_GDP,
            _REAL_GDP_PER_CAPITA,
            _TREASURY_YIELD,
            _FEDERAL_FUNDS_RATE,
            _CPI,
            _INFLATION,
            _RETAIL_SALES,
            _DURABLES,
            _UNEMPLOYMENT,
            _NONFARM_PAYROLL,
        )
    }
)

#: Secondary index by Alpha Vantage ``function`` name.
INDICATORS_BY_FUNCTION: Mapping[str, IndicatorSpec] = MappingProxyType(
    {spec.function: spec for spec in INDICATORS.values()}
)

SLUGS: tuple[str, ...] = tuple(INDICATORS)


def get_spec(slug: str) -> IndicatorSpec:
    """Look up an indicator by slug.

    Raises:
        IndicatorNotFoundError: if the slug is not in the catalog.
    """
    from .errors import IndicatorNotFoundError  # local import: avoids a cycle

    try:
        return INDICATORS[slug]
    except KeyError:
        raise IndicatorNotFoundError(slug, list(SLUGS)) from None
