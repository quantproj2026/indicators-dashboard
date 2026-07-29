import type { Metadata } from "next";

import { IndicatorView } from "@/components/dashboard/indicator-view";
import { UnknownIndicator } from "@/components/dashboard/unknown-indicator";
import { ApiError, getCatalog, getSeries } from "@/lib/api";
import { defaultParameterValues, seriesQueryFor } from "@/lib/series";
import type { IndicatorSeries, IndicatorSlug, IndicatorSummary } from "@/lib/types";

interface PageParams {
  params: Promise<{ slug: string }>;
}

/**
 * The catalog is static per backend deployment and every request on this route
 * needs it, so look it up once and reuse it for both metadata and the page.
 * `fetch` deduplicates identical requests within a single render pass.
 */
async function findSummary(slug: string): Promise<IndicatorSummary | null> {
  try {
    const catalog = await getCatalog();
    return catalog.find((entry) => entry.slug === slug) ?? null;
  } catch {
    // The backend is unreachable. Fall through to the page, which renders a
    // readable error rather than a 404 that would blame the URL.
    return null;
  }
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { slug } = await params;
  const summary = await findSummary(slug);
  if (!summary) return { title: "Indicator" };
  return {
    title: summary.short_name,
    description: summary.description,
  };
}

export default async function IndicatorPage({ params }: PageParams) {
  const { slug } = await params;

  let catalog: IndicatorSummary[] | null = null;
  let catalogError: { code: string; message: string } | null = null;

  try {
    catalog = await getCatalog();
  } catch (cause) {
    catalogError =
      cause instanceof ApiError
        ? { code: cause.code, message: cause.message }
        : { code: "unknown_error", message: "The indicator catalog is unavailable." };
  }

  // Only a reachable backend can prove a slug is wrong; if it answered and does
  // not know this slug, the URL really is unknown. When it did not answer we
  // fall through and let the view report the connection problem instead, rather
  // than blaming the URL for a backend outage.
  const summary = catalog?.find((entry) => entry.slug === slug) ?? null;
  if (catalog && !summary) return <UnknownIndicator slug={slug} />;

  const resolved =
    summary ??
    ({
      slug: slug as IndicatorSlug,
      function: slug.toUpperCase().replace(/-/g, "_"),
      name: slug,
      short_name: slug,
      description: "",
      unit: "",
      unit_short: "",
      category: "output",
      frequency: "monthly",
      higher_is_better: null,
      default_window: 120,
      parameters: [],
      path: `/api/v1/indicators/${slug}`,
      source_note: "",
    } satisfies IndicatorSummary);

  let series: IndicatorSeries | null = null;
  let seriesError = catalogError;

  if (summary) {
    const query = seriesQueryFor(defaultParameterValues(summary.parameters));
    try {
      series = await getSeries(summary.slug, query);
    } catch (cause) {
      seriesError =
        cause instanceof ApiError
          ? { code: cause.code, message: cause.message }
          : { code: "unknown_error", message: "This series could not be loaded." };
    }
  }

  return (
    <IndicatorView
      summary={resolved}
      initialSeries={series}
      initialError={seriesError}
    />
  );
}
