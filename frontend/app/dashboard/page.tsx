"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useOrqisStream } from "@/lib/useOrqisStream";
import type { LogEvent, Incident, TraceEvent } from "@/lib/types";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area,
} from "recharts";

const WS_URL  = process.env.NEXT_PUBLIC_WS_URL  ?? "ws://localhost:8000/ws";
const API_URL = process.env.NEXT_PUBLIC_API_URL  ?? "http://localhost:8000";

// ── colour tokens ────────────────────────────────────────────────────────────
const C = {
  green:  "#00ff88",
  amber:  "#ffaa00",
  red:    "#ff3333",
  blue:   "#4d94ff",
  white:  "#ffffff",
  dim:    "#444444",
  dimmer: "#222222",
  bg:     "#000000",
  bg2:    "#080808",
  bg3:    "#111111",
  border: "rgba(255,255,255,0.07)",
};

const LEVEL_COLOR: Record<string, string> = {
  DEBUG:    C.dim,
  INFO:     "#888888",
  WARNING:  C.amber,
  ERROR:    C.red,
  CRITICAL: C.red,
};

const TYPE_COLOR: Record<string, string> = {
  CONNECTION:     C.blue,
  AUTHENTICATION: C.amber,
  RATE_LIMIT:     C.amber,
  TIMEOUT:        C.amber,
  MEMORY:         C.red,
  RECURSION:      C.red,
  HTTP_ERROR:     C.red,
  TRACEBACK:      C.red,
  TYPE_ERROR:     "#cc77ff",
  VALUE_ERROR:    "#cc77ff",
  ATTRIBUTE_ERROR:"#cc77ff",
  IMPORT_ERROR:   "#cc77ff",
  TOOL_FAILURE:   C.amber,
  SYNTAX_ERROR:   C.red,
  PERMISSION_ERROR: C.amber,
  GENERIC:        C.dim,
};

// ── shared style primitives ──────────────────────────────────────────────────
const mono: React.CSSProperties = { fontFamily: "'DM Mono', monospace" };
const inter: React.CSSProperties = { fontFamily: "'Inter', sans-serif" };

function Panel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: C.bg3,
      border: `1px solid ${C.border}`,
      borderRadius: 12,
      overflow: "hidden",
      ...style,
    }}>
      {children}
    </div>
  );
}

