/** Shared hero scroll curves — ghost, glow, robot retreat/return. */

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

/** 0 = center stage, 1 = pushed to side / background */
export function heroRetreat(scrub: number): number {
  const t = clamp01(scrub);
  if (t < 0.24) return 0;
  if (t > 0.8) return 0;
  return Math.sin(((t - 0.24) / 0.56) * Math.PI);
}

/** 0 → 1 through the slam beat (final ~32% of hero scrub) */
export function heroSlam(scrub: number): number {
  const t = clamp01(scrub);
  if (t < 0.68) return 0;
  return (t - 0.68) / 0.32;
}

/** Large ORQIS watermark — intro only */
export function introGhostOpacity(scrub: number): number {
  if (scrub > 0.34) return 0;
  return Math.max(0, 0.17 * (1 - scrub / 0.34));
}

/** Scroll-story ghost word peak opacity multiplier */
export const SCROLL_GHOST_PEAK = 0.09;

/** Purple floor / portal glow multiplier */
export function heroFloorGlow(scrub: number): number {
  const retreat = heroRetreat(scrub);
  const slam = heroSlam(scrub);
  return Math.max(0.04, 1 - retreat * 0.96 + slam * 0.42);
}

/** Robot rail opacity — dips mid-scroll, returns for slam */
export function heroRobotPresence(scrub: number): number {
  const retreat = heroRetreat(scrub);
  const slam = heroSlam(scrub);
  return clamp01(1 - retreat * 0.52 + slam * 0.65);
}

/** Horizontal rail shift in vw — positive = move right */
export function heroRailShiftVw(scrub: number): number {
  const retreat = heroRetreat(scrub);
  const slam = heroSlam(scrub);
  return retreat * 24 * (1 - slam);
}

/** Tendril legibility — dim when robot is in front of copy */
export function heroTendrilLegibility(scrub: number): number {
  const retreat = heroRetreat(scrub);
  const slam = heroSlam(scrub);
  return clamp01(0.55 + retreat * 0.35 + slam * 0.25);
}

/** Post-hero: bold robot silhouette in scroll corridor */
export function guideRobotBackground(_progress: number, corridorBlend: number) {
  const t = clamp01(corridorBlend);
  return {
    opacity: clamp01(0.62 - t * 0.08),
    scale: 0.72 - t * 0.08,
    shiftVw: 0,
    blur: 0,
    brightness: 0.96,
  };
}

/** Footer finale — full-brightness robot returns center */
export function measureFinaleReveal(): number {
  if (typeof window === "undefined") return 0;
  const el = document.getElementById("finale-cta");
  if (!el) return 0;
  const rect = el.getBoundingClientRect();
  const vh = window.innerHeight;
  if (rect.bottom < vh * 0.2) return 0;
  if (rect.top <= vh * 0.38) return 1;
  if (rect.top >= vh * 0.92) return 0;
  return clamp01(1 - (rect.top - vh * 0.38) / (vh * 0.54));
}

export type RobotRailPose = {
  leftPct: number;
  opacity: number;
  scale: number;
  blur: number;
  brightness: number;
  zIndex: number;
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

/** Resolve sticky rail transform for guide + finale beats */
export function resolveRobotRailPose(
  guide: ReturnType<typeof guideRobotBackground>,
  finale: number
): RobotRailPose {
  if (finale <= 0.02) {
    return {
      leftPct: 52,
      opacity: guide.opacity,
      scale: guide.scale,
      blur: guide.blur,
      brightness: guide.brightness,
      zIndex: 2,
    };
  }
  const t = finale * finale * (3 - 2 * finale);
  return {
    leftPct: lerp(72, 50, t),
    opacity: lerp(guide.opacity, 1, t),
    scale: lerp(guide.scale, 1, t),
    blur: lerp(guide.blur, 0, t),
    brightness: lerp(guide.brightness, 1, t),
    zIndex: t > 0.35 ? 4 : 1,
  };
}
