"use client";

import { LayoutGrid } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { IndicatorIcon } from "@/components/common/indicator-icon";
import { ScrollArea } from "@/components/ui/scroll-area";
import { groupByCategory } from "@/lib/indicator-meta";
import type { IndicatorSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Indicator navigation, grouped by category in a fixed order so an item never
 * moves between visits.
 */
export function SidebarNav({ catalog }: { catalog: IndicatorSummary[] }) {
  const pathname = usePathname();
  const groups = groupByCategory(catalog);

  return (
    <ScrollArea className="lg:h-[calc(100vh-4rem)]">
      <nav aria-label="Indicators" className="px-3 py-3 lg:py-4">
        <NavLink
          href="/"
          active={pathname === "/"}
          icon={<LayoutGrid aria-hidden className="size-3.5" />}
          label="Overview"
        />

        <div className="mt-1 flex flex-wrap gap-x-6 gap-y-1 lg:block">
          {groups.map((group) => (
            <div key={group.category} className="mt-4 min-w-45 flex-1 lg:min-w-0">
              <p className="px-2 pb-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
                {group.meta.label}
              </p>
              <ul>
                {group.items.map((indicator) => {
                  const href = `/indicators/${indicator.slug}`;
                  return (
                    <li key={indicator.slug}>
                      <NavLink
                        href={href}
                        active={pathname === href}
                        icon={
                          <IndicatorIcon
                            slug={indicator.slug}
                            className="size-3.5"
                          />
                        }
                        label={indicator.short_name}
                      />
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>
    </ScrollArea>
  );
}

function NavLink({
  href,
  active,
  icon,
  label,
}: {
  href: string;
  active: boolean;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors outline-none",
        "focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-accent font-medium text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
      )}
    >
      <span className={cn("shrink-0", active ? "text-primary" : "text-muted-foreground")}>
        {icon}
      </span>
      <span className="truncate">{label}</span>
    </Link>
  );
}
