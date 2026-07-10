"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SectionMeta } from "@/components/ui/MetaLabel";
import { colors, fonts, inter, mono } from "@/lib/tokens";

gsap.registerPlugin(ScrollTrigger);

export default function FooterCTA() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const headlineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        headlineRef.current,
        { opacity: 0, scale: 0.96 },
        {
          opacity: 1,
          scale: 1,
          duration: 1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: sectionRef.current,
            start: "top 70%",
            once: true,
          },
        }
      );
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  return (
    <>
      {/* CTA Section */}
      <section
        id="finale-cta"
        ref={sectionRef}
        className="flow-section flow-tail-section"
        style={{
          position: "relative",
          paddingTop: 128,
          paddingBottom: 128,
          overflow: "hidden",
          backgroundColor: "transparent",
        }}
      >
        {/* Top divider */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 1,
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent)",
        }} />

        {/* Green glow */}
        <div style={{
          position: "absolute", top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          width: 600, height: 400, borderRadius: "50%",
          background: "#3ddc97", opacity: 0.05, filter: "blur(80px)",
          pointerEvents: "none",
        }} />

        {/* Grid */}
        <div style={{
          position: "absolute", inset: 0, opacity: 0.025, pointerEvents: "none",
          backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }} />

        <div
          ref={headlineRef}
          style={{
            maxWidth: 900, margin: "0 auto", textAlign: "center",
            position: "relative", zIndex: 1, opacity: 0,
          }}
        >
          <SectionMeta index="005" tag="(LAUNCH)" />
          <h2
            className="editorial-headline"
            style={{
              fontSize: "clamp(3.5rem, 10vw, 9rem)",
              color: colors.white,
              marginBottom: 24,
            }}
          >
            NEXT INCIDENT?
            <br />
            <em>already</em>
            <br />
            <span style={{ color: colors.green }}>HAS A PR.</span>
          </h2>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "center", marginBottom: 48 }}>
            <a href="/settings" className="btn-ghost" style={{
              padding: "14px 32px", textDecoration: "none", display: "inline-flex", alignItems: "center",
            }}>
              Connect GitHub →
            </a>
            <a href="/dashboard" className="btn-secondary" style={{
              padding: "14px 32px", borderRadius: 0, textDecoration: "none",
              fontFamily: fonts.mono, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase",
              display: "inline-flex", alignItems: "center",
            }}>
              View Demo ↗
            </a>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 28, opacity: 0.5 }}>
            {["GitHub PR-first workflow", "MCP + copy prompt — any IDE", "Never writes to main"].map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: "#00ff88", fontSize: 13 }}>✓</span>
                <span style={{ ...mono, fontSize: 12, color: colors.muted }}>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ backgroundColor: "#000000", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "48px 32px" }}>
          <div className="landing-footer-grid" style={{ marginBottom: 48 }}>

            {/* Brand */}
            <div>
              <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
                <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 18, color: "#ffffff", letterSpacing: "0.05em" }}>ORQIS</span>
              </div>
              <p style={{ ...inter, fontSize: 13, color: colors.muted, lineHeight: 1.7, maxWidth: 260 }}>
                Agent ops for production AI systems. Detect, patch, review PR, audit — automatically.
              </p>
              <div style={{ display: "flex", gap: 16, marginTop: 20 }}>
                {["𝕏", "GitHub", "Discord"].map((social) => (
                  <a key={social} href="#" style={{
                    fontFamily: "'DM Mono', monospace", fontSize: 12,
                    color: "#9fb1a8", textDecoration: "none",
                    transition: "color 0.15s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                  onMouseLeave={e => (e.currentTarget.style.color = "#9fb1a8")}
                  >
                    {social}
                  </a>
                ))}
              </div>
            </div>

            {/* Link columns */}
            {[
              { title: "Product",    links: ["Features", "Pricing", "Changelog", "Roadmap"] },
              { title: "Developers", links: ["Documentation", "SDK Reference", "Examples", "Status"] },
              { title: "Company",    links: ["About", "Blog", "Careers", "Contact"] },
            ].map((col) => (
              <div key={col.title}>
                <h4 style={{
                  fontFamily: "'DM Mono', monospace", fontSize: 10,
                  color: "#8fa39a", letterSpacing: "0.2em",
                  textTransform: "uppercase", marginBottom: 16,
                }}>
                  {col.title}
                </h4>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                  {col.links.map((link) => (
                    <li key={link}>
                      <a href="#" style={{
                        fontFamily: "'Inter', sans-serif", fontSize: 13,
                        color: "#9fb1a8", textDecoration: "none",
                        transition: "color 0.15s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                      onMouseLeave={e => (e.currentTarget.style.color = "#9fb1a8")}
                      >
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom bar */}
          <div style={{
            paddingTop: 24,
            borderTop: "1px solid rgba(255,255,255,0.04)",
            display: "flex", flexWrap: "wrap",
            alignItems: "center", justifyContent: "space-between", gap: 16,
          }}>
            <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#9aaca3" }}>
              © 2026 Orqis, Inc. All rights reserved.
            </p>
            <div style={{ display: "flex", gap: 24 }}>
              {["Privacy Policy", "Terms of Service", "Cookie Policy"].map((link) => (
                <a key={link} href="#" style={{
                  fontFamily: "'DM Mono', monospace", fontSize: 11,
                  color: "#9aaca3", textDecoration: "none",
                  transition: "color 0.15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                onMouseLeave={e => (e.currentTarget.style.color = "#9aaca3")}
                >
                  {link}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
