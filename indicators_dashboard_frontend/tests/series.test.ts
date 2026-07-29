import { describe, expect, it } from "vitest";

import {
  DEFAULT_RANGE_ID,
  decimate,
  defaultParameterValues,
  observationsPerYear,
  pickTicks,
  seriesQueryFor,
  sliceByRange,
  sliceByYears,
  usableRanges,
  valueDomain,
  windowMean,
} from "@/lib/series";
import type { Observation, ParameterSpec } from "@/lib/types";

function monthly(count: number, from = "2026-06-01"): Observation[] {
  const end = new Date(from);
  const points: Observation[] = [];
  for (let index = count - 1; index >= 0; index -= 1) {
    const date = new Date(end);
    date.setMonth(date.getMonth() - index);
    points.push({ date: date.toISOString().slice(0, 10), value: index });
  }
  return points;
}

describe("sliceByYears", () => {
  it("keeps observations within the window of the latest point", () => {
    const data = monthly(60);
    expect(sliceByYears(data, 1).length).toBeLessThanOrEqual(13);
    expect(sliceByYears(data, 1).length).toBeGreaterThanOrEqual(12);
  });

  it("measures from the last observation, not from today", () => {
    // A series that stopped in 2019 must still show its final year.
    const stale = monthly(36, "2019-12-01");
    expect(sliceByYears(stale, 1).length).toBeGreaterThan(0);
  });

  it("returns everything for the max range", () => {
    const data = monthly(24);
    expect(sliceByYears(data, null)).toHaveLength(24);
    expect(sliceByRange(data, "max")).toHaveLength(24);
  });

  it("survives an empty series", () => {
    expect(sliceByYears([], 5)).toEqual([]);
  });
});

describe("usableRanges", () => {
  it("hides ranges that would draw the same chart as Max", () => {
    // Six months of data: 1Y, 5Y, 10Y and 25Y all show everything, so only
    // the canonical full view is worth a button.
    const ids = usableRanges(monthly(6)).map((range) => range.id);
    expect(ids).toEqual(["max"]);
  });

  it("keeps a preset that genuinely narrows the view", () => {
    // Three years: 1Y is a real subset, wider presets are not.
    const ids = usableRanges(monthly(36)).map((range) => range.id);
    expect(ids).toEqual(["1y", "max"]);
  });

  it("offers every range for a long series", () => {
    const ids = usableRanges(monthly(400)).map((range) => range.id);
    expect(ids).toEqual(["1y", "5y", "10y", "25y", "max"]);
  });

  it("always offers at least one range", () => {
    expect(usableRanges([{ date: "2026-01-01", value: 1 }]).length).toBeGreaterThan(0);
    expect(usableRanges([]).length).toBeGreaterThan(0);
  });
});

describe("decimate", () => {
  it("leaves short series untouched", () => {
    const data = monthly(100);
    expect(decimate(data, 900)).toBe(data);
  });

  it("reduces a long series below the target", () => {
    const data = Array.from({ length: 15000 }, (_, index) => ({
      date: `2000-01-01`,
      value: index,
    }));
    expect(decimate(data, 900).length).toBeLessThanOrEqual(950);
  });

  it("preserves extremes rather than averaging them away", () => {
    // A single spike in the middle must survive decimation.
    const data = Array.from({ length: 5000 }, (_, index) => ({
      date: String(index).padStart(10, "0"),
      value: index === 2500 ? 9999 : 1,
    }));
    const reduced = decimate(data, 200);
    expect(reduced.some((point) => point.value === 9999)).toBe(true);
  });

  it("keeps the final observation exact", () => {
    const data = Array.from({ length: 4000 }, (_, index) => ({
      date: String(index).padStart(10, "0"),
      value: index,
    }));
    const reduced = decimate(data, 300);
    expect(reduced[reduced.length - 1]).toEqual(data[data.length - 1]);
  });

  it("emits points in chronological order", () => {
    const data = Array.from({ length: 3000 }, (_, index) => ({
      date: String(index).padStart(10, "0"),
      value: Math.sin(index / 40) * 100,
    }));
    const reduced = decimate(data, 200);
    const dates = reduced.map((point) => point.date);
    expect([...dates].sort()).toEqual(dates);
  });
});

