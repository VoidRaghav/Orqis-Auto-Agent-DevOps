"use client";

import type { Incident } from "@/lib/types";
import { C } from "../constants";
import { LiveDot } from "./ui";

export default function HealthHero({
  incidents,
  connected,
  hasChanges,
  onViewIssues,
}: {
  incidents: Incident[];
  connected: boolean;
  hasChanges: boolean;
  onViewIssues: () => void;
}) {
  const hasData = incidents.length > 0 || hasChanges;
  const prUrl = incidents.find((i) => i.pr_url)?.pr_url;
  const needsYou = incidents.filter(
    (i) =>
      i.status === "patched" ||
      i.status === "low_confidence" ||
      i.status === "pr_open" ||
      i.status === "pr_failed" ||
      i.status === "patch_stale",
  ).length;
  const fixing = incidents.filter((i) => i.status === "open" || i.status === "patching").length;
  const healed = incidents.filter((i) => i.status === "approved" || i.status === "resolved").length;

  let tone: string;
  let title: string;
  let sub: string;
  let action: React.ReactNode = null;

  if (!connected && !hasData) {
    tone = C.dim;
    title = "Standby";
    sub = "Run orqis.init() to start.";
  } else if (needsYou > 0) {
    tone = C.amber;
    title = needsYou === 1 ? "1 fix ready" : `${needsYou} fixes ready`;
    sub = "Review patch or merge PR.";
    action = prUrl ? (
      <a
        href={prUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="dashboard-status-cta"
        style={{ color: C.github, borderColor: `${C.github}44`, background: `${C.github}12` }}
      >
        Review PR
      </a>
    ) : (
      <button
        type="button"
        onClick={onViewIssues}
        className="dashboard-status-cta"
        style={{ color: C.amber, borderColor: `${C.amber}44`, background: `${C.amber}12` }}
      >
        View fixes
      </button>
    );
  } else if (fixing > 0) {
    tone = C.blue;
    title = "Investigating";
    sub = `${fixing} active · tracing root cause`;
  } else {
    tone = C.green;
    title = "All clear";
    sub = connected ? "Monitoring your app." : "Reconnecting…";
  }

  return (
    <div className="dashboard-status" style={{ borderLeftColor: tone }}>
      <div className="dashboard-status-main">
        <LiveDot color={tone} />
        <div>
          <div className="dashboard-status-title">{title}</div>
          <div className="dashboard-status-sub">{sub}</div>
        </div>
      </div>
      <div className="dashboard-status-side">
        {healed > 0 && (
          <div className="dashboard-status-stat">
            <span className="dashboard-status-stat-val" style={{ color: C.green }}>
              {healed}
            </span>
            <span className="dashboard-status-stat-label">healed</span>
          </div>
        )}
        {action}
      </div>
    </div>
  );
}
