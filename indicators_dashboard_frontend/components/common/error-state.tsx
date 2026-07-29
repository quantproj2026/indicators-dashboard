import {
  CircleAlert,
  Clock,
  KeyRound,
  ServerCog,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * How each backend error code should be explained to someone looking at the
 * dashboard. The messages name the concrete next action, because every one of
 * these is fixable by the person running the stack.
 */
const EXPLANATIONS: Record<
  string,
  { title: string; hint: string; icon: LucideIcon }
> = {
  backend_unreachable: {
    title: "The API is not responding",
    hint: "Start the FastAPI backend with `poetry run uvicorn indicators_dashboard_backend.main:app --reload`, then reload this page.",
    icon: ServerCog,
  },
  api_key_missing: {
    title: "No Alpha Vantage API key configured",
    hint: "Add ALPHA_VANTAGE_API_KEY to indicators_dashboard_backend/.env and restart the backend.",
    icon: KeyRound,
  },
  upstream_rate_limited: {
    title: "Alpha Vantage daily limit reached",
    hint: "The free tier allows 25 requests per day. Cached indicators still load; this one had no cached copy within the stale window.",
    icon: Clock,
  },
  upstream_unavailable: {
    title: "Alpha Vantage could not be reached",
    hint: "The upstream timed out or refused the connection. It is usually transient -- try again shortly.",
    icon: ServerCog,
  },
  upstream_invalid_request: {
    title: "Alpha Vantage rejected the request",
    hint: "The upstream reported an invalid call for these parameters.",
    icon: TriangleAlert,
  },
  upstream_malformed_payload: {
    title: "Unexpected response from Alpha Vantage",
    hint: "The upstream returned something that is not a time series.",
    icon: TriangleAlert,
  },
};

export interface ErrorStateProps {
  code?: string;
  message: string;
  /** Compact form for inside a metric card. */
  variant?: "panel" | "inline";
  className?: string;
  action?: React.ReactNode;
}

export function ErrorState({
  code,
  message,
  variant = "panel",
  className,
  action,
}: ErrorStateProps) {
  const explanation = code ? EXPLANATIONS[code] : undefined;
  const Icon = explanation?.icon ?? CircleAlert;

  if (variant === "inline") {
    return (
      <div className={cn("flex items-start gap-2 text-xs text-muted-foreground", className)}>
        <Icon aria-hidden className="mt-px size-3.5 shrink-0 text-muted-foreground" />
        <span className="min-w-0">{explanation?.title ?? message}</span>
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-border bg-card p-5 sm:flex-row sm:items-center",
        className,
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Icon aria-hidden className="size-4.5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{explanation?.title ?? "Could not load data"}</p>
        <p className="mt-1 text-sm text-muted-foreground">{explanation?.hint ?? message}</p>
        {explanation ? (
          <p className="mt-1.5 text-xs text-muted-foreground/80">{message}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
