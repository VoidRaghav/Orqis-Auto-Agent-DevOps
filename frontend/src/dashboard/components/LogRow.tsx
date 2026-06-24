"use client";

import type { LogEvent } from "@/lib/types";
import { C, LEVEL_COLOR, TYPE_COLOR } from "../constants";
import { mono, inter } from "../shared";

export default function LogRow({ event, flash }: { event: LogEvent; flash: boolean }) {
  const levelColor = LEVEL_COLOR[event.level] ?? C.white;
  const typeColor = event.error_type ? (TYPE_COLOR[event.error_type] ?? C.red) : undefined;

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "5px 14px",
        borderBottom: "1px solid rgba(255,255,255,0.025)",
        alignItems: "flex-start",
        background: flash ? "rgba(0,255,136,0.04)" : "transparent",
        transition: "background 0.8s ease",
        animation: "log-slide-in 0.2s ease-out",
      }}
    >
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0, paddingTop: 2 }}>
        {new Date(event.timestamp).toLocaleTimeString("en", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}
      </span>

      <span
        style={{
          ...mono,
          fontSize: 9,
          padding: "2px 6px",
          borderRadius: 4,
          background: levelColor + "18",
          color: levelColor,
          flexShrink: 0,
          letterSpacing: "0.06em",
          minWidth: 52,
          textAlign: "center",
        }}
      >
        {event.level}
      </span>

      {event.error_type && typeColor && (
        <span
          style={{
            ...mono,
            fontSize: 9,
            padding: "2px 6px",
            borderRadius: 4,
            background: typeColor + "18",
            color: typeColor,
            flexShrink: 0,
            letterSpacing: "0.06em",
            minWidth: 80,
            textAlign: "center",
          }}
        >
          {event.error_type}
        </span>
      )}

      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{event.source}</span>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            ...mono,
            fontSize: 12,
            color: event.is_error ? "#dddddd" : "#666666",
            wordBreak: "break-all",
          }}
        >
          {event.raw_line.length > 200 ? event.raw_line.slice(0, 200) + "…" : event.raw_line}
        </div>
        {event.interpretation && (
          <div style={{ ...inter, fontSize: 11, color: C.green, marginTop: 3, opacity: 0.85 }}>
            ↳ {event.interpretation}
          </div>
        )}
      </div>
    </div>
  );
}
