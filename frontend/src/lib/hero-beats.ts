import { hero, incidentFilm } from "@/lib/marketing-copy";
import { colors } from "@/lib/tokens";

export type HeroOpsPanel = {
  id: string;
  label: string;
  status: string;
  detail: string;
  accent: string;
  top: string;
  right: string;
};

export type HeroBeat = {
  at: number;
  kicker: string;
  sub: string;
  tint: string;
  activePanel: number;
};

/** Stable left-column copy — does not swap on scroll */
export const HERO_COPY = {
  line1: "Agents break",
  line2: "in prod.",
  tagline: "Orqis ships the fix.",
  taglineAccent: colors.green,
};

export const HERO_OPS_PANELS: HeroOpsPanel[] = [
  {
    id: "detect",
    label: "refund-agent",
    status: "RUNAWAY_LOOP",
    detail: "refund_agent.py:21",
    accent: colors.amber,
    top: "16%",
    right: "2%",
  },
  {
    id: "burn",
    label: "cost-meter",
    status: "$0.55/s",
    detail: "api burn rate",
    accent: colors.amber,
    top: "34%",
    right: "7%",
  },
  {
    id: "patch",
    label: "validator",
    status: "PATCHED",
    detail: "94/100 confidence",
    accent: colors.green,
    top: "52%",
    right: "3%",
  },
  {
    id: "ship",
    label: "orqis/fix-loop",
    status: "PR #1",
    detail: "review on GitHub",
    accent: colors.github,
    top: "68%",
    right: "8%",
  },
];

export const HERO_BEATS: HeroBeat[] = [
  {
    at: 0,
    kicker: "01 · Detect",
    sub: hero.sub,
    tint: colors.glow,
    activePanel: 0,
  },
  {
    at: 0.24,
    kicker: "02 · Contain",
    sub: incidentFilm[1].sub,
    tint: colors.amber,
    activePanel: 1,
  },
  {
    at: 0.48,
    kicker: "03 · Patch",
    sub: incidentFilm[2].sub,
    tint: colors.green,
    activePanel: 2,
  },
  {
    at: 0.72,
    kicker: "04 · Ship",
    sub: incidentFilm[3].sub,
    tint: colors.github,
    activePanel: 3,
  },
];

export function resolveHeroBeat(scrub: number): HeroBeat {
  let beat = HERO_BEATS[0];
  for (const b of HERO_BEATS) {
    if (scrub >= b.at) beat = b;
  }
  return beat;
}

export function beatBlend(scrub: number): number {
  const beat = resolveHeroBeat(scrub);
  const idx = HERO_BEATS.indexOf(beat);
  const next = HERO_BEATS[idx + 1];
  if (!next) return 1;
  const span = next.at - beat.at;
  if (span <= 0) return 1;
  return Math.max(0, Math.min(1, (scrub - beat.at) / span));
}
