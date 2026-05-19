"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { gsap } from "gsap";

const RobotCanvas = dynamic(() => import("./RobotCanvas"), { ssr: false });

const STATS = [
  { val: "< 1s",  label: "error detected",  color: "#00ff88" },
  { val: "14s",   label: "avg patch time",  color: "#ffffff" },
  { val: "94%",   label: "auto-heal rate",  color: "#ffaa00" },
  { val: "MCP",   label: "native IDE flow", color: "#4d94ff" },
];

const CARDS = [
  { label: "pricing-agent",  status: "patched",     color: "#00ff88", detail: "3-line fix",   top: "16%", left: "52%" },
  { label: "scraper-v2",     status: "monitoring",  color: "#4d94ff", detail: "0 errors 24h", top: "64%", left: "50%" },
  { label: "billing-agent",  status: "healed",      color: "#00ff88", detail: "-$0.62",        top: "24%", left: "78%" },
  { label: "cost guardrail", status: "active",      color: "#ffaa00", detail: "$12 saved",     top: "72%", left: "76%" },
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
      gsap.timeline({ delay: 0.5 })
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
      {/* ── Layer 0: full-screen 3D canvas ── */}
      <div style={{
        position: "absolute",
        inset: 0,
        zIndex: 0,
        // Slight right-side darkening so left text stays readable
        background: "linear-gradient(105deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.55) 45%, rgba(0,0,0,0.1) 100%)",
        pointerEvents: "none",
      }} />
      <div style={{ position: "absolute", inset: 0, zIndex: 0 }}>
        <RobotCanvas mode="bg" />
      </div>

      {/* Subtle grid overlay */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 1, opacity: 0.022, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
        backgroundSize: "64px 64px",
      }} />

      {/* ── Layer 1: content ── */}
      <div
        ref={contentRef}
        style={{
          position: "relative", zIndex: 2,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          maxWidth: 1280,
          margin: "0 auto",
          padding: "80px 40px 80px",
          width: "100%",
        }}
      >
        {/* Left column — max 52% so robot stays visible on right */}
        <div style={{ flex: "0 0 52%", minWidth: 280 }}>

          {/* Badge */}
          <div ref={badgeRef} style={{ opacity: 0, marginBottom: 28 }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "6px 14px", borderRadius: 999,
              border: "1px solid rgba(0,255,136,0.3)",
              background: "rgba(0,255,136,0.07)",
              fontFamily: "'DM Mono', monospace",
              fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase",
              color: "#00ff88",
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: "#00ff88", display: "inline-block",
                animation: "pulse-slow 2s ease-in-out infinite",
              }} />
              Production Error Intelligence
              <span style={{ color: "rgba(255,255,255,0.25)" }}>·</span>
              <span style={{ color: "#ffffff" }}>Beta</span>
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

          {/* Sub */}
          <p
            ref={subRef}
            style={{
              opacity: 0, marginBottom: 40,
              fontFamily: "'Inter', sans-serif",
              fontSize: "clamp(1rem, 1.4vw, 1.15rem)",
              lineHeight: 1.75, color: "#888888", maxWidth: 420,
            }}
          >
            Orqis detects failures in your logs under a second, explains them in plain English, and generates a code patch.{" "}
            <span style={{ color: "#cccccc" }}>
              Approve it in your IDE. Done.
            </span>
          </p>

          {/* CTA */}
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
                  fontFamily: "'Inter', sans-serif",
                  fontSize: 12, color: "#555555",
                }}>{s.label}</span>
                {i < STATS.length - 1 && (
                  <span style={{ color: "rgba(255,255,255,0.08)" }}>·</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Floating status cards — positioned absolutely over canvas ── */}
      {CARDS.map((c, i) => (
        <div
          key={i}
          className="glass animate-float"
          style={{
            position: "absolute",
            top: c.top,
            left: c.left,
            minWidth: 148,
            padding: "10px 14px",
            borderRadius: 10,
            animationDelay: `${i * 0.45}s`,
            zIndex: 3,
            pointerEvents: "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
            <div style={{
              width: 7, height: 7, borderRadius: "50%",
              background: c.color,
              animation: "pulse-slow 2s infinite",
            }} />
            <span style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 10, color: "#555555",
            }}>{c.label}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 12, fontWeight: 600, color: c.color,
            }}>{c.status}</span>
            <span style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 10, color: "#555555",
            }}>{c.detail}</span>
          </div>
        </div>
      ))}

      {/* Scroll hint */}
      <div style={{
        position: "absolute", bottom: 28, left: "50%",
        transform: "translateX(-50%)",
        display: "flex", flexDirection: "column", alignItems: "center",
        gap: 8, opacity: 0.3, zIndex: 3, pointerEvents: "none",
      }}>
        <span style={{
          fontFamily: "'DM Mono', monospace",
          fontSize: 10, letterSpacing: "0.2em", color: "#666666",
        }}>SCROLL</span>
        <div style={{
          width: 1, height: 32,
          background: "linear-gradient(to bottom, rgba(255,255,255,0.3), transparent)",
        }} />
      </div>
    </section>
  );
}
