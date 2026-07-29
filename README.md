# Economic Indicators Dashboard

A full-stack dashboard for the United States economic indicators published by
[Alpha Vantage](https://www.alphavantage.co/documentation/#economic-indicators):
a **FastAPI** backend that proxies every indicator behind a typed JSON contract,
and a **Next.js** dashboard that renders them.

The Alpha Vantage API key lives only in the backend process. It is attached to
outbound requests and stripped from every response, error body, and log line —
it never reaches the browser.

```
indicators-dashboard/
├── indicators_dashboard_backend/    FastAPI · Python 3.13 · Poetry
└── indicators_dashboard_frontend/   Next.js 16 · TypeScript · Tailwind · shadcn/ui
```

## Running it

Two terminals. The backend must be up first — the dashboard has no data source
of its own.

**1. Backend**

```bash
cd indicators_dashboard_backend
cp .env.example .env          # paste your key into ALPHA_VANTAGE_API_KEY
poetry install
poetry run uvicorn indicators_dashboard_backend.main:app --reload
```

→ API on <http://127.0.0.1:8000>, interactive docs at `/docs`.

**2. Frontend**

```bash
cd indicators_dashboard_frontend
cp .env.example .env.local    # defaults already point at localhost:8000
npm install
npm run dev
```

→ Dashboard on <http://localhost:3000>.

A free Alpha Vantage key takes about twenty seconds to claim at
<https://www.alphavantage.co/support/#api-key>.

## The indicators

All ten economic indicators in the Alpha Vantage documentation, each with the
optional parameters the upstream supports:

| Indicator | `function` | Selectable |
| --- | --- | --- |
| Real GDP | `REAL_GDP` | annual · quarterly |
| Real GDP per capita | `REAL_GDP_PER_CAPITA` | — |
| Treasury yield | `TREASURY_YIELD` | daily · weekly · monthly × 3M · 2Y · 5Y · 7Y · 10Y · 30Y |
| Federal funds rate | `FEDERAL_FUNDS_RATE` | daily · weekly · monthly |
| CPI | `CPI` | monthly · semiannual |
| Inflation | `INFLATION` | — |
| Retail sales | `RETAIL_SALES` | — |
| Durable goods orders | `DURABLES` | — |
| Unemployment rate | `UNEMPLOYMENT` | — |
| Nonfarm payroll | `NONFARM_PAYROLL` | — |

## What it does

**Overview.** A dense grid of metric cards — one per indicator, grouped by
output, prices, rates, labor, and demand. Each card carries the latest value,
the period-over-period change, the year-over-year change, and a sparkline. One
batched backend call fills the whole grid.

**Detail views.** Selecting any indicator opens the full series: an interactive
time-series chart with a crosshair readout, controls for the intervals and
maturities that indicator supports, preset time ranges, the complete historical
table beneath the chart, and a provenance panel showing exactly which upstream
parameters produced the data and when it was fetched. A CSV of the same series
downloads straight from the backend's passthrough.

**It degrades honestly.** The free Alpha Vantage tier allows 25 requests per
day, and signals exhaustion with an HTTP 200 body rather than a status code. The
backend detects that, caches aggressively — on disk as well as in memory, so a
restart does not re-spend the budget — and serves a cached copy when the
upstream refuses. The dashboard labels those figures **Cached** rather than
letting a stale number pass as current. A stopped backend renders the shell plus
an error naming the command that fixes it, not a blank page.

## Design

One tonal palette: a cool charcoal/slate base for the entire interface, with a
single restrained accent — steel blue — reserved for data. No gradients, no
emoji, no second hue. All icons come from lucide-react; every UI primitive is
shadcn/ui. Motion is limited to gentle fades, a barely-there scale on card
hover, and smooth chart transitions, and respects `prefers-reduced-motion`.

Charts are single-series by design: two muted tonal hues cannot be told apart
reliably, so comparisons are made by switching parameters rather than by
introducing a colour that would break the palette. Change figures encode
direction with an arrow and a sign as well as colour, and their tone reflects
what the indicator means — a rise in unemployment reads as negative, a rise in
payrolls as positive, a move in a Treasury yield as neither.

## Tests

```bash
cd indicators_dashboard_backend  && poetry run pytest   # 171 tests
cd indicators_dashboard_frontend && npm test            # 111 tests
```

Neither suite touches the network. The backend mocks the Alpha Vantage host with
`respx`, so running the tests costs nothing against the daily quota.

Both suites run in CI on every push and pull request — see
[`.github/workflows`](.github/workflows).

## Documentation

- [Backend README](indicators_dashboard_backend/README.md) — endpoints, response
  shape, error codes, caching, configuration.
- [Frontend README](indicators_dashboard_frontend/README.md) — stack, design
  rationale, data flow, resilience.