function PanelHeader({ label, right }: { label: string; right?: React.ReactNode }) {
  return (
    <div style={{
      padding: "10px 16px",
      borderBottom: `1px solid ${C.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      background: C.bg2,
    }}>
      <span style={{ ...mono, fontSize: 10, color: C.dim, letterSpacing: "0.1em", textTransform: "uppercase" as const }}>{label}</span>
      {right}
    </div>
  );
}

function LiveDot({ color = C.green }: { color?: string }) {
  return (
    <span style={{
      display: "inline-block",
      width: 7, height: 7,
      borderRadius: "50%",
      background: color,
      animation: "pulse-slow 2s ease-in-out infinite",
    }} />
  );
}

// ── KPI bar ──────────────────────────────────────────────────────────────────
function KpiBar({ events, incidents, connected }: {
  events: LogEvent[];
  incidents: Incident[];
  connected: boolean;
}) {
  const errors   = events.filter(e => e.is_error).length;
  const warnings = events.filter(e => e.level === "WARNING").length;
  const open     = incidents.filter(i => i.status === "open" || i.status === "patched").length;
  const healed   = incidents.filter(i => i.status === "approved").length;

  const kpis = [
    { label: "LOG LINES",   val: events.length,  color: C.white  },
    { label: "ERRORS",      val: errors,          color: C.red    },
    { label: "WARNINGS",    val: warnings,        color: C.amber  },
    { label: "OPEN",        val: open,            color: C.amber  },
    { label: "HEALED",      val: healed,          color: C.green  },
  ];

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 2,
      padding: "0 20px",
      height: 54,
      borderBottom: `1px solid ${C.border}`,
      background: C.bg2,
      overflowX: "auto" as const,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginRight: 20, flexShrink: 0 }}>
        <LiveDot color={connected ? C.green : C.red} />
        <span style={{ ...mono, fontSize: 11, color: connected ? C.green : C.red }}>
          {connected ? "LIVE" : "RECONNECTING"}
        </span>
      </div>

      {kpis.map((k, i) => (
        <div key={i} style={{
          display: "flex",
          alignItems: "baseline",
          gap: 6,
          padding: "0 16px",
          borderLeft: `1px solid ${C.border}`,
          flexShrink: 0,
        }}>
          <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 22, color: k.color, lineHeight: 1 }}>
            {k.val}
          </span>
          <span style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em" }}>{k.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── log row ──────────────────────────────────────────────────────────────────
function LogRow({ event, flash }: { event: LogEvent; flash: boolean }) {
  const levelColor = LEVEL_COLOR[event.level] ?? C.white;
  const typeColor  = event.error_type ? (TYPE_COLOR[event.error_type] ?? C.red) : undefined;

  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "5px 14px",
      borderBottom: `1px solid rgba(255,255,255,0.025)`,
      alignItems: "flex-start",
      background: flash ? "rgba(0,255,136,0.04)" : "transparent",
      transition: "background 0.8s ease",
      animation: "log-slide-in 0.2s ease-out",
    }}>
      {/* timestamp */}
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0, paddingTop: 2 }}>
        {new Date(event.timestamp).toLocaleTimeString("en", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>

      {/* level badge */}
      <span style={{
        ...mono, fontSize: 9,
        padding: "2px 6px", borderRadius: 4,
        background: levelColor + "18",
        color: levelColor,
        flexShrink: 0,
        letterSpacing: "0.06em",
        minWidth: 52,
        textAlign: "center" as const,
      }}>
        {event.level}
      </span>

      {/* error type badge */}
      {event.error_type && typeColor && (
        <span style={{
          ...mono, fontSize: 9,
          padding: "2px 6px", borderRadius: 4,
          background: typeColor + "18",
          color: typeColor,
          flexShrink: 0,
          letterSpacing: "0.06em",
          minWidth: 80,
          textAlign: "center" as const,
        }}>
          {event.error_type}
        </span>
      )}

      {/* source */}
      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{event.source}</span>

      {/* message */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ ...mono, fontSize: 12, color: event.is_error ? "#dddddd" : "#666666", wordBreak: "break-all" as const }}>
          {event.raw_line.length > 200 ? event.raw_line.slice(0, 200) + "…" : event.raw_line}
        </div>
        {event.interpretation && (
          <div style={{ ...inter, fontSize: 11, color: C.green, marginTop: 3, opacity: 0.85 }}>
            ↳ {event.interpretation}
          </div>
        )}
      </div>
    </div>
  );
}

// ── diff viewer ───────────────────────────────────────────────────────────────
function DiffViewer({ diff }: { diff: string }) {
  return (
    <div style={{ padding: "8px 0" }}>
      {diff.split("\n").map((line, i) => {
        const isAdd = line.startsWith("+") && !line.startsWith("+++");
        const isRem = line.startsWith("-") && !line.startsWith("---");
        const isAt  = line.startsWith("@@");
        return (
          <div key={i} style={{
            display: "flex",
            background: isAdd ? "rgba(0,255,136,0.07)" : isRem ? "rgba(255,51,51,0.07)" : "transparent",
            borderLeft: `3px solid ${isAdd ? C.green : isRem ? C.red : "transparent"}`,
          }}>
            <span style={{
              ...mono, fontSize: 11,
              color: isAdd ? C.green : isRem ? C.red : isAt ? C.blue : C.dim,
              padding: "2px 12px",
              userSelect: "none" as const,
              minWidth: 16,
            }}>
              {isAdd ? "+" : isRem ? "−" : " "}
            </span>
            <span style={{
              ...mono, fontSize: 11,
              color: isAdd ? "rgba(0,255,136,0.9)" : isRem ? "rgba(255,51,51,0.8)" : isAt ? C.blue : "#555",
              padding: "2px 8px 2px 0",
              wordBreak: "break-all" as const,
            }}>
              {line.slice(1) || line}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── incident card ─────────────────────────────────────────────────────────────
function IncidentCard({
  incident,
  onApprove,
  onDismiss,
}: {
  incident: Incident;
  onApprove: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);

  const statusColor = {
    open:      C.amber,
    patched:   C.green,
    approved:  C.green,
    dismissed: C.dim,
  }[incident.status] ?? C.dim;

  const isActive = incident.status === "open" || incident.status === "patched";

  async function handleApprove() {
    setLoading(true);
    try { await onApprove(incident.id); } finally { setLoading(false); }
  }
  async function handleDismiss() {
    setLoading(true);
    try { await onDismiss(incident.id); } finally { setLoading(false); }
  }

  return (
    <div style={{
      background: isActive ? C.bg2 : "transparent",
      border: `1px solid ${isActive ? statusColor + "30" : C.border}`,
      borderRadius: 10,
      marginBottom: 8,
      overflow: "hidden",
      transition: "border-color 0.3s ease",
      animation: incident.status === "open" ? "row-pulse 3s ease-in-out infinite" : "none",
    }}>
      {/* header row */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", cursor: "pointer" }}
        onClick={() => setExpanded(x => !x)}
      >
        <LiveDot color={statusColor} />

        <span style={{
          ...mono, fontSize: 9,
          padding: "2px 7px", borderRadius: 4,
          background: statusColor + "18",
          color: statusColor,
          letterSpacing: "0.06em",
          flexShrink: 0,
        }}>
          {incident.status.toUpperCase()}
        </span>

        {incident.hit_count > 1 && (
          <span style={{ ...mono, fontSize: 10, color: C.red, flexShrink: 0 }}>×{incident.hit_count}</span>
        )}

        {incident.error_type && (
          <span style={{ ...mono, fontSize: 9, color: TYPE_COLOR[incident.error_type] ?? C.dim, flexShrink: 0 }}>
            [{incident.error_type}]
          </span>
        )}

        <span style={{ ...inter, fontSize: 12, color: "#888", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
          {incident.error_message.slice(0, 120)}
        </span>

        {incident.file_path && (
          <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>
            {incident.file_path.split("/").slice(-2).join("/")}:{incident.error_line}
          </span>
        )}

        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* expanded body */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${C.border}`, padding: "12px 14px" }}>
          {incident.interpretation && (
            <div style={{ ...inter, fontSize: 12, color: C.green, marginBottom: 12 }}>
              {incident.interpretation}
            </div>
          )}

          {/* code context */}
          {incident.code_context && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                CODE CONTEXT · {incident.function_name}() · line {incident.context_start_line}
              </div>
              <div style={{
                background: C.bg,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "8px 0",
                overflowX: "auto" as const,
              }}>
                {incident.code_context.split("\n").map((line, i) => {
                  const lineno = (incident.context_start_line ?? 1) + i;
                  const isErr  = lineno === incident.error_line;
                  return (
                    <div key={i} style={{
                      display: "flex",
                      gap: 12,
                      padding: "2px 12px",
                      background: isErr ? "rgba(255,51,51,0.08)" : "transparent",
                      borderLeft: `3px solid ${isErr ? C.red : "transparent"}`,
                    }}>
                      <span style={{ ...mono, fontSize: 11, color: C.dimmer, minWidth: 32, textAlign: "right" as const, userSelect: "none" as const }}>
                        {lineno}
                      </span>
                      <span style={{ ...mono, fontSize: 11, color: isErr ? "#dddddd" : "#555" }}>{line}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* diff */}
          {incident.diff && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                SUGGESTED FIX
              </div>
              <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, overflowX: "auto" as const }}>
                <DiffViewer diff={incident.diff} />
              </div>
            </div>
          )}

          {/* action buttons */}
          {isActive && (
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {incident.diff && (
                <button
                  onClick={handleApprove}
                  disabled={loading}
                  style={{
                    ...inter,
                    padding: "7px 18px",
                    borderRadius: 7,
                    border: `1px solid ${C.green}40`,
                    background: `${C.green}12`,
                    color: C.green,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: loading ? "not-allowed" : "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  {loading ? "Applying…" : "Apply Fix →"}
                </button>
              )}
              <button
                onClick={handleDismiss}
                disabled={loading}
                style={{
                  ...inter,
                  padding: "7px 18px",
                  borderRadius: 7,
                  border: `1px solid ${C.border}`,
                  background: "transparent",
                  color: C.dim,
                  fontSize: 12,
                  cursor: loading ? "not-allowed" : "pointer",
                  transition: "all 0.15s",
                }}
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── error rate sparkline data ─────────────────────────────────────────────────
function buildSparkline(events: LogEvent[]) {
  const buckets: Record<string, { errors: number; total: number }> = {};
  const now = Date.now();
  for (let i = 9; i >= 0; i--) {
    const key = String(i);
    buckets[key] = { errors: 0, total: 0 };
  }
  for (const e of events) {
    const age = (now - new Date(e.timestamp).getTime()) / 1000;
    if (age > 60) continue;
    const bucket = String(Math.min(9, Math.floor(age / 6)));
    buckets[bucket].total++;
    if (e.is_error) buckets[bucket].errors++;
  }
  return Object.values(buckets).reverse();
}

// ── trace row ─────────────────────────────────────────────────────────────────
function TraceRow({ trace }: { trace: TraceEvent }) {
  const kindColor = trace.is_error ? C.red : trace.kind.includes("end") ? C.green : C.blue;
  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "6px 14px",
      borderBottom: `1px solid rgba(255,255,255,0.025)`,
      alignItems: "center",
    }}>
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0 }}>
        {new Date(trace.timestamp).toLocaleTimeString("en", { hour12: false })}
      </span>
      <span style={{
        ...mono, fontSize: 9, padding: "2px 6px", borderRadius: 4,
        background: kindColor + "18", color: kindColor, flexShrink: 0,
        minWidth: 72, textAlign: "center" as const,
      }}>
        {trace.kind}
      </span>
      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.provider}</span>
      {trace.model && <span style={{ ...mono, fontSize: 10, color: "#555", flexShrink: 0 }}>{trace.model}</span>}
      {trace.cost_usd != null && (
        <span style={{ ...mono, fontSize: 10, color: trace.cost_usd > 0.1 ? C.amber : C.green, marginLeft: "auto", flexShrink: 0 }}>
          ${trace.cost_usd.toFixed(4)}
        </span>
      )}
      {trace.latency_ms != null && (
        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.latency_ms}ms</span>
      )}
    </div>
  );
}