describe("valueDomain", () => {
  it("pads the range so marks clear the plot edges", () => {
    const [low, high] = valueDomain([
      { date: "a", value: 10 },
      { date: "b", value: 20 },
    ]);
    expect(low).toBeLessThan(10);
    expect(high).toBeGreaterThan(20);
  });

  it("does not imply negative territory for a non-negative series", () => {
    // Padding would push the floor below zero, which would suggest the rate
    // had been negative. Clamp to zero instead.
    const [low] = valueDomain([
      { date: "a", value: 0.02 },
      { date: "b", value: 1 },
    ]);
    expect(low).toBe(0);
  });

  it("still pads normally when the floor stays positive", () => {
    const [low] = valueDomain([
      { date: "a", value: 10 },
      { date: "b", value: 12 },
    ]);
    expect(low).toBeGreaterThan(0);
    expect(low).toBeLessThan(10);
  });

  it("gives a flat series room to breathe", () => {
    const [low, high] = valueDomain([
      { date: "a", value: 5 },
      { date: "b", value: 5 },
    ]);
    expect(high).toBeGreaterThan(low);
  });

  it("falls back for an empty series", () => {
    expect(valueDomain([])).toEqual([0, 1]);
  });
});

describe("pickTicks", () => {
  it("always includes the first and last observation", () => {
    const data = monthly(120);
    const ticks = pickTicks(data, 6);
    expect(ticks).toContain(data[0].date);
    expect(ticks).toContain(data[data.length - 1].date);
    expect(ticks.length).toBeLessThanOrEqual(6);
  });

  it("returns every point when the series is shorter than the tick count", () => {
    const data = monthly(3);
    expect(pickTicks(data, 6)).toHaveLength(3);
  });
});

describe("windowMean", () => {
  it("ignores gaps", () => {
    expect(
      windowMean([
        { date: "a", value: 2 },
        { date: "b", value: null },
        { date: "c", value: 4 },
      ]),
    ).toBe(3);
  });

  it("is null when nothing was reported", () => {
    expect(windowMean([{ date: "a", value: null }])).toBeNull();
  });
});

describe("query building", () => {
  const parameters: ParameterSpec[] = [
    {
      name: "interval",
      allowed: ["daily", "weekly", "monthly"],
      default: "monthly",
      description: "",
    },
    {
      name: "maturity",
      allowed: ["3month", "10year"],
      default: "10year",
      description: "",
    },
  ];

  it("starts on each parameter's documented default", () => {
    expect(defaultParameterValues(parameters)).toEqual({
      interval: "monthly",
      maturity: "10year",
    });
  });

  it("is empty for indicators that take no parameters", () => {
    expect(defaultParameterValues([])).toEqual({});
  });

  it("always requests ascending order so chart and table agree", () => {
    expect(seriesQueryFor({ interval: "daily" })).toEqual({
      interval: "daily",
      order: "asc",
    });
  });

  it("produces an identical query on the server and the client", () => {
    // If these diverged the client would refetch what the server embedded.
    const values = defaultParameterValues(parameters);
    expect(JSON.stringify(seriesQueryFor(values))).toBe(
      JSON.stringify(seriesQueryFor({ ...values })),
    );
  });
});

describe("observationsPerYear", () => {
  it.each([
    ["daily", 252],
    ["monthly", 12],
    ["quarterly", 4],
    ["annual", 1],
  ] as const)("%s", (frequency, expected) => {
    expect(observationsPerYear(frequency)).toBe(expected);
  });
});

it("defaults to a ten-year window", () => {
  expect(DEFAULT_RANGE_ID).toBe("10y");
});
