/**
 * Value and date formatting.
 *
 * Economic series arrive in wildly different units -- billions of dollars,
 * index points, percent, thousands of persons -- so formatting is driven by the
 * unit string the backend passes through from Alpha Vantage rather than
 * hard-coded per indicator.
 */

import type { Frequency, Observation } from "./types";

type UnitKind = "percent" | "currency" | "count" | "index";

/** Classify a unit string into the handful of shapes that format differently. */
export function unitKind(unit: string): UnitKind {
  const u = unit.toLowerCase();
  if (u.includes("percent")) return "percent";
  if (u.includes("dollar")) return "currency";
  if (u.includes("person") || u.includes("thousand of")) return "count";
  return "index";
}

/** Multiplier implied by the unit, so `$B` and `$M` can share one formatter. */
function unitScale(unit: string): number {
  const u = unit.toLowerCase();
  if (u.includes("billion")) return 1e9;
  if (u.includes("million")) return 1e6;
  if (u.includes("thousand")) return 1e3;
  return 1;
}

const COMPACT_STEPS: Array<[number, string]> = [
  [1e12, "T"],
  [1e9, "B"],
  [1e6, "M"],
  [1e3, "K"],
];

/** `1284` -> `1.28K`, `4.2e12` -> `4.20T`. */
function compact(value: number, fractionDigits = 2): string {
  const magnitude = Math.abs(value);
  for (const [threshold, suffix] of COMPACT_STEPS) {
    if (magnitude >= threshold) {
      return `${(value / threshold).toFixed(fractionDigits)}${suffix}`;
    }
  }
  return value.toFixed(magnitude < 10 ? fractionDigits : Math.min(fractionDigits, 1));
}

/**
 * The headline representation of a value, in the units the series reports.
 *
 * Currency series are rescaled to their true magnitude first, so real GDP in
 * "billions of dollars" reads as `$30.4T` rather than `30,400.0`.
 */
