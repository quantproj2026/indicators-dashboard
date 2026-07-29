# Indicators Dashboard — Frontend

A Next.js App Router dashboard for the United States economic indicators served
by the FastAPI backend in `../indicators_dashboard_backend`.

## Quick start

The backend must be running first — the dashboard has no data source of its own.

```bash
cd indicators_dashboard_backend
poetry run uvicorn indicators_dashboard_backend.main:app --reload
```

Then:

```bash
cd indicators_dashboard_frontend
cp .env.example .env.local     # defaults already point at localhost:8000
npm install
npm run dev
```

Open <http://localhost:3000>.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server (Turbopack). |
| `npm run build` | Production build, including a TypeScript pass. |
| `npm start` | Serve the production build. |
| `npm test` | Vitest suite (111 tests). |
| `npm run test:watch` | Vitest in watch mode. |
| `npm run typecheck` | `tsc --noEmit`. |
| `npm run lint` | ESLint. |

## Stack

- **Next.js 16** — App Router, Server Components, streaming via `loading.tsx`.
- **TypeScript** in strict mode; the backend contract is mirrored in
  `lib/types.ts` with no `any`.
- **Tailwind CSS v4** with the theme defined as CSS custom properties.
- **shadcn/ui** (base-vega style, Base UI primitives) for every UI primitive —
  card, select, toggle group, table, tooltip, badge, skeleton, separator,
  scroll area.
- **lucide-react** for every icon.
- **Recharts** for the time-series and sparkline charts.
- **Framer Motion** for entrance fades, card hover, and chart transitions only.

## Design

A **single tonal palette**: a cool charcoal/slate base carries the entire
interface, with exactly one accent — steel blue — reserved for data. There are
no gradients anywhere, no emoji, and no second hue. Depth comes from four flat
surface steps and hairline borders rather than shadow or colour.

The accent was picked against the real card surfaces and validated for the
lightness band, the chroma floor, and ≥ 3:1 contrast in both modes:

| | Accent | Surface |
| --- | --- | --- |
| Dark (default) | `#4b93c4` | `#191c21` |
| Light | `#1f6f9c` | `#ffffff` on a `#f7f8f9` plane |

Charts are deliberately **single-series**. Two muted tonal hues cannot be told
apart reliably — the pair fails colour-vision separation — so rather than
introduce a clashing second colour, comparisons are made by switching the
parameter controls. One series also means no legend is needed: the panel
heading already names what is plotted.

Change figures carry direction three ways — arrow glyph, explicit sign, and
colour — so meaning survives without colour vision. Their tone depends on the
indicator: a rise in unemployment is shown as negative, a rise in payrolls as
positive, and a move in a Treasury yield as neither, driven by the
`higher_is_better` flag from the backend catalog.

Motion is minimal and honours `prefers-reduced-motion`: an 8px fade-and-rise on
entry, a 1.006 scale on card hover, and a cross-fade when a chart swaps
datasets.

## Structure

```
app/
├── layout.tsx                  fonts, no-flash theme script, shell
├── globals.css                 the palette and base layer
├── page.tsx                    overview (Server Component)
├── loading.tsx / error.tsx / not-found.tsx
└── indicators/[slug]/
    ├── page.tsx                detail (Server Component)
    └── loading.tsx
components/
├── layout/                     shell, sidebar navigation, theme toggle
├── charts/                     series chart, sparkline
├── dashboard/                  overview grid, metric card, detail view,
│                               parameter controls, range selector,
│                               stat tiles, history table
├── common/                     delta, error state, stale badge
└── ui/                         shadcn primitives
hooks/use-series.ts             client-side series fetching
lib/
├── api.ts                      typed backend client
├── types.ts                    the backend contract
├── format.ts                   unit-aware value and date formatting
├── series.ts                   windowing, decimation, axis domains
├── indicator-meta.ts           icons, category order, offline fallback
└── motion.ts                   shared Framer Motion variants
```

## How data flows

1. A **Server Component** fetches from the backend during SSR, so the first
   paint already contains real values and charts. `app/page.tsx` calls
   `/api/v1/indicators/latest` once for all ten cards.
2. Changing an **interval** or **maturity** on a detail page re-fetches from the
   backend in the browser, without a navigation. Responses are memoised per
   parameter set for the life of the page, and an in-flight request is aborted
   when the selection changes again, so a slow response for an abandoned
   selection can never overwrite the current one.
3. Changing the **time range** costs nothing — it slices data already in hand.

`fetch` uses `cache: "no-store"`. The backend already caches upstream responses
for hours; a second cache here would only make the dashboard show data older
than the API is willing to serve.

## Resilience

The dashboard is built for the free Alpha Vantage tier's 25-requests-per-day
limit, so the degraded paths are first-class rather than afterthoughts:

- A **stopped backend** still renders the shell and navigation, with an inline
  error naming the `uvicorn` command that fixes it — not a blank page.
- A **missing API key** is reported as exactly that, naming the file to edit.
- An **exhausted quota** shows the indicators that are cached and marks only the
  failed ones; the overview flags itself `degraded` rather than disappearing.
- Data the backend served from cache after an upstream failure is labelled
  **Cached** on the card, so a number that has stopped updating never passes
  silently as current.
- **Gaps** in a series (`null` observations) render as breaks in the line and
  `--` in the table, never as zero.

## Performance

Long series are decimated before rendering — daily Treasury yields run to tens
of thousands of points. Buckets collapse to their **extremes**, not their
average, so a spike survives decimation; the first and last observations are
always kept exact.

## Tests

```bash
npm test
```

111 tests, covering:

- **`format.test.ts`** — unit-aware formatting: percentage points vs percent,
  currency rescaling (`23,850.44` billions renders as `$23.85T`), and local-time
  ISO date parsing so an observation never slips to the previous day.
- **`series.test.ts`** — windowing and decimation invariants, including that a
  spike survives decimation and that a non-negative series never gets a negative
  axis floor.
- **`api.test.ts`** — the client's error mapping, offline handling, and that no
  request it builds can carry a key.
- **`use-series.test.tsx`** — parameter switching: the loading state appears on
  the same render, previously seen parameters are served from memory without a
  request, a superseded request is aborted so it cannot win a race, and a forced
  refresh asks the backend to bypass its cache.
- **`components.test.tsx`** — the components that carry meaning: `Delta` tone
  selection, `ErrorState` explanations, `StatTiles`, and `HistoryTable`'s
  gap-skipping change arithmetic.
