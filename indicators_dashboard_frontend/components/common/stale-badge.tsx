import { Clock } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * Marks a figure that came from the backend cache after the upstream refused a
 * refresh -- normally because the Alpha Vantage daily budget is spent.
 *
 * The dashboard keeps working in that state, so it has to say so: a number that
 * silently stops updating is worse than a number labelled as held over.
 */
export function StaleBadge({
  ageSeconds,
  className,
}: {
  ageSeconds?: number;
  className?: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded-sm bg-muted px-1.5 py-0.5 text-[10px] leading-none font-medium tracking-wide text-muted-foreground uppercase",
              className,
            )}
          >
            <Clock aria-hidden className="size-2.5" />
            Cached
          </span>
        }
      />
      <TooltipContent className="max-w-64">
        Served from the backend cache because Alpha Vantage could not be refreshed --
        usually the free tier&apos;s 25 requests per day.
        {ageSeconds !== undefined
          ? ` This copy was fetched ${Math.round(ageSeconds / 60)} minutes ago.`
          : ""}
      </TooltipContent>
    </Tooltip>
  );
}
