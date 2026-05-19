"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const PANELS = [
  {
    num: "01",
    title: "Instant RCA",
    desc: "Errors hit your logs. Orqis reads the traceback, pinpoints the exact file and line, and sends a plain-English explanation to your dashboard in under a second. No digging.",
    accent: "#00ff88",
    code: [
      { t: "ERROR",  msg: "RecursionError: pricing_agent.py:42",          color: "#ff3333" },
      { t: "LOCATE", msg: "update_pricing() — depth 847, no base case",   color: "#ffaa00" },
      { t: "PATCH",  msg: "diff ready — 4 lines changed",                 color: "#00ff88" },
      { t: "MCP",    msg: "patch sent to Claude Code — awaiting approval", color: "#4d94ff" },
    ],
  },
  {
    num: "02",
    title: "Live Config",
    desc: "Change models, swap prompts, inject secrets at runtime. No redeploy. No downtime. The next request picks up the change immediately.",
    accent: "#4d94ff",
    config: [
      { key: "model",       val: "gpt-4o → claude-sonnet-4-5", changed: true  },
      { key: "temperature", val: "0.9 → 0.2",                   changed: true  },
      { key: "max_tokens",  val: "4096",                         changed: false },
      { key: "system",      val: "You are a pricing agent...",   changed: false },
    ],
  },
  {
    num: "03",
    title: "Cost Guardrail",
    desc: "Every token counted. Every run tracked. Set a budget per agent — Orqis kills runaway loops before they drain your API balance. Real-time burn rate on your dashboard.",
    accent: "#ffaa00",
    cost: { current: 2.31, limit: 2.5, rate: "$0.55/s" },
  },
  {
    num: "04",
    title: "Auto-Patch",
    desc: "Crash detected. Root cause found. Unified diff generated. Orqis pushes the patch to Claude Code or Cursor via MCP — you review and approve. Done in 14 seconds.",
    accent: "#ff3333",
    diff: [
      { type: "rem", code: "async def update_pricing(self, id):" },
      { type: "rem", code: "    return await self.update_pricing(id)" },
      { type: "add", code: "async def update_pricing(self, id, depth=0):" },
      { type: "add", code: "    if depth > 10: raise RecursionLimitError(id)" },
      { type: "add", code: "    price = await fetch_market_price(id)" },
      { type: "add", code: "    return {\"price\": price, \"depth\": depth}" },
    ],
  },
];

