"use client";

import { useEffect, useRef, useCallback } from "react";

/* ─────────────────────── DATA ─────────────────────── */
const PHASES = [
  {
    num: "01",
    lines:     ["YOUR LOGS", "TELL YOU", "NOTHING."],
    color:     "#ffffff",
    accent:    "#ffffff",
    sub:       "raw stack traces, unreadable json, zero context — debug it yourself",
    bg:        "#000000",
    ghostWord: "BLIND",
    accentLine: -1,
    widget: {
      title: "WITHOUT ORQIS",
      rows: [
        { label: "error context",  val: "raw trace",   bad: true  },
        { label: "root cause",     val: "unknown",     bad: true  },
        { label: "fix location",   val: "hunt for it", bad: true  },
        { label: "time to patch",  val: "hours",       bad: true  },
      ],
    },
  },
  {
    num: "02",
    lines:     ["LOOPS BURN", "MONEY."],
    color:     "#ffaa00",
    accent:    "#ffaa00",
    sub:       "recursive agents hit api rate limits and drain your balance with no kill switch",
    bg:        "#060300",
    ghostWord: "BURN",
    accentLine: -1,
    widget: {
      title: "LIVE COST METER",
      rows: [
        { label: "current spend",  val: "$2.31",    bad: true  },
        { label: "burn rate",      val: "$0.55/s",  bad: true  },
        { label: "budget left",    val: "$0.19",    bad: true  },
        { label: "auto-kill",      val: "DISABLED", bad: true  },
      ],
    },
  },
  {
    num: "03",
    lines:     ["$2.31", "GONE.", "4 SECONDS."],
    color:     "#ff3333",
    accent:    "#ff3333",
    sub:       "23 api calls · no base case · recursive loop · no alert fired",
    bg:        "#0a0000",
    ghostWord: "GONE",
    accentLine: -1,
    widget: {
      title: "INCIDENT #4421",
      rows: [
        { label: "duration",    val: "4.2s",          bad: true  },
        { label: "api calls",   val: "23",             bad: true  },
        { label: "root cause",  val: "RecursionError", bad: false },
        { label: "outcome",     val: "FAILED",         bad: true  },
      ],
    },
  },
  {
    num: "04",
    lines:     ["ORQIS", "CAUGHT IT.", "ALREADY."],
    color:     "#ffffff",
    accent:    "#00ff88",
    sub:       "detected in 800ms · diagnosed by llm · patch in your ide · approved in one click",
    bg:        "#000a04",
    ghostWord: "FIXED",
    accentLine: 1,
    widget: {
      title: "WITH ORQIS",
      rows: [
        { label: "detect",    val: "< 1s",     bad: false },
        { label: "diagnose",  val: "< 3s",     bad: false },
        { label: "patch",     val: "14s",      bad: false },
        { label: "outcome",   val: "HEALED",   bad: false },
      ],
    },
  },
] as const;

const STARS = Array.from({ length: 48 }, (_, i) => ({
  x:     ((i * 137.508) % 100).toFixed(2),
  y:     ((i * 93.74)   % 100).toFixed(2),
  size:  i % 5 === 0 ? 1.5 : 0.8,
  dur:   2 + (i % 3),
  delay: ((i * 0.28) % 3).toFixed(2),
}));

/* ─── 400 vh total — snappy transitions, long hold ─── */
const TOTAL_VH  = 400;
/* Each phase: 12% in, 76% hold, 12% out — feels crisp */
const IN  = 0.12;
const OUT = 0.88;

function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }
function clamp(v: number, lo = 0, hi = 1)      { return Math.max(lo, Math.min(hi, v)); }
function easeOut(t: number) { return 1 - Math.pow(1 - t, 3); }
function easeIn(t: number)  { return t * t * t; }
function easeInOut(t: number) { return t < 0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2; }

