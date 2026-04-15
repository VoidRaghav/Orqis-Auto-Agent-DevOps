"use client";

import { useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, RadialBarChart, RadialBar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const BAR_DATA = [
  { d: "Apr 1",  v: 12, f: 1 }, { d: "Apr 2",  v: 18, f: 0 },
  { d: "Apr 3",  v: 9,  f: 2 }, { d: "Apr 4",  v: 22, f: 1 },
  { d: "Apr 5",  v: 31, f: 4 }, { d: "Apr 6",  v: 14, f: 0 },
  { d: "Apr 7",  v: 27, f: 1 }, { d: "Apr 8",  v: 19, f: 0 },
  { d: "Apr 9",  v: 34, f: 2 }, { d: "Apr 10", v: 28, f: 1 },
  { d: "Apr 11", v: 41, f: 0 }, { d: "Apr 12", v: 38, f: 1 },
  { d: "Apr 13", v: 33, f: 0 }, { d: "Apr 14", v: 47, f: 2 },
];

const RADIAL_DATA = [{ name: "healed", value: 94, fill: "#00ff88" }];

const INCIDENTS = [
  { agent: "research-agent", error: "Tool loop ×47",   fix: "max_iter patch",   status: "auto-fixed", cost: "-$1.84", sc: "#00ff88" },
  { agent: "billing-agent",  error: "Token bloat",      fix: "prompt compress",  status: "auto-fixed", cost: "-$0.62", sc: "#00ff88" },
  { agent: "qa-agent",       error: "Hallucination",    fix: "temp ↓0.9→0.2",   status: "healing",    cost: "-$0.11", sc: "#ffaa00" },
  { agent: "scraper-v2",     error: "Silent crash",     fix: "retry + fallback", status: "auto-fixed", cost: "-$0.08", sc: "#00ff88" },
];

const FEED = [
  { time: "3:02m", agent: "scraper-v2",     msg: "silent crash → retry injected → back online",               mc: "#00ff88" },
  { time: "0:47s", agent: "billing-agent",  msg: "cost spike $4.20/run → compression applied → $0.31/run",   mc: "#ffaa00" },
  { time: "2:11m", agent: "qa-agent",       msg: "hallucination rate 18% → temperature adjusted → monitoring", mc: "#4d94ff" },
];

const KPIS = [
  { label: "AGENTS HEALED",  val: "247",    sub: "↑ 18 today",          sc: "#00ff88", tc: "#00ff88" },
  { label: "COST SAVED",     val: "$1,842", sub: "↑ $312 today",        sc: "#00ff88", tc: "#ffffff" },
  { label: "AVG FIX TIME",   val: "1.4s",   sub: "↓ 0.3s vs last wk",  sc: "#00ff88", tc: "#ffaa00" },
  { label: "ERROR RATE",     val: "0.3%",   sub: "↓ from 8.1%",        sc: "#00ff88", tc: "#ffffff" },
];

const NAV_ITEMS = [
  { section: "OVERVIEW",   items: ["Dashboard", "Trace Explorer", "Agent Runs"] },
  { section: "ANALYTICS",  items: ["Cost Attribution", "Tool Health", "Anomaly Feed"] },
  { section: "CONFIG",     items: ["Alert Rules", "SDK Setup"] },
];

export default function DashboardPreview() {
  const [active, setActive] = useState("Dashboard");
  const sectionRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.2 });
    if (sectionRef.current) obs.observe(sectionRef.current);
    return () => obs.disconnect();
  }, []);

  const mono: React.CSSProperties = { fontFamily: "'DM Mono', monospace" };
  const inter: React.CSSProperties = { fontFamily: "'Inter', sans-serif" };

  return (
    <section ref={sectionRef} style={{ backgroundColor: "#000000", padding: "100px 32px" }}>
      {/* Heading */}
      <div style={{ textAlign: "center", marginBottom: 60 }}>
        <span style={{ ...mono, fontSize: 11, letterSpacing: "0.2em", color: "#444", textTransform: "uppercase" }}>
          ◆ Mission Control
        </span>
        <h2 style={{
          fontFamily: "'Anton', sans-serif",
          fontSize: "clamp(2.5rem, 5vw, 4.5rem)",
          color: "#ffffff", lineHeight: 1, marginTop: 16, letterSpacing: "-0.01em",
        }}>
          YOUR DASHBOARD.<br />
          <span style={{ color: "#00ff88" }}>ALWAYS WATCHING.</span>
        </h2>
      </div>

      {/* Dashboard frame */}
      <div style={{
        maxWidth: 1200, margin: "0 auto",
        background: "#0a0a0a",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16, overflow: "hidden",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(30px)",
        transition: "opacity 0.7s ease, transform 0.7s ease",
        boxShadow: "0 40px 120px rgba(0,0,0,0.8), 0 0 0 1px rgba(0,255,136,0.05)",
      }}>
        {/* Title bar */}
        <div style={{
          background: "#111", height: 42, display: "flex", alignItems: "center",
          padding: "0 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
          gap: 10,
        }}>
          {["#ff5f57","#febc2e","#28c840"].map((c,i)=>(
            <div key={i} style={{ width: 11, height: 11, borderRadius: "50%", background: c }} />
          ))}
          <span style={{ ...mono, fontSize: 12, color: "#444", marginLeft: 8 }}>
            orqis · production dashboard
          </span>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#00ff88", animation: "pulse-slow 2s infinite" }} />
            <span style={{ ...mono, fontSize: 11, color: "#00ff88" }}>live · self-healing active</span>
          </div>
        </div>

        <div style={{ display: "flex", height: 640 }}>
          {/* Sidebar */}
          <div style={{
            width: 220, background: "#0a0a0a",
            borderRight: "1px solid rgba(255,255,255,0.06)",
            flexShrink: 0, padding: "12px 0",
            overflowY: "auto",
          }}>
            {NAV_ITEMS.map((group) => (
              <div key={group.section} style={{ marginBottom: 8 }}>
                <div style={{ ...mono, fontSize: 9, color: "#333", letterSpacing: "0.12em", padding: "8px 16px 4px" }}>
                  {group.section}
                </div>
                {group.items.map((item) => (
                  <button key={item} onClick={() => setActive(item)} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    width: "100%", padding: "7px 16px",
                    background: active === item ? "rgba(0,255,136,0.08)" : "transparent",
                    border: "none", borderLeft: `2px solid ${active === item ? "#00ff88" : "transparent"}`,
                    cursor: "pointer", textAlign: "left",
                    ...inter, fontSize: 13,
                    color: active === item ? "#ffffff" : "#666",
                    transition: "all 0.15s",
                  }}>
                    {item}
                    {item === "Agent Runs" && (
                      <span style={{ marginLeft: "auto", background: "#ff3333", color: "#fff", borderRadius: 10, padding: "1px 6px", fontSize: 10 }}>3</span>
                    )}
                    {item === "Tool Health" && (
                      <span style={{ marginLeft: "auto", background: "#ffaa00", color: "#000", borderRadius: 10, padding: "1px 6px", fontSize: 10 }}>2</span>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </div>

          {/* Main content */}
          <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
            {/* KPI grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
              {KPIS.map((k, i) => (
                <div key={i} style={{
                  background: "#111", border: "1px solid rgba(255,255,255,0.06)",
                  borderRadius: 10, padding: "14px 16px",
                  borderTop: `2px solid ${k.sc}`,
                }}>
                  <div style={{ ...mono, fontSize: 9, color: "#444", letterSpacing: "0.1em", marginBottom: 8 }}>{k.label}</div>
                  <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 32, color: k.tc, lineHeight: 1, marginBottom: 6 }}>{k.val}</div>
                  <div style={{ ...mono, fontSize: 10, color: "#00ff88" }}>{k.sub}</div>
                </div>
              ))}
            </div>

            {/* Charts row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: 12, marginBottom: 20 }}>
              {/* Bar chart */}
              <div style={{
                background: "#111", border: "1px solid rgba(255,255,255,0.06)",
                borderRadius: 10, padding: 16,
              }}>
                <div style={{ ...mono, fontSize: 10, color: "#444", letterSpacing: "0.1em", marginBottom: 16 }}>
                  INCIDENTS AUTO-RESOLVED · 14 DAYS
                </div>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={BAR_DATA} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="d" tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{ background: "#1a1a1a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6, fontFamily: "DM Mono", fontSize: 11 }}
                      labelStyle={{ color: "#666" }} itemStyle={{ color: "#00ff88" }}
                    />
                    <Bar dataKey="v" radius={[3,3,0,0]}>
                      {BAR_DATA.map((e, i) => (
                        <Cell key={i} fill={e.f > 0 ? "#ff3333" : i % 3 === 0 ? "#4d94ff" : "#00ff88"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Radial chart */}
              <div style={{
                background: "#111", border: "1px solid rgba(255,255,255,0.06)",
                borderRadius: 10, padding: 16, display: "flex", flexDirection: "column", alignItems: "center",
              }}>
                <div style={{ ...mono, fontSize: 10, color: "#444", letterSpacing: "0.1em", marginBottom: 8, textAlign: "center" }}>
                  AUTO-HEAL RATE
                </div>
                <div style={{ position: "relative", width: 120, height: 120 }}>
                  <RadialBarChart
                    width={120} height={120}
                    cx={60} cy={60}
                    innerRadius={40} outerRadius={55}
                    barSize={10}
                    data={RADIAL_DATA}
                    startAngle={90} endAngle={-270}
                  >
                    <RadialBar background={{ fill: "rgba(255,255,255,0.05)" }} dataKey="value" />
                  </RadialBarChart>
                  <div style={{
                    position: "absolute", inset: 0, display: "flex",
                    flexDirection: "column", alignItems: "center", justifyContent: "center",
                  }}>
                    <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 26, color: "#00ff88", lineHeight: 1 }}>94%</span>
                    <span style={{ ...mono, fontSize: 9, color: "#444" }}>healed</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Incidents table */}
            <div style={{
              background: "#111", border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 10, marginBottom: 16, overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                <span style={{ ...mono, fontSize: 10, color: "#444", letterSpacing: "0.1em" }}>RECENT INCIDENTS</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "rgba(255,255,255,0.02)" }}>
                    {["AGENT","ERROR TYPE","FIX APPLIED","STATUS","COST ↓"].map(h => (
                      <th key={h} style={{ ...mono, fontSize: 9, color: "#333", padding: "8px 14px", textAlign: "left", letterSpacing: "0.08em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {INCIDENTS.map((inc, i) => (
                    <tr key={i} style={{
                      borderTop: "1px solid rgba(255,255,255,0.04)",
                      background: inc.status === "healing" ? "rgba(255,170,0,0.03)" : "transparent",
                    }}>
                      <td style={{ ...mono, fontSize: 12, color: "#ffffff", padding: "10px 14px" }}>{inc.agent}</td>
                      <td style={{ ...inter, fontSize: 12, color: "#666", padding: "10px 14px" }}>{inc.error}</td>
                      <td style={{ padding: "10px 14px" }}>
                        <span style={{ ...mono, fontSize: 10, background: "rgba(255,255,255,0.06)", color: "#a0a0a0", padding: "3px 8px", borderRadius: 4 }}>
                          {inc.fix}
                        </span>
                      </td>
                      <td style={{ padding: "10px 14px" }}>
                        <span style={{
                          ...inter, fontSize: 11, fontWeight: 600,
                          color: inc.sc, background: inc.sc + "18",
                          padding: "3px 8px", borderRadius: 4,
                          display: "flex", alignItems: "center", gap: 5, width: "fit-content",
                        }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: inc.sc, animation: "pulse-slow 2s infinite" }} />
                          {inc.status}
                        </span>
                      </td>
                      <td style={{ ...mono, fontSize: 12, color: "#00ff88", padding: "10px 14px" }}>{inc.cost}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Live feed */}
            <div style={{
              background: "#111", border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 10, padding: 16,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00ff88", animation: "pulse-slow 1.5s infinite" }} />
                <span style={{ ...mono, fontSize: 10, color: "#444", letterSpacing: "0.1em" }}>LIVE HEALING FEED</span>
              </div>
              {FEED.map((f, i) => (
                <div key={i} style={{
                  display: "flex", gap: 12, padding: "8px 0",
                  borderTop: i > 0 ? "1px solid rgba(255,255,255,0.04)" : "none",
                }}>
                  <span style={{ ...mono, fontSize: 10, color: "#333", minWidth: 40 }}>{f.time}</span>
                  <span style={{ ...mono, fontSize: 12, fontWeight: 600, color: "#ffffff", minWidth: 110 }}>{f.agent}</span>
                  <span style={{ ...inter, fontSize: 12, color: "#666" }}>{f.msg}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