export function formatValue(
  value: number | null | undefined,
  unit: string,
  options: { precise?: boolean } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";

  const kind = unitKind(unit);

  if (kind === "percent") {
    return `${value.toFixed(2)}%`;
  }

  if (kind === "currency") {
    const absolute = value * unitScale(unit);
    return options.precise
      ? `$${absolute.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
      : `$${compact(absolute)}`;
  }

  if (kind === "count") {
    const absolute = value * unitScale(unit);
    return options.precise
      ? absolute.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : compact(absolute);
  }

  return value.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  });
}

/** Axis ticks: terse, no currency symbol, never wider than a few characters. */
export function formatAxisValue(value: number, unit: string): string {
  const kind = unitKind(unit);
  if (kind === "percent") {
    return Number.isInteger(value) ? `${value}%` : `${value.toFixed(1)}%`;
  }
  if (kind === "currency" || kind === "count") {
    return compact(value * unitScale(unit), 1);
  }
  return Math.abs(value) >= 1000
    ? value.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : value.toFixed(Math.abs(value) < 10 ? 1 : 0);
}

/** A signed absolute change, in the same units as the value. */
export function formatChange(change: number | null | undefined, unit: string): string {
  if (change === null || change === undefined || Number.isNaN(change)) return "--";
  const sign = change > 0 ? "+" : change < 0 ? "-" : "";
  const kind = unitKind(unit);
  const magnitude = Math.abs(change);

  if (kind === "percent") return `${sign}${magnitude.toFixed(2)} pp`;
  if (kind === "currency") return `${sign}$${compact(magnitude * unitScale(unit))}`;
  if (kind === "count") return `${sign}${compact(magnitude * unitScale(unit))}`;
  return `${sign}${magnitude.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

export function formatPercent(
  percent: number | null | undefined,
  options: { signed?: boolean; digits?: number } = {},
): string {
  const { signed = true, digits = 2 } = options;
  if (percent === null || percent === undefined || Number.isNaN(percent)) return "--";
  const sign = signed && percent > 0 ? "+" : "";
  return `${sign}${percent.toFixed(digits)}%`;
}

/** Parse an ISO `YYYY-MM-DD` as a local date, avoiding UTC off-by-one shifts. */
export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
}

/** Label an observation the way its release cadence is normally quoted. */
export function formatObservationDate(iso: string, frequency: Frequency): string {
  const date = parseIsoDate(iso);

  switch (frequency) {
    case "annual":
      return String(date.getFullYear());
    case "quarterly":
      return `Q${Math.floor(date.getMonth() / 3) + 1} ${date.getFullYear()}`;
    case "semiannual":
      return `${date.getMonth() < 6 ? "H1" : "H2"} ${date.getFullYear()}`;
    case "monthly":
      return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    default:
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
  }
}

/** Compact axis tick label -- drops the year where the window makes it obvious. */
export function formatAxisDate(
  iso: string,
  frequency: Frequency,
  spansMultipleYears: boolean,
): string {
  const date = parseIsoDate(iso);

  if (frequency === "annual") return String(date.getFullYear());
  if (frequency === "quarterly") {
    return spansMultipleYears
      ? `${String(date.getFullYear()).slice(2)} Q${Math.floor(date.getMonth() / 3) + 1}`
      : `Q${Math.floor(date.getMonth() / 3) + 1}`;
  }
  if (!spansMultipleYears) {
    return date.toLocaleDateString("en-US", { month: "short" });
  }
  if (frequency === "daily" || frequency === "weekly") {
    return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  }
  return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

export function formatFullDate(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** "3 minutes ago" for cache ages and last-refreshed stamps. */
export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";

  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return "just now";

  const formatter = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  if (seconds < 3600) return formatter.format(-Math.round(seconds / 60), "minute");
  if (seconds < 86400) return formatter.format(-Math.round(seconds / 3600), "hour");
  if (seconds < 2592000) return formatter.format(-Math.round(seconds / 86400), "day");
  return formatter.format(-Math.round(seconds / 2592000), "month");
}

export function formatDuration(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)}s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

const FREQUENCY_LABELS: Record<Frequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  semiannual: "Semiannual",
  annual: "Annual",
};

export function frequencyLabel(frequency: Frequency): string {
  return FREQUENCY_LABELS[frequency] ?? frequency;
}

/** The period a change is measured over, for labelling a delta. */
export function periodLabel(frequency: Frequency): string {
  switch (frequency) {
    case "daily":
      return "prior day";
    case "weekly":
      return "prior week";
    case "monthly":
      return "prior month";
    case "quarterly":
      return "prior quarter";
    case "semiannual":
      return "prior half";
    default:
      return "prior year";
  }
}

/** Human label for a parameter value, e.g. `3month` -> `3M`, `annual` -> `Annual`. */
export function parameterValueLabel(name: string, value: string): string {
  if (name === "maturity") {
    const match = /^(\d+)(month|year)$/.exec(value);
    if (match) return `${match[1]}${match[2] === "month" ? "M" : "Y"}`;
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Longer form of the same, for select menus where width is not scarce. */
export function parameterValueDescription(name: string, value: string): string {
  if (name === "maturity") {
    const match = /^(\d+)(month|year)$/.exec(value);
    if (match) {
      const plural = Number(match[1]) === 1 ? "" : "s";
      return `${match[1]} ${match[2]}${plural}`;
    }
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Observations sorted oldest-first, which is what every chart wants. */
export function ascending(data: Observation[]): Observation[] {
  return [...data].sort((a, b) => a.date.localeCompare(b.date));
}

/** True when the window crosses a calendar-year boundary. */
export function spansMultipleYears(data: Observation[]): boolean {
  if (data.length < 2) return false;
  const years = new Set(data.map((point) => point.date.slice(0, 4)));
  return years.size > 1;
}
