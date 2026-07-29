"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * Re-runs the Server Component that renders the overview.
 *
 * This asks the backend for the overview again; the backend answers from its
 * own cache unless that has expired, so the button is safe to press and does
 * not spend the daily Alpha Vantage budget on its own.
 */
export function RefreshOverviewButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            disabled={pending}
            onClick={() => startTransition(() => router.refresh())}
          >
            <RefreshCw
              aria-hidden
              className={cn("size-3.5", pending && "animate-spin")}
            />
            Refresh
          </Button>
        }
      />
      <TooltipContent className="max-w-60">
        Reload every indicator from the backend. Cached series are served
        instantly and cost no upstream requests.
      </TooltipContent>
    </Tooltip>
  );
}
