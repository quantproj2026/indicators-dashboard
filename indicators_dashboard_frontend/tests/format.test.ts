import { describe, expect, it } from "vitest";

import {
  ascending,
  formatAxisDate,
  formatAxisValue,
  formatChange,
  formatDuration,
  formatObservationDate,
  formatPercent,
  formatValue,
  frequencyLabel,
  parameterValueDescription,
  parameterValueLabel,
  parseIsoDate,
  periodLabel,
  spansMultipleYears,
  unitKind,
} from "@/lib/format";

describe("unitKind", () => {
  it.each([
    ["percent", "percent"],
    ["billions of dollars", "currency"],
    ["chained 2012 dollars", "currency"],
    ["thousands of persons", "count"],
    ["index 1982-1984=100", "index"],
  ])("classifies %s", (unit, expected) => {
    expect(unitKind(unit)).toBe(expected);
  });
});

describe("formatValue", () => {
  it("renders percent units to two decimals with a sign-free suffix", () => {
    expect(formatValue(4.2, "percent")).toBe("4.20%");
  });

  it("rescales currency series to their true magnitude", () => {
    // Real GDP reports 23,850.44 *billions*, which is 23.85 trillion.
    expect(formatValue(23850.44, "billions of dollars")).toBe("$23.85T");
    expect(formatValue(672368, "millions of dollars")).toBe("$672.37B");
  });

  it("rescales counts the same way", () => {
    expect(formatValue(159830, "thousands of persons")).toBe("159.83M");
  });

  it("leaves index levels unscaled", () => {
    expect(formatValue(333.95, "index 1982-1984=100")).toBe("333.95");
  });

  it("renders exact figures when asked", () => {
    expect(formatValue(23850.44, "billions of dollars", { precise: true })).toBe(
      "$23,850,440,000,000",
    );
  });

  it("renders a placeholder for missing observations", () => {
    expect(formatValue(null, "percent")).toBe("--");
    expect(formatValue(undefined, "percent")).toBe("--");
    expect(formatValue(Number.NaN, "percent")).toBe("--");
  });
});

describe("formatChange", () => {
  it("labels percentage-point moves as pp, not percent", () => {
    // A rate going 4.2 -> 4.1 moved 0.1 percentage points, not 0.1 percent.
    expect(formatChange(-0.1, "percent")).toBe("-0.10 pp");
    expect(formatChange(0.25, "percent")).toBe("+0.25 pp");
  });

  it("signs currency changes and rescales them", () => {
    expect(formatChange(492.01, "billions of dollars")).toBe("+$492.01B");
  });

  it("marks a flat reading without a sign", () => {
    expect(formatChange(0, "percent")).toBe("0.00 pp");
  });

  it("returns a placeholder when there is no prior observation", () => {
    expect(formatChange(null, "percent")).toBe("--");
  });
});

describe("formatPercent", () => {
  it("signs gains but not losses (the minus already reads as one)", () => {
    expect(formatPercent(2.1063)).toBe("+2.11%");
    expect(formatPercent(-16.1663)).toBe("-16.17%");
  });

  it("can suppress the sign", () => {
    expect(formatPercent(2.1, { signed: false })).toBe("2.10%");
  });

  it("handles a missing figure", () => {
    expect(formatPercent(null)).toBe("--");
  });
});

describe("formatAxisValue", () => {
  it("keeps ticks short", () => {
    expect(formatAxisValue(4, "percent")).toBe("4%");
    expect(formatAxisValue(4.25, "percent")).toBe("4.3%");
    expect(formatAxisValue(23850, "billions of dollars")).toBe("23.9T");
  });
});

describe("date handling", () => {
  it("parses ISO dates in local time, not UTC", () => {
    // Parsing via `new Date('2026-06-01')` would land on May 31 west of GMT.
    const parsed = parseIsoDate("2026-06-01");
    expect(parsed.getFullYear()).toBe(2026);
    expect(parsed.getMonth()).toBe(5);
    expect(parsed.getDate()).toBe(1);
  });

  it.each([
    ["2026-06-01", "annual", "2026"],
    ["2026-04-01", "quarterly", "Q2 2026"],
    ["2026-08-01", "semiannual", "H2 2026"],
    ["2026-06-01", "monthly", "Jun 2026"],
  ] as const)("labels %s at %s cadence", (iso, frequency, expected) => {
    expect(formatObservationDate(iso, frequency)).toBe(expected);
  });

  it("drops the year from axis ticks inside a single year", () => {
    expect(formatAxisDate("2026-06-01", "monthly", false)).toBe("Jun");
    expect(formatAxisDate("2026-06-01", "monthly", true)).toBe("Jun 26");
  });

  it("formats cache ages compactly", () => {
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(300)).toBe("5m");
    expect(formatDuration(7200)).toBe("2h");
    expect(formatDuration(200000)).toBe("2d");
  });
});

describe("labels", () => {
  it("abbreviates maturities for narrow controls", () => {
    expect(parameterValueLabel("maturity", "3month")).toBe("3M");
    expect(parameterValueLabel("maturity", "30year")).toBe("30Y");
  });

  it("spells maturities out where there is room", () => {
    expect(parameterValueDescription("maturity", "3month")).toBe("3 months");
    expect(parameterValueDescription("maturity", "10year")).toBe("10 years");
  });

  it("title-cases interval values", () => {
    expect(parameterValueLabel("interval", "semiannual")).toBe("Semiannual");
  });

  it("names the comparison period per cadence", () => {
    expect(periodLabel("monthly")).toBe("prior month");
    expect(periodLabel("quarterly")).toBe("prior quarter");
    expect(periodLabel("annual")).toBe("prior year");
  });

  it("labels frequencies", () => {
    expect(frequencyLabel("semiannual")).toBe("Semiannual");
  });
});

describe("series helpers", () => {
  const data = [
    { date: "2026-03-01", value: 3 },
    { date: "2026-01-01", value: 1 },
    { date: "2026-02-01", value: 2 },
  ];

  it("sorts oldest first without mutating the input", () => {
    const sorted = ascending(data);
    expect(sorted.map((point) => point.value)).toEqual([1, 2, 3]);
    expect(data[0].date).toBe("2026-03-01");
  });

  it("detects a window that crosses a year boundary", () => {
    expect(spansMultipleYears(data)).toBe(false);
    expect(
      spansMultipleYears([...data, { date: "2025-12-01", value: 0 }]),
    ).toBe(true);
  });
});
