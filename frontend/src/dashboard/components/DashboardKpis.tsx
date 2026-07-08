"use client";

import type { Incident, LogEvent } from "@/lib/types";
import { C, ACTIVE_STATUSES, HEALED_STATUSES } from "../constants";
import { mono } from "../shared";

export default function DashboardKpis({
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
    { label: "live", value: connected ? "on" : "off", color: connected ? C.green : C.red },
    { label: "errors", value: String(errors), color: errors > 0 ? C.red : C.dim },
    { label: "warnings", value: String(warnings), color: warnings > 0 ? C.amber : C.dim },
    { label: "active", value: String(open), color: open > 0 ? C.amber : C.dim },
    { label: "healed", value: String(healed), color: healed > 0 ? C.green : C.dim },
  ];

  return (
    <>
      {kpis.map((k) => (
        <div key={k.label} className="mc-kpi-pill" style={{ borderColor: `${k.color}33`, background: `${k.color}0a` }}>
          <span style={{ ...mono, fontSize: 9, color: C.dimmer, letterSpacing: "0.14em" }}>{k.label}</span>
          <span style={{ ...mono, fontSize: 17, color: k.color, fontWeight: 600 }}>{k.value}</span>
        </div>
      ))}
    </>
  );
}
