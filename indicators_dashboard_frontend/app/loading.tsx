import { Skeleton } from "@/components/ui/skeleton";

/**
 * Streamed while the overview's server fetch is in flight.
 *
 * Mirrors the real grid's geometry so the layout does not jump when the data
 * lands.
 */
export default function OverviewLoading() {
  return (
    <div className="mx-auto max-w-450 px-4 py-6 sm:px-6 lg:py-8">
      <div className="mb-6">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="mt-2.5 h-4 w-full max-w-160" />
      </div>

      {[0, 1, 2].map((section) => (
        <div key={section} className="mb-8">
          <Skeleton className="mb-3 h-4 w-28" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {Array.from({ length: section === 2 ? 2 : 4 }).map((_, card) => (
              <Skeleton key={card} className="h-45 rounded-xl" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
