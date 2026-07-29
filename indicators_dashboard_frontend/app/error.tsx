"use client";

import { RefreshCw } from "lucide-react";
import { useEffect } from "react";

import { ErrorState } from "@/components/common/error-state";
import { Button } from "@/components/ui/button";

/**
 * Route-level fallback for anything the page code did not handle itself.
 *
 * Expected failures -- an unreachable backend, an exhausted Alpha Vantage quota
 * -- are caught inside the pages and rendered inline with a specific
 * explanation. Reaching here means something genuinely unexpected happened.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <ErrorState
        message={error.message || "An unexpected error occurred while rendering this view."}
        action={
          <Button variant="outline" size="sm" onClick={reset}>
            <RefreshCw aria-hidden className="size-3.5" />
            Try again
          </Button>
        }
      />
    </div>
  );
}
