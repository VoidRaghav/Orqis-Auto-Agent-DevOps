"use client";

import type { Incident } from "@/lib/types";
import { C } from "../constants";
import { mono } from "../shared";

const STAGES: { key: string; label: string; match: (s: string) => boolean }[] = [
  { key: "detected", label: "Detected", match: () => true },
  { key: "located", label: "Located", match: (s) => !["open"].includes(s) || false },
  { key: "patched", label: "Patched", match: (s) =>
    ["patched", "low_confidence", "approved", "pr_open", "pr_failed", "patch_stale", "resolved"].includes(s) },
  { key: "pr", label: "PR opened", match: (s) =>
    ["pr_open", "pr_failed", "patch_stale", "resolved"].includes(s) },
  { key: "merged", label: "Merged", match: (s) => s === "resolved" },
];

function stageDone(incident: Incident, stageKey: string): boolean {
  const s = incident.status;
  if (stageKey === "detected") return true;
  if (stageKey === "located") return !!(incident.file_path || incident.repo_relative_path);
  if (stageKey === "patched") return !!incident.diff;
  if (stageKey === "pr") return !!incident.pr_url || s === "pr_open" || s === "resolved";
  if (stageKey === "merged") return s === "resolved";
  return false;
}

export default function IncidentTimeline({ incident }: { incident: Incident }) {
  return (
    <ol className="incident-timeline" style={{ ...mono, fontSize: 11, margin: "8px 0 12px", padding: 0, listStyle: "none", display: "flex", gap: 8, flexWrap: "wrap" }}>
      {STAGES.map((stage) => {
        const done = stageDone(incident, stage.key);
        const active = incident.status === "patch_stale" && stage.key === "pr";
        return (
          <li
            key={stage.key}
            style={{
              padding: "4px 8px",
              borderRadius: 4,
              border: `1px solid ${done ? C.green : C.border}`,
              color: done ? C.green : C.dim,
              background: active ? `${C.amber}20` : "transparent",
            }}
          >
            {stage.label}
          </li>
        );
      })}
    </ol>
  );
}
