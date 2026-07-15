"use client";

import { useEffect, useState } from "react";
import type { AgentStatus } from "@/lib/types";
import { colors, mono } from "@/lib/tokens";

// No ping for 3 intervals (the SDK pings every ~15s) => treat the agent as down.
const DOWN_MS = 45_000;

function ago(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h`;
}

export default function AgentStatusPill({ agents }: { agents: Record<string, AgentStatus> }) {
  // Re-render on a timer so "last seen" ticks and the pill flips to down on its own.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 2000);
    return () => clearInterval(id);
  }, []);

  const list = Object.values(agents);
  if (list.length === 0) return null;

  const now = Date.now();
  const ages = list.map((a) => now - new Date(a.last_seen).getTime());
  const upCount = ages.filter((age) => age < DOWN_MS).length;
  const anyUp = upCount > 0;
  const newestAge = Math.min(...ages);
  const color = anyUp ? colors.green : colors.red;

  const label =
    list.length === 1
      ? newestAge < DOWN_MS
        ? `AGENT UP · ${ago(newestAge)}`
        : `AGENT DOWN · ${ago(newestAge)}`
      : `AGENTS ${upCount}/${list.length}`;

  return (
    <span style={{ ...mono, fontSize: 10, color, display: "flex", alignItems: "center", gap: 6 }}>
      <span
        className={anyUp ? "pulse-slow" : ""}
        style={{ width: 6, height: 6, borderRadius: "50%", background: color }}
      />
      {label}
    </span>
  );
}
