/**
 * WebGL capability tiers for adaptive rendering.
 *
 * `narrow` (width < 768) affects GPU quality only.
 * Landing *layout* / nav breakpoints use 900px — see `layout-breakpoint.ts`.
 * Do not conflate layout width with WebGL tier.
 */

export type DeviceTier = "high" | "mid" | "low";

export type TierConfig = {
  tier: DeviceTier;
  fluidSim: boolean;
  postFx: boolean;
  loopNodes: number;
  pixelRatio: number;
  robotCanvas: boolean;
};

function getGpuTier(): number {
  if (typeof window === "undefined") return 1;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return 0;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    if (!dbg) return 1;
    const renderer = (gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) as string).toLowerCase();
    if (/swiftshader|llvmpipe|basic render/.test(renderer)) return 0;
    if (/intel|hd graphics|uhd|iris/.test(renderer)) return 1;
    if (/apple m|nvidia|geforce|radeon|rx |rtx |arc /.test(renderer)) return 2;
    return 1;
  } catch {
    return 1;
  }
}

export function detectDeviceTier(): DeviceTier {
  if (typeof window === "undefined") return "mid";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) return "low";

  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  const cores = navigator.hardwareConcurrency ?? 4;
  const gpu = getGpuTier();
  const narrow = window.innerWidth < 768;

  if (gpu === 0 || mem < 3 || (narrow && gpu < 2)) return "low";
  if (gpu >= 2 && mem >= 6 && cores >= 6 && !narrow) return "high";
  return "mid";
}

export function tierConfig(tier: DeviceTier): TierConfig {
  switch (tier) {
    case "high":
      return { tier, fluidSim: true, postFx: true, loopNodes: 120, pixelRatio: 2, robotCanvas: true };
    case "mid":
      return { tier, fluidSim: false, postFx: true, loopNodes: 72, pixelRatio: 1.5, robotCanvas: true };
    case "low":
      return { tier, fluidSim: false, postFx: false, loopNodes: 36, pixelRatio: 1, robotCanvas: true };
  }
}
