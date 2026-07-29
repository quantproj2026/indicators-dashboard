"use client";

import { motion } from "framer-motion";

import { MetricCard } from "@/components/dashboard/metric-card";
import { CATEGORY_META, CATEGORY_ORDER } from "@/lib/indicator-meta";
import { fadeInUp, inViewOnce, stagger } from "@/lib/motion";
import type { Category, IndicatorSnapshot } from "@/lib/types";

/**
 * The overview: every indicator's latest value, grouped by what it measures.
 *
 * Sections appear in a fixed order so a card is always in the same place, and
 * the entrance cascade is short enough that the data is never gated on motion.
 */
export function OverviewGrid({ snapshots }: { snapshots: IndicatorSnapshot[] }) {
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: snapshots.filter((snapshot) => snapshot.indicator.category === category),
  })).filter((group) => group.items.length > 0);

  const ungrouped = snapshots.filter(
    (snapshot) => !CATEGORY_ORDER.includes(snapshot.indicator.category as Category),
  );

  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <section key={group.category} aria-labelledby={`section-${group.category}`}>
          <motion.header
            initial="hidden"
            whileInView="visible"
            viewport={inViewOnce}
            variants={fadeInUp}
            className="mb-3 flex items-baseline gap-3"
          >
            <h2
              id={`section-${group.category}`}
              className="text-sm font-medium tracking-tight"
            >
              {CATEGORY_META[group.category].label}
            </h2>
            <p className="truncate text-xs text-muted-foreground">
              {CATEGORY_META[group.category].blurb}
            </p>
          </motion.header>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={inViewOnce}
            variants={stagger}
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
          >
            {group.items.map((snapshot) => (
              <MetricCard key={snapshot.indicator.slug} snapshot={snapshot} />
            ))}
          </motion.div>
        </section>
      ))}

      {ungrouped.length > 0 ? (
        <motion.div
          initial="hidden"
          animate="visible"
          variants={stagger}
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
        >
          {ungrouped.map((snapshot) => (
            <MetricCard key={snapshot.indicator.slug} snapshot={snapshot} />
          ))}
        </motion.div>
      ) : null}
    </div>
  );
}