/* ─────────────────────── COMPONENT ─────────────────────── */
export default function ScrollTextSection() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const stickyRef  = useRef<HTMLDivElement>(null);
  const rafRef     = useRef<number>(0);
  const prevProg   = useRef(-1);

  const phaseRefs  = useRef<(HTMLDivElement | null)[]>([]);
  const ghostRefs  = useRef<(HTMLDivElement | null)[]>([]);
  const subRefs    = useRef<(HTMLDivElement | null)[]>([]);
  const widgetRefs = useRef<(HTMLDivElement | null)[]>([]);
  const lineRefs   = useRef<(HTMLDivElement | null)[][]>(PHASES.map(() => []));
  const barRef     = useRef<HTMLDivElement>(null);
  const dotRefs    = useRef<(HTMLDivElement | null)[]>([]);
  const numRef     = useRef<HTMLSpanElement>(null);

  /* jump to a phase by scrolling to the right position */
  const scrollToPhase = useCallback((idx: number) => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const wTop      = wrapper.getBoundingClientRect().top + window.scrollY;
    const scrollable = wrapper.offsetHeight - window.innerHeight;
    /* aim for middle of that phase's hold window */
    const target = wTop + (idx / PHASES.length + 0.5 / PHASES.length) * scrollable;
    window.scrollTo({ top: target, behavior: "smooth" });
  }, []);

  const update = useCallback(() => {
    const wrapper = wrapperRef.current;
    const sticky  = stickyRef.current;
    if (!wrapper || !sticky) return;

    const rect       = wrapper.getBoundingClientRect();
    const scrollable = rect.height - window.innerHeight;
    if (scrollable <= 0) return;

    const progress = clamp(-rect.top / scrollable);
    if (Math.abs(progress - prevProg.current) < 0.00012) return;
    prevProg.current = progress;

    const N = PHASES.length;

    PHASES.forEach((phase, i) => {
      const phaseEl  = phaseRefs.current[i];
      const ghostEl  = ghostRefs.current[i];
      const subEl    = subRefs.current[i];
      const widgetEl = widgetRefs.current[i];
      if (!phaseEl) return;

      const c = clamp((progress - i / N) / (1 / N));

      /* opacity + blur */
      let op = 0, blur = 0;
      if (c < IN) {
        const t = easeOut(c / IN);
        op = t; blur = lerp(14, 0, t);
      } else if (c < OUT) {
        op = 1; blur = 0;
      } else {
        const t = easeIn((c - OUT) / (1 - OUT));
        op = 1 - t; blur = lerp(0, 12, t);
      }
      phaseEl.style.opacity = op.toFixed(4);
      phaseEl.style.filter  = blur > 0.1 ? `blur(${blur.toFixed(2)}px)` : "none";

      /* ghost word — drifts at 0.25× speed */
      if (ghostEl) {
        let gop = 0, gy = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          gop = t * 0.045; gy = lerp(30, 0, t);
        } else if (c < OUT) {
          gop = 0.045;
          gy  = lerp(0, -18, (c - IN) / (OUT - IN));
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          gop = (1 - t) * 0.045; gy = lerp(-18, -48, t);
        }
        ghostEl.style.opacity   = gop.toFixed(4);
        ghostEl.style.transform = `translateY(${gy.toFixed(2)}px)`;
      }

      /* per-line staggered parallax */
      lineRefs.current[i].forEach((lineEl, j) => {
        if (!lineEl) return;
        const depth = 1 + j * 0.45;
        let ty = 0;
        if (c < IN) {
          ty = lerp(80 * depth, 0, easeOut(c / IN));
        } else if (c < OUT) {
          ty = lerp(0, -12 * depth, easeInOut((c - IN) / (OUT - IN)));
        } else {
          ty = lerp(-12 * depth, -65 * depth, easeIn((c - OUT) / (1 - OUT)));
        }
        lineEl.style.transform = `translateY(${ty.toFixed(2)}px)`;
      });

      /* widget — slides from right */
      if (widgetEl) {
        let wx = 0, wop = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          wx = lerp(70, 0, t); wop = t;
        } else if (c < OUT) {
          wx = 0; wop = 1;
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          wx = lerp(0, -35, t); wop = 1 - t;
        }
        widgetEl.style.transform = `translateX(${wx.toFixed(2)}px)`;
        widgetEl.style.opacity   = wop.toFixed(4);
      }

      /* sub — slides from left */
      if (subEl) {
        let sx = 0, sop = 0;
        if (c < IN) {
          const t = easeOut(c / IN);
          sx = lerp(-32, 0, t); sop = t * 0.6;
        } else if (c < OUT) {
          sx = 0; sop = 0.6;
        } else {
          const t = easeIn((c - OUT) / (1 - OUT));
          sx = lerp(0, 32, t); sop = (1 - t) * 0.6;
        }
        subEl.style.transform = `translateX(${sx.toFixed(2)}px)`;
        subEl.style.opacity   = sop.toFixed(4);
      }
    });

    /* progress bar */
    if (barRef.current) barRef.current.style.transform = `scaleX(${progress.toFixed(4)})`;

    /* dots + phase counter */
    const active = clamp(Math.floor(progress * N), 0, N - 1);
    dotRefs.current.forEach((dot, i) => {
      if (!dot) return;
      const on = i === active;
      dot.style.background = on ? PHASES[i].accent : "rgba(255,255,255,0.15)";
      dot.style.width      = on ? "22px" : "6px";
    });
    if (numRef.current) numRef.current.textContent = PHASES[active].num;

    sticky.style.backgroundColor = PHASES[active].bg;
  }, []);

  useEffect(() => {
    const tick = () => { update(); rafRef.current = requestAnimationFrame(tick); };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [update]);

  return (
    <>
      <div ref={wrapperRef} style={{ height: `${TOTAL_VH}vh`, position: "relative" }}>
        <div
          ref={stickyRef}
          style={{
            position: "sticky", top: 0, height: "100vh", overflow: "hidden",
            backgroundColor: "#000000",
            transition: "background-color 0.5s ease",
          }}
        >
          {/* Stars */}
          <div style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }}>
            {STARS.map((s, i) => (
              <div key={i} style={{
                position: "absolute", left: `${s.x}%`, top: `${s.y}%`,
                width: s.size, height: s.size, borderRadius: "50%",
                background: "rgba(255,255,255,0.45)",
                animation: `pulse-slow ${s.dur}s ease-in-out ${s.delay}s infinite`,
              }} />
            ))}
          </div>

          {/* Ghost words */}
          {PHASES.map((phase, i) => (
            <div
              key={i}
              ref={(el) => { ghostRefs.current[i] = el; }}
              style={{
                position: "absolute", inset: 0, zIndex: 1,
                display: "flex", alignItems: "center", justifyContent: "center",
                opacity: 0, pointerEvents: "none", willChange: "opacity, transform",
                userSelect: "none",
              }}
            >
              <span style={{
                fontFamily: "'Anton', sans-serif",
                fontSize: "clamp(10rem, 36vw, 34rem)",
                lineHeight: 1, letterSpacing: "-0.03em",
                color: phase.accent, whiteSpace: "nowrap",
              }}>
                {phase.ghostWord}
              </span>
            </div>
          ))}

          {/* Vignette */}
          <div style={{
            position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none",
            background: "radial-gradient(ellipse 85% 85% at 50% 50%, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0.88) 100%)",
          }} />

          {/* Phase content */}
          {PHASES.map((phase, i) => (
            <div
              key={i}
              ref={(el) => { phaseRefs.current[i] = el; }}
              style={{
                position: "absolute", inset: 0, zIndex: 3,
                opacity: 0, willChange: "opacity, filter", pointerEvents: "none",
              }}
            >
              <div style={{
                width: "100%", height: "100%",
                maxWidth: 1280, margin: "0 auto",
                padding: "0 6vw",
                display: "flex", alignItems: "center",
                justifyContent: "space-between", gap: "4vw",
              }}>
                {/* LEFT */}
                <div style={{ flex: "0 0 auto", maxWidth: "56%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 28 }}>
                    <div style={{ width: 28, height: 1, background: phase.accent, opacity: 0.5 }} />
                    <span style={{
                      fontFamily: "'DM Mono', monospace", fontSize: 11,
                      letterSpacing: "0.22em", color: phase.accent, opacity: 0.65,
                      textTransform: "uppercase",
                    }}>
                      {phase.num} / 04
                    </span>
                  </div>

                  <div style={{ overflow: "visible", marginBottom: 32 }}>
                    {(phase.lines as readonly string[]).map((line, j) => {
                      const isAccent = phase.accentLine === j;
                      return (
                        <div
                          key={j}
                          ref={(el) => { lineRefs.current[i][j] = el; }}
                          style={{
                            fontFamily: "'Anton', sans-serif",
                            fontSize: "clamp(3.8rem, 9vw, 9rem)",
                            lineHeight: 0.87, letterSpacing: "-0.02em",
                            color: isAccent ? "#00ff88" : phase.color,
                            display: "block", willChange: "transform",
                            textShadow: isAccent ? "0 0 60px rgba(0,255,136,0.2)" : "none",
                          }}
                        >
                          {line}
                        </div>
                      );
                    })}
                  </div>

                  <div
                    ref={(el) => { subRefs.current[i] = el; }}
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: "clamp(0.58rem, 0.85vw, 0.78rem)",
                      letterSpacing: "0.16em", textTransform: "uppercase",
                      color: phase.accent, opacity: 0,
                      willChange: "opacity, transform",
                      maxWidth: 460, lineHeight: 1.9,
                    }}
                  >
                    {phase.sub}
                  </div>
                </div>

                {/* RIGHT — widget */}
                <div
                  ref={(el) => { widgetRefs.current[i] = el; }}
                  style={{ flex: "0 0 270px", opacity: 0, willChange: "opacity, transform" }}
                >
                  <div style={{
                    background: "rgba(255,255,255,0.025)",
                    border: `1px solid ${phase.accent}20`,
                    borderRadius: 14, overflow: "hidden",
                  }}>
                    <div style={{
                      padding: "13px 18px",
                      borderBottom: `1px solid ${phase.accent}15`,
                      display: "flex", alignItems: "center", gap: 9,
                    }}>
                      <div style={{
                        width: 6, height: 6, borderRadius: "50%",
                        background: phase.accent,
                        animation: "pulse-slow 1.5s ease-in-out infinite",
                      }} />
                      <span style={{
                        fontFamily: "'DM Mono', monospace", fontSize: 10,
                        letterSpacing: "0.18em", color: phase.accent,
                        textTransform: "uppercase", opacity: 0.8,
                      }}>
                        {phase.widget.title}
                      </span>
                    </div>
                    <div style={{ padding: "6px 0" }}>
                      {phase.widget.rows.map((row, ri) => (
                        <div key={ri} style={{
                          display: "flex", justifyContent: "space-between",
                          alignItems: "center", padding: "10px 18px",
                          borderBottom: ri < phase.widget.rows.length - 1
                            ? "1px solid rgba(255,255,255,0.03)" : "none",
                        }}>
                          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#3a3a3a" }}>
                            {row.label}
                          </span>
                          <span style={{
                            fontFamily: "'DM Mono', monospace", fontSize: 12,
                            color: i === 3
                              ? "#00ff88"
                              : row.bad
                                ? (i === 2 ? "#ff3333" : i === 1 ? "#ffaa00" : "#444444")
                                : phase.accent,
                          }}>
                            {row.val}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* ── Bottom nav bar ── */}
          <div style={{
            position: "absolute", bottom: 0, left: 0, right: 0, zIndex: 10,
          }}>
            {/* thin progress line */}
            <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }}>
              <div
                ref={barRef}
                style={{
                  height: "100%",
                  background: "linear-gradient(90deg, #00ff88, #4d94ff)",
                  transformOrigin: "left", transform: "scaleX(0)",
                  willChange: "transform",
                }}
              />
            </div>

            {/* clickable dots + counter */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: 20, padding: "14px 32px",
            }}>
              {/* phase counter */}
              <span style={{
                fontFamily: "'DM Mono', monospace", fontSize: 10,
                color: "#333333", letterSpacing: "0.15em",
                position: "absolute", left: 32,
              }}>
                <span ref={numRef} style={{ color: "#666666" }}>01</span>
                <span style={{ color: "#222222" }}> / 04</span>
              </span>

              {/* dots */}
              {PHASES.map((phase, i) => (
                <button
                  key={i}
                  onClick={() => scrollToPhase(i)}
                  title={`Jump to phase ${phase.num}`}
                  style={{
                    width: 6, height: 6, borderRadius: 99,
                    background: "rgba(255,255,255,0.15)",
                    border: "none", cursor: "pointer", padding: 0,
                    transition: "background 0.3s ease, width 0.3s ease",
                    willChange: "background, width",
                    pointerEvents: "all",
                  }}
                  ref={(el) => { dotRefs.current[i] = el as any; }}
                />
              ))}

              {/* scroll hint */}
              <span style={{
                fontFamily: "'DM Mono', monospace", fontSize: 10,
                color: "#222222", letterSpacing: "0.15em",
                position: "absolute", right: 32,
              }}>
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
