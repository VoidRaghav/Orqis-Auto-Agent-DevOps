"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import MetaLabel, { SectionMeta } from "@/components/ui/MetaLabel";
import ScanlineOverlay from "@/components/ui/ScanlineOverlay";
import TerminalPanel from "@/components/ui/TerminalPanel";
import FlowSectionOverlay from "@/components/FlowSectionOverlay";
import { INCIDENT_CHAPTERS } from "@/lib/incident-sim";
import { colors, fonts, mono, inter } from "@/lib/tokens";
import { useLayoutMobile } from "@/hooks/useLayoutMobile";

gsap.registerPlugin(ScrollTrigger);

const TABS = ["ISSUES & FIXES", "CHANGES", "ACTIVITY", "AI CALLS"] as const;
type Tab = (typeof TABS)[number];

const KPIS = [
  { label: "detect", value: "<1s", accent: colors.green },
  { label: "PR open", value: "1", accent: colors.github },
  { label: "burn blocked", value: "$0.55/s", accent: colors.amber },
];

const CHANGES = [
  { t: "14:04:52", file: "refund_agent.py", action: "PR merged", sc: colors.github },
  { t: "14:02:18", file: "orqis/fix-loop", action: "PR opened", sc: colors.github },
  { t: "13:58:03", file: "billing_agent.py", action: "fix_applied", sc: colors.green },
];

const ACTIVITY = [
  { t: "14:05", msg: "WebSocket connected — live ingest", sc: colors.green },
  { t: "14:02", msg: "GitHub PR #1 created from incident #4421", sc: colors.github },
  { t: "14:01", msg: "RUNAWAY_LOOP guard tripped — patch queued", sc: colors.amber },
];

const AI_CALLS = [
  { t: "14:02:02", model: "claude-sonnet", tokens: "1.2k", purpose: "patch generation" },
  { t: "14:02:01", model: "claude-sonnet", tokens: "840", purpose: "root cause analysis" },
];

const DIFF_LINES = [
  { type: "rem" as const, code: "while True:" },
  { type: "add" as const, code: "    _attempts = 0" },
  { type: "add" as const, code: "    while _attempts < 5:" },
];

function accentColor(a: string) {
  if (a === "amber") return colors.amber;
  if (a === "red") return colors.red;
  if (a === "green") return colors.green;
  return colors.muted;
}

