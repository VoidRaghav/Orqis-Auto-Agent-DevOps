"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

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
        ref={sectionRef}
        style={{
          position: "relative",
          padding: "128px 24px",
          overflow: "hidden",
          backgroundColor: "#000000",
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
          background: "#00ff88", opacity: 0.04, filter: "blur(80px)",
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
          <h2 style={{
            fontFamily: "'Anton', sans-serif",
            fontSize: "clamp(3.5rem, 10vw, 9rem)",
            lineHeight: 0.9,
            letterSpacing: "-0.01em",
            color: "#ffffff",
            marginBottom: 24,
          }}>
            NEXT PROD
            <br />
            INCIDENT?
            <br />
            <span style={{ color: "#00ff88" }}>ALREADY FIXED.</span>
          </h2>

          <p style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: "clamp(1rem, 1.5vw, 1.15rem)",
            color: "#666666",
            marginBottom: 40,
            maxWidth: 520,
            margin: "0 auto 40px",
          }}>
            Orqis watches your logs, finds the root cause, and patches the code — before you even open a ticket.
          </p>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "center", marginBottom: 48 }}>
            <a href="#" className="btn-primary" style={{
              padding: "14px 36px", borderRadius: 10, fontSize: 15,
              textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
            }}>
              Get Started Free →
            </a>
            <a href="#" className="btn-secondary" style={{
              padding: "14px 36px", borderRadius: 10, fontSize: 15,
              textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
            }}>
              View Docs ↗
            </a>
          </div>

          {/* Social proof */}
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 28, opacity: 0.45 }}>
            {["Zero config — pipe logs and go", "MCP-native for Claude Code & Cursor", "No credit card required"].map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: "#00ff88", fontSize: 13 }}>✓</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#666666" }}>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ backgroundColor: "#000000", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "48px 32px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48, marginBottom: 48 }}>

            {/* Brand */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 6,
                  background: "#00ff88", display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 11, color: "#000000" }}>O</span>
                </div>
                <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 18, color: "#ffffff", letterSpacing: "0.05em" }}>ORQIS</span>
              </div>
              <p style={{
                fontFamily: "'Inter', sans-serif", fontSize: 13,
                color: "#555555", lineHeight: 1.7, maxWidth: 260,
              }}>
                Self-healing production for AI agents and DevOps pipelines.
                Detect, diagnose, patch — automatically.
              </p>
              <div style={{ display: "flex", gap: 16, marginTop: 20 }}>
                {["𝕏", "GitHub", "Discord"].map((social) => (
                  <a key={social} href="#" style={{
                    fontFamily: "'DM Mono', monospace", fontSize: 12,
                    color: "#555555", textDecoration: "none",
                    transition: "color 0.15s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                  onMouseLeave={e => (e.currentTarget.style.color = "#555555")}
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
                  color: "#444444", letterSpacing: "0.2em",
                  textTransform: "uppercase", marginBottom: 16,
                }}>
                  {col.title}
                </h4>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                  {col.links.map((link) => (
                    <li key={link}>
                      <a href="#" style={{
                        fontFamily: "'Inter', sans-serif", fontSize: 13,
                        color: "#555555", textDecoration: "none",
                        transition: "color 0.15s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                      onMouseLeave={e => (e.currentTarget.style.color = "#555555")}
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
            <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#333333" }}>
              © 2025 Orqis, Inc. All rights reserved.
            </p>
            <div style={{ display: "flex", gap: 24 }}>
              {["Privacy Policy", "Terms of Service", "Cookie Policy"].map((link) => (
                <a key={link} href="#" style={{
                  fontFamily: "'DM Mono', monospace", fontSize: 11,
                  color: "#333333", textDecoration: "none",
                  transition: "color 0.15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.color = "#ffffff")}
                onMouseLeave={e => (e.currentTarget.style.color = "#333333")}
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
