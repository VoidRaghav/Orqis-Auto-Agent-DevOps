"use client";

import { useEffect, useRef, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import MetaLabel, { SectionMeta } from "@/components/ui/MetaLabel";
import TerminalPanel from "@/components/ui/TerminalPanel";
import { colors, fonts, mono, inter } from "@/lib/tokens";

const TABS = ["ISSUES & FIXES", "CHANGES", "ACTIVITY", "AI CALLS"] as const;
type Tab = (typeof TABS)[number];

const SPARK = [
  { t: "-60s", e: 0 },
  { t: "-54s", e: 1 },
  { t: "-48s", e: 0 },
  { t: "-42s", e: 2 },
  { t: "-36s", e: 1 },
  { t: "-30s", e: 0 },
  { t: "-24s", e: 3 },
  { t: "-18s", e: 1 },
  { t: "-12s", e: 0 },
  { t: "-6s", e: 1 },
];

const INCIDENTS = [
  { id: "#4421", agent: "refund-agent", error: "RUNAWAY_LOOP", fix: "max_iter guard", status: "PR open", sc: colors.github },
  { id: "#4418", agent: "billing-agent", error: "RecursionError", fix: "base case added", status: "healed", sc: colors.green },
  { id: "#4412", agent: "qa-agent", error: "Tool loop ×12", fix: "circuit breaker", status: "local apply", sc: colors.glow },
];

const CHANGES = [
  { t: "14:04:52", file: "refund_agent.py", action: "PR merged", sc: colors.github },
  { t: "14:02:18", file: "orqis/fix-loop", action: "PR opened", sc: colors.github },
  { t: "13:58:03", file: "billing_agent.py", action: "fix_applied", sc: colors.green },
];

const ACTIVITY = [
  { t: "14:05", msg: "WebSocket connected — live ingest", sc: colors.green },
  { t: "14:02", msg: "GitHub PR #1 created from incident #4421", sc: colors.github },
  { t: "14:01", msg: "RUNAWAY_LOOP guard tripped — patch queued", sc: colors.amber },
];

const AI_CALLS = [
  { t: "14:02:02", model: "claude-sonnet", tokens: "1.2k", purpose: "patch generation" },
  { t: "14:02:01", model: "claude-sonnet", tokens: "840", purpose: "root cause analysis" },
];

export default function DashboardPreview() {
  const [tab, setTab] = useState<Tab>("ISSUES & FIXES");
  const sectionRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) setVisible(true);
    }, { threshold: 0.15 });
    if (sectionRef.current) obs.observe(sectionRef.current);
    return () => obs.disconnect();
  }, []);

  return (
    <section ref={sectionRef} className="flow-section flow-tail-section" style={{ padding: "100px 32px" }}>
      <div style={{ textAlign: "center", marginBottom: 56 }}>
        <SectionMeta index="003" tag="(MISSION_CONTROL)" />
        <h2
          className="editorial-headline"
          style={{ fontSize: "clamp(2.5rem, 5vw, 4.5rem)", color: colors.white, marginTop: 8 }}
        >
          LIVE <em>console</em>.
          <br />
          <span style={{ color: colors.green }}>REAL TABS.</span>
        </h2>
      </div>

      <div
        className="corner-brackets"
        style={{
          maxWidth: 1180,
          margin: "0 auto",
          background: colors.bg2,
          border: `1px solid ${colors.borderStrong}`,
          overflow: "hidden",
          opacity: visible ? 1 : 0,
          transform: visible ? "translateY(0)" : "translateY(24px)",
          transition: "opacity 0.7s ease, transform 0.7s ease",
          boxShadow: `0 40px 120px rgba(0,0,0,0.85), 0 0 80px ${colors.glowDim}`,
          position: "relative",
        }}
      >
        <div
          style={{
            padding: "14px 20px",
            borderBottom: `1px solid ${colors.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MetaLabel accent={colors.glow}>(ORQIS_DASHBOARD)</MetaLabel>
            <span className="pulse-slow" style={{ width: 6, height: 6, borderRadius: "50%", background: colors.green }} />
            <MetaLabel accent={colors.green}>live ingest</MetaLabel>
          </div>
          <a
            href="/dashboard"
            className="btn-ghost"
            style={{ padding: "8px 16px", textDecoration: "none", fontSize: 10 }}
          >
            Open full →
          </a>
        </div>

        <div
          style={{
            display: "flex",
            gap: 0,
            borderBottom: `1px solid ${colors.border}`,
            overflowX: "auto",
          }}
        >
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: "12px 20px",
                border: "none",
                borderBottom: tab === t ? `2px solid ${colors.green}` : "2px solid transparent",
                background: tab === t ? colors.greenDim : "transparent",
                cursor: "pointer",
                ...mono,
                fontSize: 10,
                letterSpacing: "0.12em",
                color: tab === t ? colors.white : colors.dim,
                whiteSpace: "nowrap",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        <div style={{ padding: 24, minHeight: 420 }}>
          {tab === "ISSUES & FIXES" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}>
              <TerminalPanel label="open incidents" accent={colors.amber}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {["ID", "AGENT", "ERROR", "FIX", "STATUS"].map((h) => (
                        <th
                          key={h}
                          style={{
                            ...mono,
                            fontSize: 9,
                            color: colors.dimmer,
                            padding: "10px 14px",
                            textAlign: "left",
                            letterSpacing: "0.1em",
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {INCIDENTS.map((inc) => (
                      <tr key={inc.id} style={{ borderTop: `1px solid ${colors.border}` }}>
                        <td style={{ ...mono, fontSize: 11, color: colors.white, padding: "10px 14px" }}>{inc.id}</td>
                        <td style={{ ...mono, fontSize: 11, color: colors.muted, padding: "10px 14px" }}>{inc.agent}</td>
                        <td style={{ ...mono, fontSize: 11, color: colors.amber, padding: "10px 14px" }}>{inc.error}</td>
                        <td style={{ ...mono, fontSize: 10, color: colors.muted, padding: "10px 14px" }}>{inc.fix}</td>
                        <td style={{ ...mono, fontSize: 10, color: inc.sc, padding: "10px 14px" }}>{inc.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TerminalPanel>
              <TerminalPanel label="error rate · 60s" accent={colors.green}>
                <ResponsiveContainer width="100%" height={160}>
                  <AreaChart data={SPARK}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="t" tick={{ fontSize: 9, fill: colors.dim, fontFamily: "DM Mono" }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{
                        background: colors.bg3,
                        border: `1px solid ${colors.border}`,
                        fontFamily: "DM Mono",
                        fontSize: 11,
                      }}
                    />
                    <Area type="monotone" dataKey="e" stroke={colors.green} fill={colors.greenDim} strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </TerminalPanel>
            </div>
          )}

          {tab === "CHANGES" && (
            <TerminalPanel label="CHANGES · audit spine" accent={colors.green}>
              <div style={{ padding: "8px 0" }}>
                {CHANGES.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 20,
                      padding: "14px 18px",
                      borderBottom: i < CHANGES.length - 1 ? `1px solid ${colors.border}` : "none",
                      borderLeft: `2px solid ${c.sc}`,
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer, minWidth: 64 }}>{c.t}</span>
                    <span style={{ ...mono, fontSize: 12, color: colors.white, minWidth: 160 }}>{c.file}</span>
                    <span style={{ ...mono, fontSize: 11, color: c.sc }}>{c.action}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}

          {tab === "ACTIVITY" && (
            <TerminalPanel label="activity feed" accent={colors.glow}>
              <div style={{ padding: "8px 0" }}>
                {ACTIVITY.map((a, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 16,
                      padding: "12px 18px",
                      borderBottom: i < ACTIVITY.length - 1 ? `1px solid ${colors.border}` : "none",
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer, minWidth: 48 }}>{a.t}</span>
                    <span style={{ ...inter, fontSize: 13, color: a.sc }}>{a.msg}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}

          {tab === "AI CALLS" && (
            <TerminalPanel label="ai calls · attribution" accent={colors.github}>
              <div style={{ padding: "8px 0" }}>
                {AI_CALLS.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "64px 1fr 80px 1fr",
                      gap: 12,
                      padding: "12px 18px",
                      borderBottom: i < AI_CALLS.length - 1 ? `1px solid ${colors.border}` : "none",
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer }}>{c.t}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.github }}>{c.model}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.muted }}>{c.tokens}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.white }}>{c.purpose}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}
        </div>
      </div>
    </section>
  );
}
