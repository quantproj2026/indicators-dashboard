"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { RangePreset } from "@/lib/series";

/**
 * Window presets above the chart.
 *
 * Ranges that would leave fewer than two observations are filtered out by the
 * caller, so every option shown draws something.
 */
export function RangeSelector({
  ranges,
  value,
  onChange,
  disabled = false,
}: {
  ranges: RangePreset[];
  value: string;
  onChange: (rangeId: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        id="range-label"
        className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
      >
        Range
      </span>
      <ToggleGroup
        aria-labelledby="range-label"
        value={[value]}
        onValueChange={(next) => {
          if (next.length > 0) onChange(next[0]);
        }}
        disabled={disabled}
        spacing={0}
        variant="outline"
        size="sm"
      >
        {ranges.map((range) => (
          <ToggleGroupItem key={range.id} value={range.id} aria-label={range.description}>
            {range.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
