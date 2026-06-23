"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useFlow } from "@/components/FlowZone";
import { registerPanel, unregisterPanel } from "@/lib/panel-registry";
import MetaLabel, { SectionMeta } from "@/components/ui/MetaLabel";
import TerminalPanel from "@/components/ui/TerminalPanel";
import FlowSectionOverlay from "@/components/FlowSectionOverlay";
import { colors, fonts, mono } from "@/lib/tokens";
import { SCROLL_GHOST_PEAK } from "@/lib/hero-choreography";

const PANELS = [
  {
    num: "01",
    title: "Detect",
    ghostWord: "TRACE",
    desc: "Logs and AI tool traces stream in. Orqis fingerprints runaway loops and tracebacks, locates the exact file and line, and opens an incident in under a second.",
    accent: colors.green,
    code: [
      { t: "TRACE", msg: "check_order_status ×8 in 30s — circuit_break", color: colors.amber },
      { t: "LOOP", msg: "RUNAWAY_LOOP detected — refund_agent.py:88", color: colors.amber },
      { t: "LOCATE", msg: "while True without exit — depth 847", color: colors.red },
      { t: "OPEN", msg: "incident #4421 — patch pipeline armed", color: colors.green },
    ],
  },
  {
    num: "02",
    title: "Patch",
    ghostWord: "PATCH",
    desc: "Deterministic diff from the traceback — no hallucinated rewrites. Guardrails cap blast radius. Every line tied to the incident fingerprint.",
    accent: colors.amber,
    diff: [
      { type: "rem", code: "while True:" },
      { type: "rem", code: "    status = check_order_status(id)" },
      { type: "add", code: "    _attempts = 0" },
      { type: "add", code: "    while _attempts < 5:" },
      { type: "add", code: "        status = check_order_status(id)" },
      { type: "add", code: "        _attempts += 1" },
    ],
  },
  {
    num: "03",
    title: "Review PR",
    ghostWord: "PR",
    desc: "Ships to a branch — never main. GitHub PR with diff, incident context, and CI checks. You review like any other engineer's PR.",
    accent: colors.github,
    pr: {
      branch: "orqis/fix-runaway-loop-4421",
      title: "fix: break runaway loop in refund_agent",
      checks: ["diff verified", "no secrets", "tests green"],
      url: "github.com/you/repo/pull/1",
    },
  },
  {
    num: "04",
    title: "Apply Local",
    ghostWord: "APPLY",
    desc: "No GitHub? Patch lands on disk instantly. MCP push to your IDE or copy the neutral prompt — Cursor, Claude Code, Windsurf, VS Code.",
    accent: colors.glow,
    local: [
      { key: "path", val: "agents/refund_agent.py" },
      { key: "action", val: "fix_applied" },
      { key: "mcp", val: "patch sent → awaiting approval" },
      { key: "fallback", val: "copy prompt → any assistant" },
    ],
  },
  {
    num: "05",
    title: "Audit",
    ghostWord: "AUDIT",
    desc: "CHANGES tab is the source of truth — who approved, what shipped, PR link or local apply. Full timeline for compliance and postmortems.",
    accent: colors.green,
    audit: [
      { t: "14:02:01", event: "RUNAWAY_LOOP detected", sc: colors.amber },
      { t: "14:02:03", event: "patch generated — 6 lines", sc: colors.green },
      { t: "14:02:18", event: "PR #1 opened on orqis/fix-loop", sc: colors.github },
      { t: "14:04:52", event: "merged → CHANGES logged", sc: colors.green },
    ],
  },
];

const PANEL_LAYOUTS = [
  { textTop: "15%", panelTop: "14%", panelRight: "3%" },
  { textTop: "15%", panelTop: "14%", panelRight: "3%" },
  { textTop: "15%", panelTop: "14%", panelRight: "3%" },
  { textTop: "15%", panelTop: "14%", panelRight: "3%" },
  { textTop: "15%", panelTop: "14%", panelRight: "3%" },
];

const TOTAL_VH = 300;
const IN = 0.06;
const OUT = 0.94;

