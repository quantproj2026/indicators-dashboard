/**
 * Presentation metadata that belongs to the frontend rather than the API:
 * which icon represents an indicator, how categories are ordered and labelled,
 * and a static fallback catalog so navigation still works when the backend is
 * unreachable.
 *
 * Everything factual -- names, units, supported parameters -- comes from the
 * backend catalog at runtime. Only the fallback duplicates it, and only enough
 * to render a usable shell alongside an explicit error message.
 */

import {
  Activity,
  Banknote,
  Building2,
  Coins,
  Factory,
  Gauge,
  Landmark,
  Percent,
  ShoppingCart,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { Category, IndicatorSlug, IndicatorSummary } from "./types";

export const INDICATOR_ICONS: Record<IndicatorSlug, LucideIcon> = {
  "real-gdp": TrendingUp,
  "real-gdp-per-capita": Users,
  "treasury-yield": Landmark,
  "federal-funds-rate": Banknote,
  cpi: Gauge,
  inflation: Percent,
  "retail-sales": ShoppingCart,
  durables: Factory,
  unemployment: Activity,
  "nonfarm-payroll": Building2,
};

export function indicatorIcon(slug: string): LucideIcon {
  return INDICATOR_ICONS[slug as IndicatorSlug] ?? Coins;
}

interface CategoryMeta {
  label: string;
  blurb: string;
}

/** Display order of the sections on the overview and in the sidebar. */
export const CATEGORY_ORDER: Category[] = [
  "output",
  "prices",
  "rates",
  "labor",
  "demand",
];

export const CATEGORY_META: Record<Category, CategoryMeta> = {
  output: { label: "Output", blurb: "Aggregate production and living standards" },
  prices: { label: "Prices", blurb: "Consumer price level and its rate of change" },
  rates: { label: "Rates", blurb: "Policy rate and the Treasury curve" },
  labor: { label: "Labor", blurb: "Employment and joblessness" },
  demand: { label: "Demand", blurb: "Household spending and capital orders" },
};

/** Group a catalog into the fixed category order, dropping empty sections. */
export function groupByCategory<T extends { category: Category }>(
  items: T[],
): Array<{ category: Category; meta: CategoryMeta; items: T[] }> {
  return CATEGORY_ORDER.map((category) => ({
    category,
    meta: CATEGORY_META[category],
    items: items.filter((item) => item.category === category),
  })).filter((group) => group.items.length > 0);
}

/**
 * Minimal catalog used only when the backend cannot be reached, so the shell
 * and its navigation still render around the error state.
 */
export const FALLBACK_CATALOG: IndicatorSummary[] = (
  [
    ["real-gdp", "Real GDP", "Real Gross Domestic Product", "output", "annual"],
    [
      "real-gdp-per-capita",
      "Real GDP / Capita",
      "Real Gross Domestic Product per Capita",
      "output",
      "quarterly",
    ],
    ["treasury-yield", "Treasury Yield", "Treasury Yield", "rates", "monthly"],
    [
      "federal-funds-rate",
      "Fed Funds Rate",
      "Effective Federal Funds Rate",
      "rates",
      "monthly",
    ],
    ["cpi", "CPI", "Consumer Price Index", "prices", "monthly"],
    ["inflation", "Inflation", "Inflation - US Consumer Prices", "prices", "annual"],
    [
      "retail-sales",
      "Retail Sales",
      "Advance Retail Sales: Retail Trade",
      "demand",
      "monthly",
    ],
    [
      "durables",
      "Durable Goods",
      "Manufacturers' New Orders: Durable Goods",
      "demand",
      "monthly",
    ],
    ["unemployment", "Unemployment", "Unemployment Rate", "labor", "monthly"],
    ["nonfarm-payroll", "Nonfarm Payroll", "Total Nonfarm Payroll", "labor", "monthly"],
  ] as const
).map(([slug, shortName, name, category, frequency]) => ({
  slug: slug as IndicatorSlug,
  function: slug.toUpperCase().replace(/-/g, "_"),
  name,
  short_name: shortName,
  description: "",
  unit: "",
  unit_short: "",
  category: category as Category,
  frequency: frequency as IndicatorSummary["frequency"],
  higher_is_better: null,
  default_window: 120,
  parameters: [],
  path: `/api/v1/indicators/${slug}`,
  source_note: "",
}));
