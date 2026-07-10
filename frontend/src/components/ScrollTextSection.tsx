"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useFlow } from "@/components/FlowZone";
import { registerPanel, unregisterPanel } from "@/lib/panel-registry";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { SCROLL_GHOST_PEAK } from "@/lib/hero-choreography";
import FlowSectionOverlay from "@/components/FlowSectionOverlay";
import { useLayoutMobile } from "@/hooks/useLayoutMobile";

const PHASES = [
  {
    num: "01",
    lines: ["YOUR LOGS", "TELL YOU", "NOTHING."],
    color: "#ffffff",
    accent: "#ffffff",
    sub: "raw stack traces, unreadable json, zero context — debug it yourself",
    ghostWord: "BLIND",
    accentLine: -1,
    widget: {
      title: "WITHOUT ORQIS",
      rows: [
        { label: "error context", val: "raw trace", bad: true },
        { label: "root cause", val: "unknown", bad: true },
        { label: "fix location", val: "hunt for it", bad: true },
        { label: "time to patch", val: "hours", bad: true },
      ],
    },
  },
  {
    num: "02",
    lines: ["LOOPS BURN", "MONEY."],
    color: "#ffaa00",
    accent: "#ffaa00",
    sub: "recursive agents hit api rate limits and drain your balance with no kill switch",
    ghostWord: "BURN",
    accentLine: -1,
    widget: {
      title: "LIVE COST METER",
      rows: [
        { label: "current spend", val: "$2.31", bad: true },
        { label: "burn rate", val: "$0.55/s", bad: true },
        { label: "budget left", val: "$0.19", bad: true },
        { label: "auto-kill", val: "DISABLED", bad: true },
      ],
    },
  },
  {
    num: "03",
    lines: ["$2.31", "GONE.", "4 SECONDS."],
    color: "#ff3333",
    accent: "#ff3333",
    sub: "23 api calls · no base case · recursive loop · no alert fired",
    ghostWord: "GONE",
    accentLine: -1,
    widget: {
      title: "INCIDENT #4421",
      rows: [
        { label: "duration", val: "4.2s", bad: true },
        { label: "api calls", val: "23", bad: true },
        { label: "root cause", val: "RecursionError", bad: false },
        { label: "outcome", val: "FAILED", bad: true },
      ],
    },
  },
  {
    num: "04",
    lines: ["ORQIS", "CAUGHT IT.", "ALREADY."],
    color: "#ffffff",
    accent: "#00ff88",
    sub: "detected in <1s · patch generated · PR or local apply · CHANGES logged",
    ghostWord: "FIXED",
    accentLine: 1,
    widget: {
      title: "WITH ORQIS",
      rows: [
        { label: "detect", val: "< 1s", bad: false },
        { label: "patch", val: "verified", bad: false },
        { label: "ship", val: "PR / local", bad: false },
        { label: "outcome", val: "HEALED", bad: false },
      ],
    },
  },
  {
    num: "05",
    lines: ["GITHUB", "PR", "FIRST."],
    color: "#ffffff",
    accent: "#58a6ff",
    sub: "branch never hits main without review · full diff · CI checks · merge when ready",
    ghostWord: "SHIP",
    accentLine: -1,
    widget: {
      title: "PR #1 · orqis/fix-loop",
      rows: [
        { label: "branch", val: "orqis/fix-loop", bad: false },
        { label: "checks", val: "3 passing", bad: false },
        { label: "review", val: "awaiting you", bad: false },
        { label: "main", val: "protected", bad: false },
      ],
    },
  },
] as const;