function clamp(v: number, lo = 0, hi = 1) {
  return Math.max(lo, Math.min(hi, v));
}
function easeOut(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
function easeIn(t: number) {
  return t * t * t;
}
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export default function FeaturesSection() {
  const { setTint } = useFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef(0);
  const prevProg = useRef(-1);

  const panelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const ghostRefs = useRef<(HTMLDivElement | null)[]>([]);
  const headlineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const prevActive = useRef(-1);
  const registeredActive = useRef(-1);
  const introRef = useRef<HTMLDivElement>(null);
  const [activeAccent, setActiveAccent] = useState(PANELS[0].accent);

  const update = useCallback(() => {
    const wrapper = wrapperRef.current;
    const sticky = stickyRef.current;
    if (!wrapper || !sticky) return;

    const rect = wrapper.getBoundingClientRect();
    const scrollable = rect.height - window.innerHeight;
    if (scrollable <= 0) return;

    const progress = clamp(-rect.top / scrollable);
    if (Math.abs(progress - prevProg.current) < 0.0001) return;
    prevProg.current = progress;

    const N = PANELS.length;
    const active = clamp(Math.floor(progress * N), 0, N - 1);
    if (active !== prevActive.current) {
      prevActive.current = active;
      setActiveAccent(PANELS[active].accent);
      setTint(PANELS[active].accent);
    }

    if (active !== registeredActive.current) {
      if (registeredActive.current >= 0) {
        unregisterPanel(`feature-headline-${registeredActive.current}`);
      }
      registeredActive.current = active;
      const headline = headlineRefs.current[active];
      if (headline) {
        registerPanel({
          id: `feature-headline-${active}`,
          section: "features",
          el: headline,
          accent: PANELS[active].accent,
          priority: 2.4,
        });
      }
    }

    PANELS.forEach((panel, i) => {
      const el = panelRefs.current[i];
      const ghostEl = ghostRefs.current[i];
      if (!el) return;
      const c = clamp((progress - i / N) / (1 / N));
      let op = 0;
      if (c < IN) op = easeOut(c / IN);
      else if (c < OUT) op = 1;
      else op = 1 - easeIn((c - OUT) / (1 - OUT));
      el.style.opacity = op.toFixed(4);
      el.style.transform = `translateY(${(1 - op) * 28}px)`;
      el.style.pointerEvents = op > 0.5 ? "auto" : "none";

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
    });

    if (introRef.current) {
      const introOp = progress < 0.07 ? 1 - progress / 0.07 : 0;
      introRef.current.style.opacity = introOp.toFixed(4);
    }
  }, [setTint]);

  useEffect(() => {
    const tick = () => {
      update();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(rafRef.current);
      if (registeredActive.current >= 0) {
        unregisterPanel(`feature-headline-${registeredActive.current}`);
      }
    };
  }, [update]);

  return (
    <div className="flow-features-wrap">
      <div ref={wrapperRef} className="flow-features-scroll">
        <div ref={stickyRef} className="flow-features-stage">
          <div ref={introRef} className="flow-features-intro flow-section-headline">
            <SectionMeta index="002" tag="(HOW_IT_WORKS)" />
            <h2
              className="editorial-headline"
              style={{ fontSize: "clamp(2rem, 4.5vw, 3.8rem)", color: colors.white, marginTop: 8 }}
            >
              DETECT. PATCH.
              <br />
              <em>review.</em> // <span style={{ color: colors.green }}>SHIP.</span>
            </h2>
          </div>
          <FlowSectionOverlay accent={activeAccent} side="left" />
          <div className="flow-features-corridor" aria-hidden />

          {PANELS.map((panel, i) => (
            <div
              key={`ghost-${i}`}
              ref={(el) => {
                ghostRefs.current[i] = el;
              }}
              className="flow-ghost-word"
              style={{ opacity: 0, willChange: "opacity, transform" }}
              aria-hidden
            >
              <span style={{ color: panel.accent }}>{panel.ghostWord}</span>
            </div>
          ))}

          {PANELS.map((panel, i) => {
            const layout = PANEL_LAYOUTS[i];
            return (
            <div
              key={i}
              ref={(el) => {
                panelRefs.current[i] = el;
              }}
              style={{
                position: "absolute",
                inset: 0,
                zIndex: 2,
                opacity: 0,
                willChange: "opacity, transform",
              }}
            >
              {/* text block — left, staggered vertically */}
              <div
                className="flow-panel flow-col-left"
                ref={(el) => {
                  headlineRefs.current[i] = el;
                }}
                style={{
                  top: layout.textTop,
                  padding: "28px 32px",
                  borderRadius: 16,
                }}
              >
                <MetaLabel accent={panel.accent} style={{ display: "block", marginBottom: 20 }}>
                  [{panel.num} / 05]
                </MetaLabel>
                <h3
                  style={{
                    fontFamily: fonts.anton,
                    fontSize: "clamp(2rem, 3.8vw, 3.4rem)",
                    color: panel.accent,
                    lineHeight: 0.92,
                    marginBottom: 20,
                  }}
                >
                  {panel.title.toUpperCase()}
                </h3>
                <p
                  style={{
                    fontFamily: fonts.inter,
                    fontSize: "clamp(0.85rem, 1vw, 0.98rem)",
                    color: colors.muted,
                    lineHeight: 1.75,
                  }}
                >
                  {panel.desc}
                </p>
              </div>

              {/* terminal — right corridor; robot sits in center gap */}
              <div
                className="flow-col-right"
                style={{ top: layout.panelTop }}
              >
                <FeatureVisual panel={panel} />
              </div>
            </div>
          );})}

          <div style={{ position: "absolute", bottom: 24, left: 32, zIndex: 3 }}>
            <MetaLabel accent={colors.dimmer}>scroll ↓ — flow state</MetaLabel>
          </div>
        </div>
      </div>

      <div className="section-divider" />
    </div>
  );
}

function FeatureVisual({ panel }: { panel: (typeof PANELS)[0] }) {
  if (panel.code) {
    return (
      <TerminalPanel label="incident.log · live" accent={panel.accent} right={<MetaLabel accent={colors.green}>● live</MetaLabel>}>
        <div style={{ padding: "4px 0" }}>
          {panel.code.map((l, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 14,
                padding: "9px 18px",
                borderBottom: `1px solid ${colors.border}`,
                alignItems: "flex-start",
              }}
            >
              <span style={{ ...mono, color: colors.dimmer, minWidth: 44, fontSize: 10 }}>{`14:0${2 + i}`}</span>
              <span style={{ ...mono, fontSize: 10, padding: "2px 8px", border: `1px solid ${l.color}44`, color: l.color, minWidth: 44, textAlign: "center" }}>
                {l.t}
              </span>
              <span style={{ ...mono, color: colors.muted, fontSize: 12 }}>{l.msg}</span>
            </div>
          ))}
        </div>
      </TerminalPanel>
    );
  }

  if (panel.diff) {
    return (
      <TerminalPanel
        label="refund_agent.py · patch"
        accent={panel.accent}
        right={
          <span style={{ ...mono, fontSize: 11 }}>
            <span style={{ color: colors.green }}>+{panel.diff.filter((d) => d.type === "add").length}</span>{" "}
            <span style={{ color: colors.red }}>−{panel.diff.filter((d) => d.type === "rem").length}</span>
          </span>
        }
      >
        <div style={{ padding: "8px 0" }}>
          {panel.diff.map((l, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                background: l.type === "add" ? colors.greenDim : colors.redDim,
                borderLeft: `2px solid ${l.type === "add" ? colors.green : colors.red}`,
              }}
            >
              <span style={{ ...mono, color: l.type === "add" ? colors.green : colors.red, padding: "6px 14px", fontSize: 12 }}>
                {l.type === "add" ? "+" : "−"}
              </span>
              <span style={{ ...mono, color: colors.muted, padding: "6px 14px 6px 0", fontSize: 12 }}>{l.code}</span>
            </div>
          ))}
        </div>
      </TerminalPanel>
    );
  }

  if (panel.pr) {
    const pr = panel.pr;
    return (
      <TerminalPanel label="github · pull request" accent={colors.github}>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <MetaLabel accent={colors.github} style={{ display: "block" }}>
            ({pr.branch})
          </MetaLabel>
          <div style={{ fontFamily: fonts.inter, fontSize: 15, color: colors.white }}>{pr.title}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {pr.checks.map((c) => (
              <span key={c} style={{ ...mono, fontSize: 10, padding: "4px 10px", border: `1px solid ${colors.green}33`, color: colors.green }}>
                ✓ {c}
              </span>
            ))}
          </div>
          <MetaLabel accent={colors.dimmer}>{pr.url}</MetaLabel>
        </div>
      </TerminalPanel>
    );
  }

  if (panel.local) {
    return (
      <TerminalPanel label="local apply · mcp" accent={colors.glow}>
        <div style={{ padding: "8px 0" }}>
          {panel.local.map((row, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "12px 18px",
                borderBottom: i < panel.local!.length - 1 ? `1px solid ${colors.border}` : "none",
              }}
            >
              <span style={{ ...mono, fontSize: 11, color: colors.dimmer }}>{row.key}</span>
              <span style={{ ...mono, fontSize: 11, color: colors.glow }}>{row.val}</span>
            </div>
          ))}
        </div>
      </TerminalPanel>
    );
  }

  if (panel.audit) {
    return (
      <TerminalPanel label="CHANGES · audit trail" accent={colors.green}>
        <div style={{ padding: "8px 0" }}>
          {panel.audit.map((row, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 16,
                padding: "10px 18px",
                borderBottom: i < panel.audit!.length - 1 ? `1px solid ${colors.border}` : "none",
                borderLeft: `2px solid ${row.sc}`,
              }}
            >
              <span style={{ ...mono, fontSize: 10, color: colors.dimmer, minWidth: 56 }}>{row.t}</span>
              <span style={{ ...mono, fontSize: 12, color: row.sc }}>{row.event}</span>
            </div>
          ))}
        </div>
      </TerminalPanel>
    );
  }

  return null;
}
