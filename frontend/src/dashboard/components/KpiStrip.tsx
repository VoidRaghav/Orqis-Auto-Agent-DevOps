"use client";

import type { Incident, LogEvent } from "@/lib/types";
import { C, ACTIVE_STATUSES, HEALED_STATUSES } from "../constants";
import { mono } from "../shared";

export default function KpiStrip({
  events,
  incidents,
}: {
  events: LogEvent[];
  incidents: Incident[];
}) {
  const errors = events.filter((e) => e.is_error).length;
  const warnings = events.filter((e) => e.level === "WARNING").length;
  const open = incidents.filter((i) => ACTIVE_STATUSES.has(i.status)).length;
  const healed = incidents.filter((i) => HEALED_STATUSES.has(i.status)).length;

  const kpis = [
    { label: "ERRORS", val: errors, color: errors > 0 ? C.red : C.dim },
    { label: "WARN", val: warnings, color: warnings > 0 ? C.amber : C.dim },
    { label: "ACTIVE", val: open, color: open > 0 ? C.amber : C.dim },
    { label: "HEALED", val: healed, color: healed > 0 ? C.green : C.dim },
  ];

  return (
    <div className="dashboard-kpis">
      {kpis.map((k) => (
        <div key={k.label} className="dashboard-kpi">
          <span className="dashboard-kpi-val" style={{ color: k.color }}>
            {k.val}
          </span>
          <span className="dashboard-kpi-label" style={{ ...mono }}>
            {k.label}
          </span>
        </div>
      ))}
    </div>
  );
}
