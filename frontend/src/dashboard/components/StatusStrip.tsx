"use client";

import type { Incident } from "@/lib/types";
import { C } from "../constants";
import { inter, mono } from "../shared";

export default function StatusStrip({
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

  let tone: string = C.green;
  let title = "All clear";
  let sub = connected ? "No open incidents — Orqis is watching." : "Reconnecting live stream…";
  let action: React.ReactNode = null;

  if (!connected && !hasData) {
    tone = C.muted;
    title = "Standby";
    sub = "Waiting for orqis.init() in your app.";
  } else if (needsYou > 0) {
    tone = C.amber;
    title = `${needsYou} fix${needsYou > 1 ? "es" : ""} ready`;
    sub = "Review the suggested patch or open the PR.";
    action = prUrl ? (
      <a href={prUrl} target="_blank" rel="noopener noreferrer" className="mc-status-cta" style={{ color: C.github, borderColor: `${C.github}44` }}>
        Review PR →
      </a>
    ) : (
      <button type="button" onClick={onViewIssues} className="mc-status-cta" style={{ color: C.amber, borderColor: `${C.amber}44` }}>
        View fixes →
      </button>
    );
  } else if (fixing > 0) {
    tone = C.github;
    title = "Investigating";
    sub = `${fixing} active incident${fixing > 1 ? "s" : ""} — tracing root cause.`;
  }

  return (
    <div className="mc-status-strip" style={{ borderLeftColor: tone }}>
      <div>
        <div style={{ ...mono, fontSize: 11, color: tone, letterSpacing: "0.08em", marginBottom: 4 }}>{title.toUpperCase()}</div>
        <div style={{ ...inter, fontSize: 13, color: C.muted }}>{sub}</div>
      </div>
      {action}
    </div>
  );
}
