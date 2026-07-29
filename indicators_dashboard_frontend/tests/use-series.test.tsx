import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSeries } from "@/hooks/use-series";
import { ApiError } from "@/lib/api";
import { seriesQueryFor } from "@/lib/series";
import type { IndicatorSeries, SeriesQuery } from "@/lib/types";

const getSeries = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getSeries };
});

function series(label: string): IndicatorSeries {
  return {
    indicator: {
      slug: "treasury-yield",
      function: "TREASURY_YIELD",
      name: label,
      short_name: "Treasury Yield",
      unit: "percent",
      unit_short: "%",
      category: "rates",
      frequency: "monthly",
      interval: "monthly",
      maturity: "10year",
      higher_is_better: null,
    },
    meta: {
      source: "Alpha Vantage",
      source_url: "",
      function: "TREASURY_YIELD",
      parameters: {},
      order: "asc",
      returned: 1,
      total_available: 1,
      fetched_at: new Date().toISOString(),
      cached: false,
      stale: false,
      cache_age_seconds: 0,
    },
    latest: null,
    stats: {
      count: 1,
      minimum: 1,
      maximum: 1,
      mean: 1,
      first_date: "2026-01-01",
      last_date: "2026-01-01",
    },
    data: [{ date: "2026-01-01", value: 1 }],
  };
}

const INITIAL_QUERY: SeriesQuery = seriesQueryFor({
  interval: "monthly",
  maturity: "10year",
});

function renderSeries(initialQuery = INITIAL_QUERY, initial = series("10-year")) {
  return renderHook(
    ({ query }: { query: SeriesQuery }) =>
      useSeries("treasury-yield", query, initial, initialQuery),
    { initialProps: { query: initialQuery } },
  );
}

beforeEach(() => {
  getSeries.mockReset();
});

describe("useSeries", () => {
  it("uses the server-rendered data without a fetch", async () => {
    const { result } = renderSeries();

    expect(result.current.series?.indicator.name).toBe("10-year");
    expect(result.current.loading).toBe(false);
    await waitFor(() => expect(getSeries).not.toHaveBeenCalled());
  });

  it("fetches when the parameters change", async () => {
    getSeries.mockResolvedValue(series("2-year"));
    const { result, rerender } = renderSeries();

    rerender({ query: seriesQueryFor({ interval: "monthly", maturity: "2year" }) });

    // The loading state appears on the same render as the parameter change,
    // not one render later.
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.series?.indicator.name).toBe("2-year"));
    expect(result.current.loading).toBe(false);
    expect(getSeries).toHaveBeenCalledTimes(1);
    expect(getSeries.mock.calls[0][1]).toMatchObject({ maturity: "2year" });
  });

  it("serves a previously seen parameter set from memory", async () => {
    getSeries.mockResolvedValue(series("2-year"));
    const { result, rerender } = renderSeries();

    const twoYear = seriesQueryFor({ interval: "monthly", maturity: "2year" });
    rerender({ query: twoYear });
    await waitFor(() => expect(result.current.series?.indicator.name).toBe("2-year"));

    // Back to the original: instant, and no second request.
    rerender({ query: INITIAL_QUERY });
    expect(result.current.series?.indicator.name).toBe("10-year");
    expect(result.current.loading).toBe(false);

    // ...and forward again, still cached.
    rerender({ query: twoYear });
    expect(result.current.series?.indicator.name).toBe("2-year");
    expect(getSeries).toHaveBeenCalledTimes(1);
  });

  it("surfaces a backend error for the current parameters", async () => {
    getSeries.mockRejectedValue(
      new ApiError("Daily limit reached.", {
        status: 429,
        code: "upstream_rate_limited",
      }),
    );

    const { result, rerender } = renderSeries();
    rerender({ query: seriesQueryFor({ interval: "daily", maturity: "10year" }) });

    await waitFor(() => expect(result.current.error?.code).toBe("upstream_rate_limited"));
    expect(result.current.loading).toBe(false);
  });

  it("clears a stale error once different parameters load", async () => {
    getSeries.mockRejectedValueOnce(
      new ApiError("boom", { status: 503, code: "upstream_unavailable" }),
    );

    const { result, rerender } = renderSeries();

    rerender({ query: seriesQueryFor({ interval: "daily", maturity: "10year" }) });
    await waitFor(() => expect(result.current.error).not.toBeNull());

    // The error belonged to the daily query; returning to a cached one drops it.
    rerender({ query: INITIAL_QUERY });
    expect(result.current.error).toBeNull();
    expect(result.current.series?.indicator.name).toBe("10-year");
  });

  it("asks the backend to bypass its cache on a forced refresh", async () => {
    getSeries.mockResolvedValue(series("fresh"));
    const { result } = renderSeries();

    await act(async () => {
      result.current.refresh({ force: true });
    });

    await waitFor(() => expect(result.current.series?.indicator.name).toBe("fresh"));
    expect(getSeries).toHaveBeenCalledTimes(1);
    expect(getSeries.mock.calls[0][1]).toMatchObject({ refresh: true });
  });

  it("does not refetch on a plain refresh when the data is memoised", async () => {
    const { result } = renderSeries();

    await act(async () => {
      result.current.refresh();
    });

    expect(getSeries).not.toHaveBeenCalled();
    expect(result.current.series?.indicator.name).toBe("10-year");
  });

  it("aborts a request that a newer parameter change supersedes", async () => {
    const signals: AbortSignal[] = [];
    getSeries.mockImplementation(
      (_slug: string, _query: SeriesQuery, signal?: AbortSignal) => {
        if (signal) signals.push(signal);
        return new Promise(() => {}); // never settles
      },
    );

    const { rerender } = renderSeries();

    rerender({ query: seriesQueryFor({ interval: "daily", maturity: "10year" }) });
    rerender({ query: seriesQueryFor({ interval: "weekly", maturity: "10year" }) });

    await waitFor(() => expect(signals.length).toBe(2));
    // The abandoned request is cancelled, so its response can never win a race
    // against the selection the user is actually looking at.
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it("starts in a loading state when there is no server-rendered data", async () => {
    getSeries.mockResolvedValue(series("first"));

    const { result } = renderHook(() =>
      useSeries("cpi", INITIAL_QUERY, null, INITIAL_QUERY),
    );

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.series?.indicator.name).toBe("first"));
  });
});
