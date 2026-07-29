/**
 * Client-side transforms applied to a series before it is drawn.
 *
 * The backend returns the complete history -- daily Treasury yields run to tens
 * of thousands of observations -- so the window and the point count are decided
 * here, where the chart's pixel width is known.
 */

import type {
  Frequency,
  Observation,
  ParameterSpec,
  SeriesQuery,
} from "./types";

/** The parameter set an indicator starts on: each parameter's own default. */
export function defaultParameterValues(
  parameters: ParameterSpec[],
): Record<string, string> {
  return Object.fromEntries(
    parameters.map((parameter) => [parameter.name, parameter.default]),
  );
}

/**
 * Build the backend query for a parameter set.
 *
 * Always requests ascending order: charts and tables both want oldest-first,
 * and asking for it here means neither has to re-sort. The server and the
 * client must produce an identical query for the same parameters, or the
 * client would re-fetch data the server already embedded.
 */
export function seriesQueryFor(values: Record<string, string>): SeriesQuery {
  return { ...values, order: "asc" };
}

/** A preset time window offered above the chart. */
export interface RangePreset {
  id: string;
  label: string;
  /** Full label for assistive technology. */
  description: string;
  /** Years of history, or `null` for the entire series. */
  years: number | null;
}

export const RANGE_PRESETS: RangePreset[] = [
  { id: "1y", label: "1Y", description: "Last year", years: 1 },
  { id: "5y", label: "5Y", description: "Last 5 years", years: 5 },
  { id: "10y", label: "10Y", description: "Last 10 years", years: 10 },
  { id: "25y", label: "25Y", description: "Last 25 years", years: 25 },
  { id: "max", label: "Max", description: "Full history", years: null },
];

export const DEFAULT_RANGE_ID = "10y";

/**
 * The presets worth offering for a given series.
 *
 * A preset earns its place only if it actually narrows the view: on a series
 * with three years of history, "10Y" and "25Y" would draw exactly the same
 * chart as "Max", and three buttons that do the same thing is worse than one.
 * "Max" is always offered as the canonical full view.
 */
export function usableRanges(data: Observation[]): RangePreset[] {
  if (data.length === 0) return RANGE_PRESETS;

  return RANGE_PRESETS.filter((preset) => {
    if (preset.years === null) return true;
    const windowed = sliceByYears(data, preset.years);
    return windowed.length >= 2 && windowed.length < data.length;
  });
}

/** Keep the observations within `years` of the most recent one. */
export function sliceByYears(data: Observation[], years: number | null): Observation[] {
  if (years === null || data.length === 0) return data;

  const last = data[data.length - 1];
  const cutoff = new Date(last.date);
  cutoff.setFullYear(cutoff.getFullYear() - years);
  const cutoffIso = cutoff.toISOString().slice(0, 10);

  return data.filter((point) => point.date >= cutoffIso);
}

export function sliceByRange(data: Observation[], rangeId: string): Observation[] {
  const preset = RANGE_PRESETS.find((candidate) => candidate.id === rangeId);
  return sliceByYears(data, preset?.years ?? null);
}

/**
 * Reduce a long series to at most `target` points for rendering.
 *
 * Buckets are collapsed to their extremes rather than to an average, so peaks
 * and troughs survive: a decimated chart must not flatten a spike that the
 * underlying data contains. The first and last observations are always kept so
 * the endpoints stay exact.
 */
export function decimate(data: Observation[], target = 900): Observation[] {
  if (data.length <= target) return data;

  const bucketSize = Math.ceil(data.length / (target / 2));
  const result: Observation[] = [];

  for (let start = 0; start < data.length; start += bucketSize) {
    const bucket = data.slice(start, start + bucketSize);
    const valued = bucket.filter((point) => point.value !== null);

    if (valued.length === 0) {
      result.push(bucket[0]);
      continue;
    }

    let lowest = valued[0];
    let highest = valued[0];
    for (const point of valued) {
      if ((point.value as number) < (lowest.value as number)) lowest = point;
      if ((point.value as number) > (highest.value as number)) highest = point;
    }

    // Emit in chronological order so the line never doubles back.
    if (lowest.date === highest.date) {
      result.push(lowest);
    } else if (lowest.date < highest.date) {
      result.push(lowest, highest);
    } else {
      result.push(highest, lowest);
    }
  }

  const last = data[data.length - 1];
  if (result[result.length - 1]?.date !== last.date) result.push(last);

  return result;
}

/** Padded y-domain that keeps a flat series off the top edge of the plot. */
export function valueDomain(data: Observation[]): [number, number] {
  const values = data
    .map((point) => point.value)
    .filter((value): value is number => value !== null);

  if (values.length === 0) return [0, 1];

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const pad = span === 0 ? Math.abs(max) * 0.1 || 1 : span * 0.08;

  // Series that live at or above zero should not imply negative territory.
  const lower = min >= 0 && min - pad < 0 ? 0 : min - pad;
  return [lower, max + pad];
}

/** Evenly spaced category ticks, always including the first and last points. */
export function pickTicks(data: Observation[], count = 6): string[] {
  if (data.length <= count) return data.map((point) => point.date);

  const step = (data.length - 1) / (count - 1);
  const ticks = new Set<string>();
  for (let index = 0; index < count; index += 1) {
    ticks.add(data[Math.round(index * step)].date);
  }
  return [...ticks];
}

/** Mean of the visible window, drawn as a reference line. */
export function windowMean(data: Observation[]): number | null {
  const values = data
    .map((point) => point.value)
    .filter((value): value is number => value !== null);
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

/** How many observations make up roughly one year at this cadence. */
export function observationsPerYear(frequency: Frequency): number {
  switch (frequency) {
    case "daily":
      return 252;
    case "weekly":
      return 52;
    case "monthly":
      return 12;
    case "quarterly":
      return 4;
    case "semiannual":
      return 2;
    default:
      return 1;
  }
}
