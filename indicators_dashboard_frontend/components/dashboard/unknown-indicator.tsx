import { ArrowLeft, SearchX } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Shown when the backend catalog has no series at the requested slug.
 *
 * Rendered as ordinary page content rather than through `notFound()`. For a
 * streamed route Next.js returns 200 either way, and the boundary's UI arrives
 * only in the flight payload -- rendering it directly puts it in the
 * server-rendered HTML, where it is visible without JavaScript and can be
 * verified. Genuinely unmatched URLs still fall through to `app/not-found.tsx`.
 */
export function UnknownIndicator({ slug }: { slug: string }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-start px-4 py-16 sm:px-6">
      <span className="flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <SearchX aria-hidden className="size-4.5" />
      </span>
      <p className="mt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Not found
      </p>
      <h1 className="mt-1 text-lg font-semibold tracking-tight">
        No indicator called{" "}
        <span className="font-mono text-base">{slug}</span>
      </h1>
      <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">
        The backend catalog has no series at that address. Every indicator Alpha
        Vantage publishes is listed in the sidebar and on the overview.
      </p>
      <Button variant="outline" size="sm" className="mt-5" render={<Link href="/" />}>
        <ArrowLeft aria-hidden className="size-3.5" />
        Back to the overview
      </Button>
    </div>
  );
}
