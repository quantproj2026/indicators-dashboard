"use client";

import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { Sparkline } from "@/components/charts/sparkline";
import { Delta } from "@/components/common/delta";
import { ErrorState } from "@/components/common/error-state";
import { IndicatorIcon } from "@/components/common/indicator-icon";
import { StaleBadge } from "@/components/common/stale-badge";
import { Card } from "@/components/ui/card";
import {
  formatChange,
  formatObservationDate,
  formatPercent,
  formatValue,
  frequencyLabel,
  parameterValueLabel,
  periodLabel,
} from "@/lib/format";
import { cardHover, cardTap, gridItem } from "@/lib/motion";
import type { IndicatorSnapshot } from "@/lib/types";

/**
 * One indicator in the overview grid.
 *
 * The card leads with the value, because that is what the grid exists to show.
 * Everything else -- period change, year-over-year, the trend strip -- is
 * secondary ink beneath it. The whole card is the link target, so the pointer
 * never has to find a small hit area.
 */
export function MetricCard({ snapshot }: { snapshot: IndicatorSnapshot }) {
  const { indicator, latest, sparkline, meta, error } = snapshot;
  const href = `/indicators/${indicator.slug}`;

  const parameterChip = indicator.maturity
    ? parameterValueLabel("maturity", indicator.maturity)
    : indicator.interval
      ? parameterValueLabel("interval", indicator.interval)
      : frequencyLabel(indicator.frequency);

  return (
    <motion.div variants={gridItem} whileHover={cardHover} whileTap={cardTap}>
      <Card
        size="sm"
        className="group h-full gap-0 transition-colors hover:ring-foreground/20"
      >
        <Link
          href={href}
          className="flex h-full flex-col outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0"
        >
          <div className="flex items-start gap-2.5 px-(--card-spacing)">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground transition-colors group-hover:text-foreground">
              <IndicatorIcon slug={indicator.slug} className="size-3.5" />
            </span>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm leading-tight font-medium">
                {indicator.short_name}
              </p>
              <p className="mt-0.5 truncate text-[11px] leading-tight text-muted-foreground">
                {parameterChip} · {indicator.unit_short || indicator.unit}
              </p>
            </div>

            <ChevronRight
              aria-hidden
              className="mt-1 size-3.5 shrink-0 text-muted-foreground/50 transition-colors group-hover:text-muted-foreground"
            />
          </div>

          {error ? (
            <div className="mt-4 flex flex-1 flex-col justify-end px-(--card-spacing)">
              <ErrorState variant="inline" code={error.code} message={error.message} />
            </div>
          ) : latest ? (
            <>
              <div className="mt-3.5 px-(--card-spacing)">
                <p className="text-2xl leading-none font-semibold tracking-tight">
                  {formatValue(latest.value, indicator.unit)}
                </p>

                <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <Delta
                    change={latest.change}
                    label={formatChange(latest.change, indicator.unit)}
                    higherIsBetter={indicator.higher_is_better}
                    suffix={`vs ${periodLabel(indicator.frequency)}`}
                  />
                </div>

                {latest.year_over_year_percent !== null ? (
                  <div className="mt-1">
                    <Delta
                      change={latest.year_over_year_change}
                      label={formatPercent(latest.year_over_year_percent)}
                      higherIsBetter={indicator.higher_is_better}
                      suffix="year over year"
                    />
                  </div>
                ) : null}
              </div>

              <div className="mt-auto pt-3">
                <Sparkline data={sparkline} height={36} />
              </div>

              <div className="mt-2 flex items-center gap-2 px-(--card-spacing) text-[11px] text-muted-foreground">
                <span className="truncate">
                  as of {formatObservationDate(latest.date, indicator.frequency)}
                </span>
                {meta?.stale ? <StaleBadge className="ml-auto" /> : null}
              </div>
            </>
          ) : (
            <div className="mt-4 flex flex-1 items-end px-(--card-spacing)">
              <p className="text-sm text-muted-foreground">No observations reported.</p>
            </div>
          )}
        </Link>
      </Card>
    </motion.div>
  );
}
