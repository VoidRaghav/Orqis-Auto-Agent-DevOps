"use client";

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { hero } from "@/lib/marketing-copy";
import {
  HERO_COPY,
  HERO_OPS_PANELS,
  beatBlend,
  resolveHeroBeat,
} from "@/lib/hero-beats";
import { heroSlam, heroRetreat, introGhostOpacity } from "@/lib/hero-choreography";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { useFlowOptional } from "@/components/FlowZone";
import { colors } from "@/lib/tokens";
import FloatingOpsPanel from "@/components/FloatingOpsPanel";

function useHeroScrub(): number {
  const flow = useRobotFlowOptional();
  const [scrub, setScrub] = useState(0);

  useEffect(() => {
    if (!flow) return;
    let raf = 0;
    const tick = () => {
      setScrub(flow.heroScrubRef.current);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [flow]);

  return scrub;
}

export default function CinematicHero() {
  const scrub = useHeroScrub();
  const flowCtx = useFlowOptional();
  const robotFlow = useRobotFlowOptional();
  const subRef = useRef<HTMLParagraphElement>(null);

  const beat = resolveHeroBeat(scrub);
  const blend = beatBlend(scrub);
  const slam = heroSlam(scrub);
  const retreat = heroRetreat(scrub);

  useEffect(() => {
    if (flowCtx) flowCtx.tintRef.current = beat.tint;
  }, [beat.tint, flowCtx]);

  useEffect(() => {
    if (!robotFlow) return;
    robotFlow.handoffRef.current = Math.max(0, Math.min(1, (scrub - 0.88) / 0.12));
  }, [scrub, robotFlow]);

  const ghostOpacity = introGhostOpacity(scrub);
  const copyShift = scrub * 14 * (1 - retreat * 0.65);
  const portalPulse = slam;
  const subFade = 1 - blend * 0.45;

  return (
    <div
      className="cinematic-hero"
      style={{
        background:
          slam > 0.05
            ? `radial-gradient(ellipse 55% 48% at 50% 44%, ${beat.tint}18 0%, transparent 58%)`
            : "transparent",
      }}
    >
      <div className="cinematic-hero-grain" aria-hidden />
      <div className="cinematic-hero-vignette" aria-hidden />

      <div
        className="cinematic-hero-ghost"
        aria-hidden
        style={{ opacity: ghostOpacity, visibility: ghostOpacity < 0.003 ? "hidden" : "visible" }}
      >
        ORQIS
      </div>

      <div
        className="cinematic-hero-portal"
        aria-hidden
        style={{
          opacity: slam > 0.04 ? 0.12 + portalPulse * 0.38 : 0,
          transform: `translate(-50%, -50%) scale(${0.85 + portalPulse * 0.4})`,
        }}
      />

      <div className="cinematic-hero-grid">
        <div
          className="cinematic-hero-col cinematic-hero-col--copy"
          style={{ transform: `translateY(${copyShift}px)` }}
        >
          <div className="cinematic-hero-badge">
            Agent Ops · GitHub PR-first
          </div>

          <h1 className="cinematic-hero-headline editorial-headline">
            <span className="cinematic-hero-headline-line">{HERO_COPY.line1}</span>
            <span className="cinematic-hero-headline-line">{HERO_COPY.line2}</span>
            <span
              className="cinematic-hero-tagline"
              style={{ color: HERO_COPY.taglineAccent }}
            >
              {HERO_COPY.tagline}
            </span>
          </h1>

          <p
            ref={subRef}
            key={beat.kicker}
            className="cinematic-hero-sub"
            style={{ opacity: subFade }}
          >
            {beat.sub}
          </p>

          <div className="cinematic-hero-ctas">
            <Link to="/settings" className="btn-ghost cinematic-hero-btn">
              Connect GitHub →
            </Link>
            <Link to="/dashboard" className="btn-ghost cinematic-hero-btn">
              View Demo ↗
            </Link>
          </div>

          <div className="cinematic-hero-stats">
            {hero.telemetry.map((t) => (
              <div key={t.label} className="cinematic-hero-stat">
                <span
                  style={{
                    color:
                      t.accent === "heal"
                        ? colors.green
                        : t.accent === "amber"
                          ? colors.amber
                          : t.accent === "cyan"
                            ? colors.github
                            : colors.white,
                  }}
                >
                  {t.val}
                </span>
                <span>{t.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="cinematic-hero-col cinematic-hero-col--corridor" aria-hidden>
          <div
            className="cinematic-hero-corridor-ring"
            style={{ opacity: Math.max(0, 0.1 + scrub * 0.22 - retreat * 0.28) }}
          />
        </div>

        <div className="cinematic-hero-col cinematic-hero-col--ops">
          <div className="cinematic-hero-ops-rail" aria-hidden>
            {HERO_OPS_PANELS.map((panel, i) => {
              const active = beat.activePanel === i;
              const near = Math.abs(beat.activePanel - i) === 1;
              const panelOpacity = active ? 1 : near ? 0.62 : 0.48;
              return (
                <FloatingOpsPanel
                  key={panel.id}
                  id={`hero-${panel.id}`}
                  section="hero"
                  label={panel.label}
                  status={panel.status}
                  detail={panel.detail}
                  accent={panel.accent}
                  top={panel.top}
                  right={panel.right}
                  priority={active ? 1 : 0.5}
                  className={active ? "cinematic-hero-ops-panel--active" : "cinematic-hero-ops-panel"}
                  style={{
                    opacity: panelOpacity,
                    borderColor: active ? `${panel.accent}88` : `${panel.accent}33`,
                    boxShadow: active ? `0 0 28px ${panel.accent}22` : "none",
                    transform: active ? "translateX(-4px)" : "none",
                  }}
                />
              );
            })}
          </div>

          <div className="cinematic-hero-scrub-hint">
            <span>scroll the story</span>
            <div className="cinematic-hero-scrub-bar">
              <div style={{ width: `${scrub * 100}%` }} />
            </div>
          </div>
        </div>
      </div>

      <Link to="/dashboard" className="cinematic-hero-dash-link">
        OPEN DASHBOARD
        <ArrowRight size={28} strokeWidth={2.25} />
      </Link>
    </div>
  );
}
