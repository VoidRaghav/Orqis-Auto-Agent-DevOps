"use client";

import { useEffect, useRef } from "react";

/** Subtle drifting particles + scan lines behind hero / flow zone */
export default function HeroAmbientLayer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    type Dot = { x: number; y: number; r: number; vx: number; vy: number; a: number };
    const dots: Dot[] = Array.from({ length: 42 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: 0.4 + Math.random() * 1.2,
      vx: (Math.random() - 0.5) * 0.00012,
      vy: (Math.random() - 0.5) * 0.00008,
      a: 0.08 + Math.random() * 0.22,
    }));

    let scanY = 0;

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

      if (!reducedMotion) {
        for (const dot of dots) {
          dot.x += dot.vx;
          dot.y += dot.vy;
          if (dot.x < 0) dot.x = 1;
          if (dot.x > 1) dot.x = 0;
          if (dot.y < 0) dot.y = 1;
          if (dot.y > 1) dot.y = 0;

          ctx.beginPath();
          ctx.arc(dot.x * w, dot.y * h, dot.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(168, 212, 255, ${dot.a})`;
          ctx.fill();
        }

        scanY = (scanY + 0.35) % h;
        const grad = ctx.createLinearGradient(0, scanY - 40, 0, scanY + 40);
        grad.addColorStop(0, "rgba(0, 255, 136, 0)");
        grad.addColorStop(0.5, "rgba(0, 255, 136, 0.025)");
        grad.addColorStop(1, "rgba(0, 255, 136, 0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, scanY - 40, w, 80);
      }

      ctx.strokeStyle = "rgba(168, 212, 255, 0.04)";
      ctx.lineWidth = 1;
      const grid = 96;
      const offset = reducedMotion ? 0 : (performance.now() * 0.008) % grid;
      for (let x = -grid; x < w + grid; x += grid) {
        ctx.beginPath();
        ctx.moveTo(x + offset, 0);
        ctx.lineTo(x + offset, h);
        ctx.stroke();
      }
      for (let y = -grid; y < h + grid; y += grid) {
        ctx.beginPath();
        ctx.moveTo(0, y + offset * 0.6);
        ctx.lineTo(w, y + offset * 0.6);
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return <canvas ref={canvasRef} className="hero-ambient-canvas" aria-hidden />;
}
