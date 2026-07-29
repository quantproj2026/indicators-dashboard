import { Activity } from "lucide-react";
import Link from "next/link";

import { SidebarNav } from "@/components/layout/sidebar-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { getCatalog } from "@/lib/api";
import { FALLBACK_CATALOG } from "@/lib/indicator-meta";
import type { IndicatorSummary } from "@/lib/types";

/**
 * The persistent frame: brand, navigation, theme control.
 *
 * The catalog drives navigation, but the shell must render even when the
 * backend is down -- otherwise a stopped API would replace the whole app with a
 * blank page instead of a page containing a readable error. On failure it falls
 * back to a static list so navigation keeps working while the route below
 * explains what went wrong.
 */
async function loadCatalog(): Promise<IndicatorSummary[]> {
  try {
    return await getCatalog();
  } catch {
    return FALLBACK_CATALOG;
  }
}

export async function AppShell({ children }: { children: React.ReactNode }) {
  const catalog = await loadCatalog();

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-popover focus:px-3 focus:py-2 focus:text-sm focus:ring-1 focus:ring-border"
      >
        Skip to content
      </a>

      <aside className="border-border bg-sidebar lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:shrink-0 lg:border-r">
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4 lg:h-16 lg:px-5">
          <Link
            href="/"
            className="flex min-w-0 items-center gap-2.5 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/12 text-primary ring-1 ring-primary/20">
              <Activity aria-hidden className="size-4" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm leading-tight font-medium tracking-tight">
                Economic Indicators
              </span>
              <span className="block truncate text-[11px] leading-tight text-muted-foreground">
                United States
              </span>
            </span>
          </Link>
          <div className="ml-auto lg:hidden">
            <ThemeToggle />
          </div>
        </div>

        <SidebarNav catalog={catalog} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 hidden h-16 shrink-0 items-center gap-3 border-b border-border bg-background/85 px-6 backdrop-blur-sm lg:flex">
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
          </div>
        </header>

        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
