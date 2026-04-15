"use client";

const ITEMS = [
  "NARRATIVE LOGS", "LIVE CONFIG", "COST GUARDRAIL", "SELF-HEAL LOOP",
  "LOOP DETECTION", "AUTO-PAUSE", "MCP INTEGRATION", "ZERO CONFIG",
  "NPX INSTALL", "AGENT OPS", "TOKEN TRACKING", "IDE PATCH",
];

export default function TickerSection() {
  const doubled = [...ITEMS, ...ITEMS];
  return (
    <div style={{
      backgroundColor: "#000000",
      borderTop: "1px solid rgba(255,255,255,0.06)",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      overflow: "hidden", padding: "14px 0",
      position: "relative",
    }}>
      {/* Fade edges */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none",
        background: "linear-gradient(90deg, #000 0%, transparent 8%, transparent 92%, #000 100%)",
      }} />
      <div className="ticker-inner">
        {doubled.map((item, i) => (
          <span key={i} style={{
            display: "inline-flex", alignItems: "center", gap: 20,
            padding: "0 20px",
            fontFamily: "'DM Mono', monospace",
            fontSize: 11, letterSpacing: "0.16em",
            color: i % 4 === 0 ? "#00ff88" : "#444444",
            whiteSpace: "nowrap",
          }}>
            {item}
            <span style={{ color: "rgba(255,255,255,0.12)", fontSize: 8 }}>◆</span>
          </span>
        ))}
      </div>
    </div>
  );
}
