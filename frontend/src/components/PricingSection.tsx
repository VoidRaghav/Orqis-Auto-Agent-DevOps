"use client";

import { useState } from "react";
import { SectionMeta } from "@/components/ui/MetaLabel";
import { colors, fonts, mono, inter } from "@/lib/tokens";

const PLANS = [
  {
    name: "Free",
    price: { mo: 0, yr: 0 },
    desc: "Pipe logs. See incidents. No card.",
    features: ["1 agent", "Incident detect + RCA", "3-day retention", "Copy prompt for any IDE", "npx install"],
    cta: "Start Free",
    href: "/settings",
    highlight: false,
  },
  {
    name: "Pro",
    price: { mo: 20, yr: 16 },
    desc: "GitHub PR-first fixes at scale.",
    features: [
      "Unlimited agents",
      "GitHub PR workflow",
      "RUNAWAY_LOOP guard",
      "CHANGES audit log",
      "MCP + local apply",
      "30-day retention",
      "Slack + email alerts",
    ],
    cta: "Connect GitHub →",
    href: "/settings",
    highlight: true,
  },
  {
    name: "Team",
    price: { mo: 79, yr: 63 },
    desc: "Multi-agent production fleets.",
    features: [
      "Everything in Pro",
      "Shared repo grants",
      "Multi-agent topology",
      "Priority support",
      "SSO (coming soon)",
    ],
    cta: "Contact Us",
    href: "#",
    highlight: false,
  },
];

export default function PricingSection() {
  const [annual, setAnnual] = useState(false);

  return (
    <section className="flow-section flow-tail-section" style={{ padding: "100px 32px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <SectionMeta index="004" tag="(PRICING)" />
          <h2
            className="editorial-headline"
            style={{ fontSize: "clamp(2.5rem, 5vw, 4.5rem)", color: colors.white, marginTop: 8 }}
          >
            SIMPLE. <em>honest.</em>
            <br />
            <span style={{ color: colors.green }}>NO SEAT TAX.</span>
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

              <a href={plan.href} className={plan.highlight ? "btn-primary" : "btn-ghost"} style={{
                display: "block", textAlign: "center",
                padding: "11px 24px", marginBottom: 24,
                ...inter, fontSize: 13, fontWeight: 600, textDecoration: "none",
                borderRadius: 0,
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
