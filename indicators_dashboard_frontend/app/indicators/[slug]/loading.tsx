import { Skeleton } from "@/components/ui/skeleton";

export default function IndicatorLoading() {
  return (
    <div className="mx-auto max-w-450 px-4 py-6 sm:px-6 lg:py-8">
      <div className="flex items-start gap-3">
        <Skeleton className="size-9 shrink-0 rounded-lg" />
        <div className="min-w-0 flex-1">
          <Skeleton className="h-5 w-72 max-w-full" />
          <Skeleton className="mt-2.5 h-4 w-full max-w-160" />
        </div>
      </div>

      <div className="mt-6 space-y-4">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-105 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    </div>
  );
}
