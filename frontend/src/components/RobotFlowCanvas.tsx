"use client";

import { useEffect, useRef } from "react";
import { resolveAllPaths2D } from "@/lib/flow-paths";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";

export default function RobotFlowCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);
  const flow = useRobotFlowOptional();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !flow) return;

    const {
      progressRef,
      tintRef,
      anchorsRef,
      hubXRef,
      phaseRef,
      corridorBlendRef,
      heroScrubRef,
      visualPresetRef,
    } = flow;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const draw = () => {
      const dpr = Math.min(window.devicePixelRatio, 2);
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const progress = progressRef.current ?? 0;
      const phase = phaseRef.current ?? "hero";
      const visualPreset = visualPresetRef?.current ?? "hero";
      const corridorBlend = corridorBlendRef.current ?? 0;
      const heroScrub = heroScrubRef.current ?? 0;

      if (visualPreset !== "hero" && phase !== "hero") {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }
      /* Hero tendrils removed — keep canvas clear during hero scroll */
      if (phase === "hero") {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const tint = tintRef.current ?? "#00e5ff";
      const time = reducedMotion ? 0 : performance.now() * 0.001;

      const blend =
        progress < 0.02 ? 0 :
        progress < 0.14 ? (progress - 0.02) / 0.12 :
        1;

      const formation = Math.min(1, Math.pow(heroScrub, 0.72) * 1.25);
      const hubX = w * 0.5;
      const paths = resolveAllPaths2D(anchorsRef.current, w, h, progress, time, hubX, formation);

      ctx.save();
      const clipFrac =
        phase === "guide"
          ? 0.22
          : 0.3 + corridorBlend * 0.04;
      const clipX = w * clipFrac;
      ctx.beginPath();
      ctx.rect(clipX, 0, w - clipX, h);
      ctx.clip();

      const heroFade =
        progress < 0.14
          ? 0.28 + blend * 0.22
          : 0.46 + (progress - 0.14) * 0.03;

      const phaseScale =
        phase === "guide" ? 0.88 - corridorBlend * 0.25 :
        0.42 - corridorBlend * 0.1;

      const dashTravel = reducedMotion ? 0 : progress * 1.1;

      for (const path of paths) {
        const isWisp = path.tier === "wisp";
        if (isWisp && progress < 0.15) continue;

        const baseAlpha = isWisp ? 0.22 : 0.38;
        const alpha = baseAlpha * heroFade * phaseScale;

        ctx.beginPath();
        ctx.moveTo(path.x0, path.y0);
        ctx.bezierCurveTo(path.x1, path.y1, path.x2, path.y2, path.x3, path.y3);

        const len = estimateBezierLength(path);
        const dashLen = len * 0.28;
        const gap = len * 0.32;
        ctx.setLineDash([dashLen, gap]);
        ctx.lineDashOffset = -dashTravel * len * 1.1;

        ctx.strokeStyle = tint;
        ctx.lineWidth = path.width + 8;
        ctx.globalAlpha = alpha * 0.14;
        ctx.filter = "blur(6px)";
        ctx.stroke();

        ctx.filter = "none";
        ctx.lineWidth = path.width;
        ctx.globalAlpha = Math.min(alpha * 0.48, 0.42);
        ctx.strokeStyle = "#d8f4ff";
        ctx.stroke();
      }

      ctx.restore();
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [flow]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    />
  );
}

function estimateBezierLength(p: {
  x0: number; y0: number;
  x1: number; y1: number;
  x2: number; y2: number;
  x3: number; y3: number;
}): number {
  let len = 0;
  let px = p.x0;
  let py = p.y0;
  const steps = 24;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const mt = 1 - t;
    const x =
      mt ** 3 * p.x0 +
      3 * mt ** 2 * t * p.x1 +
      3 * mt * t ** 2 * p.x2 +
      t ** 3 * p.x3;
    const y =
      mt ** 3 * p.y0 +
      3 * mt ** 2 * t * p.y1 +
      3 * mt * t ** 2 * p.y2 +
      t ** 3 * p.y3;
    len += Math.hypot(x - px, y - py);
    px = x;
    py = y;
  }
  return Math.max(len, 80);
}
