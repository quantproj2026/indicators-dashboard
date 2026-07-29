import { Delta } from "@/components/common/delta";
import {
  formatChange,
  formatObservationDate,
  formatPercent,
  formatValue,
  periodLabel,
} from "@/lib/format";
import type { Frequency, Latest, SeriesStats } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The figure row beneath an indicator's title.
 *
 * Headline value, its two changes, and the window's extremes -- the four things
 * a reader wants before they look at the chart shape.
 */
export function StatTiles({
  latest,
  stats,
  unit,
  frequency,
  higherIsBetter,
  className,
}: {
  latest: Latest | null;
  stats: SeriesStats;
  unit: string;
  frequency: Frequency;
  higherIsBetter: boolean | null;
  className?: string;
}) {
  return (
    <dl
      className={cn(
        "grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-5",
        className,
      )}
    >
      <Tile label="Latest">
        {latest ? (
          <>
            <span className="text-2xl leading-none font-semibold tracking-tight">
              {formatValue(latest.value, unit)}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              {formatObservationDate(latest.date, frequency)}
            </span>
          </>
        ) : (
          <span className="text-2xl leading-none font-semibold">--</span>
        )}
      </Tile>

      <Tile label={`vs ${periodLabel(frequency)}`}>
        <Delta
          size="md"
          change={latest?.change ?? null}
          label={formatChange(latest?.change ?? null, unit)}
          higherIsBetter={higherIsBetter}
          className="font-medium"
        />
        <span className="mt-1 block text-xs text-muted-foreground tabular">
          {latest?.change_percent !== null && latest?.change_percent !== undefined
            ? formatPercent(latest.change_percent)
            : "--"}
        </span>
      </Tile>

      <Tile label="Year over year">
        <Delta
          size="md"
          change={latest?.year_over_year_change ?? null}
          label={formatPercent(latest?.year_over_year_percent ?? null)}
          higherIsBetter={higherIsBetter}
          className="font-medium"
        />
        <span className="mt-1 block text-xs text-muted-foreground tabular">
          {latest?.year_ago_value !== null && latest?.year_ago_value !== undefined
            ? `from ${formatValue(latest.year_ago_value, unit)}`
            : "no comparable period"}
        </span>
      </Tile>

      <Tile label="Window low">
        <span className="text-sm font-medium tabular">
          {formatValue(stats.minimum, unit)}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground">
          {/* Describes the window the extremes were taken over -- not the date
              the low itself occurred, which this figure does not claim. */}
          {stats.first_date
            ? `since ${formatObservationDate(stats.first_date, frequency)}`
            : "--"}
        </span>
      </Tile>

      <Tile label="Window high">
        <span className="text-sm font-medium tabular">
          {formatValue(stats.maximum, unit)}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground tabular">
          mean {formatValue(stats.mean, unit)}
        </span>
      </Tile>
    </dl>
  );
}

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="mt-1.5">{children}</dd>
    </div>
  );
}
