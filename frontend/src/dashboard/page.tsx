"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useOrqisStream } from "@/lib/useOrqisStream";
import { C, ACTIVE_STATUSES } from "./constants";
import { mono } from "./shared";
import TopBar from "./components/TopBar";
import HealthHero from "./components/HealthHero";
import KpiStrip from "./components/KpiStrip";
import LogRow from "./components/LogRow";
import IncidentCard from "./components/IncidentCard";
import ChangeRow from "./components/ChangeRow";
import TraceRow from "./components/TraceRow";
import RightRail from "./components/RightRail";
import { EmptyState } from "./components/ui";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const {
    events,
    traces,
    incidents,
    changes,
    github,
    connected,
    approveIncident,
    dismissIncident,
    openPr,
    resolveIncident,
    copyPrompt,
  } = useOrqisStream(WS_URL, API_URL);

  const [activeTab, setActiveTab] = useState<"logs" | "incidents" | "traces" | "changes">("incidents");
  const [highlightIncidentId, setHighlightIncidentId] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const prevEventCount = useRef(0);

  useEffect(() => {
    if (autoScroll && logRef.current && events.length > prevEventCount.current) {
      logRef.current.scrollTop = 0;
    }
    prevEventCount.current = events.length;
  }, [events.length, autoScroll]);

  const flashSet = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (events[0]) {
      flashSet.current.add(events[0].id);
      setTimeout(() => flashSet.current.delete(events[0].id), 800);
    }
  }, [events[0]?.id]);

  const openCount = incidents.filter((i) => ACTIVE_STATUSES.has(i.status)).length;
  const totalCost = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);

  const viewIncidentFromChange = useCallback((incidentId: string) => {
    setActiveTab("incidents");
    setHighlightIncidentId(incidentId);
    setTimeout(() => setHighlightIncidentId(null), 2500);
  }, []);

  const tabs = [
    { id: "incidents", label: "ISSUES & FIXES", badge: openCount > 0 ? openCount : null },
    { id: "changes", label: "CHANGES", badge: changes.length > 0 ? changes.length : null },
    { id: "logs", label: "ACTIVITY", badge: null },
    { id: "traces", label: "AI CALLS", badge: null },
  ] as const;

  const hasPrChanges = changes.some((c) => c.action === "pr_opened" || c.action === "pr_merged");

  return (
    <div
      className="terminal-grid"
      style={{
        background: C.bg,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'DM Mono', monospace",
      }}
    >
      <TopBar connected={connected} totalCost={totalCost} github={github} />

      <HealthHero
        incidents={incidents}
        connected={connected}
        hasChanges={changes.length > 0}
        onViewIssues={() => setActiveTab("incidents")}
      />

      <KpiStrip events={events} incidents={incidents} connected={connected} />

      <div className="dashboard-main" style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderRight: `1px solid ${C.border}`,
            minWidth: 0,
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 0,
              borderBottom: `1px solid ${C.border}`,
              background: C.bg2,
              flexShrink: 0,
              overflowX: "auto",
            }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`mc-tab ${activeTab === tab.id ? "mc-tab-active" : ""} ${
                  tab.id === "changes" && hasPrChanges && activeTab === "changes" ? "mc-tab-pr" : ""
                }`}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                {tab.label}
                {tab.badge != null && (
                  <span
                    style={{
                      background: C.red,
                      color: C.white,
                      borderRadius: 10,
                      padding: "1px 6px",
                      fontSize: 9,
                      fontWeight: 700,
                    }}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}

            {activeTab === "logs" && (
              <button
                onClick={() => setAutoScroll((x) => !x)}
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

          <div ref={logRef} style={{ flex: 1, overflowY: "auto" }}>
            {activeTab === "logs" &&
              (events.length === 0 ? (
                <EmptyState label="Waiting for log events…" />
              ) : (
                events.map((e) => <LogRow key={e.id} event={e} flash={flashSet.current.has(e.id)} />)
              ))}

            {activeTab === "incidents" && (
              <div style={{ padding: 14 }}>
                {incidents.length === 0 ? (
                  <EmptyState label="No problems found. Your app is healthy." />
                ) : (
                  incidents.map((i) => (
                    <IncidentCard
                      key={i.id}
                      incident={i}
                      highlighted={highlightIncidentId === i.id}
                      onApprove={approveIncident}
                      onDismiss={dismissIncident}
                      onOpenPr={openPr}
                      onResolve={resolveIncident}
                      onCopyPrompt={copyPrompt}
                    />
                  ))
                )}
              </div>
            )}

            {activeTab === "changes" &&
              (changes.length === 0 ? (
                <EmptyState label="No changes yet." hint="Connect GitHub in Settings →" />
              ) : (
                <div style={{ padding: 14, position: "relative" }}>
                  <div
                    style={{
                      position: "absolute",
                      left: 26,
                      top: 20,
                      bottom: 20,
                      width: 2,
                      background: `linear-gradient(180deg, ${C.github}40, ${C.green}40)`,
                    }}
                  />
                  {changes.map((c) => (
                    <ChangeRow key={c.id} change={c} onViewIncident={viewIncidentFromChange} />
                  ))}
                </div>
              ))}

            {activeTab === "traces" &&
              (traces.length === 0 ? (
                <EmptyState label="No trace events yet. Add orqis.init() to your app." />
              ) : (
                traces.map((t) => <TraceRow key={t.id} trace={t} />)
              ))}
          </div>
        </div>

        <RightRail events={events} traces={traces} />
      </div>
    </div>
  );
}
