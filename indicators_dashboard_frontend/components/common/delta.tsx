import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

type Tone = "positive" | "negative" | "neutral";

/**
 * Decide how a change should read.
 *
 * Direction alone is not meaning: unemployment rising is bad, payrolls rising
 * is good, and a Treasury yield moving is neither. `higherIsBetter` comes from
 * the backend catalog and is `null` where the sign carries no verdict, in which
 * case the figure stays in neutral ink.
 */
function toneFor(change: number, higherIsBetter: boolean | null): Tone {
  if (change === 0 || higherIsBetter === null) return "neutral";
  const rising = change > 0;
  return rising === higherIsBetter ? "positive" : "negative";
}

const TONE_CLASS: Record<Tone, string> = {
  positive: "text-positive",
  negative: "text-negative",
  neutral: "text-muted-foreground",
};

export interface DeltaProps {
  /** Signed change, used for direction. */
  change: number | null | undefined;
  /** Pre-formatted text, e.g. `+0.20 pp` or `+1.42%`. */
  label: string;
  higherIsBetter?: boolean | null;
  /** What the change is measured against, rendered after the figure. */
  suffix?: string;
  size?: "sm" | "md";
  className?: string;
}

/**
 * A signed change figure.
 *
 * Direction is carried three ways -- arrow glyph, explicit sign, and colour --
 * so the meaning survives for a colourblind reader and in monochrome print.
 */
export function Delta({
  change,
  label,
  higherIsBetter = null,
  suffix,
  size = "sm",
  className,
}: DeltaProps) {
  if (change === null || change === undefined || Number.isNaN(change)) {
    return (
      <span
        className={cn(
          "text-muted-foreground",
          size === "sm" ? "text-xs" : "text-sm",
          className,
        )}
      >
        --
      </span>
    );
  }

  const tone = toneFor(change, higherIsBetter);
  const Icon = change > 0 ? ArrowUpRight : change < 0 ? ArrowDownRight : Minus;

  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1 whitespace-nowrap",
        size === "sm" ? "text-xs" : "text-sm",
        className,
      )}
    >
      <span className={cn("inline-flex items-center gap-0.5 tabular", TONE_CLASS[tone])}>
        <Icon
          aria-hidden
          className={cn("translate-y-px", size === "sm" ? "size-3" : "size-3.5")}
        />
        {label}
      </span>
      {suffix ? <span className="text-muted-foreground">{suffix}</span> : null}
    </span>
  );
}
