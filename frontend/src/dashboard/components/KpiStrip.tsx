"use client";

import type { Incident, LogEvent } from "@/lib/types";
import { C, ACTIVE_STATUSES, HEALED_STATUSES } from "../constants";
import { mono } from "../shared";
import { LiveDot } from "./ui";

export default function KpiStrip({
  events,
  incidents,
  connected,
}: {
  events: LogEvent[];
  incidents: Incident[];
  connected: boolean;
}) {
  const errors = events.filter((e) => e.is_error).length;
  const warnings = events.filter((e) => e.level === "WARNING").length;
  const open = incidents.filter((i) => ACTIVE_STATUSES.has(i.status)).length;
  const healed = incidents.filter((i) => HEALED_STATUSES.has(i.status)).length;

  const kpis = [
    { label: "ERRORS", val: errors, color: C.red },
    { label: "WARNINGS", val: warnings, color: C.amber },
    { label: "ACTIVE", val: open, color: C.amber },
    { label: "HEALED", val: healed, color: C.green },
  ];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        padding: "0 20px",
        height: 54,
        borderBottom: `1px solid ${C.border}`,
        background: C.bg2,
        overflowX: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginRight: 20, flexShrink: 0 }}>
        <LiveDot color={connected ? C.green : C.red} />
        <span style={{ ...mono, fontSize: 11, color: connected ? C.green : C.red }}>
          {connected ? "LIVE" : "RECONNECTING"}
        </span>
      </div>

      {kpis.map((k, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 6,
            padding: "0 16px",
            borderLeft: `1px solid ${C.border}`,
            flexShrink: 0,
          }}
        >
          <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 22, color: k.color, lineHeight: 1 }}>
            {k.val}
          </span>
          <span style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em" }}>{k.label}</span>
        </div>
      ))}
    </div>
  );
}
