"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Download, ExternalLink, LoaderCircle, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { SeriesChart } from "@/components/charts/series-chart";
import { ErrorState } from "@/components/common/error-state";
import { IndicatorIcon } from "@/components/common/indicator-icon";
import { StaleBadge } from "@/components/common/stale-badge";
import { HistoryTable } from "@/components/dashboard/history-table";
import { ParameterControls } from "@/components/dashboard/parameter-controls";
import { RangeSelector } from "@/components/dashboard/range-selector";
import { StatTiles } from "@/components/dashboard/stat-tiles";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useSeries } from "@/hooks/use-series";
import { csvDownloadUrl } from "@/lib/api";
import {
  formatDuration,
  formatObservationDate,
  formatRelativeTime,
  frequencyLabel,
} from "@/lib/format";
import { chartSwap, fadeInUp } from "@/lib/motion";
import {
  DEFAULT_RANGE_ID,
  defaultParameterValues,
  seriesQueryFor,
  sliceByRange,
  usableRanges,
} from "@/lib/series";
import type { IndicatorSeries, IndicatorSummary } from "@/lib/types";

interface IndicatorViewProps {
  summary: IndicatorSummary;
  initialSeries: IndicatorSeries | null;
  initialError: { code: string; message: string } | null;
}

/**
 * The detail view for one indicator.
 *
 * Server-rendered with its default parameters, then fully interactive: changing
 * an interval or maturity fetches the new series from the FastAPI backend
 * without a navigation, while the time range is applied client-side to data
 * already in hand (so it is instant and costs the upstream nothing).
 */
