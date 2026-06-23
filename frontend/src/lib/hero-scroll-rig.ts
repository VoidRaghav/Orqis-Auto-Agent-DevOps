/** Slam-dunk hero scroll rig — wind-up, retreat, slam arc on centered robot. */

import {
  heroFloorGlow,
  heroRetreat,
  heroRobotPresence,
  heroSlam,
} from "@/lib/hero-choreography";

export type ScrollRigState = {
  posX: number;
  posY: number;
  posZ: number;
  rotY: number;
  rotX: number;
  scale: number;
  glowScale: number;
  eyeIntensity: number;
  portalFlash: number;
  formation: number;
  retreat: number;
  floorGlow: number;
  robotAlpha: number;
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function sampleKeyframe(scrub: number): ScrollRigState {
  const t = easeInOut(Math.max(0, Math.min(1, scrub)));
  const retreat = heroRetreat(scrub);
  const slam = heroSlam(scrub);
  const slamEased = easeInOut(slam);
  const arc = Math.sin(slamEased * Math.PI);

  const posX = retreat * 0.5 * (1 - slam) + slam * lerp(0.14, 0, slamEased);
  const posY =
    retreat * -0.1 +
    slam * lerp(0.26, -0.52, slamEased) +
    arc * 0.14 * slam;
  const posZ = lerp(0.04, -0.16, retreat) + slam * lerp(-0.08, 0.1, slamEased);

  const rotY = retreat * -0.38 + slam * lerp(-0.75, 0.26, slamEased);
  const rotX = retreat * 0.05 + slam * (0.1 + arc * 0.06);

  const idleScale = 1 - retreat * 0.22;
  const slamScale = slam > 0 ? lerp(idleScale, lerp(1.16, 1.02, slamEased), slam) : idleScale;
  const scale = slamScale;

  const floorGlow = heroFloorGlow(scrub);
  const glowScale = (1 + arc * 0.2 * slam) * floorGlow;
  const eyeIntensity =
    1.45 +
    retreat * 0.15 +
    slam * (0.55 + arc * 0.45) +
    (t > 0.52 && t < 0.66 ? 0.2 : 0);
  const portalFlash = slam > 0 ? Math.pow(slam, 0.65) * 0.85 : 0;
  const formation = Math.min(1, Math.pow(t, 0.72) * 1.25) * (1 - retreat * 0.35 + slam * 0.35);

  return {
    posX,
    posY,
    posZ,
    rotY,
    rotX,
    scale,
    glowScale,
    eyeIntensity,
    portalFlash,
    formation,
    retreat,
    floorGlow,
    robotAlpha: heroRobotPresence(scrub),
  };
}

export function guideBodyOffset(
  target: { nx: number; ny: number },
  strength: number
): { x: number; y: number } {
  const pull = Math.min(1, strength * 1.5);
  const x = Math.max(-0.28, Math.min(0.28, (0.5 - target.nx) * 0.72 * pull));
  const y = (target.ny - 0.44) * -0.28 * pull;
  return { x, y };
}

export function scrollAliveDrift(
  progress: number,
  phase: string,
  time: number,
  reducedMotion: boolean
): { x: number; y: number } {
  if (reducedMotion) return { x: 0, y: 0 };

  const scrollSway = Math.sin(progress * Math.PI * 5.5) * 0.16;
  const scrollSway2 = Math.sin(progress * Math.PI * 2.2 + 0.6) * 0.06;
  const breatheX = Math.sin(time * 0.7) * 0.04;
  const breatheY = Math.sin(time * 0.48 + 1.1) * 0.022;

  const boost =
    phase === "guide" ? 0.18 :
    phase === "hero" ? 0.2 :
    0.35;

  return {
    x: (scrollSway + scrollSway2 + breatheX) * boost,
    y: (breatheY + Math.sin(progress * Math.PI * 3) * 0.025) * boost,
  };
}

export function applyHeroScrollRig(scrub: number, reducedMotion: boolean): ScrollRigState {
  if (reducedMotion) {
    return {
      posX: 0, posY: 0, posZ: 0, rotY: 0, rotX: 0,
      scale: 1, glowScale: 0.35, eyeIntensity: 1.5, portalFlash: 0, formation: 0.65,
      retreat: 0, floorGlow: 0.35, robotAlpha: 1,
    };
  }
  return sampleKeyframe(scrub);
}

export function applyGuideScrollRig(corridorBlend: number): ScrollRigState {
  return {
    posX: 0.1 + corridorBlend * 0.06,
    posY: -0.06 - corridorBlend * 0.03,
    posZ: -0.08,
    rotY: -0.12,
    rotX: 0,
    scale: 0.74 - corridorBlend * 0.08,
    glowScale: 0.22,
    eyeIntensity: 1.65,
    portalFlash: 0,
    formation: 0.12,
    retreat: 0.35,
    floorGlow: 0.18,
    robotAlpha: 0.78,
  };
}

export function applyFinaleScrollRig(t: number): ScrollRigState {
  const e = t * t * (3 - 2 * t);
  return {
    posX: 0,
    posY: -0.04,
    posZ: 0.05,
    rotY: 0,
    rotX: 0,
    scale: 0.92 + e * 0.1,
    glowScale: 0.65 + e * 0.45,
    eyeIntensity: 1.75 + e * 0.35,
    portalFlash: e * 0.35,
    formation: 0.55 + e * 0.35,
    retreat: 0,
    floorGlow: 0.55 + e * 0.45,
    robotAlpha: 0.88 + e * 0.12,
  };
}

export function blendScrollRigs(a: ScrollRigState, b: ScrollRigState, t: number): ScrollRigState {
  const mix = (ka: keyof ScrollRigState) => lerp(a[ka], b[ka], t);
  return {
    posX: mix("posX"),
    posY: mix("posY"),
    posZ: mix("posZ"),
    rotY: mix("rotY"),
    rotX: mix("rotX"),
    scale: mix("scale"),
    glowScale: mix("glowScale"),
    eyeIntensity: mix("eyeIntensity"),
    portalFlash: mix("portalFlash"),
    formation: mix("formation"),
    retreat: mix("retreat"),
    floorGlow: mix("floorGlow"),
    robotAlpha: mix("robotAlpha"),
  };
}

export function robotBodyOpacity(phase: string, corridorBlend: number): number {
  if (phase === "corridor") return Math.max(0.04, 0.9 - corridorBlend * 0.88);
  if (phase === "guide") return 1 - corridorBlend * 0.12;
  return 1;
}