export default function FeaturesSection() {
  const wrapperRef   = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const totalWidth = PANELS.length * window.innerWidth;

      gsap.to(containerRef.current, {
        x: -(totalWidth - window.innerWidth),
        ease: "none",
        scrollTrigger: {
          trigger: wrapperRef.current,
          start: "top top",
          end: () => `+=${totalWidth - window.innerWidth}`,
          scrub: 1,
          pin: true,
          anticipatePin: 1,
          invalidateOnRefresh: true,
        },
      });
    }, wrapperRef);
    return () => ctx.revert();
  }, []);

  return (
    <div style={{ backgroundColor: "#000000" }}>
      {/* ── Section label lives ABOVE the pinned wrapper ── */}
      <div style={{
        textAlign: "center",
        padding: "96px 32px 56px",
        backgroundColor: "#000000",
      }}>
        <span style={{
          fontFamily: "'DM Mono', monospace", fontSize: 11,
          letterSpacing: "0.2em", color: "#444444", textTransform: "uppercase",
        }}>
          ◆ How It Works
        </span>
        <h2 style={{
          fontFamily: "'Anton', sans-serif",
          fontSize: "clamp(2.8rem, 5.5vw, 5rem)",
          color: "#ffffff", lineHeight: 0.95, marginTop: 20,
          letterSpacing: "-0.01em",
        }}>
          DETECT. EXPLAIN.<br />
          <span style={{ color: "#00ff88" }}>PATCH. DONE.</span>
        </h2>
      </div>

      {/* ── Pinned wrapper — NO extra content inside ── */}
      <div ref={wrapperRef}>
        <div style={{ overflow: "hidden" }}>
          <div ref={containerRef} style={{ display: "flex", willChange: "transform" }}>
            {PANELS.map((panel, i) => (
              <div
                key={i}
                style={{
                  minWidth: "100vw",
                  height: "100vh",
                  display: "flex",
                  alignItems: "center",
                  backgroundColor: "#000000",
                  position: "relative",
                  overflow: "hidden",
                  flexShrink: 0,
                }}
              >
                {/* accent glow */}
                <div style={{
                  position: "absolute", right: "8%", top: "50%",
                  transform: "translateY(-50%)",
                  width: 500, height: 500, borderRadius: "50%",
                  background: panel.accent, opacity: 0.04,
                  filter: "blur(100px)", pointerEvents: "none",
                }} />

                {/* panel number watermark */}
                <div style={{
                  position: "absolute", right: 48, bottom: 40,
                  fontFamily: "'Anton', sans-serif",
                  fontSize: "clamp(6rem, 14vw, 12rem)",
                  color: "rgba(255,255,255,0.03)",
                  lineHeight: 1, pointerEvents: "none",
                  userSelect: "none",
                }}>
                  {panel.num}
                </div>

                {/* content */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6vw",
                  maxWidth: 1280,
                  margin: "0 auto",
                  width: "100%",
                  padding: "0 6vw",
                }}>
                  {/* LEFT */}
                  <div style={{ flex: "0 0 38%", minWidth: 280 }}>
                    <div style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 11,
                      color: panel.accent,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      marginBottom: 20,
                      opacity: 0.7,
                    }}>
                      {panel.num} / 04
                    </div>
                    <h3 style={{
                      fontFamily: "'Anton', sans-serif",
                      fontSize: "clamp(2.8rem, 5vw, 4.5rem)",
                      color: panel.accent,
                      lineHeight: 0.92,
                      marginBottom: 28,
                      letterSpacing: "-0.01em",
                    }}>
                      {panel.title.toUpperCase()}
                    </h3>
                    <p style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: "clamp(0.95rem, 1.2vw, 1.1rem)",
                      color: "#555555",
                      lineHeight: 1.8,
                      maxWidth: 400,
                    }}>
                      {panel.desc}
                    </p>

                    {/* progress dots */}
                    <div style={{ display: "flex", gap: 8, marginTop: 40 }}>
                      {PANELS.map((_, di) => (
                        <div key={di} style={{
                          width: di === i ? 28 : 6,
                          height: 3,
                          borderRadius: 99,
                          background: di === i ? panel.accent : "rgba(255,255,255,0.1)",
                          transition: "width 0.3s ease",
                        }} />
                      ))}
                    </div>
                  </div>

                  {/* RIGHT */}
                  <div style={{ flex: 1, maxWidth: 620 }}>
                    <FeatureVisual panel={panel} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{
        height: 1,
        background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent)",
      }} />
    </div>
  );
}

