"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { parameterValueDescription, parameterValueLabel } from "@/lib/format";
import type { ParameterSpec } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ParameterControlsProps {
  /** Parameters this indicator supports, straight from the backend catalog. */
  parameters: ParameterSpec[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Controls for the upstream parameters an indicator accepts.
 *
 * Which controls exist, and which values each offers, is read from the backend
 * catalog rather than hard-coded -- so the UI can never offer a `maturity` that
 * Alpha Vantage would silently ignore, and a new allowed value appears here as
 * soon as the API advertises it.
 *
 * Short option lists become a segmented control (all choices visible at once);
 * longer ones become a select, so the row never wraps.
 */
export function ParameterControls({
  parameters,
  values,
  onChange,
  disabled = false,
  className,
}: ParameterControlsProps) {
  if (parameters.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-x-5 gap-y-3", className)}>
      {parameters.map((parameter) => {
        const current = values[parameter.name] ?? parameter.default;
        const labelId = `param-${parameter.name}`;

        return (
          <div key={parameter.name} className="flex items-center gap-2">
            <span
              id={labelId}
              className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
            >
              {parameter.name}
            </span>

            {parameter.allowed.length <= 3 ? (
              <ToggleGroup
                aria-labelledby={labelId}
                value={[current]}
                onValueChange={(next) => {
                  // Single-select: an empty array means the active item was
                  // pressed again. Keep the current value rather than clearing.
                  if (next.length > 0) onChange(parameter.name, next[0]);
                }}
                disabled={disabled}
                spacing={0}
                variant="outline"
                size="sm"
              >
                {parameter.allowed.map((option) => (
                  <ToggleGroupItem
                    key={option}
                    value={option}
                    aria-label={parameterValueDescription(parameter.name, option)}
                  >
                    {parameterValueLabel(parameter.name, option)}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            ) : (
              <Select
                value={current}
                onValueChange={(next) => {
                  if (typeof next === "string") onChange(parameter.name, next);
                }}
                disabled={disabled}
                // Without this the trigger would show the raw upstream value
                // (`10year`) instead of the label used in the menu.
                items={Object.fromEntries(
                  parameter.allowed.map((option) => [
                    option,
                    parameterValueDescription(parameter.name, option),
                  ]),
                )}
              >
                <SelectTrigger size="sm" aria-labelledby={labelId} className="min-w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {parameter.allowed.map((option) => (
                    <SelectItem key={option} value={option}>
                      {parameterValueDescription(parameter.name, option)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        );
      })}
    </div>
  );
}
