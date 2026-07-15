"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useOrqisStream } from "@/lib/useOrqisStream";
import { API_URL, WS_URL } from "@/lib/env";
import { C, ACTIVE_STATUSES } from "@/dashboard/constants";
import { mono } from "@/dashboard/shared";
import DashboardNav from "@/dashboard/components/DashboardNav";
import HealthHero from "@/dashboard/components/HealthHero";
import KpiStrip from "@/dashboard/components/KpiStrip";
import LogRow from "@/dashboard/components/LogRow";
import IncidentCard from "@/dashboard/components/IncidentCard";
import ChangeRow from "@/dashboard/components/ChangeRow";
import TraceRow from "@/dashboard/components/TraceRow";
import RightRail from "@/dashboard/components/RightRail";
import OpsAmbientLayer from "@/dashboard/components/OpsAmbientLayer";
import { resolveOpsMood } from "@/dashboard/components/ops-ambient";
import { EmptyState } from "@/dashboard/components/ui";

export default function Dashboard() {
  const {
    events,
    traces,
    incidents,
    changes,
    agents,
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
  const traceCost = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);
  const costRecovered = incidents.reduce((s, i) => s + (i.cost_recovered_usd ?? 0), 0);

  const viewIncidentFromChange = useCallback((incidentId: string) => {
    setActiveTab("incidents");
    setHighlightIncidentId(incidentId);
    setTimeout(() => setHighlightIncidentId(null), 2500);
  }, []);

  const tabs = [
    { id: "incidents", label: "Issues", badge: openCount > 0 ? openCount : null },
    { id: "changes", label: "Changes", badge: changes.length > 0 ? changes.length : null },
    { id: "logs", label: "Activity", badge: null },
    { id: "traces", label: "AI calls", badge: null },
  ] as const;

  const hasPrChanges = changes.some((c) => c.action === "pr_opened" || c.action === "pr_merged");
  const alertCount = incidents.filter(
    (i) =>
      i.status === "patched" ||
      i.status === "low_confidence" ||
      i.status === "pr_open" ||
      i.status === "pr_failed" ||
      i.status === "patch_stale" ||
      i.status === "open" ||
      i.status === "patching",
  ).length;
  const mood = resolveOpsMood({
    connected,
    hasData: incidents.length > 0 || changes.length > 0 || events.length > 0,
    alertCount,
  });

  return (
    <div className="dashboard-page" data-mood={mood}>
      <OpsAmbientLayer mood={mood} />
      <div className="ops-page-content">
      <DashboardNav connected={connected} totalCost={traceCost} github={github} agents={agents} />

      <div className="dashboard-toolbar">
        <HealthHero
          incidents={incidents}
          connected={connected}
          hasChanges={changes.length > 0}
          onViewIssues={() => setActiveTab("incidents")}
        />
        <KpiStrip events={events} incidents={incidents} costRecoveredUsd={costRecovered} />
      </div>

      <div className="ops-terminal-frame">
        <div className="ops-terminal-frame-edge" />
        <div className="dashboard-body">
        <div className="dashboard-main">
          <div className="dashboard-tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`dashboard-tab ${activeTab === tab.id ? "dashboard-tab-active" : ""} ${
                  tab.id === "changes" && hasPrChanges && activeTab === "changes" ? "dashboard-tab-pr" : ""
                }`}
              >
                {tab.label}
                {tab.badge != null && <span className="dashboard-tab-badge">{tab.badge}</span>}
              </button>
            ))}
            {activeTab === "logs" && (
              <button
                type="button"
                onClick={() => setAutoScroll((x) => !x)}
                className="dashboard-autoscroll-btn"
                style={{ ...mono, color: autoScroll ? C.green : C.dim }}
              >
                {autoScroll ? "Auto-scroll" : "Paused"}
              </button>
            )}
          </div>

          <div ref={logRef} className="dashboard-main-scroll">
            {activeTab === "logs" &&
              (events.length === 0 ? (
                <EmptyState label="No activity yet." hint="Add orqis.init() →" />
              ) : (
                events.map((e) => <LogRow key={e.id} event={e} flash={flashSet.current.has(e.id)} />)
              ))}

            {activeTab === "incidents" && (
              <div className="dashboard-incidents">
                {incidents.length === 0 ? (
                  <EmptyState
                    hero
                    label="No open incidents yet."
                    githubConnected={!!github?.connected}
                    hint={
                      github?.connected
                        ? "Add orqis.init() to your agent to start →"
                        : "Connect GitHub for auto-fix PRs →"
                    }
                  />
                ) : (
                  incidents.map((i, idx) => (
                    <IncidentCard
                      key={i.id}
                      index={idx + 1}
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
                <EmptyState label="No changes yet." hint="Connect GitHub →" />
              ) : (
                <div className="dashboard-changes">
                  <div className="dashboard-changes-spine" />
                  {changes.map((c) => (
                    <ChangeRow key={c.id} change={c} onViewIncident={viewIncidentFromChange} />
                  ))}
                </div>
              ))}

            {activeTab === "traces" &&
              (traces.length === 0 ? (
                <EmptyState label="No AI calls yet." hint="orqis.init() instruments LLMs" />
              ) : (
                traces.map((t) => <TraceRow key={t.id} trace={t} />)
              ))}
          </div>
        </div>

        <RightRail events={events} traces={traces} />
        </div>
      </div>
      </div>
    </div>
  );
}
