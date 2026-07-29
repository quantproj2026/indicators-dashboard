/**
 * Client for the FastAPI backend.
 *
 * The Alpha Vantage key lives only in the backend process, so every request --
 * from a Server Component during SSR or from the browser after a control
 * changes -- goes through this service. Nothing here knows an API key exists.
 */

import type {
  IndicatorSeries,
  IndicatorSlug,
  IndicatorSummary,
  Overview,
  SeriesQuery,
  ServiceMeta,
} from "./types";

const API_PREFIX = "/api/v1";

const DEFAULT_SERVER_BASE = "http://127.0.0.1:8000";
const DEFAULT_BROWSER_BASE = "http://localhost:8000";

/**
 * Resolve the backend origin.
 *
 * Server-side rendering can talk to the backend over a private address
 * (`API_BASE_URL`), while the browser needs a publicly reachable one
 * (`NEXT_PUBLIC_API_BASE_URL`). In local development both are localhost.
 */
export function apiBaseUrl(): string {
  const configured =
    typeof window === "undefined"
      ? process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL
      : process.env.NEXT_PUBLIC_API_BASE_URL;

  const fallback =
    typeof window === "undefined" ? DEFAULT_SERVER_BASE : DEFAULT_BROWSER_BASE;

  return (configured ?? fallback).replace(/\/+$/, "");
}

/** A failure from the backend, carrying its machine-readable error code. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown> | null;

  constructor(
    message: string,
    options: {
      status: number;
      code: string;
      details?: Record<string, unknown> | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }

  /** True when the backend could not be reached at all. */
  get isOffline(): boolean {
    return this.status === 0;
  }

  /** True when the Alpha Vantage daily budget is exhausted. */
  get isRateLimited(): boolean {
    return this.status === 429 || this.code === "upstream_rate_limited";
  }

  get isMissingKey(): boolean {
    return this.code === "api_key_missing";
  }
}

function buildQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

interface RequestOptions {
  params?: Record<string, unknown>;
  signal?: AbortSignal;
  /**
   * Next.js fetch caching. Defaults to `no-store`: the backend already caches
   * upstream responses for hours, so a second cache here would only make the
   * dashboard show older data than the API is willing to serve.
   */
  cache?: RequestCache;
}

export async function apiFetch<T>(
  path: string,
  { params, signal, cache = "no-store" }: RequestOptions = {},
): Promise<T> {
  const url = `${apiBaseUrl()}${API_PREFIX}${path}${buildQuery(params)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      cache,
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(
      `Cannot reach the indicators API at ${apiBaseUrl()}. Is the FastAPI backend running?`,
      { status: 0, code: "backend_unreachable" },
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)
      ?.error;
    throw new ApiError(error?.message ?? `Request failed with status ${response.status}.`, {
      status: response.status,
      code: error?.code ?? `http_${response.status}`,
      details: error?.details ?? null,
    });
  }

  return (await response.json()) as T;
}

/** Static catalog of every indicator and the parameters it supports. */
export function getCatalog(signal?: AbortSignal): Promise<IndicatorSummary[]> {
  return apiFetch<IndicatorSummary[]>("/indicators", { signal });
}

/** Latest value, changes, and a sparkline for every indicator, in one call. */
export function getOverview(signal?: AbortSignal): Promise<Overview> {
  return apiFetch<Overview>("/indicators/latest", { signal });
}

/** Full time series for one indicator. */
export function getSeries(
  slug: IndicatorSlug,
  query: SeriesQuery = {},
  signal?: AbortSignal,
): Promise<IndicatorSeries> {
  return apiFetch<IndicatorSeries>(`/indicators/${slug}`, {
    params: query as Record<string, unknown>,
    signal,
  });
}

/** Backend version and cache statistics. */
export function getServiceMeta(signal?: AbortSignal): Promise<ServiceMeta> {
  return apiFetch<ServiceMeta>("/meta", { signal });
}

/** Direct link to the backend's CSV passthrough for a series. */
export function csvDownloadUrl(slug: IndicatorSlug, query: SeriesQuery = {}): string {
  const params = buildQuery({ ...query, datatype: "csv" });
  return `${apiBaseUrl()}${API_PREFIX}/indicators/${slug}${params}`;
}

export const API_DOCS_URL = () => `${apiBaseUrl()}/docs`;
