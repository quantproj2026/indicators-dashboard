/**
 * The wire contract exposed by the FastAPI backend.
 *
 * These mirror `indicators_dashboard_backend/schemas.py` one-for-one. The
 * backend is the single source of truth for shape; if a field is added there,
 * add it here rather than reaching into `any`.
 */

export type IndicatorSlug =
  | "real-gdp"
  | "real-gdp-per-capita"
  | "treasury-yield"
  | "federal-funds-rate"
  | "cpi"
  | "inflation"
  | "retail-sales"
  | "durables"
  | "unemployment"
  | "nonfarm-payroll";

export type Category = "output" | "rates" | "prices" | "labor" | "demand";

export type Frequency =
  | "daily"
  | "weekly"
  | "monthly"
  | "quarterly"
  | "semiannual"
  | "annual";

export type SortOrder = "asc" | "desc";

export interface Observation {
  /** ISO date, `YYYY-MM-DD`. */
  date: string;
  /** `null` where the source reported no observation for that date. */
  value: number | null;
}

export interface ParameterSpec {
  name: "interval" | "maturity";
  allowed: string[];
  default: string;
  description: string;
}

export interface IndicatorSummary {
  slug: IndicatorSlug;
  /** The Alpha Vantage `function` this endpoint proxies. */
  function: string;
  name: string;
  short_name: string;
  description: string;
  unit: string;
  unit_short: string;
  category: Category;
  frequency: Frequency;
  higher_is_better: boolean | null;
  default_window: number;
  parameters: ParameterSpec[];
  path: string;
  source_note: string;
}

export interface IndicatorIdentity {
  slug: IndicatorSlug;
  function: string;
  name: string;
  short_name: string;
  unit: string;
  unit_short: string;
  category: Category;
  frequency: Frequency;
  interval: string | null;
  maturity: string | null;
  higher_is_better: boolean | null;
}

export interface Latest {
  date: string;
  value: number;
  previous_date: string | null;
  previous_value: number | null;
  change: number | null;
  change_percent: number | null;
  year_ago_date: string | null;
  year_ago_value: number | null;
  year_over_year_change: number | null;
  year_over_year_percent: number | null;
}

export interface SeriesStats {
  count: number;
  minimum: number | null;
  maximum: number | null;
  mean: number | null;
  first_date: string | null;
  last_date: string | null;
}

export interface SeriesMeta {
  source: string;
  source_url: string;
  function: string;
  parameters: Record<string, string>;
  order: SortOrder;
  returned: number;
  total_available: number;
  fetched_at: string;
  cached: boolean;
  /** True when a cached copy was served because the upstream was unavailable. */
  stale: boolean;
  cache_age_seconds: number;
}

export interface IndicatorSeries {
  indicator: IndicatorIdentity;
  meta: SeriesMeta;
  latest: Latest | null;
  stats: SeriesStats;
  data: Observation[];
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface IndicatorSnapshot {
  indicator: IndicatorIdentity;
  latest: Latest | null;
  sparkline: Observation[];
  meta: SeriesMeta | null;
  /** Set when this one indicator failed; the rest of the overview is unaffected. */
  error: ErrorDetail | null;
}

export interface Overview {
  generated_at: string;
  count: number;
  /** True when at least one indicator failed to load. */
  degraded: boolean;
  indicators: IndicatorSnapshot[];
}

export interface CacheStats {
  entries: number;
  hits: number;
  misses: number;
  stale_hits: number;
  evictions: number;
  hit_rate: number;
  ttl_seconds: number;
  stale_grace_seconds: number;
  persisted: boolean;
}

export interface ServiceMeta {
  name: string;
  version: string;
  upstream: string;
  api_key_configured: boolean;
  indicator_count: number;
  api_prefix: string;
  cache: CacheStats;
}

/** Query parameters accepted by every series endpoint. */
export interface SeriesQuery {
  interval?: string;
  maturity?: string;
  limit?: number;
  start_date?: string;
  end_date?: string;
  order?: SortOrder;
  refresh?: boolean;
}
