"use client";

import { useState } from "react";
import type { ChangeLogEntry } from "@/lib/types";
import { C, CHANGE_META } from "../constants";
import { mono, inter } from "../shared";

export default function ChangeRow({
  change,
  onViewIncident,
}: {
  change: ChangeLogEntry;
  onViewIncident: (incidentId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = CHANGE_META[change.action] ?? { label: change.action.toUpperCase(), color: C.dim, icon: "•" };
  const when = new Date(change.timestamp);
  const timeLabel =
    when.toLocaleDateString() === new Date().toLocaleDateString()
      ? when.toLocaleTimeString("en", { hour12: false })
      : when.toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  return (
    <div
      style={{
        marginBottom: 8,
        marginLeft: 12,
        background: C.bg2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        position: "relative",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 14px",
          cursor: change.diff ? "pointer" : "default",
        }}
        onClick={() => change.diff && setExpanded((x) => !x)}
      >
        <span style={{ color: meta.color, fontSize: 14, width: 16, textAlign: "center", flexShrink: 0 }}>
          {meta.icon}
        </span>
        <span
          style={{
            ...mono,
            fontSize: 9,
            letterSpacing: "0.08em",
            flexShrink: 0,
            padding: "3px 7px",
            borderRadius: 4,
            background: meta.color + "18",
            color: meta.color,
            minWidth: 104,
            textAlign: "center",
          }}
        >
          {meta.label}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              ...inter,
              fontSize: 13,
              color: C.white,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {change.summary}
          </div>
          <div style={{ ...mono, fontSize: 10, color: C.dim, marginTop: 2 }}>
            {change.repo_full_name ? `${change.repo_full_name} · ` : ""}
            {change.file ?? "—"}
            {change.applied_locally ? " · written to disk" : ""}
            {change.error_type ? ` · ${change.error_type}` : ""}
          </div>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onViewIncident(change.incident_id);
          }}
          style={{
            ...mono,
            fontSize: 10,
            color: C.github,
            background: "transparent",
            border: `1px solid ${C.github}40`,
            borderRadius: 5,
            padding: "4px 8px",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          View issue
        </button>
        {change.pr_url && (
          <a
            href={change.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              ...mono,
              fontSize: 11,
              color: C.github,
              textDecoration: "none",
              flexShrink: 0,
              padding: "4px 8px",
              border: `1px solid ${C.github}30`,
              borderRadius: 5,
              background: `${C.github}10`,
            }}
          >
            PR{change.pr_number ? ` #${change.pr_number}` : ""} →
          </a>
        )}
        <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0 }}>
          {timeLabel}
          {change.diff ? (expanded ? " ▲" : " ▼") : ""}
        </span>
      </div>
      {expanded && change.diff && (
        <div style={{ padding: "0 14px 12px", borderTop: `1px solid ${C.border}` }}>
          <pre
            style={{
              ...mono,
              fontSize: 10,
              color: "#aaa",
              margin: "10px 0 0",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 220,
              overflow: "auto",
              background: C.bg,
              padding: 10,
              borderRadius: 6,
            }}
          >
            {change.diff}
          </pre>
        </div>
      )}
    </div>
  );
}
