import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Shown for URLs that match no route at all. An address under
 * `/indicators/<slug>` does match a route, so an unknown indicator is handled
 * by the page itself rather than here.
 */
export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-start px-4 py-16 sm:px-6">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        404
      </p>
      <h1 className="mt-2 text-lg font-semibold tracking-tight">
        This page does not exist
      </h1>
      <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">
        There is nothing at that address. The overview and the sidebar list every
        indicator this dashboard serves.
      </p>
      <Button variant="outline" size="sm" className="mt-5" render={<Link href="/" />}>
        <ArrowLeft aria-hidden className="size-3.5" />
        Back to the overview
      </Button>
    </div>
  );
}
