"use client";

import { useState } from "react";

const PLANS = [
  {
    name: "Free",
    price: { mo: 0, yr: 0 },
    desc: "Get started — no credit card.",
    features: ["1 agent", "Basic narrative logs", "3-day log retention", "Community support", "npx install"],
    cta: "Start Free",
    highlight: false,
  },
  {
    name: "Pro",
    price: { mo: 20, yr: 16 },
    desc: "For builders who are serious.",
    features: ["Unlimited agents", "Cost tracking + kill switch", "Self-heal send-to-IDE", "Live config hot-swap", "30-day retention", "Slack + email alerts", "Loop detection + auto-pause"],
    cta: "Get Started →",
    highlight: true,
  },
  {
    name: "Team",
    price: { mo: 79, yr: 63 },
    desc: "Multi-agent production systems.",
    features: ["Everything in Pro", "Multi-agent topology view", "Shared prompt versioning", "Prompt A/B testing", "Context vault (RAG memory)", "Replay + time-machine debug", "Priority support", "SOC2 (coming soon)"],
    cta: "Contact Us",
    highlight: false,
  },
];

export default function PricingSection() {
  const [annual, setAnnual] = useState(false);
  const mono: React.CSSProperties = { fontFamily: "'DM Mono', monospace" };
  const inter: React.CSSProperties = { fontFamily: "'Inter', sans-serif" };

  return (
    <section style={{ backgroundColor: "#000000", padding: "100px 32px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <span style={{ ...mono, fontSize: 11, letterSpacing: "0.2em", color: "#444", textTransform: "uppercase" }}>
            ◆ Pricing
          </span>
          <h2 style={{
            fontFamily: "'Anton', sans-serif",
            fontSize: "clamp(2.5rem, 5vw, 4.5rem)",
            color: "#ffffff", lineHeight: 1, marginTop: 16, letterSpacing: "-0.01em",
          }}>
            SIMPLE.<br />
            <span style={{ color: "#00ff88" }}>HONEST.</span>
          </h2>
          <p style={{ ...inter, fontSize: 16, color: "#666", marginTop: 16 }}>
            Pay for the time you save, not the seats you fill.
          </p>

          {/* Toggle */}
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 12,
            marginTop: 24, padding: "6px",
            background: "#111", borderRadius: 10,
            border: "1px solid rgba(255,255,255,0.07)",
          }}>
            {["Monthly", "Annual"].map((label) => (
              <button key={label} onClick={() => setAnnual(label === "Annual")} style={{
                padding: "7px 20px", borderRadius: 7, border: "none", cursor: "pointer",
                ...mono, fontSize: 12,
                background: (annual ? label === "Annual" : label === "Monthly")
                  ? "#ffffff" : "transparent",
                color: (annual ? label === "Annual" : label === "Monthly") ? "#000" : "#666",
                transition: "all 0.2s",
              }}>
                {label} {label === "Annual" && <span style={{ color: "#00ff88", marginLeft: 4 }}>-20%</span>}
              </button>
            ))}
          </div>
        </div>

        {/* Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {PLANS.map((plan) => (
            <div key={plan.name} className="pricing-card" style={{
              background: plan.highlight ? "#ffffff" : "#0a0a0a",
              border: `1px solid ${plan.highlight ? "#ffffff" : "rgba(255,255,255,0.08)"}`,
              borderRadius: 16, padding: 28,
              position: "relative",
              boxShadow: plan.highlight ? "0 0 60px rgba(255,255,255,0.08)" : "none",
            }}>
              {plan.highlight && (
                <div style={{
                  position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)",
                  background: "#00ff88", color: "#000", ...mono, fontSize: 10,
                  padding: "4px 12px", borderRadius: 20, letterSpacing: "0.1em",
                }}>
                  MOST POPULAR
                </div>
              )}
              <div style={{ marginBottom: 20 }}>
                <div style={{
                  fontFamily: "'Anton', sans-serif", fontSize: 24,
                  color: plan.highlight ? "#000" : "#ffffff", marginBottom: 8,
                }}>{plan.name}</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 8 }}>
                  <span style={{
                    fontFamily: "'Anton', sans-serif", fontSize: 48,
                    color: plan.highlight ? "#000" : plan.name === "Team" ? "#ffffff" : "#666",
                  }}>
                    ${annual ? plan.price.yr : plan.price.mo}
                  </span>
                  {plan.price.mo > 0 && (
                    <span style={{ ...mono, fontSize: 12, color: plan.highlight ? "#666" : "#444" }}>/mo</span>
                  )}
                </div>
                <p style={{ ...inter, fontSize: 13, color: plan.highlight ? "#444" : "#666" }}>{plan.desc}</p>
              </div>

              <a href="#" style={{
                display: "block", textAlign: "center",
                padding: "11px 24px", borderRadius: 10, marginBottom: 24,
                ...inter, fontSize: 14, fontWeight: 600, textDecoration: "none",
                background: plan.highlight ? "#000" : "transparent",
                color: plan.highlight ? "#fff" : "#ffffff",
                border: plan.highlight ? "none" : "1px solid rgba(255,255,255,0.15)",
                transition: "all 0.2s",
              }}>
                {plan.cta}
              </a>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {plan.features.map((f) => (
                  <div key={f} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span style={{ color: "#00ff88", fontSize: 13, flexShrink: 0, marginTop: 1 }}>✓</span>
                    <span style={{ ...inter, fontSize: 13, color: plan.highlight ? "#444" : "#666" }}>{f}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
