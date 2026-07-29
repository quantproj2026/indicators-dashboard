"use client";

import { useId } from "react";
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

import type { Observation } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The trend strip on a metric card.
 *
 * No axes, no grid, no tooltip -- it exists to show shape, and the card's
 * figures carry the values. The final observation gets a solid marker so the
 * eye lands on "now" rather than on the middle of the window.
 */
export function Sparkline({
  data,
  className,
  height = 40,
}: {
  data: Observation[];
  className?: string;
  height?: number;
}) {
  const gradientId = useId();
  const points = data.filter((point) => point.value !== null);

  if (points.length < 2) {
    return <div style={{ height }} className={className} aria-hidden />;
  }

  const values = points.map((point) => point.value as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series would otherwise collapse onto the top edge of the box.
  const pad = (max - min || Math.abs(max) || 1) * 0.15;

  return (
    <div className={cn("w-full", className)} style={{ height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 3, right: 3, bottom: 3, left: 3 }}>
          <defs>
            {/* A single-hue wash, not a decorative gradient: it fades one
                colour to transparent so the line stays the only hard edge. */}
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series)" stopOpacity={0.16} />
              <stop offset="100%" stopColor="var(--series)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={[min - pad, max + pad]} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--series)"
            strokeWidth={1.75}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
            dot={false}
            activeDot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
