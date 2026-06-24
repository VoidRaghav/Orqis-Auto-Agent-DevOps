/** Section-aware flow phases — guide lasts through Features, corridor at dashboard handoff. */

import type { FlowPhase } from "@/components/RobotFlowContext";

export type FlowPhaseState = {
  phase: FlowPhase;
  /** 0 = full guide robot, 1 = robot fully handed off to corridor */
  corridorBlend: number;
};

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

/** Scroll-derived hero scrub — works without GSAP / reduced-motion. */
export function measureHeroScrub(): number {
  if (typeof window === "undefined") return 0;
  const el = document.querySelector(".cinematic-hero-scroll");
  if (!el) return 0;
  const rect = el.getBoundingClientRect();
  const span = rect.height - window.innerHeight;
  if (span <= 8) return rect.top <= 0 ? 1 : 0;
  return clamp01(-rect.top / span);
}

/** True once the pinned hero scroll region has been passed. */
export function isPastHeroPin(heroScrub: number): boolean {
  if (heroScrub >= 0.99) return true;
  if (typeof window === "undefined") return false;
  const el = document.querySelector(".cinematic-hero-scroll");
  if (!el) return heroScrub >= 0.99;
  return el.getBoundingClientRect().bottom < window.innerHeight * 0.52;
}

export function resolveFlowPhase(heroScrub: number): FlowPhaseState {
  if (!isPastHeroPin(heroScrub)) {
    return { phase: "hero", corridorBlend: 0 };
  }

  if (typeof window === "undefined") {
    return { phase: "guide", corridorBlend: 0 };
  }

  const mission = document.getElementById("mission-control");
  if (!mission) {
    return { phase: "guide", corridorBlend: 0 };
  }

  const rect = mission.getBoundingClientRect();
  const vh = window.innerHeight;
  const startFade = vh * 0.92;
  const endFade = vh * 0.38;

  if (rect.top >= startFade) {
    return { phase: "guide", corridorBlend: 0 };
  }

  if (rect.top <= endFade) {
    return { phase: "corridor", corridorBlend: 1 };
  }

  const blend = 1 - (rect.top - endFade) / (startFade - endFade);
  return { phase: "guide", corridorBlend: clamp01(blend) };
}
