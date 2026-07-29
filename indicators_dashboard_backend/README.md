# Indicators Dashboard — Backend

A FastAPI service that proxies the [Alpha Vantage economic indicators](https://www.alphavantage.co/documentation/#economic-indicators)
behind a consistent, typed JSON contract. The Alpha Vantage API key lives only
in this process and is never exposed to a client.

## Quick start

```bash
cd indicators_dashboard_backend
cp .env.example .env          # then paste your key into ALPHA_VANTAGE_API_KEY
poetry install
poetry run uvicorn indicators_dashboard_backend.main:app --reload
```

- API root: <http://127.0.0.1:8000>
- Interactive docs: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

A free Alpha Vantage key is available at
<https://www.alphavantage.co/support/#api-key>.

## Endpoints

All indicator routes live under `/api/v1`.

### Indicators

| Route | Alpha Vantage `function` | Parameters |
| --- | --- | --- |
| `GET /indicators/real-gdp` | `REAL_GDP` | `interval` = `annual` (default) · `quarterly` |
| `GET /indicators/real-gdp-per-capita` | `REAL_GDP_PER_CAPITA` | — |
| `GET /indicators/treasury-yield` | `TREASURY_YIELD` | `interval` = `daily` · `weekly` · `monthly` (default)<br>`maturity` = `3month` · `2year` · `5year` · `7year` · `10year` (default) · `30year` |
| `GET /indicators/federal-funds-rate` | `FEDERAL_FUNDS_RATE` | `interval` = `daily` · `weekly` · `monthly` (default) |
| `GET /indicators/cpi` | `CPI` | `interval` = `monthly` (default) · `semiannual` |
| `GET /indicators/inflation` | `INFLATION` | — |
| `GET /indicators/retail-sales` | `RETAIL_SALES` | — |
| `GET /indicators/durables` | `DURABLES` | — |
| `GET /indicators/unemployment` | `UNEMPLOYMENT` | — |
| `GET /indicators/nonfarm-payroll` | `NONFARM_PAYROLL` | — |

Indicators that Alpha Vantage publishes at a single frequency take no
`interval`, and the parameter is **not** forwarded upstream for them.

### Catalog, overview, and system

| Route | Purpose |
| --- | --- |
| `GET /api/v1/indicators` | Static catalog: every indicator with its supported parameters, allowed values, and defaults. Contacts no upstream service. |
| `GET /api/v1/indicators/latest` | Latest value, period change, year-over-year change, and a sparkline for all ten indicators in one call. Failures are isolated per indicator. |
| `GET /api/v1/meta` | Service version and cache statistics. |
| `GET /api/v1/cache` · `DELETE /api/v1/cache?confirm=true` | Inspect or clear the response cache. |
| `GET /health` | Liveness probe. Also mounted at `/api/v1/health`. |

### Shared query parameters

Every series endpoint additionally accepts:

| Parameter | Default | Effect |
| --- | --- | --- |
| `limit` | — | Keep only the most recent *N* observations. |
| `start_date` / `end_date` | — | Inclusive `YYYY-MM-DD` bounds. |
| `order` | `desc` | `desc` (newest first) or `asc`. |
| `datatype` | `json` | `csv` streams Alpha Vantage's CSV file unchanged, as `text/csv`. |
| `refresh` | `false` | Bypass the cache and force a live upstream call. |

`limit`, `start_date`, `end_date`, and `order` are applied to the cached
payload, so using them never costs an upstream request.

## Response shape

Every indicator returns the same envelope, so a client renders any series with
one code path:

```jsonc
{
  "indicator": {
    "slug": "treasury-yield",
    "function": "TREASURY_YIELD",
    "name": "10-Year Treasury Constant Maturity Rate",  // as reported upstream
    "short_name": "Treasury Yield",
    "unit": "percent",
    "unit_short": "%",
    "category": "rates",
    "frequency": "monthly",
    "interval": "monthly",
    "maturity": "10year",
    "higher_is_better": null
  },
  "meta": {
    "source": "Alpha Vantage",
    "function": "TREASURY_YIELD",
    "parameters": { "function": "TREASURY_YIELD", "interval": "monthly", "maturity": "10year" },
    "order": "desc",
    "returned": 121,
    "total_available": 879,
    "fetched_at": "2026-07-29T12:07:11Z",
    "cached": true,
    "stale": false,          // true when served from cache after an upstream failure
    "cache_age_seconds": 312.4
  },
  "latest": {
    "date": "2026-06-01", "value": 4.47,
    "previous_date": "2026-05-01", "previous_value": 4.48,
    "change": -0.01, "change_percent": -0.2232,
    "year_ago_date": "2025-06-01", "year_ago_value": 4.38,
    "year_over_year_change": 0.09, "year_over_year_percent": 2.0548
  },
  "stats": { "count": 121, "minimum": 0.62, "maximum": 4.8, "mean": 2.81,
             "first_date": "2016-06-01", "last_date": "2026-06-01" },
  "data": [ { "date": "2026-06-01", "value": 4.47 }, "..." ]
}
```

Errors use one shape too:

```json
{ "error": { "code": "upstream_rate_limited", "message": "…", "details": { } } }
```

| Code | Status | Meaning |
| --- | --- | --- |
| `invalid_request` | 422 | A query parameter is not an allowed value. |
| `indicator_not_found` | 404 | Unknown indicator slug. |
| `upstream_rate_limited` | 429 | Alpha Vantage quota exhausted, with no cached copy to serve. |
| `upstream_invalid_request` | 502 | Alpha Vantage rejected the call. |
| `upstream_malformed_payload` | 502 | The response was not a time series. |
| `upstream_unavailable` | 503 | Timeout or transport failure. |
| `api_key_missing` | 500 | No `ALPHA_VANTAGE_API_KEY` configured. |

## What this adds over calling Alpha Vantage directly

**The key stays server-side.** It is attached to outbound requests only, and
stripped from every response body, error payload, and log line. A test asserts
this for both the success and the failure path.

**Errors are real errors.** Alpha Vantage returns HTTP 200 for rate limits,
invalid calls, and premium-only endpoints, signalling the problem with an
`Information`, `Note`, or `Error Message` field in the body. The status code
cannot be trusted, so the body is inspected and mapped onto distinct exceptions
— a client gets 429 for a quota problem and 502 for a bad call.

**Strict parameter validation.** Alpha Vantage silently substitutes its default
for an unrecognised value: `maturity=1month` quietly returns the 10-year series.
This API rejects it with 422 instead, so a chart can never be mislabelled.

**Quota protection.** The free tier allows **25 requests per day**. The service
therefore:

- caches successful responses for 6 hours by default, **on disk as well as in
  memory**, so a dev-server restart does not re-spend the budget;
- collapses concurrent identical requests into a single upstream call
  (single-flight), so a cold overview costs 10 requests rather than 10 × N;
- serves an expired cached copy — flagged `meta.stale` — when the upstream is
  unavailable or rate limited, for up to 14 days, so the dashboard keeps working
  after the budget runs out;
- serialises outbound calls with a ~1.1 s gap, as Alpha Vantage requests.

**Derived figures are computed once, server-side.** Period-over-period and
year-over-year changes ship with the payload. The year-ago match is found *by
date* rather than by counting back N rows, so gaps in daily series (holidays in
the Treasury data) do not skew the comparison.

**Gaps stay visible.** Alpha Vantage writes `"."` for a date with no
observation. Those become `null` rather than being dropped or coerced to zero,
so a chart shows a break instead of inventing a value.

## Configuration

Every setting is an environment variable, read from `.env`. See
[`.env.example`](.env.example) for the full annotated list. Only
`ALPHA_VANTAGE_API_KEY` is required.

## Tests

```bash
poetry run pytest          # 171 tests
poetry run pytest -q --tb=short
```

The suite never touches the network — `respx` mocks the Alpha Vantage host — so
it costs nothing against the daily quota and is deterministic. Coverage
includes:

- **`test_catalog.py`** — the catalog matches the published parameter surface
  exactly, and unsupported parameters are dropped rather than forwarded.
- **`test_cache.py`** — TTL, LRU eviction, single-flight under concurrency,
  stale-while-error including its grace boundary, disk persistence across a
  simulated restart, and recovery from a corrupt cache file.
- **`test_alpha_vantage.py`** — every HTTP-200 error body maps to the right
  exception, retries fire for 5xx but not 4xx, and the key never appears in an
  error payload.
- **`test_services.py`** — value/date parsing including `"."` placeholders,
  year-over-year matching across gaps, percent change against a negative or
  zero base, and window filtering.
- **`test_api.py`** — all ten endpoints forward the right parameters, the shared
  envelope, CSV passthrough, validation rejections, caching behaviour, overview
  failure isolation, and CORS.

## Layout

```
indicators_dashboard_backend/
├── main.py            application factory, error handlers, CORS, routers
├── config.py          settings, read from .env
├── catalog.py         the ten indicators and their parameter surface
├── schemas.py         the public JSON contract
├── alpha_vantage.py   HTTP client, upstream error mapping, throttle
├── cache.py           TTL + LRU + single-flight + stale-while-error + disk
├── services.py        normalisation and derived figures
├── errors.py          domain exceptions
├── dependencies.py    shared FastAPI dependencies
└── routers/
    ├── indicators.py  the ten indicator routes, catalog, overview
    └── system.py      health, meta, cache administration
```

Adding an indicator means adding one `IndicatorSpec` to `catalog.py` and one
route to `routers/indicators.py`; validation, the catalog endpoint, the
overview, and the frontend's controls all follow from the spec.