export function IndicatorView({
  summary,
  initialSeries,
  initialError,
}: IndicatorViewProps) {
  const initialValues = useMemo(
    () => defaultParameterValues(summary.parameters),
    [summary.parameters],
  );
  const [values, setValues] = useState(initialValues);
  const [rangeId, setRangeId] = useState(DEFAULT_RANGE_ID);

  const query = useMemo(() => seriesQueryFor(values), [values]);
  const initialQuery = useMemo(() => seriesQueryFor(initialValues), [initialValues]);

  const { series, loading, error, refresh } = useSeries(
    summary.slug,
    query,
    initialSeries,
    initialQuery,
  );

  const activeError = error ?? (series ? null : initialError);

  const ranges = useMemo(
    () => usableRanges(series?.data ?? []),
    [series?.data],
  );
  const effectiveRange = ranges.some((range) => range.id === rangeId)
    ? rangeId
    : (ranges[ranges.length - 1]?.id ?? DEFAULT_RANGE_ID);

  const windowed = useMemo(
    () => sliceByRange(series?.data ?? [], effectiveRange),
    [series?.data, effectiveRange],
  );

  const identity = series?.indicator;
  const unit = identity?.unit ?? summary.unit;
  const frequency = identity?.frequency ?? summary.frequency;

  return (
    <div className="mx-auto max-w-450 px-4 py-6 sm:px-6 lg:py-8">
      {/* Heading -------------------------------------------------------- */}
      <motion.header initial="hidden" animate="visible" variants={fadeInUp}>
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary ring-1 ring-primary/20">
            <IndicatorIcon slug={summary.slug} className="size-4.5" />
          </span>

          <div className="min-w-0 flex-1">
            <h1 className="text-lg leading-tight font-semibold tracking-tight text-balance">
              {identity?.name ?? summary.name}
            </h1>
            <p className="mt-1.5 max-w-200 text-sm leading-relaxed text-muted-foreground">
              {summary.description}
            </p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="font-mono text-[11px]">
            {summary.function}
          </Badge>
          <Badge variant="ghost" className="text-[11px] text-muted-foreground">
            {frequencyLabel(frequency)}
          </Badge>
          <Badge variant="ghost" className="text-[11px] text-muted-foreground">
            {unit}
          </Badge>
          {series?.meta.stale ? (
            <StaleBadge ageSeconds={series.meta.cache_age_seconds} />
          ) : null}
        </div>
      </motion.header>

      {activeError ? (
        <ErrorState
          className="mt-6"
          code={activeError.code}
          message={activeError.message}
          action={
            <Button variant="outline" size="sm" onClick={() => refresh()}>
              <RefreshCw aria-hidden className="size-3.5" />
              Try again
            </Button>
          }
        />
      ) : null}

      {series ? (
        <div className="mt-6 space-y-4">
          {/* Figures ---------------------------------------------------- */}
          <Card>
            <CardContent>
              <StatTiles
                latest={series.latest}
                stats={{
                  ...series.stats,
                  count: windowed.length,
                  minimum: minOf(windowed),
                  maximum: maxOf(windowed),
                  mean: meanOf(windowed),
                  first_date: windowed[0]?.date ?? null,
                  last_date: windowed[windowed.length - 1]?.date ?? null,
                }}
                unit={unit}
                frequency={frequency}
                higherIsBetter={summary.higher_is_better}
              />
            </CardContent>
          </Card>

          {/* Chart ------------------------------------------------------ */}
          <Card>
            <CardHeader className="gap-3">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                <ParameterControls
                  parameters={summary.parameters}
                  values={values}
                  onChange={(name, value) =>
                    setValues((current) => ({ ...current, [name]: value }))
                  }
                  disabled={loading}
                />
                <RangeSelector
                  ranges={ranges}
                  value={effectiveRange}
                  onChange={setRangeId}
                />

                <div className="ml-auto flex items-center gap-1">
                  {loading ? (
                    <LoaderCircle
                      aria-label="Loading series"
                      className="mr-1 size-3.5 animate-spin text-muted-foreground"
                    />
                  ) : null}

                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => refresh({ force: true })}
                          disabled={loading}
                          aria-label="Fetch fresh data from Alpha Vantage"
                        >
                          <RefreshCw aria-hidden className="size-3.5" />
                        </Button>
                      }
                    />
                    <TooltipContent className="max-w-60">
                      Bypass the backend cache and fetch live. Uses one of the free
                      tier&apos;s 25 daily Alpha Vantage requests.
                    </TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          render={
                            <a
                              href={csvDownloadUrl(summary.slug, values)}
                              aria-label="Download this series as CSV"
                            />
                          }
                        >
                          <Download aria-hidden className="size-3.5" />
                        </Button>
                      }
                    />
                    <TooltipContent>Download CSV</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </CardHeader>

            <CardContent>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={`${JSON.stringify(values)}-${effectiveRange}`}
                  variants={chartSwap}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                >
                  <SeriesChart
                    data={windowed}
                    unit={unit}
                    frequency={frequency}
                    name={identity?.name ?? summary.name}
                    height={340}
                  />
                </motion.div>
              </AnimatePresence>
            </CardContent>
          </Card>

          {/* Table and provenance --------------------------------------- */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <Card>
              <CardHeader>
                <CardTitle>Historical data</CardTitle>
              </CardHeader>
              <CardContent className="px-2">
                <HistoryTable
                  data={windowed}
                  unit={unit}
                  frequency={frequency}
                  higherIsBetter={summary.higher_is_better}
                />
              </CardContent>
            </Card>

            <Card className="h-fit">
              <CardHeader>
                <CardTitle>About this series</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <dl className="space-y-2.5 text-sm">
                  <Row label="Source">{series.meta.source}</Row>
                  <Row label="Function">
                    <span className="font-mono text-xs">{series.meta.function}</span>
                  </Row>
                  {Object.entries(series.meta.parameters)
                    .filter(([key]) => key !== "function")
                    .map(([key, value]) => (
                      <Row key={key} label={key}>
                        {value}
                      </Row>
                    ))}
                  <Row label="Observations">
                    <span className="tabular">
                      {windowed.length.toLocaleString("en-US")} shown ·{" "}
                      {series.meta.total_available.toLocaleString("en-US")} total
                    </span>
                  </Row>
                  {series.stats.first_date ? (
                    <Row label="Full history">
                      <span className="tabular">
                        {formatObservationDate(series.data[0].date, frequency)} –{" "}
                        {formatObservationDate(
                          series.data[series.data.length - 1].date,
                          frequency,
                        )}
                      </span>
                    </Row>
                  ) : null}
                  <Row label="Retrieved">
                    <span title={series.meta.fetched_at}>
                      {formatRelativeTime(series.meta.fetched_at)}
                      {series.meta.cached
                        ? ` · cached ${formatDuration(series.meta.cache_age_seconds)}`
                        : " · live"}
                    </span>
                  </Row>
                </dl>

                {summary.source_note ? (
                  <>
                    <Separator />
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {summary.source_note}
                    </p>
                  </>
                ) : null}

                <a
                  href={series.meta.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                >
                  Alpha Vantage documentation
                  <ExternalLink aria-hidden className="size-3" />
                </a>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-xs text-muted-foreground capitalize">{label}</dt>
      <dd className="min-w-0 text-right text-xs">{children}</dd>
    </div>
  );
}

function values_(data: { value: number | null }[]): number[] {
  return data
    .map((point) => point.value)
    .filter((value): value is number => value !== null);
}

function minOf(data: { value: number | null }[]): number | null {
  const list = values_(data);
  return list.length ? Math.min(...list) : null;
}

function maxOf(data: { value: number | null }[]): number | null {
  const list = values_(data);
  return list.length ? Math.max(...list) : null;
}

function meanOf(data: { value: number | null }[]): number | null {
  const list = values_(data);
  if (!list.length) return null;
  return list.reduce((total, value) => total + value, 0) / list.length;
}
