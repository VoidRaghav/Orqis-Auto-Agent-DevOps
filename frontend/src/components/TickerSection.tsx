"use client";

import MetaLabel from "@/components/ui/MetaLabel";
import { colors, fonts } from "@/lib/tokens";

const ITEMS = [
  "GITHUB PR-FIRST",
  "RUNAWAY LOOP GUARD",
  "CHANGES AUDIT LOG",
  "MCP + COPY PROMPT",
  "IDE AGNOSTIC",
  "NEVER WRITES TO MAIN",
  "DETERMINISTIC PATCHES",
  "TRACE + LOG INGEST",
];

export default function TickerSection() {
  const doubled = [...ITEMS, ...ITEMS];
  return (
    <div
      className="flow-section flow-section--ticker"
      style={{
        backgroundColor: "transparent",
        borderTop: `1px solid ${colors.github}22`,
        borderBottom: `1px solid ${colors.green}15`,
        overflow: "hidden",
        padding: "16px 0",
        position: "relative",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 1,
          pointerEvents: "none",
          background: "linear-gradient(90deg, #000 0%, transparent 10%, transparent 90%, #000 100%)",
        }}
      />
      <div className="ticker-inner">
        {doubled.map((item, i) => (
          <span
            key={i}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 16,
              padding: "0 24px",
              fontFamily: fonts.mono,
              fontSize: 10,
              letterSpacing: "0.2em",
              color: i % 3 === 0 ? colors.glow : colors.dimmer,
              whiteSpace: "nowrap",
            }}
          >
            <MetaLabel accent={i % 3 === 0 ? colors.glow : colors.dimmer}>[{item}]</MetaLabel>
          </span>
        ))}
      </div>
    </div>
  );
}
