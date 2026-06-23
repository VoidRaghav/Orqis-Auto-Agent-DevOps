"use client";

import type { TraceEvent } from "@/lib/types";
import { C } from "../constants";
import { mono } from "../shared";

export default function TraceRow({ trace }: { trace: TraceEvent }) {
  const kindColor = trace.is_error ? C.red : trace.kind.includes("end") ? C.green : C.blue;

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "6px 14px",
        borderBottom: "1px solid rgba(255,255,255,0.025)",
        alignItems: "center",
      }}
    >
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0 }}>
        {new Date(trace.timestamp).toLocaleTimeString("en", { hour12: false })}
      </span>
      <span
        style={{
          ...mono,
          fontSize: 9,
          padding: "2px 6px",
          borderRadius: 4,
          background: kindColor + "18",
          color: kindColor,
          flexShrink: 0,
          minWidth: 72,
          textAlign: "center",
        }}
      >
        {trace.kind}
      </span>
      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.provider}</span>
      {trace.model && <span style={{ ...mono, fontSize: 10, color: "#555", flexShrink: 0 }}>{trace.model}</span>}
      {trace.tool_name && (
        <span style={{ ...mono, fontSize: 10, color: C.blue, flexShrink: 0 }}>{trace.tool_name}()</span>
      )}
      {(trace.input_tokens != null || trace.output_tokens != null) && (
        <span style={{ ...mono, fontSize: 10, color: "#555", flexShrink: 0 }}>
          {trace.input_tokens ?? 0}→{trace.output_tokens ?? 0} tok
        </span>
      )}
      {trace.cost_usd != null && (
        <span
          style={{
            ...mono,
            fontSize: 10,
            color: trace.cost_usd > 0.1 ? C.amber : C.green,
            marginLeft: "auto",
            flexShrink: 0,
          }}
        >
          ${trace.cost_usd.toFixed(4)}
        </span>
      )}
      {trace.latency_ms != null && (
        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.latency_ms}ms</span>
      )}
    </div>
  );
}