// ── main dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { events, traces, incidents, connected, approveIncident, dismissIncident } =
    useOrqisStream(WS_URL, API_URL);

  const [activeTab, setActiveTab] = useState<"logs" | "incidents" | "traces">("logs");
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const prevEventCount = useRef(0);

  // Auto-scroll log stream
  useEffect(() => {
    if (autoScroll && logRef.current && events.length > prevEventCount.current) {
      logRef.current.scrollTop = 0;
    }
    prevEventCount.current = events.length;
  }, [events.length, autoScroll]);

  // Track which event IDs are "new" for the flash animation
  const flashSet = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (events[0]) {
      flashSet.current.add(events[0].id);
      setTimeout(() => flashSet.current.delete(events[0].id), 800);
    }
  }, [events[0]?.id]);

  const sparkData = buildSparkline(events);
  const openCount = incidents.filter(i => i.status === "open" || i.status === "patched").length;
  const totalCost = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);

  const tabs = [
    { id: "logs",      label: "LOG STREAM",  badge: null },
    { id: "incidents", label: "INCIDENTS",   badge: openCount > 0 ? openCount : null },
    { id: "traces",    label: "TRACES",      badge: null },
  ] as const;

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column" as const,
      fontFamily: "'DM Mono', monospace",
    }}>
      {/* Top bar */}
      <div style={{
        height: 54,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        borderBottom: `1px solid ${C.border}`,
        background: C.bg2,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {/* Logo */}
          <a href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
            <div style={{
              width: 26, height: 26, borderRadius: 6,
              background: "linear-gradient(135deg, #ffffff 0%, #a0a0a0 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, color: "#000",
            }}>⌬</div>
            <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 16, color: C.white, letterSpacing: "0.03em" }}>ORQIS</span>
          </a>

          <span style={{ color: C.border, fontSize: 16 }}>/</span>
          <span style={{ ...mono, fontSize: 12, color: C.dim }}>production</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {totalCost > 0 && (
            <span style={{ ...mono, fontSize: 11, color: totalCost > 1 ? C.amber : C.green }}>
              ${totalCost.toFixed(4)} tracked
            </span>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LiveDot color={connected ? C.green : C.red} />
            <span style={{ ...mono, fontSize: 10, color: connected ? C.green : C.red }}>
              {connected ? "CONNECTED" : "OFFLINE"}
            </span>
          </div>
        </div>
      </div>

      {/* KPI bar */}
      <KpiBar events={events} incidents={incidents} connected={connected} />

      {/* Main layout */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* ── left: log / incidents / traces panel ── */}
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column" as const,
          overflow: "hidden",
          borderRight: `1px solid ${C.border}`,
        }}>
          {/* Tabs */}
          <div style={{
            display: "flex",
            gap: 0,
            borderBottom: `1px solid ${C.border}`,
            background: C.bg2,
            flexShrink: 0,
          }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  ...mono,
                  padding: "10px 20px",
                  fontSize: 10,
                  letterSpacing: "0.1em",
                  color: activeTab === tab.id ? C.white : C.dim,
                  background: "transparent",
                  border: "none",
                  borderBottom: `2px solid ${activeTab === tab.id ? C.green : "transparent"}`,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  transition: "color 0.15s, border-color 0.15s",
                }}
              >
                {tab.label}
                {tab.badge != null && (
                  <span style={{
                    background: C.red,
                    color: C.white,
                    borderRadius: 10,
                    padding: "1px 6px",
                    fontSize: 9,
                    fontWeight: 700,
                  }}>
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}

            {activeTab === "logs" && (
              <button
                onClick={() => setAutoScroll(x => !x)}
                style={{
                  ...mono,
                  marginLeft: "auto",
                  padding: "10px 16px",
                  fontSize: 9,
                  color: autoScroll ? C.green : C.dim,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  letterSpacing: "0.08em",
                }}
              >
                {autoScroll ? "⬆ AUTO" : "PAUSED"}
              </button>
            )}
          </div>

          {/* Content */}
          <div ref={logRef} style={{ flex: 1, overflowY: "auto" as const }}>
            {activeTab === "logs" && (
              events.length === 0
                ? <EmptyState label="Waiting for log events…" />
                : events.map(e => (
                    <LogRow key={e.id} event={e} flash={flashSet.current.has(e.id)} />
                  ))
            )}

            {activeTab === "incidents" && (
              <div style={{ padding: 14 }}>
                {incidents.length === 0
                  ? <EmptyState label="No incidents yet." />
                  : incidents.map(i => (
                      <IncidentCard
                        key={i.id}
                        incident={i}
                        onApprove={approveIncident}
                        onDismiss={dismissIncident}
                      />
                    ))
                }
              </div>
            )}

            {activeTab === "traces" && (
              traces.length === 0
                ? <EmptyState label="No trace events yet. Add orqis.init() to your app." />
                : traces.map(t => <TraceRow key={t.id} trace={t} />)
            )}
          </div>
        </div>

        {/* ── right sidebar ── */}
        <div style={{
          width: 320,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column" as const,
          gap: 12,
          padding: 14,
          overflowY: "auto" as const,
          background: C.bg,
        }}>
          {/* Error rate sparkline */}
          <Panel>
            <PanelHeader label="Error rate · last 60s" />
            <div style={{ padding: "12px 8px 8px" }}>
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
                    contentStyle={{ background: C.bg3, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: "DM Mono", fontSize: 10 }}
                    labelStyle={{ color: C.dim }}
                    itemStyle={{ color: C.red }}
                  />
                  <Area type="monotone" dataKey="errors" stroke={C.red} strokeWidth={1.5} fill="url(#errGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {/* Error type breakdown */}
          <Panel>
            <PanelHeader label="Error types" />
            <ErrorBreakdown events={events} />
          </Panel>

          {/* Cost tracker */}
          {traces.length > 0 && (
            <Panel>
              <PanelHeader label="LLM cost" />
              <CostTracker traces={traces} />
            </Panel>
          )}

          {/* Setup hint */}
          <Panel style={{ border: `1px solid ${C.green}20` }}>
            <PanelHeader label="Connect your app" right={<span style={{ ...mono, fontSize: 9, color: C.green }}>SDK</span>} />
            <div style={{ padding: "12px 14px" }}>
              <div style={{ ...mono, fontSize: 10, color: C.dim, marginBottom: 8 }}>Instrument in one line:</div>
              <div style={{
                background: C.bg,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "10px 12px",
              }}>
                <div style={{ ...mono, fontSize: 11, color: "#cc77ff" }}>import <span style={{ color: C.green }}>orqis</span></div>
                <div style={{ ...mono, fontSize: 11, color: C.green }}>orqis<span style={{ color: C.white }}>.init()</span></div>
              </div>
              <div style={{ ...inter, fontSize: 11, color: C.dim, marginTop: 10, lineHeight: 1.6 }}>
                Auto-patches OpenAI, Anthropic &amp; LangChain. Zero config.
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ── supporting sub-components ─────────────────────────────────────────────────

function EmptyState({ label }: { label: string }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column" as const,
      alignItems: "center",
      justifyContent: "center",
      height: 200,
      gap: 12,
      opacity: 0.4,
    }}>
      <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 32, color: C.dim }}>⌬</div>
      <span style={{ ...mono, fontSize: 11, color: C.dim }}>{label}</span>
    </div>
  );
}

function ErrorBreakdown({ events }: { events: LogEvent[] }) {
  const counts: Record<string, number> = {};
  for (const e of events) {
    if (e.error_type) counts[e.error_type] = (counts[e.error_type] ?? 0) + 1;
  }
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  if (sorted.length === 0) {
    return <div style={{ ...mono, fontSize: 10, color: C.dim, padding: "12px 14px" }}>No errors yet.</div>;
  }
  const max = sorted[0][1];
  return (
    <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column" as const, gap: 6 }}>
      {sorted.map(([type, count]) => {
        const color = TYPE_COLOR[type] ?? C.dim;
        return (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ ...mono, fontSize: 10, color, minWidth: 100 }}>{type}</span>
            <div style={{ flex: 1, background: C.bg, borderRadius: 3, height: 4, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${(count / max) * 100}%`,
                background: color,
                borderRadius: 3,
                transition: "width 0.4s ease",
              }} />
            </div>
            <span style={{ ...mono, fontSize: 10, color: C.dim, minWidth: 20, textAlign: "right" as const }}>{count}</span>
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
      <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 28, color: total > 1 ? C.amber : C.green, marginBottom: 10 }}>
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
