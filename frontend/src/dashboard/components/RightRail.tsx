"use client";

import type { LogEvent, TraceEvent } from "@/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { C, TYPE_COLOR } from "../constants";
import { mono, inter, buildSparkline } from "../shared";
import { Panel, PanelHeader } from "./ui";

function ErrorBreakdown({ events }: { events: LogEvent[] }) {
  const counts: Record<string, number> = {};
  for (const e of events) {
    if (e.error_type) counts[e.error_type] = (counts[e.error_type] ?? 0) + 1;
  }
  const sorted = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  if (sorted.length === 0) {
    return <div style={{ ...mono, fontSize: 10, color: C.dim, padding: "12px 14px" }}>No errors yet.</div>;
  }
  const max = sorted[0][1];
  return (
    <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 6 }}>
      {sorted.map(([type, count]) => {
        const color = TYPE_COLOR[type] ?? C.dim;
        return (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ ...mono, fontSize: 10, color, minWidth: 100 }}>{type}</span>
            <div style={{ flex: 1, background: C.bg, borderRadius: 3, height: 4, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${(count / max) * 100}%`,
                  background: color,
                  borderRadius: 3,
                  transition: "width 0.4s ease",
                }}
              />
            </div>
            <span style={{ ...mono, fontSize: 10, color: C.dim, minWidth: 20, textAlign: "right" }}>{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function CostTracker({ traces }: { traces: TraceEvent[] }) {
  const total = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);
  const byProvider: Record<string, number> = {};
  for (const t of traces) {
    if (t.cost_usd) byProvider[t.provider] = (byProvider[t.provider] ?? 0) + t.cost_usd;
  }
  const provColors: Record<string, string> = { openai: C.green, anthropic: C.blue, langchain: C.amber };

  return (
    <div style={{ padding: "12px 14px" }}>
      <div
        style={{
          fontFamily: "'Anton', sans-serif",
          fontSize: 28,
          color: total > 1 ? C.amber : C.green,
          marginBottom: 10,
        }}
      >
        ${total.toFixed(4)}
      </div>
      {Object.entries(byProvider).map(([p, cost]) => (
        <div key={p} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ ...mono, fontSize: 10, color: provColors[p] ?? C.dim }}>{p}</span>
          <span style={{ ...mono, fontSize: 10, color: C.dim }}>${cost.toFixed(4)}</span>
        </div>
      ))}
    </div>
  );
}

export default function RightRail({ events, traces }: { events: LogEvent[]; traces: TraceEvent[] }) {
  const sparkData = buildSparkline(events);

  return (
    <div
      className="dashboard-right-rail"
      style={{
        width: 320,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: 14,
        overflowY: "auto",
        background: C.bg,
      }}
    >
      <Panel>
        <PanelHeader label="Error rate · last 60s" />
        <div style={{ padding: "12px 8px 8px" }}>
          {events.length === 0 ? (
            <div style={{ ...mono, fontSize: 10, color: C.dim, padding: "8px 6px 16px" }}>
              Flat — no events yet.
            </div>
          ) : (
          <ResponsiveContainer width="100%" height={80}>
            <AreaChart data={sparkData}>
              <defs>
                <linearGradient id="errGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={C.red} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={C.red} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="label" hide />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  background: C.bg3,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  fontFamily: "DM Mono",
                  fontSize: 10,
                }}
                labelStyle={{ color: C.dim }}
                itemStyle={{ color: C.red }}
              />
              <Area type="monotone" dataKey="errors" stroke={C.red} strokeWidth={1.5} fill="url(#errGrad)" />
            </AreaChart>
          </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {events.some((e) => e.is_error) && (
        <Panel>
          <PanelHeader label="Error types" />
          <ErrorBreakdown events={events} />
        </Panel>
      )}

      {traces.length > 0 && (
        <Panel>
          <PanelHeader label="LLM cost" />
          <CostTracker traces={traces} />
        </Panel>
      )}

      {traces.length === 0 && (
        <Panel style={{ border: `1px solid ${C.green}20` }}>
          <PanelHeader
            label="Connect your app"
            right={<span style={{ ...mono, fontSize: 9, color: C.green }}>SDK</span>}
          />
          <div style={{ padding: "12px 14px" }}>
            <div style={{ ...mono, fontSize: 10, color: C.dim, marginBottom: 8 }}>One line:</div>
            <div
              style={{
                background: C.bg,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "10px 12px",
              }}
            >
              <div style={{ ...mono, fontSize: 11, color: "#cc77ff" }}>
                import <span style={{ color: C.green }}>orqis</span>
              </div>
              <div style={{ ...mono, fontSize: 11, color: C.green }}>
                orqis<span style={{ color: C.white }}>.init()</span>
              </div>
            </div>
            <div style={{ ...inter, fontSize: 11, color: C.dim, marginTop: 10 }}>
              OpenAI · Anthropic · LangChain
            </div>
            <a
              href="/settings"
              style={{
                ...inter,
                display: "inline-block",
                marginTop: 12,
                fontSize: 11,
                color: C.github,
                textDecoration: "none",
              }}
            >
              Connect GitHub →
            </a>
          </div>
        </Panel>
      )}
    </div>
  );
}