export default function MissionControlCinematic() {
  const sectionRef = useRef<HTMLElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<Tab>("ISSUES & FIXES");
  const [tabProgress, setTabProgress] = useState(0);
  const [paused, setPaused] = useState(false);
  const [chapterIdx, setChapterIdx] = useState(1);
  const [stamp, setStamp] = useState("14:02:00");
  const [reducedMotion, setReducedMotion] = useState(false);
  const isMobile = useLayoutMobile();
  const tabIdxRef = useRef(0);
  const tabStartRef = useRef(Date.now());

  useEffect(() => {
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  useEffect(() => {
    const section = sectionRef.current;
    const shell = shellRef.current;
    if (!section || !shell || reducedMotion) return;

    // Flat entrance on mobile — no perspective tilt (clips on narrow screens)
    const from = isMobile
      ? { opacity: 0, y: 32 }
      : { opacity: 0, y: 48, rotateX: 8, transformPerspective: 1200 };
    const to = isMobile
      ? { opacity: 1, y: 0, duration: 0.9, ease: "power3.out" }
      : { opacity: 1, y: 0, rotateX: 4, duration: 1.1, ease: "power3.out" };

    const st = ScrollTrigger.create({
      trigger: section,
      start: "top 75%",
      onEnter: () => {
        gsap.fromTo(shell, from, to);
      },
      once: true,
    });

    return () => st.kill();
  }, [reducedMotion, isMobile]);

  useEffect(() => {
    if (paused || reducedMotion) return;
    const interval = setInterval(() => {
      const elapsed = Date.now() - tabStartRef.current;
      const p = Math.min(1, elapsed / 4000);
      setTabProgress(p);
      if (p >= 1) {
        tabIdxRef.current = (tabIdxRef.current + 1) % TABS.length;
        setTab(TABS[tabIdxRef.current]);
        tabStartRef.current = Date.now();
        setTabProgress(0);
      }
    }, 50);
    return () => clearInterval(interval);
  }, [paused, reducedMotion]);

  useEffect(() => {
    if (reducedMotion) return;
    const simChapters = INCIDENT_CHAPTERS.filter((c) =>
      ["detect", "patch", "ship", "audit"].includes(c.id)
    );
    let i = 0;
    const tick = () => {
      const ch = simChapters[i % simChapters.length];
      setChapterIdx(INCIDENT_CHAPTERS.indexOf(ch));
      setStamp(ch.stamp.replace("04:", "14:"));
      i += 1;
    };
    tick();
    const id = setInterval(tick, 3200);
    return () => clearInterval(id);
  }, [reducedMotion]);

  const selectTab = useCallback((t: Tab) => {
    setTab(t);
    tabIdxRef.current = TABS.indexOf(t);
    tabStartRef.current = Date.now();
    setTabProgress(0);
  }, []);

  const chapter = INCIDENT_CHAPTERS[chapterIdx] ?? INCIDENT_CHAPTERS[1];

  return (
    <section
      ref={sectionRef}
      id="mission-control"
      className="flow-section flow-tail-section mc-cinematic"
      style={{ paddingTop: 80, paddingBottom: 100 }}
    >
      <FlowSectionOverlay accent={colors.glow} side="full" />

      <div className="flow-section-headline" style={{ textAlign: "center", marginBottom: 48, position: "relative", zIndex: 12 }}>
        <SectionMeta index="003" tag="(MISSION_CONTROL)" />
        <h2
          className="editorial-headline"
          style={{ fontSize: "clamp(2.5rem, 5vw, 4.5rem)", color: colors.white, marginTop: 8 }}
        >
          LIVE <em>console</em>.
          <br />
          <span style={{ color: colors.green }}>REAL TABS.</span>
        </h2>
      </div>

      <div
        ref={shellRef}
        className="mc-cinematic-shell"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => {
          setPaused(false);
          tabStartRef.current = Date.now();
        }}
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          position: "relative",
          zIndex: 8,
          background: colors.bg2,
          border: `1px solid ${colors.borderStrong}`,
          borderRadius: 18,
          overflow: "hidden",
          opacity: reducedMotion ? 1 : 0,
          transform: reducedMotion || isMobile ? "none" : "perspective(1200px) rotateX(4deg)",
          transformOrigin: "center top",
          boxShadow: `0 48px 140px rgba(0,0,0,0.9), 0 0 100px ${colors.glowDim}`,
        }}
      >
        <ScanlineOverlay opacity={0.05} />

        <div
          style={{
            padding: "14px 20px",
            borderBottom: `1px solid ${colors.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MetaLabel accent={colors.glow}>(ORQIS_DASHBOARD)</MetaLabel>
            <span className="pulse-slow" style={{ width: 6, height: 6, borderRadius: "50%", background: colors.green }} />
            <MetaLabel accent={colors.green}>live ingest</MetaLabel>
            <MetaLabel accent={colors.dimmer}>{stamp}</MetaLabel>
          </div>
          <a href="/dashboard" className="btn-ghost" style={{ padding: "8px 16px", textDecoration: "none", fontSize: 10 }}>
            Command Deck →
          </a>
        </div>

        <div
          style={{
            display: "flex",
            gap: 12,
            padding: "16px 20px",
            borderBottom: `1px solid ${colors.border}`,
            flexWrap: "wrap",
          }}
        >
          {KPIS.map((k) => (
            <div
              key={k.label}
              style={{
                padding: "10px 16px",
                borderRadius: 10,
                border: `1px solid ${colors.border}`,
                background: colors.bg3,
                minWidth: 120,
              }}
            >
              <div style={{ ...mono, fontSize: 9, color: colors.dimmer, letterSpacing: "0.14em", marginBottom: 4 }}>
                {k.label.toUpperCase()}
              </div>
              <div style={{ ...mono, fontSize: 18, color: k.accent, fontWeight: 600 }}>{k.value}</div>
            </div>
          ))}
        </div>

        <div style={{ position: "relative", borderBottom: `1px solid ${colors.border}` }}>
          <div style={{ display: "flex", overflowX: "auto" }}>
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => selectTab(t)}
                style={{
                  padding: "12px 20px",
                  border: "none",
                  borderBottom: tab === t ? `2px solid ${colors.green}` : "2px solid transparent",
                  background: tab === t ? colors.greenDim : "transparent",
                  cursor: "pointer",
                  ...mono,
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  color: tab === t ? colors.white : colors.dim,
                  whiteSpace: "nowrap",
                }}
              >
                {t}
              </button>
            ))}
          </div>
          {!reducedMotion && (
            <div
              style={{
                position: "absolute",
                bottom: 0,
                left: 0,
                height: 2,
                width: `${tabProgress * 100}%`,
                background: `linear-gradient(90deg, ${colors.green}, ${colors.glow})`,
                transition: "width 0.05s linear",
                maxWidth: "100%",
              }}
            />
          )}
        </div>

        <div className="mc-cinematic-body">
          {tab === "ISSUES & FIXES" && (
            <div className="mc-issues-grid">
              <div
                style={{
                  border: `1px solid ${colors.borderStrong}`,
                  borderRadius: 12,
                  overflow: "hidden",
                  background: colors.bg3,
                }}
              >
                <div
                  style={{
                    padding: "14px 18px",
                    borderBottom: `1px solid ${colors.border}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <MetaLabel accent={accentColor(chapter.accent)} style={{ display: "block", marginBottom: 6 }}>
                      [{chapter.label}]
                    </MetaLabel>
                    <div style={{ ...inter, fontSize: 16, color: colors.white, fontWeight: 600 }}>{chapter.headline}</div>
                  </div>
                  <span style={{ ...mono, fontSize: 10, color: colors.amber }}>#4421</span>
                </div>
                <div style={{ padding: "16px 18px" }}>
                  {chapter.lines.map((line, i) => (
                    <div key={i} style={{ ...mono, fontSize: 12, color: colors.muted, marginBottom: 8 }}>
                      {line}
                    </div>
                  ))}
                  <div style={{ marginTop: 16, padding: 12, background: colors.bg2, borderRadius: 8, border: `1px solid ${colors.border}` }}>
                    {DIFF_LINES.map((l, i) => (
                      <div
                        key={i}
                        style={{
                          ...mono,
                          fontSize: 11,
                          color: l.type === "add" ? colors.green : colors.red,
                          padding: "4px 0",
                        }}
                      >
                        {l.type === "add" ? "+" : "−"} {l.code}
                      </div>
                    ))}
                  </div>
                  <a
                    href="/dashboard"
                    style={{
                      display: "inline-block",
                      marginTop: 16,
                      ...inter,
                      padding: "10px 18px",
                      borderRadius: 8,
                      border: `1px solid ${colors.github}55`,
                      background: `${colors.github}14`,
                      color: colors.github,
                      fontSize: 12,
                      fontWeight: 600,
                      textDecoration: "none",
                    }}
                  >
                    Review PR →
                  </a>
                </div>
              </div>
              <TerminalPanel label="live sim · chapter" accent={accentColor(chapter.accent)}>
                <div style={{ padding: 16 }}>
                  {INCIDENT_CHAPTERS.slice(1, 6).map((ch) => (
                    <div
                      key={ch.id}
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: "8px 0",
                        borderBottom: `1px solid ${colors.border}`,
                        opacity: ch.id === chapter.id ? 1 : 0.35,
                      }}
                    >
                      <span style={{ ...mono, fontSize: 9, color: colors.dimmer, minWidth: 52 }}>{ch.stamp}</span>
                      <span style={{ ...mono, fontSize: 10, color: accentColor(ch.accent) }}>{ch.label}</span>
                    </div>
                  ))}
                </div>
              </TerminalPanel>
            </div>
          )}

          {tab === "CHANGES" && (
            <TerminalPanel label="CHANGES · audit spine" accent={colors.green}>
              <div style={{ padding: "8px 0" }}>
                {CHANGES.map((c, i) => (
                  <div
                    key={i}
                    className="mc-change-row"
                    style={{
                      display: "flex",
                      gap: 20,
                      padding: "14px 18px",
                      borderBottom: i < CHANGES.length - 1 ? `1px solid ${colors.border}` : "none",
                      borderLeft: `2px solid ${c.sc}`,
                      animationDelay: `${i * 0.15}s`,
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer, minWidth: 64 }}>{c.t}</span>
                    <span style={{ ...mono, fontSize: 12, color: colors.white, minWidth: 160 }}>{c.file}</span>
                    <span style={{ ...mono, fontSize: 11, color: c.sc }}>{c.action}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}

          {tab === "ACTIVITY" && (
            <TerminalPanel label="activity feed" accent={colors.glow}>
              <div style={{ padding: "8px 0" }}>
                {ACTIVITY.map((a, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 16,
                      padding: "12px 18px",
                      borderBottom: i < ACTIVITY.length - 1 ? `1px solid ${colors.border}` : "none",
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer, minWidth: 48 }}>{a.t}</span>
                    <span style={{ ...inter, fontSize: 13, color: a.sc }}>{a.msg}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}

          {tab === "AI CALLS" && (
            <TerminalPanel label="ai calls · attribution" accent={colors.github}>
              <div style={{ padding: "8px 0" }}>
                {AI_CALLS.map((c, i) => (
                  <div
                    key={i}
                    className="mc-ai-calls-row"
                    style={{
                      display: "grid",
                      gap: 12,
                      padding: "12px 18px",
                      borderBottom: i < AI_CALLS.length - 1 ? `1px solid ${colors.border}` : "none",
                    }}
                  >
                    <span style={{ ...mono, fontSize: 10, color: colors.dimmer }}>{c.t}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.github }}>{c.model}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.muted }}>{c.tokens}</span>
                    <span style={{ ...mono, fontSize: 11, color: colors.white }}>{c.purpose}</span>
                  </div>
                ))}
              </div>
            </TerminalPanel>
          )}
        </div>
      </div>
    </section>
  );
}
