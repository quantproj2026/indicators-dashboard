/**
 * Shared Framer Motion primitives.
 *
 * Motion here is deliberately minimal: content fades and rises a few pixels on
 * entry, cards lift almost imperceptibly on hover, and charts tween between
 * datasets. Nothing bounces, nothing springs across the screen, and nothing
 * moves that the user did not ask to move.
 */

import type { Transition, Variants } from "framer-motion";

/** The one easing curve used everywhere. Calm, no overshoot. */
export const EASE = [0.22, 0.61, 0.36, 1] as const;

export const QUICK: Transition = { duration: 0.18, ease: EASE };
export const BASE: Transition = { duration: 0.28, ease: EASE };
export const CALM: Transition = { duration: 0.42, ease: EASE };

/** Fade and rise, for a panel or section entering the viewport. */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: BASE },
};

/** Plain fade, for content that should not move at all. */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: BASE },
};

/**
 * Parent of a grid of cards. Children enter in a quick, shallow cascade --
 * enough to read as ordered, short enough never to delay the data.
 */
export const stagger: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.035, delayChildren: 0.04 },
  },
};

/** A single card within a `stagger` parent. */
export const gridItem: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: BASE },
};

/** Soft scale on card hover. 1.006 is intentionally almost nothing. */
export const cardHover = {
  scale: 1.006,
  transition: QUICK,
} as const;

export const cardTap = {
  scale: 0.998,
  transition: { duration: 0.1, ease: EASE },
} as const;

/** Cross-fade used when a chart swaps to a different parameter set. */
export const chartSwap: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.3, ease: EASE } },
  exit: { opacity: 0, transition: QUICK },
};

/** Expand/collapse for the inline detail panel on the overview grid. */
export const collapse: Variants = {
  hidden: { height: 0, opacity: 0 },
  visible: {
    height: "auto",
    opacity: 1,
    transition: { height: BASE, opacity: { duration: 0.2, delay: 0.06 } },
  },
  exit: {
    height: 0,
    opacity: 0,
    transition: { height: BASE, opacity: { duration: 0.12 } },
  },
};

/** Viewport config for scroll-triggered entrances: fire once, slightly early. */
export const inViewOnce = { once: true, margin: "-40px" } as const;
