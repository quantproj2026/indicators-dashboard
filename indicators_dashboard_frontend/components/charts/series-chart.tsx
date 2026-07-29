"use client";

import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  formatAxisDate,
  formatAxisValue,
  formatChange,
  formatObservationDate,
  formatValue,
  spansMultipleYears,
} from "@/lib/format";
import { decimate, pickTicks, valueDomain, windowMean } from "@/lib/series";
import type { Frequency, Observation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SeriesChartProps {
  data: Observation[];
  unit: string;
  frequency: Frequency;
  /** Series name, used in the accessible description. */
  name: string;
  showMean?: boolean;
  height?: number;
  className?: string;
}

/**
 * The detail view's time-series chart.
 *
 * Deliberately single-series: one steel-blue line over a wash of the same hue.
 * With one series there is nothing to tell apart, so no legend is needed and no
 * second colour is introduced -- the panel heading already names what is
 * plotted. Comparisons across parameters are made by switching the controls,
 * which keeps every chart to one colour.
 */
export function SeriesChart({
  data,
  unit,
  frequency,
  name,
  showMean = true,
  height = 320,
  className,
}: SeriesChartProps) {
  const gradientId = useId();

  const { points, ticks, domain, mean, multiYear, last } = useMemo(() => {
    const rendered = decimate(data);
    const valued = rendered.filter((point) => point.value !== null);
    return {
      points: rendered,
      ticks: pickTicks(rendered),
      domain: valueDomain(rendered),
      mean: showMean ? windowMean(rendered) : null,
      multiYear: spansMultipleYears(rendered),
      last: valued[valued.length - 1] ?? null,
    };
  }, [data, showMean]);

  if (points.length < 2) {
    return (
      <div
        style={{ height }}
        className={cn(
          "flex items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground",
          className,
        )}
      >
        Not enough observations to plot.
      </div>
    );
  }

  return (
    <figure className={cn("w-full", className)}>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
            <defs>
              {/* One hue fading to transparent -- a wash under the line, not a
                  decorative gradient between two colours. */}
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series)" stopOpacity={0.18} />
                <stop offset="100%" stopColor="var(--series)" stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="var(--grid)"
              strokeWidth={1}
              vertical={false}
            />

            <XAxis
              dataKey="date"
              ticks={ticks}
              tickFormatter={(value: string) =>
                formatAxisDate(value, frequency, multiYear)
              }
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--axis)" }}
              tickMargin={8}
              minTickGap={12}
            />

            <YAxis
              domain={domain}
              tickFormatter={(value: number) => formatAxisValue(value, unit)}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={56}
              tickCount={6}
              orientation="right"
            />

            {mean !== null ? (
              <ReferenceLine
                y={mean}
                stroke="var(--axis)"
                strokeWidth={1}
                strokeDasharray="4 4"
                label={{
                  value: `mean ${formatAxisValue(mean, unit)}`,
                  position: "insideTopLeft",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                }}
              />
            ) : null}

            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              isAnimationActive={false}
              content={
                <ChartTooltip unit={unit} frequency={frequency} points={points} />
              }
            />

            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--series)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill={`url(#${gradientId})`}
              connectNulls={false}
              dot={false}
              activeDot={{
                r: 4,
                fill: "var(--series)",
                stroke: "var(--card)",
                strokeWidth: 2,
              }}
              animationDuration={420}
              animationEasing="ease-out"
            />

            {last ? (
              // The 2px ring in the surface colour keeps the marker legible
              // where it sits on top of the line.
              <ReferenceDot
                x={last.date}
                y={last.value as number}
                r={4}
                fill="var(--series)"
                stroke="var(--card)"
                strokeWidth={2}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <figcaption className="sr-only">
        {name} from {formatObservationDate(points[0].date, frequency)} to{" "}
        {formatObservationDate(points[points.length - 1].date, frequency)}, measured in{" "}
        {unit}. The full data is available in the table below the chart.
      </figcaption>
    </figure>
  );
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: Observation }>;
  unit: string;
  frequency: Frequency;
  points: Observation[];
}

/**
 * Crosshair readout: the value at the cursor plus its change from the previous
 * observation, so the tooltip answers "what moved" and not only "what is it".
 */
function ChartTooltip({ active, payload, unit, frequency, points }: TooltipProps) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  if (point.value === null) {
    return (
      <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-xs shadow-md">
        <p className="text-muted-foreground">
          {formatObservationDate(point.date, frequency)}
        </p>
        <p className="mt-0.5">No observation reported</p>
      </div>
    );
  }

  const index = points.findIndex((candidate) => candidate.date === point.date);
  let previous: Observation | undefined;
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (points[cursor].value !== null) {
      previous = points[cursor];
      break;
    }
  }
  const change =
    previous?.value != null ? point.value - previous.value : null;

  return (
    <div className="min-w-40 rounded-md border border-border bg-popover px-2.5 py-2 shadow-md">
      <p className="text-[11px] text-muted-foreground">
        {formatObservationDate(point.date, frequency)}
      </p>
      <p className="mt-0.5 flex items-baseline gap-1.5">
        <span
          aria-hidden
          className="size-2 shrink-0 translate-y-px rounded-full bg-series"
        />
        <span className="text-sm font-medium tabular">
          {formatValue(point.value, unit, { precise: true })}
        </span>
      </p>
      {change !== null ? (
        <p className="mt-1 border-t border-border pt-1 text-[11px] text-muted-foreground tabular">
          {formatChange(change, unit)} from prior
        </p>
      ) : null}
    </div>
  );
}
