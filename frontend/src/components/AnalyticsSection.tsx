"use client";

import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { SectionMeta } from "@/components/ui/MetaLabel";
import { colors, fonts, mono, inter } from "@/lib/tokens";

// 30-day token usage
const TOKEN_DATA = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  tokens: Math.round(12000 + Math.sin(i * 0.4) * 8000 + Math.random() * 5000 + (i > 20 ? -4000 : 0)),
}));

// Agent runs with failures
const RUNS_DATA = Array.from({ length: 14 }, (_, i) => ({
  day: `Apr ${i + 1}`,
  ok: Math.round(20 + Math.random() * 30),
  fail: i === 4 ? 8 : Math.round(Math.random() * 3),
}));

// Cost per run — dramatic drop when Orqis enabled at day 18
const COST_DATA = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  cost: i < 18
    ? +(0.8 + Math.random() * 1.2 + Math.sin(i * 0.5) * 0.4).toFixed(3)
    : +(0.06 + Math.random() * 0.08).toFixed(3),
}));

// Error rate — drops from ~18% to ~0.3% after Orqis
const ERR_DATA = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  rate: i < 18
    ? +(12 + Math.random() * 10 + Math.cos(i * 0.6) * 4).toFixed(1)
    : +(0.1 + Math.random() * 0.5).toFixed(1),
}));

const CHARTS = [
  {
    title: "Token Usage · 30 Days",
    sub: "Total LLM tokens consumed across all agents",
    chart: "area",
    data: TOKEN_DATA,
    key: "tokens",
    color: "#4d94ff",
    format: (v: number) => `${(v / 1000).toFixed(0)}k`,
  },
  {
    title: "Agent Runs · 14 Days",
    sub: "Successful vs failed executions",
    chart: "bar",
    data: RUNS_DATA,
    keyOk: "ok",
    keyFail: "fail",
  },
  {
    title: "Cost Per Run · 30 Days",
    sub: "Avg LLM cost per execution — orqis enabled day 18",
    chart: "line",
    data: COST_DATA,
    key: "cost",
    color: "#ffaa00",
    format: (v: number) => `$${v.toFixed(2)}`,
    refLine: 18,
  },
  {
    title: "Error Rate % · 30 Days",
    sub: "Percentage of runs ending in error",
    chart: "area",
    data: ERR_DATA,
    key: "rate",
    color: "#ff3333",
    format: (v: number) => `${v}%`,
    refLine: 18,
  },
];

const TT_STYLE = {
  contentStyle: { background: "#1a1a1a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontFamily: "DM Mono", fontSize: 11 },
  labelStyle: { color: "#666" },
};

export default function AnalyticsSection() {
  return (
    <section className="flow-section flow-tail-section" style={{ padding: "100px 32px" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 60 }}>
          <SectionMeta index="003" tag="(ANALYTICS)" />
          <h2
            className="editorial-headline"
            style={{ fontSize: "clamp(2.5rem, 5vw, 4.5rem)", color: colors.white, marginTop: 8 }}
          >
            OBSERVE <em>and</em> //
            <br />
            <span style={{ color: colors.green }}>AUTO-FIX.</span>
          </h2>
          <p style={{ ...inter, fontSize: 16, color: colors.muted, marginTop: 16, maxWidth: 520, margin: "16px auto 0" }}>
            Error rates, token burn, and incident volume — with patches and PRs flowing from the same console.
          </p>
        </div>

        {/* 2×2 chart grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {CHARTS.map((c, i) => (
            <div key={i} className="corner-brackets" style={{
              background: colors.bg2,
              border: `1px solid ${colors.border}`,
              borderRadius: 0, padding: 24,
              position: "relative",
            }}>
              <div style={{ marginBottom: 20 }}>
                <div style={{ ...mono, fontSize: 11, color: "#ffffff", marginBottom: 4 }}>{c.title}</div>
                <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 12, color: "#444" }}>{c.sub}</div>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                {c.chart === "area" ? (
                  <AreaChart data={c.data}>
                    <defs>
                      <linearGradient id={`g${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={c.color} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={c.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} interval={4} />
                    <YAxis tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} tickFormatter={c.format} width={36} />
                    <Tooltip {...TT_STYLE} itemStyle={{ color: c.color }} formatter={(v: any) => [c.format!(v), ""]} />
                    {c.refLine && <ReferenceLine x={`D${c.refLine}`} stroke="#00ff88" strokeDasharray="4 4" label={{ value: "orqis on", fill: "#00ff88", fontSize: 9, fontFamily: "DM Mono" }} />}
                    <Area type="monotone" dataKey={c.key!} stroke={c.color} strokeWidth={1.5} fill={`url(#g${i})`} dot={false} />
                  </AreaChart>
                ) : c.chart === "bar" ? (
                  <BarChart data={c.data} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} interval={1} />
                    <YAxis hide />
                    <Tooltip {...TT_STYLE} />
                    <Bar dataKey="ok"   stackId="a" fill="#00ff88" radius={[0,0,0,0]} />
                    <Bar dataKey="fail" stackId="a" fill="#ff3333" radius={[3,3,0,0]} />
                  </BarChart>
                ) : (
                  <LineChart data={c.data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} interval={4} />
                    <YAxis tick={{ fontSize: 9, fill: "#444", fontFamily: "DM Mono" }} axisLine={false} tickLine={false} tickFormatter={c.format} width={36} />
                    <Tooltip {...TT_STYLE} itemStyle={{ color: c.color }} formatter={(v: any) => [c.format!(v), ""]} />
                    {c.refLine && <ReferenceLine x={`D${c.refLine}`} stroke="#00ff88" strokeDasharray="4 4" label={{ value: "orqis on", fill: "#00ff88", fontSize: 9, fontFamily: "DM Mono" }} />}
                    <Line type="monotone" dataKey={c.key!} stroke={c.color} strokeWidth={1.5} dot={false} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
