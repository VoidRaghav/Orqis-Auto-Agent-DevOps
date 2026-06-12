"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { gsap } from "gsap";

const RobotScene = dynamic(() => import("./RobotScene"), { ssr: false });

const STATS = [
  { val: "< 1s",  label: "error detected",  color: "#00ff88" },
  { val: "14s",   label: "avg patch time",   color: "#ffffff" },
  { val: "94%",   label: "auto-heal rate",   color: "#ffaa00" },
  { val: "MCP",   label: "native IDE flow",  color: "#4d94ff" },
];

const CARDS = [
  { label: "pricing-agent",  status: "patched",    color: "#00ff88", detail: "3-line fix",    top: "14%", right: "3%"  },
  { label: "billing-agent",  status: "healed",     color: "#00ff88", detail: "-$0.62",         top: "18%", right: "41%" },
  { label: "scraper-v2",     status: "monitoring", color: "#4d94ff", detail: "0 errors 24h",  top: "70%", right: "3%"  },
  { label: "cost guardrail", status: "active",     color: "#ffaa00", detail: "$12 saved",      top: "72%", right: "41%" },
];

export default function HeroSection() {
  const contentRef = useRef<HTMLDivElement>(null);
  const badgeRef   = useRef<HTMLDivElement>(null);
  const h1Ref      = useRef<HTMLHeadingElement>(null);
  const subRef     = useRef<HTMLParagraphElement>(null);
  const ctaRef     = useRef<HTMLDivElement>(null);
  const statsRef   = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.timeline({ delay: 0.3 })
        .fromTo(badgeRef.current,  { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" })
        .fromTo(h1Ref.current,     { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out" }, "-=0.3")
        .fromTo(subRef.current,    { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.4")
        .fromTo(ctaRef.current,    { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3")
        .fromTo(statsRef.current,  { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3");
    }, contentRef);
    return () => ctx.revert();
  }, []);

  return (
    <section
      style={{
        minHeight: "100vh",
        position: "relative",
        overflow: "hidden",
        backgroundColor: "#000000",
        paddingTop: 60,
      }}
    >
      {/* ── Layer 0: full-screen grid ──────────────────────── */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 0, opacity: 0.02, pointerEvents: "none",
        backgroundImage:
          "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px)," +
          "linear-gradient(90deg,rgba(255,255,255,1) 1px,transparent 1px)",
        backgroundSize: "64px 64px",
      }} />

      {/* Top-left green glow */}
      <div style={{
        position: "absolute", top: "15%", left: "5%",
        width: 500, height: 500, borderRadius: "50%",
        background: "#00ff88", opacity: 0.03, filter: "blur(120px)",
        pointerEvents: "none", zIndex: 0,
      }} />

      {/* ── Layer 1: 3D robot — right half of screen ──────── */}
      <div style={{
        position: "absolute",
        top: 0, right: 0,
        width: "58%",
        height: "100vh",   // explicit 100vh — avoids clientHeight:0 at mount
        zIndex: 1,
      }}>
        <RobotScene />
      </div>

      {/* Fade edge: robot side → black (blends into text column) */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none",
        background:
          "linear-gradient(90deg, #000000 0%, #000000 32%, rgba(0,0,0,0.7) 48%, rgba(0,0,0,0) 68%)",
      }} />

      {/* ── Layer 3: text content ──────────────────────────── */}
      <div
        ref={contentRef}
        style={{
          position: "relative", zIndex: 3,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          maxWidth: 1280,
          margin: "0 auto",
          padding: "80px 48px",
          width: "100%",
          pointerEvents: "none",
        }}
      >
        <div style={{ flex: "0 0 50%", minWidth: 260, pointerEvents: "all" }}>

          {/* Badge */}
          <div ref={badgeRef} style={{ opacity: 0, marginBottom: 28 }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "6px 14px", borderRadius: 999,
              border: "1px solid rgba(0,255,136,0.3)",
              background: "rgba(0,255,136,0.06)",
              fontFamily: "'DM Mono', monospace",
              fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase",
              color: "#00ff88",
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", background: "#00ff88",
                display: "inline-block", animation: "pulse-slow 2s ease-in-out infinite",
              }} />
              Production Error Intelligence
            </span>
          </div>

          {/* Headline */}
          <h1
            ref={h1Ref}
            style={{
              opacity: 0,
              fontFamily: "'Anton', sans-serif",
              fontSize: "clamp(3.8rem, 7.5vw, 7rem)",
              lineHeight: 0.9,
              letterSpacing: "-0.01em",
              color: "#ffffff",
              marginBottom: 32,
            }}
          >
            YOUR PROD
            <br />
            <span style={{ color: "#00ff88" }}>BREAKS.</span>
            <br />
            ORQIS
            <br />
            FIXES IT.
          </h1>

          {/* Subtext */}
          <p
            ref={subRef}
            style={{
              opacity: 0, marginBottom: 40,
              fontFamily: "'DM Mono', monospace",
              fontSize: "clamp(0.78rem, 0.95vw, 0.92rem)",
              lineHeight: 1.85, color: "#888888", maxWidth: 430,
              letterSpacing: "0.01em",
            }}
          >
            Detects failures in your logs under a second, explains them in plain English,
            generates a code patch.{" "}
            <span style={{ color: "#cccccc" }}>Approve in your IDE. Done.</span>
          </p>

          {/* CTA buttons */}
          <div ref={ctaRef} style={{ opacity: 0, display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 52 }}>
            <a href="#" className="btn-primary" style={{
              padding: "13px 30px", borderRadius: 10, fontSize: 14,
              textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
            }}>
              Get Started Free →
            </a>
            <a href="#" className="btn-secondary" style={{
              padding: "13px 30px", borderRadius: 10, fontSize: 14,
              textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
            }}>
              View Demo ↗
            </a>
          </div>

          {/* Stats */}
          <div ref={statsRef} style={{ opacity: 0, display: "flex", flexWrap: "wrap", gap: 28 }}>
            {STATS.map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 18, fontWeight: 700, color: s.color,
                }}>{s.val}</span>
                <span style={{
                  fontFamily: "'Inter', sans-serif", fontSize: 12, color: "#555555",
                }}>{s.label}</span>
                {i < STATS.length - 1 && (
                  <span style={{ color: "rgba(255,255,255,0.07)" }}>·</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Layer 4: floating status cards over robot ─────── */}
      {CARDS.map((c, i) => (
        <div
          key={i}
          className="glass animate-float"
          style={{
            position: "absolute",
            top: c.top,
            right: c.right,
            minWidth: 148,
            padding: "10px 14px",
            borderRadius: 10,
            animationDelay: `${i * 0.45}s`,
            zIndex: 4,
            pointerEvents: "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
            <div style={{
              width: 7, height: 7, borderRadius: "50%",
              background: c.color, animation: "pulse-slow 2s infinite",
            }} />
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#555555" }}>
              {c.label}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600, color: c.color }}>
              {c.status}
            </span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#555555" }}>
              {c.detail}
            </span>
          </div>
        </div>
      ))}

      {/* Scroll hint */}
      <div style={{
        position: "absolute", bottom: 28, left: "50%",
        transform: "translateX(-50%)",
        display: "flex", flexDirection: "column", alignItems: "center",
        gap: 8, opacity: 0.28, zIndex: 4, pointerEvents: "none",
      }}>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.2em", color: "#666666" }}>
          SCROLL
        </span>
        <div style={{
          width: 1, height: 32,
          background: "linear-gradient(to bottom, rgba(255,255,255,0.3), transparent)",
        }} />
      </div>
    </section>
  );
}
