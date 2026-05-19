"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { gsap } from "gsap";

const RobotCanvas = dynamic(() => import("./RobotCanvas"), { ssr: false });

const STATS = [
  { val: "247",    label: "agents healed",   color: "#00ff88" },
  { val: "$1,842", label: "cost saved",       color: "#ffffff" },
  { val: "94%",    label: "auto-heal rate",   color: "#ffaa00" },
  { val: "1.4s",   label: "avg fix time",     color: "#4d94ff" },
];

const CARDS = [
  { label: "pricing-agent",  status: "healed",      color: "#00ff88", detail: "-$1.84",      top: "14%",  left: "-2%" },
  { label: "scraper-v2",     status: "monitoring",  color: "#4d94ff", detail: "0 errors",    top: "68%",  left: "-4%" },
  { label: "billing-agent",  status: "auto-fixed",  color: "#00ff88", detail: "-$0.62",      top: "22%",  right: "-2%", left: "auto" },
  { label: "cost guardrail", status: "active",      color: "#ffaa00", detail: "$12 saved",   top: "75%",  right: "-2%", left: "auto" },
];

export default function HeroSection() {
  const heroRef  = useRef<HTMLDivElement>(null);
  const badgeRef = useRef<HTMLDivElement>(null);
  const h1Ref    = useRef<HTMLHeadingElement>(null);
  const subRef   = useRef<HTMLParagraphElement>(null);
  const ctaRef   = useRef<HTMLDivElement>(null);
  const statsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.timeline({ delay: 0.4 })
        .fromTo(badgeRef.current, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" })
        .fromTo(h1Ref.current,    { opacity: 0, y: 36 }, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, "-=0.3")
        .fromTo(subRef.current,   { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.4")
        .fromTo(ctaRef.current,   { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3")
        .fromTo(statsRef.current, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3");
    }, heroRef);
    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={heroRef}
      style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        position: "relative", overflow: "hidden",
        backgroundColor: "#000000",
        paddingTop: 60,
      }}
    >
      {/* Subtle grid */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.028, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
        backgroundSize: "64px 64px",
      }} />

      {/* Green glow top-left */}
      <div style={{
        position: "absolute", top: "20%", left: "10%",
        width: 600, height: 600, borderRadius: "50%",
        background: "#00ff88", opacity: 0.025, filter: "blur(120px)",
        pointerEvents: "none",
      }} />

      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "48px 32px 48px", width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 48, flexWrap: "wrap" }}>

          {/* LEFT — 55% */}
          <div ref={heroRef} style={{ flex: "0 0 55%", minWidth: 300, zIndex: 1 }}>

            {/* Badge */}
            <div ref={badgeRef} style={{ opacity: 0, marginBottom: 24 }}>
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "6px 14px", borderRadius: 999,
                border: "1px solid rgba(0,255,136,0.25)",
                background: "rgba(0,255,136,0.06)",
                fontFamily: "'DM Mono', monospace",
                fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase",
                color: "#00ff88",
              }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00ff88", display: "inline-block", animation: "pulse-slow 2s ease-in-out infinite" }} />
                Self-Healing Agents
                <span style={{ color: "rgba(255,255,255,0.3)" }}>·</span>
                <span style={{ color: "#ffffff" }}>Now in Beta</span>
              </span>
            </div>

            {/* Headline */}
            <h1
              ref={h1Ref}
              style={{
                opacity: 0,
                fontFamily: "'Anton', sans-serif",
                fontSize: "clamp(3.5rem, 7vw, 6.5rem)",
                lineHeight: 0.92,
                letterSpacing: "-0.01em",
                color: "#ffffff",
                marginBottom: 28,
              }}
            >
              MISSION
              <br />
              <span style={{ color: "#00ff88" }}>CONTROL</span>
              <br />
              FOR YOUR
              <br />
              AGENTS.
            </h1>

            {/* Sub */}
            <p
              ref={subRef}
              style={{
                opacity: 0, marginBottom: 36,
                fontFamily: "'Inter', sans-serif",
                fontSize: "clamp(1rem, 1.5vw, 1.15rem)",
                lineHeight: 1.7, color: "#a0a0a0", maxWidth: 440,
              }}
            >
              Zero config. Self-healing. Always watching.{" "}
              <span style={{ color: "#ffffff" }}>
                Built for vibe coders who need to ship, not debug.
              </span>
            </p>

            {/* CTA */}
            <div ref={ctaRef} style={{ opacity: 0, display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 44 }}>
              <a href="#" className="btn-primary" style={{
                padding: "12px 28px", borderRadius: 10, fontSize: 14,
                textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
              }}>
                Get Started Free →
              </a>
              <a href="#" className="btn-secondary" style={{
                padding: "12px 28px", borderRadius: 10, fontSize: 14,
                textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
              }}>
                Watch Demo ↗
              </a>
            </div>

            {/* Stats */}
            <div ref={statsRef} style={{ opacity: 0, display: "flex", flexWrap: "wrap", gap: 28 }}>
              {STATS.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    fontFamily: "'DM Mono', monospace", fontSize: 20,
                    fontWeight: 700, color: s.color,
                  }}>{s.val}</span>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 13, color: "#666666" }}>{s.label}</span>
                  {i < STATS.length - 1 && <span style={{ color: "rgba(255,255,255,0.1)" }}>·</span>}
                </div>
              ))}
            </div>
          </div>

          {/* RIGHT — robot + cards */}
          <div style={{ flex: "0 0 40%", position: "relative", height: 560 }}>
            <RobotCanvas />
            {CARDS.map((c, i) => (
              <div key={i} className="glass animate-float" style={{
                position: "absolute",
                top: c.top, left: c.left, right: (c as any).right,
                minWidth: 150, padding: "10px 14px", borderRadius: 10,
                animationDelay: `${i * 0.4}s`,
                zIndex: 10,
              }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <div style={{ width: 7, height: 7, borderRadius: "50%", background: c.color, animation: "pulse-slow 2s infinite" }} />
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#666666" }}>{c.label}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600, color: c.color }}>{c.status}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#666666" }}>{c.detail}</span>
                </div>
              </div>
            ))}
          </div>

        </div>
      </div>

      {/* Scroll hint */}
      <div style={{
        position: "absolute", bottom: 28, left: "50%", transform: "translateX(-50%)",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 8, opacity: 0.35,
      }}>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.2em", color: "#666666" }}>SCROLL</span>
        <div style={{ width: 1, height: 32, background: "linear-gradient(to bottom, rgba(255,255,255,0.3), transparent)" }} />
      </div>
    </section>
  );
}
