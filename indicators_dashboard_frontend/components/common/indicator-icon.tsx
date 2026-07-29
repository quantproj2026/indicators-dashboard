import { createElement } from "react";

import { indicatorIcon } from "@/lib/indicator-meta";

/**
 * Renders the lucide icon that stands for an indicator.
 *
 * `createElement` rather than `const Icon = indicatorIcon(slug); <Icon/>`: the
 * lookup returns a stable module-level reference either way, but assigning it
 * to a local reads as creating a component during render, which is a real bug
 * in the general case. Doing it here once keeps every call site clean.
 */
export function IndicatorIcon({
  slug,
  className,
}: {
  slug: string;
  className?: string;
}) {
  return createElement(indicatorIcon(slug), { className, "aria-hidden": true });
}
