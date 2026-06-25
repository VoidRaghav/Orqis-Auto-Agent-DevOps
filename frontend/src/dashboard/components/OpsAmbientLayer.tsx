"use client";

import { useEffect, useRef } from "react";
import OpsAmbientRobot from "./OpsAmbientRobot";
import { MOOD_RGB, type OpsMood } from "./ops-ambient";

type Streak = { y: number; x: number; speed: number; len: number; alpha: number };
type Node = { angle: number; dist: number; speed: number; size: number };

function rgb(mood: OpsMood, alpha: number) {
  const [r, g, b] = MOOD_RGB[mood];
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Mission-control ambient — mood-reactive aurora, sonar, constellation, robot */
export default function OpsAmbientLayer({ mood = "standby" }: { mood?: OpsMood }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);
  const moodRef = useRef(mood);

  useEffect(() => {
    moodRef.current = mood;
  }, [mood]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    if (!parent) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const streaks: Streak[] = Array.from({ length: 26 }, () => ({
      y: Math.random(),
      x: Math.random(),
      speed: 0.0004 + Math.random() * 0.0007,
      len: 32 + Math.random() * 90,
      alpha: 0.06 + Math.random() * 0.14,
    }));

    const nodes: Node[] = Array.from({ length: 14 }, (_, i) => ({
      angle: (i / 14) * Math.PI * 2,
      dist: 0.12 + Math.random() * 0.28,
      speed: 0.00015 + Math.random() * 0.0002,
      size: 1.2 + Math.random() * 1.8,
    }));

    const drawHorizon = (ctx: CanvasRenderingContext2D, w: number, h: number, t: number, m: OpsMood) => {
      const horizon = h * 0.7;
      const vpX = w * 0.34;
      const drift = reducedMotion ? 0 : Math.sin(t * 0.00035) * 8;

      for (let i = 1; i <= 16; i++) {
        const p = i / 16;
        const y = horizon + (h - horizon) * p * p;
        ctx.strokeStyle = rgb(m, 0.04 + p * 0.03);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      for (let i = -24; i <= 24; i++) {
        const spread = i / 24;
        const xBottom = vpX + spread * w * 0.98 + drift;
        ctx.strokeStyle = rgb(m, 0.025 + Math.abs(spread) * 0.025);
        ctx.beginPath();
        ctx.moveTo(vpX + drift * 0.25, horizon);
        ctx.lineTo(xBottom, h + 24);
        ctx.stroke();
      }
    };

    const drawSonar = (ctx: CanvasRenderingContext2D, w: number, h: number, t: number, m: OpsMood) => {
      const cx = w * 0.24;
      const cy = h * 0.5;
      const maxR = Math.min(w, h) * 0.48;
      const phase = reducedMotion ? 0.4 : (t * 0.00042) % 1;

      for (let i = 0; i < 5; i++) {
        const p = (phase + i * 0.2) % 1;
        const r = p * maxR;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = rgb(m, (1 - p) * 0.2);
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      const sweep = reducedMotion ? 1.2 : (t * 0.00055) % (Math.PI * 2);
      const grad = ctx.createConicGradient(sweep, cx, cy);
      grad.addColorStop(0, rgb(m, 0));
      grad.addColorStop(0.06, rgb(m, 0.12));
      grad.addColorStop(0.14, rgb(m, 0));
      grad.addColorStop(1, rgb(m, 0));

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR * 0.9, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = rgb(m, 0.5);
      ctx.fill();
    };

    const drawConstellation = (ctx: CanvasRenderingContext2D, w: number, h: number, m: OpsMood) => {
      const cx = w * 0.24;
      const cy = h * 0.5;
      const baseR = Math.min(w, h) * 0.32;
      const pts: { x: number; y: number }[] = [];

      for (const n of nodes) {
        if (!reducedMotion) n.angle += n.speed;
        const r = baseR * n.dist;
        const x = cx + Math.cos(n.angle) * r;
        const y = cy + Math.sin(n.angle) * r * 0.72;
        pts.push({ x, y });

        ctx.beginPath();
        ctx.arc(x, y, n.size, 0, Math.PI * 2);
        ctx.fillStyle = rgb(m, 0.35);
        ctx.fill();
      }

      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x;
          const dy = pts[i].y - pts[j].y;
          const d = Math.hypot(dx, dy);
          if (d < baseR * 0.55) {
            ctx.strokeStyle = rgb(m, 0.08 * (1 - d / (baseR * 0.55)));
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(pts[i].x, pts[i].y);
            ctx.lineTo(pts[j].x, pts[j].y);
            ctx.stroke();
          }
        }
      }
    };

    const drawStreaks = (ctx: CanvasRenderingContext2D, w: number, h: number, m: OpsMood) => {
      const bandTop = h * 0.06;
      const bandH = h * 0.55;

      for (const s of streaks) {
        if (!reducedMotion) {
          s.x += s.speed;
          if (s.x > 1.18) s.x = -0.12;
        }

        const y = bandTop + s.y * bandH;
        const x = s.x * w;
        const grad = ctx.createLinearGradient(x, y, x + s.len, y);
        grad.addColorStop(0, rgb(m, 0));
        grad.addColorStop(0.35, rgb(m, s.alpha));
        grad.addColorStop(1, rgb(m, 0));

        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + s.len, y);
        ctx.stroke();
      }
    };

    const draw = (t: number) => {
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      const dpr = Math.min(window.devicePixelRatio, 2);
      const m = moodRef.current;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      drawHorizon(ctx, w, h, t, m);
      drawSonar(ctx, w, h, t, m);
      drawConstellation(ctx, w, h, m);
      drawStreaks(ctx, w, h, m);

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    const ro = new ResizeObserver(() => draw(performance.now()));
    ro.observe(parent);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return (
    <div className="ops-ambient" data-mood={mood} aria-hidden>
      <div className="ops-ambient-aurora" />
      <div className="ops-ambient-aurora ops-ambient-aurora-b" />
      <div className="ops-ambient-beams">
        <div className="ops-ambient-beam ops-ambient-beam-a" />
        <div className="ops-ambient-beam ops-ambient-beam-b" />
      </div>
      <OpsAmbientRobot mood={mood} />
      <canvas ref={canvasRef} className="ops-ambient-canvas" />
      <div className="ops-ambient-noise" />
      <div className="ops-ambient-vignette" />
      <div className="ops-ambient-scanlines" />
    </div>
  );
}