const IN = 0.06;
const OUT = 0.94;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
function clamp(v: number, lo = 0, hi = 1) {
  return Math.max(lo, Math.min(hi, v));
}
function easeOut(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
function easeIn(t: number) {
  return t * t * t;
}
function easeInOut(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function PhaseWidget({
  phase,
  phaseIndex,
}: {
  phase: (typeof PHASES)[number];
  phaseIndex: number;
}) {
  return (
    <div
      className="flow-panel landing-static-widget"
      style={{
        borderRadius: 14,
        overflow: "hidden",
        border: `1px solid ${phase.accent}28`,
      }}
    >
      <div
        style={{
          padding: "13px 18px",
          borderBottom: `1px solid ${phase.accent}15`,
          display: "flex",
          alignItems: "center",
          gap: 9,
        }}
      >
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: phase.accent,
          }}
        />
        <span
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: 10,
            letterSpacing: "0.18em",
            color: phase.accent,
            textTransform: "uppercase",
            opacity: 0.8,
          }}
        >
          {phase.widget.title}
        </span>
      </div>
      <div style={{ padding: "6px 0" }}>
        {phase.widget.rows.map((row, ri) => (
          <div
            key={ri}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 18px",
              borderBottom:
                ri < phase.widget.rows.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none",
            }}
          >
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#8fa39a" }}>
              {row.label}
            </span>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 12,
                color:
                  phaseIndex === 3
                    ? "#00ff88"
                    : row.bad
                      ? phaseIndex === 2
                        ? "#ff3333"
                        : phaseIndex === 1
                          ? "#ffaa00"
                          : "#8fa39a"
                      : phase.accent,
              }}
            >
              {row.val}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ScrollTextSection() {
  const { setTint } = useFlow();
  const flow = useRobotFlowOptional();
  const isMobile = useLayoutMobile();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const prevProg = useRef(-1);

  const phaseRefs = useRef<(HTMLDivElement | null)[]>([]);
  const headlineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const ghostRefs = useRef<(HTMLDivElement | null)[]>([]);
  const subRefs = useRef<(HTMLDivElement | null)[]>([]);
  const widgetRefs = useRef<(HTMLDivElement | null)[]>([]);
  const lineRefs = useRef<(HTMLDivElement | null)[][]>(PHASES.map(() => []));
  const barRef = useRef<HTMLDivElement>(null);
  const dotRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const numRef = useRef<HTMLSpanElement>(null);
  const prevActive = useRef(-1);
  const registeredActive = useRef(-1);
  const [activeAccent, setActiveAccent] = useState<string>(PHASES[0].accent);

  const scrollToPhase = useCallback((idx: number) => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const wTop = wrapper.getBoundingClientRect().top + window.scrollY;
    const scrollable = wrapper.offsetHeight - window.innerHeight;
    const target = wTop + (idx / PHASES.length + 0.5 / PHASES.length) * scrollable;
    window.scrollTo({ top: target, behavior: "smooth" });
  }, []);

  const update = useCallback(() => {
    const wrapper = wrapperRef.current;
    const sticky = stickyRef.current;
    if (!wrapper || !sticky) return;

    const rect = wrapper.getBoundingClientRect();
    const scrollable = rect.height - window.innerHeight;
    if (scrollable <= 0) return;

    const progress = clamp(-rect.top / scrollable);
    if (Math.abs(progress - prevProg.current) < 0.00012) return;
    prevProg.current = progress;

    const handoff = flow?.handoffRef.current ?? 0;
    const N = PHASES.length;

    PHASES.forEach((phase, i) => {
      const phaseEl = phaseRefs.current[i];
      const ghostEl = ghostRefs.current[i];
      const subEl = subRefs.current[i];
      const widgetEl = widgetRefs.current[i];
      if (!phaseEl) return;

      const c = clamp((progress - i / N) / (1 / N));

      let op = 0;
      let blur = 0;
      if (c < IN) {
        const t = easeOut(c / IN);
        op = t;
        blur = lerp(14, 0, t);
      } else if (c < OUT) {
        op = 1;
        blur = 0;
      } else {
        const t = easeIn((c - OUT) / (1 - OUT));
        op = 1 - t;
        blur = lerp(0, 12, t);
      }

      if (i === 0 && progress < 0.08 && handoff > 0) {
        op = Math.max(op, handoff * 0.92);
        blur = blur * (1 - handoff);
      }

      phaseEl.style.opacity = op.toFixed(4);
      phaseEl.style.filter = blur > 0.1 ? `blur(${blur.toFixed(2)}px)` : "none";

      if (ghostEl) {
        let gop = 0;
        let gy = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          gop = t * SCROLL_GHOST_PEAK;
          gy = lerp(30, 0, t);
        } else if (c < OUT) {
          gop = SCROLL_GHOST_PEAK;
          gy = lerp(0, -18, (c - IN) / (OUT - IN));
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          gop = (1 - t) * SCROLL_GHOST_PEAK;
          gy = lerp(-18, -48, t);
        }
        ghostEl.style.opacity = gop.toFixed(4);
        ghostEl.style.transform = `translateY(${gy.toFixed(2)}px)`;
      }

      lineRefs.current[i].forEach((lineEl, j) => {
        if (!lineEl) return;
        const depth = 1 + j * 0.35;
        let ty = 0;
        if (c < IN) {
          ty = lerp(60 * depth, 0, easeOut(c / IN));
        } else if (c < OUT) {
          ty = lerp(0, -10 * depth, easeInOut((c - IN) / (OUT - IN)));
        } else {
          ty = lerp(-10 * depth, -50 * depth, easeIn((c - OUT) / (1 - OUT)));
        }
        lineEl.style.transform = `translateY(${ty.toFixed(2)}px)`;
      });

      if (widgetEl) {
        let wx = 0;
        let wop = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          wx = lerp(50, 0, t);
          wop = t;
        } else if (c < OUT) {
          wx = 0;
          wop = 1;
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          wx = lerp(0, -30, t);
          wop = 1 - t;
        }
        if (i === 0 && progress < 0.08 && handoff > 0) {
          wop = Math.max(wop, handoff * 0.85);
        }
        widgetEl.style.transform = `translateX(${wx.toFixed(2)}px)`;
        widgetEl.style.opacity = wop.toFixed(4);
      }

      if (subEl) {
        let sx = 0;
        let sop = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          sx = lerp(-24, 0, t);
          sop = t * 0.6;
        } else if (c < OUT) {
          sx = 0;
          sop = 0.6;
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          sx = lerp(0, 24, t);
          sop = (1 - t) * 0.6;
        }
        subEl.style.transform = `translateX(${sx.toFixed(2)}px)`;
        subEl.style.opacity = sop.toFixed(4);
      }
    });

    if (barRef.current) barRef.current.style.transform = `scaleX(${progress.toFixed(4)})`;

    const active = clamp(Math.floor(progress * N), 0, N - 1);
    if (active !== prevActive.current) {
      prevActive.current = active;
      setActiveAccent(PHASES[active].accent);
      setTint(PHASES[active].accent);
    }

    if (active !== registeredActive.current) {
      if (registeredActive.current >= 0) {
        unregisterPanel(`scroll-headline-${registeredActive.current}`);
      }
      registeredActive.current = active;
      const headline = headlineRefs.current[active];
      if (headline) {
        registerPanel({
          id: `scroll-headline-${active}`,
          section: "scroll",
          el: headline,
          accent: PHASES[active].accent,
          priority: 2.0,
        });
      }
    }

    dotRefs.current.forEach((dot, i) => {
      if (!dot) return;
      const on = i === active;
      dot.style.background = on ? PHASES[i].accent : "rgba(255,255,255,0.15)";
      dot.style.width = on ? "22px" : "6px";
    });
    if (numRef.current) numRef.current.textContent = PHASES[active].num;
  }, [setTint, flow]);

  useEffect(() => {
    if (isMobile) {
      cancelAnimationFrame(rafRef.current);
      if (registeredActive.current >= 0) {
        unregisterPanel(`scroll-headline-${registeredActive.current}`);
        registeredActive.current = -1;
      }
      return;
    }
    const tick = () => {
      update();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(rafRef.current);
      if (registeredActive.current >= 0) {
        unregisterPanel(`scroll-headline-${registeredActive.current}`);
      }
    };
  }, [update, isMobile]);

  if (isMobile) {
    return (
      <>
        <section className="landing-static-section flow-section" aria-label="The problem">
          <div className="landing-static-stack">
            {PHASES.map((phase, i) => (
              <div key={phase.num} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div
                  className="flow-panel landing-static-card"
                  style={{ border: `1px solid ${phase.accent}28` }}
                >
                  <div
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 10,
                      letterSpacing: "0.18em",
                      color: phase.accent,
                      marginBottom: 12,
                    }}
                  >
                    {phase.num}
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    {phase.lines.map((line, j) => {
                      const isAccent = phase.accentLine === j;
                      return (
                        <div
                          key={j}
                          style={{
                            fontFamily: "'Anton', sans-serif",
                            fontSize: "clamp(1.8rem, 9vw, 2.6rem)",
                            lineHeight: 0.92,
                            letterSpacing: "-0.02em",
                            color: isAccent ? "#00ff88" : phase.color,
                          }}
                        >
                          {line}
                        </div>
                      );
                    })}
                  </div>
                  <p
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 11,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      color: phase.accent,
                      lineHeight: 1.7,
                      opacity: 0.85,
                    }}
                  >
                    {phase.sub}
                  </p>
                </div>
                <PhaseWidget phase={phase} phaseIndex={i} />
              </div>
            ))}
          </div>
        </section>
        <div className="section-divider" />
      </>
    );
  }

  return (
    <>
      <div ref={wrapperRef} className="scroll-phase-wrap scroll-phase-wrap--desktop">
        <div
          ref={stickyRef}
          className="scroll-phase-stage"
          style={{
            position: "sticky",
            top: 0,
            height: "100vh",
            overflow: "hidden",
            backgroundColor: "transparent",
          }}
        >
          <FlowSectionOverlay accent={activeAccent} side="left" />

          {PHASES.map((phase, i) => (
            <div
              key={i}
              ref={(el) => {
                ghostRefs.current[i] = el;
              }}
              className="flow-ghost-word"
              style={{
                opacity: 0,
                willChange: "opacity, transform",
              }}
            >
              <span style={{ color: phase.accent }}>
                {phase.ghostWord}
              </span>
            </div>
          ))}

          {PHASES.map((phase, i) => (
            <div
              key={i}
              ref={(el) => {
                phaseRefs.current[i] = el;
              }}
              style={{
                position: "absolute",
                inset: 0,
                zIndex: 5,
                opacity: 0,
                willChange: "opacity, filter",
                pointerEvents: "none",
              }}
            >
              <div
                className="flow-panel flow-col-left"
                style={{ top: "15%", padding: "28px 32px", borderRadius: 16 }}
                ref={(el) => {
                  headlineRefs.current[i] = el;
                }}
              >
                  <div style={{ overflow: "visible", marginBottom: 20 }}>
                    {(phase.lines as readonly string[]).map((line, j) => {
                      const isAccent = phase.accentLine === j;
                      return (
                        <div
                          key={j}
                          ref={(el) => {
                            lineRefs.current[i][j] = el;
                          }}
                          style={{
                            fontFamily: "'Anton', sans-serif",
                            fontSize: "clamp(2.2rem, 5.5vw, 5.5rem)",
                            lineHeight: 0.87,
                            letterSpacing: "-0.02em",
                            color: isAccent ? "#00ff88" : phase.color,
                            display: "block",
                            willChange: "transform",
                            textShadow: isAccent ? "0 0 60px rgba(0,255,136,0.2)" : "none",
                          }}
                        >
                          {line}
                        </div>
                      );
                    })}
                  </div>

                  <div
                    ref={(el) => {
                      subRefs.current[i] = el;
                    }}
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: "clamp(0.58rem, 0.85vw, 0.78rem)",
                      letterSpacing: "0.16em",
                      textTransform: "uppercase",
                      color: phase.accent,
                      opacity: 0,
                      willChange: "opacity, transform",
                      lineHeight: 1.9,
                    }}
                  >
                    {phase.sub}
                  </div>
              </div>

              <div
                ref={(el) => {
                  widgetRefs.current[i] = el;
                }}
                className="flow-col-right"
                style={{ top: "14%", opacity: 0, willChange: "opacity, transform" }}
              >
                <div
                  className="flow-panel"
                  style={{
                    borderRadius: 14,
                    overflow: "hidden",
                    border: `1px solid ${phase.accent}28`,
                  }}
                >
                  <div
                    style={{
                      padding: "13px 18px",
                      borderBottom: `1px solid ${phase.accent}15`,
                      display: "flex",
                      alignItems: "center",
                      gap: 9,
                    }}
                  >
                    <div
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: phase.accent,
                        animation: "pulse-slow 1.5s ease-in-out infinite",
                      }}
                    />
                    <span
                      style={{
                        fontFamily: "'DM Mono', monospace",
                        fontSize: 10,
                        letterSpacing: "0.18em",
                        color: phase.accent,
                        textTransform: "uppercase",
                        opacity: 0.8,
                      }}
                    >
                      {phase.widget.title}
                    </span>
                  </div>
                  <div style={{ padding: "6px 0" }}>
                    {phase.widget.rows.map((row, ri) => (
                      <div
                        key={ri}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 18px",
                          borderBottom:
                            ri < phase.widget.rows.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none",
                        }}
                      >
                        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#8fa39a" }}>
                          {row.label}
                        </span>
                        <span
                          style={{
                            fontFamily: "'DM Mono', monospace",
                            fontSize: 12,
                            color:
                              i === 3
                                ? "#00ff88"
                                : row.bad
                                  ? i === 2
                                    ? "#ff3333"
                                    : i === 1
                                      ? "#ffaa00"
                                      : "#8fa39a"
                                  : phase.accent,
                          }}
                        >
                          {row.val}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}

          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, zIndex: 10 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                padding: "14px 32px",
              }}
            >
              <span
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 10,
                  color: "#9fb1a8",
                  letterSpacing: "0.15em",
                }}
              >
                SCROLL ↓
              </span>
            </div>
          </div>
        </div>
      </div>
      <div className="section-divider" />
    </>
  );
}
