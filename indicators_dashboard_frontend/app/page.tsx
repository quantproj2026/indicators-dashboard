import { Database, TriangleAlert } from "lucide-react";

import { ErrorState } from "@/components/common/error-state";
import { OverviewGrid } from "@/components/dashboard/overview-grid";
import { RefreshOverviewButton } from "@/components/dashboard/refresh-overview-button";
import { ApiError, getOverview } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { Overview } from "@/lib/types";

export const metadata = {
  title: "Overview",
  description:
    "Latest values for every United States economic indicator published by Alpha Vantage.",
};

type Result =
  | { ok: true; overview: Overview }
  | { ok: false; code: string; message: string };

async function loadOverview(): Promise<Result> {
  try {
    return { ok: true, overview: await getOverview() };
  } catch (cause) {
    if (cause instanceof ApiError) {
      return { ok: false, code: cause.code, message: cause.message };
    }
    return {
      ok: false,
      code: "unknown_error",
      message: "The overview could not be loaded.",
    };
  }
}

export default async function OverviewPage() {
  const result = await loadOverview();

  return (
    <div className="mx-auto max-w-450 px-4 py-6 sm:px-6 lg:py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="text-lg leading-tight font-semibold tracking-tight">
            Economic indicators
          </h1>
          <p className="mt-1.5 max-w-200 text-sm leading-relaxed text-muted-foreground">
            Every economic series Alpha Vantage publishes for the United States,
            proxied through the FastAPI backend. Select any card for the full
            history, interval and maturity controls, and the underlying table.
          </p>
        </div>

        {result.ok ? (
          <div className="flex items-center gap-3">
            <p className="text-xs text-muted-foreground">
              Updated {formatRelativeTime(result.overview.generated_at)}
            </p>
            <RefreshOverviewButton />
          </div>
        ) : null}
      </header>

      {result.ok ? (
        <>
          {result.overview.degraded ? (
            <div
              role="status"
              className="mb-5 flex items-start gap-2.5 rounded-lg border border-border bg-card px-4 py-3"
            >
              <TriangleAlert
                aria-hidden
                className="mt-0.5 size-4 shrink-0 text-muted-foreground"
              />
              <p className="text-sm text-muted-foreground">
                Some indicators could not be refreshed. Those cards say so
                individually; every other value below is current.
              </p>
            </div>
          ) : null}

          <OverviewGrid snapshots={result.overview.indicators} />

        </>
      ) : (
        <ErrorState code={result.code} message={result.message} />
      )}
    </div>
  );
}
