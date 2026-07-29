import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Delta } from "@/components/common/delta";
import { ErrorState } from "@/components/common/error-state";
import { HistoryTable } from "@/components/dashboard/history-table";
import { StatTiles } from "@/components/dashboard/stat-tiles";
import type { Latest, Observation, SeriesStats } from "@/lib/types";

describe("Delta", () => {
  it("reads a rise as good when higher is better", () => {
    const { container } = render(
      <Delta change={0.5} label="+0.50" higherIsBetter={true} />,
    );
    expect(container.querySelector(".text-positive")).not.toBeNull();
  });

  it("reads a rise as bad when higher is worse", () => {
    // Unemployment going up is not good news, even though the sign is positive.
    const { container } = render(
      <Delta change={0.5} label="+0.50" higherIsBetter={false} />,
    );
    expect(container.querySelector(".text-negative")).not.toBeNull();
  });

  it("stays neutral where the sign carries no verdict", () => {
    // A Treasury yield moving is neither good nor bad on its own.
    const { container } = render(
      <Delta change={0.5} label="+0.50" higherIsBetter={null} />,
    );
    expect(container.querySelector(".text-positive")).toBeNull();
    expect(container.querySelector(".text-negative")).toBeNull();
  });

  it("carries direction with a glyph as well as colour", () => {
    const { container } = render(
      <Delta change={-1} label="-1.00" higherIsBetter={true} />,
    );
    // An icon is present, so the meaning survives without colour vision.
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("renders a placeholder when there is no change to show", () => {
    render(<Delta change={null} label="--" />);
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("shows the comparison period alongside the figure", () => {
    render(<Delta change={1} label="+1.00" suffix="vs prior month" />);
    expect(screen.getByText("vs prior month")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("explains a stopped backend with the command that fixes it", () => {
    render(<ErrorState code="backend_unreachable" message="Cannot reach the API." />);
    expect(screen.getByText(/API is not responding/i)).toBeInTheDocument();
    expect(screen.getByText(/uvicorn/i)).toBeInTheDocument();
  });

  it("explains the free-tier quota rather than showing a bare 429", () => {
    render(<ErrorState code="upstream_rate_limited" message="limit" />);
    expect(screen.getByText(/25 requests per day/i)).toBeInTheDocument();
  });

  it("names the file to edit when the key is absent", () => {
    render(<ErrorState code="api_key_missing" message="no key" />);
    expect(screen.getByText(/\.env/)).toBeInTheDocument();
  });

  it("falls back to the raw message for an unrecognised code", () => {
    render(<ErrorState code="something_new" message="Unhandled failure." />);
    expect(screen.getByText("Unhandled failure.")).toBeInTheDocument();
  });

  it("announces itself to assistive technology", () => {
    render(<ErrorState message="broken" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

const LATEST: Latest = {
  date: "2026-06-01",
  value: 4.2,
  previous_date: "2026-05-01",
  previous_value: 4.3,
  change: -0.1,
  change_percent: -2.33,
  year_ago_date: "2025-06-01",
  year_ago_value: 4.1,
  year_over_year_change: 0.1,
  year_over_year_percent: 2.44,
};

const STATS: SeriesStats = {
  count: 120,
  minimum: 3.4,
  maximum: 14.8,
  mean: 5.9,
  first_date: "2016-06-01",
  last_date: "2026-06-01",
};

describe("StatTiles", () => {
  it("leads with the latest value and its date", () => {
    render(
      <StatTiles
        latest={LATEST}
        stats={STATS}
        unit="percent"
        frequency="monthly"
        higherIsBetter={false}
      />,
    );
    expect(screen.getByText("4.20%")).toBeInTheDocument();
    expect(screen.getByText("Jun 2026")).toBeInTheDocument();
  });

  it("names the comparison period for the cadence", () => {
    render(
      <StatTiles
        latest={LATEST}
        stats={STATS}
        unit="percent"
        frequency="quarterly"
        higherIsBetter={null}
      />,
    );
    expect(screen.getByText(/vs prior quarter/i)).toBeInTheDocument();
  });

  it("describes the window the extremes span, not when they occurred", () => {
    render(
      <StatTiles
        latest={LATEST}
        stats={STATS}
        unit="percent"
        frequency="monthly"
        higherIsBetter={false}
      />,
    );
    expect(screen.getByText(/since Jun 2016/)).toBeInTheDocument();
  });

  it("degrades gracefully when there is no observation", () => {
    render(
      <StatTiles
        latest={null}
        stats={{ ...STATS, minimum: null, maximum: null, mean: null }}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );
    expect(screen.getAllByText("--").length).toBeGreaterThan(0);
  });
});

const SERIES: Observation[] = [
  { date: "2026-01-01", value: 4.0 },
  { date: "2026-02-01", value: null },
  { date: "2026-03-01", value: 4.4 },
  { date: "2026-04-01", value: 4.5 },
];

describe("HistoryTable", () => {
  it("lists the newest observation first", () => {
    render(
      <HistoryTable
        data={SERIES}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );
    const rows = screen.getAllByRole("row").slice(1); // drop the header
    expect(within(rows[0]).getByText("Apr 2026")).toBeInTheDocument();
  });

  it("computes change against the previous reported value, skipping gaps", () => {
    // March follows a missing February, so its change is measured from January:
    // 4.4 - 4.0 = +0.40 pp, not "no change".
    render(
      <HistoryTable
        data={SERIES}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );
    const marchRow = screen.getByText("Mar 2026").closest("tr")!;
    expect(within(marchRow).getByText("+0.40 pp")).toBeInTheDocument();
  });

  it("shows a gap as missing rather than as zero", () => {
    render(
      <HistoryTable
        data={SERIES}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );
    const februaryRow = screen.getByText("Feb 2026").closest("tr")!;
    expect(within(februaryRow).getAllByText("--").length).toBeGreaterThan(0);
  });

  it("reports the observation count", () => {
    render(
      <HistoryTable
        data={SERIES}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );
    expect(screen.getByText(/4 observations in this window/)).toBeInTheDocument();
  });

  it("paginates long histories behind a control", async () => {
    const long: Observation[] = Array.from({ length: 60 }, (_, index) => ({
      date: `2021-${String((index % 12) + 1).padStart(2, "0")}-01`,
      value: index,
    }));

    render(
      <HistoryTable
        data={long}
        unit="percent"
        frequency="monthly"
        higherIsBetter={null}
      />,
    );

    expect(screen.getByText(/Showing 25 of 60/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show \d+ more/ }));
    expect(screen.queryByText(/Showing 25 of 60/)).not.toBeInTheDocument();
  });

  it("says so when the window is empty", () => {
    render(
      <HistoryTable data={[]} unit="percent" frequency="monthly" higherIsBetter={null} />,
    );
    expect(screen.getByText(/No observations in this window/)).toBeInTheDocument();
  });
});

describe("indicator metadata", () => {
  it("maps every catalog slug to an icon", async () => {
    const { INDICATOR_ICONS, FALLBACK_CATALOG, groupByCategory } = await import(
      "@/lib/indicator-meta"
    );

    for (const entry of FALLBACK_CATALOG) {
      expect(INDICATOR_ICONS[entry.slug]).toBeDefined();
    }

    // Grouping keeps every indicator and drops no category.
    const grouped = groupByCategory(FALLBACK_CATALOG);
    const total = grouped.reduce((sum, group) => sum + group.items.length, 0);
    expect(total).toBe(FALLBACK_CATALOG.length);
  });
});

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ refresh: vi.fn() }),
}));
