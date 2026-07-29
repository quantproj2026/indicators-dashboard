"use client";

import { useEffect, useState } from "react";

import { ApiError, getSeries } from "@/lib/api";
import type { IndicatorSeries, IndicatorSlug, SeriesQuery } from "@/lib/types";

export interface UseSeriesState {
  series: IndicatorSeries | null;
  loading: boolean;
  error: { code: string; message: string } | null;
  /** Re-fetch. `force` also bypasses the backend's own cache. */
  refresh: (options?: { force?: boolean }) => void;
}

interface Outcome {
  key: string;
  series: IndicatorSeries | null;
  error: { code: string; message: string } | null;
}

function queryKey(slug: string, query: SeriesQuery): string {
  return `${slug}?${JSON.stringify(query)}`;
}

/**
 * Loads one indicator's series, re-fetching when its parameters change.
 *
 * The first render is seeded with data the Server Component already fetched, so
 * the chart is populated in the initial HTML and only later parameter changes
 * cost a round trip. Responses are memoised per parameter set for the life of
 * the page, which makes flipping back to a previously viewed maturity instant
 * and costs the backend nothing.
 *
 * Everything the render needs is *derived* rather than mirrored into state: the
 * series is whatever the memo holds for the current key, and `loading` is
 * simply "no data and no error yet". State is written only from asynchronous
 * callbacks, so changing a parameter shows the loading state on the very same
 * render rather than one render later.
 *
 * In-flight requests are aborted when the parameters change again, so a slow
 * response for an abandoned selection can never overwrite the current one.
 */
export function useSeries(
  slug: IndicatorSlug,
  query: SeriesQuery,
  initial: IndicatorSeries | null,
  initialQuery: SeriesQuery,
): UseSeriesState {
  const key = queryKey(slug, query);

  // Held in state, not a ref, so it can legally be read during render. The map
  // identity is stable for the life of the component; only its contents change.
  // `initial` comes from the server render and cannot change without a remount,
  // so seeding it once in the initialiser is sufficient.
  const [cache] = useState(() => {
    const store = new Map<string, IndicatorSeries>();
    if (initial) store.set(queryKey(slug, initialQuery), initial);
    return store;
  });

  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [attempt, setAttempt] = useState(0);
  /** The key, if any, whose next fetch should also bypass the backend cache. */
  const [forcedKey, setForcedKey] = useState<string | null>(null);

  const forThisKey = outcome?.key === key ? outcome : null;
  const series = cache.get(key) ?? forThisKey?.series ?? null;
  const error = forThisKey?.error ?? null;
  const loading = series === null && error === null;

  // Not memoised: it is only ever passed to click handlers, so a fresh identity
  // each render costs nothing, and hand-written deps here would have to name the
  // state setters explicitly to satisfy the compiler.
  function refresh(options?: { force?: boolean }) {
    if (options?.force) {
      cache.delete(key);
      setForcedKey(key);
    }
    setOutcome(null);
    setAttempt((current) => current + 1);
  }

  useEffect(() => {
    const force = forcedKey === key;
    if (cache.has(key) && !force) return;

    const controller = new AbortController();
    let active = true;

    getSeries(slug, force ? { ...query, refresh: true } : query, controller.signal)
      .then((result) => {
        if (!active) return;
        cache.set(key, result);
        setOutcome({ key, series: result, error: null });
      })
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setOutcome({
          key,
          series: null,
          error:
            cause instanceof ApiError
              ? { code: cause.code, message: cause.message }
              : {
                  code: "unknown_error",
                  message: "Something went wrong loading this series.",
                },
        });
      })
      .finally(() => {
        if (active && force) setForcedKey(null);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // `query` is captured through `key`, which is its stable serialisation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, slug, cache, attempt, forcedKey]);

  return { series, loading, error, refresh };
}
