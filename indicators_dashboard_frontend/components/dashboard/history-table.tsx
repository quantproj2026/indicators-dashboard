"use client";

import { useMemo, useState } from "react";

import { Delta } from "@/components/common/delta";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatChange,
  formatObservationDate,
  formatPercent,
  formatValue,
} from "@/lib/format";
import type { Frequency, Observation } from "@/lib/types";

const PAGE_SIZE = 25;

interface HistoryTableProps {
  /** Observations in the visible window, oldest first. */
  data: Observation[];
  unit: string;
  frequency: Frequency;
  higherIsBetter: boolean | null;
}

interface Row {
  date: string;
  value: number | null;
  change: number | null;
  changePercent: number | null;
}

/**
 * The numbers behind the chart.
 *
 * Newest first, because that is the order a reader scans for "what just
 * happened". Change columns are computed against the previous *reported*
 * observation, skipping gaps, so a holiday in a daily series does not produce a
 * spurious zero.
 */
export function HistoryTable({
  data,
  unit,
  frequency,
  higherIsBetter,
}: HistoryTableProps) {
  const [visible, setVisible] = useState(PAGE_SIZE);

  const rows = useMemo<Row[]>(() => {
    const ascending = [...data].sort((a, b) => a.date.localeCompare(b.date));
    const built: Row[] = [];

    let previous: number | null = null;
    for (const point of ascending) {
      const change =
        point.value !== null && previous !== null ? point.value - previous : null;
      const changePercent =
        change !== null && previous !== null && previous !== 0
          ? (change / Math.abs(previous)) * 100
          : null;

      built.push({
        date: point.date,
        value: point.value,
        change,
        changePercent,
      });

      if (point.value !== null) previous = point.value;
    }

    return built.reverse();
  }, [data]);

  if (rows.length === 0) {
    return (
      <p className="px-1 py-6 text-sm text-muted-foreground">
        No observations in this window.
      </p>
    );
  }

  const shown = rows.slice(0, visible);
  const remaining = rows.length - shown.length;

  return (
    <div>
      <div className="max-h-115 overflow-y-auto">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-1/3 text-xs font-medium text-muted-foreground">
                Period
              </TableHead>
              <TableHead className="text-right text-xs font-medium text-muted-foreground">
                Value
              </TableHead>
              <TableHead className="text-right text-xs font-medium text-muted-foreground">
                Change
              </TableHead>
              <TableHead className="text-right text-xs font-medium text-muted-foreground">
                %
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow key={row.date}>
                <TableCell className="text-sm text-muted-foreground">
                  {formatObservationDate(row.date, frequency)}
                </TableCell>
                <TableCell className="text-right text-sm font-medium tabular">
                  {row.value === null
                    ? "--"
                    : formatValue(row.value, unit, { precise: true })}
                </TableCell>
                <TableCell className="text-right">
                  <Delta
                    change={row.change}
                    label={formatChange(row.change, unit)}
                    higherIsBetter={higherIsBetter}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <Delta
                    change={row.change}
                    label={formatPercent(row.changePercent)}
                    higherIsBetter={higherIsBetter}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {remaining > 0 ? (
        <div className="flex items-center justify-between border-t border-border px-2 pt-3">
          <p className="text-xs text-muted-foreground tabular">
            Showing {shown.length} of {rows.length} observations
          </p>
          <Button
            variant="outline"
            size="xs"
            onClick={() => setVisible((current) => current + PAGE_SIZE * 4)}
          >
            Show {Math.min(remaining, PAGE_SIZE * 4)} more
          </Button>
        </div>
      ) : (
        <p className="border-t border-border px-2 pt-3 text-xs text-muted-foreground tabular">
          {rows.length} observation{rows.length === 1 ? "" : "s"} in this window
        </p>
      )}
    </div>
  );
}