/* ── Visuals ──────────────────────────────────── */
function FeatureVisual({ panel }: { panel: typeof PANELS[0] }) {
  const mono: React.CSSProperties = {
    fontFamily: "'DM Mono', monospace", fontSize: 13,
  };
  const card: React.CSSProperties = {
    background: "#080808",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 16,
    overflow: "hidden",
  };
  const titleBar = (label: string, right?: React.ReactNode) => (
    <div style={{
      background: "#0d0d0d",
      padding: "12px 20px",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
          <div key={i} style={{ width: 11, height: 11, borderRadius: "50%", background: c }} />
        ))}
        <span style={{ ...mono, color: "#3a3a3a", marginLeft: 10, fontSize: 12 }}>{label}</span>
      </div>
      {right}
    </div>
  );

  /* Logs */
  if (panel.code) return (
    <div style={card}>
      {titleBar("narrative.log · live",
        <span style={{ ...mono, fontSize: 11, color: "#00ff88", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00ff88", display: "inline-block", animation: "pulse-slow 1.5s infinite" }} />
          LIVE
        </span>
      )}
      <div style={{ padding: "8px 0" }}>
        {panel.code.map((l, i) => (
          <div key={i} style={{
            display: "flex", gap: 14, padding: "9px 20px",
            borderBottom: "1px solid rgba(255,255,255,0.03)",
            alignItems: "flex-start",
          }}>
            <span style={{ ...mono, color: "#2a2a2a", minWidth: 44, fontSize: 11, paddingTop: 1 }}>{`14:0${2 + i}`}</span>
            <span style={{
              ...mono, fontSize: 11,
              padding: "2px 8px", borderRadius: 4,
              background: l.color + "22", color: l.color,
              minWidth: 44, textAlign: "center", whiteSpace: "nowrap",
            }}>{l.t}</span>
            <span style={{ ...mono, color: "#888888", fontSize: 13 }}>{l.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );

  /* Config */
  if (panel.config) return (
    <div style={card}>
      {titleBar("live-config.yaml · hot-reload")}
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        {panel.config!.map((c, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "13px 18px", borderRadius: 10,
            background: c.changed ? "rgba(77,148,255,0.07)" : "rgba(255,255,255,0.02)",
            border: `1px solid ${c.changed ? "rgba(77,148,255,0.2)" : "rgba(255,255,255,0.04)"}`,
          }}>
            <span style={{ ...mono, color: "#555555" }}>{c.key}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ ...mono, color: c.changed ? "#4d94ff" : "#555555" }}>{c.val}</span>
              {c.changed && (
                <span style={{
                  fontSize: 10, background: "rgba(77,148,255,0.15)",
                  color: "#4d94ff", padding: "2px 8px", borderRadius: 4,
                  letterSpacing: "0.05em",
                }}>CHANGED</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  /* Cost */
  if (panel.cost) {
    const { current, limit, rate } = panel.cost!;
    const pct = (current / limit) * 100;
    return (
      <div style={card}>
        {titleBar("cost-guardrail · real-time")}
        <div style={{ padding: 32 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 32 }}>
            <div>
              <div style={{ ...mono, color: "#444", fontSize: 11, marginBottom: 8, letterSpacing: "0.12em" }}>CURRENT SPEND</div>
              <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 72, color: "#ff3333", lineHeight: 1 }}>${current}</div>
              <div style={{ ...mono, color: "#ff3333", fontSize: 12, marginTop: 8 }}>{rate} · climbing</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ ...mono, color: "#444", fontSize: 11, marginBottom: 8, letterSpacing: "0.12em" }}>LIMIT</div>
              <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 72, color: "#333333", lineHeight: 1 }}>${limit}</div>
            </div>
          </div>
          <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 6, height: 10, overflow: "hidden", marginBottom: 16 }}>
            <div style={{
              height: "100%", borderRadius: 6,
              width: `${pct}%`,
              background: "linear-gradient(90deg, #ffaa00, #ff3333)",
            }} />
          </div>
          <div style={{ ...mono, color: "#ffaa00", fontSize: 12, textAlign: "center" }}>
            ⚠ {pct.toFixed(0)}% of budget consumed · auto-kill at 100%
          </div>
        </div>
      </div>
    );
  }

  /* Diff */
  if (panel.diff) return (
    <div style={card}>
      {titleBar("agent.py · orqis patch",
        <span style={{ ...mono, fontSize: 12 }}>
          <span style={{ color: "#00ff88" }}>+{panel.diff!.filter(d => d.type === "add").length}</span>
          {" "}
          <span style={{ color: "#ff3333" }}>−{panel.diff!.filter(d => d.type === "rem").length}</span>
        </span>
      )}
      <div style={{ padding: "14px 0" }}>
        {panel.diff!.map((l, i) => (
          <div key={i} style={{
            display: "flex",
            background: l.type === "add" ? "rgba(0,255,136,0.05)" : "rgba(255,51,51,0.05)",
            borderLeft: `3px solid ${l.type === "add" ? "#00ff88" : "#ff3333"}`,
            marginBottom: 2,
          }}>
            <span style={{ ...mono, color: l.type === "add" ? "#00ff88" : "#ff3333", padding: "6px 14px", fontSize: 13, userSelect: "none" }}>
              {l.type === "add" ? "+" : "−"}
            </span>
            <span style={{ ...mono, color: l.type === "add" ? "rgba(0,255,136,0.8)" : "rgba(255,51,51,0.7)", padding: "6px 14px 6px 0", fontSize: 13 }}>
              {l.code}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  return null;
}
