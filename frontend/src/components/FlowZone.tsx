"use client";

import { lazy, Suspense, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import RobotFlowCanvas from "@/components/RobotFlowCanvas";
import HeroAmbientLayer from "@/components/HeroAmbientLayer";
import OrqisSplash from "@/components/OrqisSplash";
import { RobotFlowContext, type FlowPhase, type VisualPreset } from "@/components/RobotFlowContext";
import { resolveFlowPhase, measureHeroScrub } from "@/lib/flow-phase";
import { resolveDirector } from "@/lib/scroll-director";
import { detectDeviceTier } from "@/lib/device-tier";
import { heroFloorGlow, heroRailShiftVw, heroRobotPresence, guideRobotBackground, measureFinaleReveal, resolveRobotRailPose } from "@/lib/hero-choreography";
import type { RobotSocket, ScreenAnchor } from "@/lib/flow-paths";
import { colors } from "@/lib/tokens";
import { isLayoutMobile, onLayoutMobileChange } from "@/lib/layout-breakpoint";

const RobotScene = lazy(() => import("@/components/RobotScene"));

const SPLASH_MIN_MS = 1200;

type FlowCtx = {
  progressRef: React.MutableRefObject<number>;
  tintRef: React.MutableRefObject<string>;
  setTint: (color: string) => void;
};

const FlowContext = createContext<FlowCtx | null>(null);

export function useFlow() {
  const ctx = useContext(FlowContext);
  if (!ctx) throw new Error("useFlow must be used inside FlowZone");
  return ctx;
}

export function useFlowOptional() {
  return useContext(FlowContext);
}

export default function FlowZone({ children }: { children: React.ReactNode }) {
  const zoneRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef(0);
  const tintRef = useRef<string>(colors.glow);
  const anchorsRef = useRef<Partial<Record<RobotSocket, ScreenAnchor>>>({});
  const hubXRef = useRef(0);
  const hubLockedRef = useRef(false);
  const heroScrubRef = useRef(0);
  const phaseRef = useRef<FlowPhase>("hero");
  const corridorBlendRef = useRef(0);
  const handoffRef = useRef(0);
  const finaleRef = useRef(0);
  const directorRef = useRef<ReturnType<typeof resolveDirector> | null>(null);
  const deviceTierRef = useRef(detectDeviceTier());
  const visualPresetRef = useRef<VisualPreset>("splash");
  const splashActiveRef = useRef(true);
  const rafRef = useRef(0);
  const splashStartRef = useRef(0);
  const mobileLayoutRef = useRef(isLayoutMobile());

  const [splashVisible, setSplashVisible] = useState(true);
  const [splashFading, setSplashFading] = useState(false);

  useEffect(() => onLayoutMobileChange((m) => {
    mobileLayoutRef.current = m;
  }), []);

  const setTint = useCallback((color: string) => {
    tintRef.current = color;
  }, []);

  useEffect(() => {
    splashStartRef.current = Date.now();
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const minMs = reducedMotion ? 350 : SPLASH_MIN_MS;

    const dismiss = () => {
      const elapsed = Date.now() - splashStartRef.current;
      const wait = Math.max(0, minMs - elapsed);
      window.setTimeout(() => {
        setSplashFading(true);
        window.setTimeout(() => {
          splashActiveRef.current = false;
          visualPresetRef.current = "hero";
          setSplashVisible(false);
          window.dispatchEvent(new CustomEvent("orqis:splash-done"));
        }, 620);
      }, wait);
    };

    if (document.readyState === "complete") dismiss();
    else window.addEventListener("load", dismiss, { once: true });

    return () => window.removeEventListener("load", dismiss);
  }, []);

  useEffect(() => {
    const tick = () => {
      const zone = zoneRef.current;
      if (zone) {
        const rect = zone.getBoundingClientRect();
        const scrollable = rect.height - window.innerHeight;
        if (scrollable > 0) {
          progressRef.current = Math.max(0, Math.min(1, -rect.top / scrollable));
        }
        directorRef.current = resolveDirector(progressRef.current);
        if (progressRef.current > 0.08 && !hubLockedRef.current && phaseRef.current !== "hero") {
          const base = anchorsRef.current.base;
          const crown = anchorsRef.current.crown;
          const cx = base?.visible ? base.x : crown?.visible ? crown.x : hubXRef.current;
          if (cx > 0) {
            hubXRef.current = cx;
            hubLockedRef.current = true;
          }
        }
      }

      const measuredScrub = measureHeroScrub();
      const scrub = Math.max(heroScrubRef.current, measuredScrub);
      heroScrubRef.current = scrub;
      handoffRef.current = Math.max(0, Math.min(1, (scrub - 0.85) / 0.15));
      const { phase, corridorBlend } = resolveFlowPhase(scrub);
      phaseRef.current = phase;
      corridorBlendRef.current = corridorBlend;

      finaleRef.current = measureFinaleReveal();
      const finale = finaleRef.current;

      if (splashActiveRef.current) {
        visualPresetRef.current = "splash";
      } else if (phase === "hero") {
        visualPresetRef.current = "hero";
      } else if (finale > 0.45) {
        visualPresetRef.current = "hero";
      } else {
        visualPresetRef.current = "guide";
      }

      if (railRef.current) {
        const inHero = !splashActiveRef.current && phase === "hero" && scrub < 0.995;
        const mobile = mobileLayoutRef.current;
        // Phone: keep robot in hero; hide/degrade after hero so it doesn't overlap stacked content
        if (mobile && !splashActiveRef.current && !inHero && finale < 0.35) {
          railRef.current.style.opacity = "0";
          railRef.current.style.visibility = "hidden";
          railRef.current.style.pointerEvents = "none";
          railRef.current.style.setProperty("--robot-rail-shift", "0");
        } else if (inHero) {
          railRef.current.style.left = "50%";
          // Desktop: corridor z; mobile: stay under copy (CSS z-index: 2)
          railRef.current.style.zIndex = mobile ? "2" : "4";
          const shift = mobile ? 0 : heroRailShiftVw(scrub);
          const presence = heroRobotPresence(scrub);
          railRef.current.style.transform = `translateX(calc(-50% + ${shift}vw))`;
          railRef.current.style.opacity = String(presence);
          railRef.current.style.filter = "none";
          railRef.current.style.visibility = "visible";
          railRef.current.style.pointerEvents = "none";
          if (mobile) {
            railRef.current.style.top = "52vh";
            railRef.current.style.height = "48vh";
          } else {
            railRef.current.style.top = "";
            railRef.current.style.height = "";
          }
        } else if (!splashActiveRef.current) {
          const guide = guideRobotBackground(progressRef.current, corridorBlendRef.current);
          const pose = resolveRobotRailPose(guide, finale);
          // Soft finale reappear on mobile only if finale is strong
          const op = mobile ? pose.opacity * Math.min(1, finale) * 0.55 : pose.opacity;
          railRef.current.style.left = `${pose.leftPct}%`;
          railRef.current.style.zIndex = String(pose.zIndex);
          railRef.current.style.transform = `translateX(-50%) scale(${pose.scale})`;
          railRef.current.style.opacity = String(op);
          railRef.current.style.filter = pose.blur > 0.05 ? `brightness(${pose.brightness})` : "none";
          railRef.current.style.visibility = op > 0.02 ? "visible" : "hidden";
          railRef.current.style.pointerEvents = "none";
          if (!mobile) {
            railRef.current.style.top = "";
            railRef.current.style.height = "";
          }
        } else {
          railRef.current.style.left = "50%";
          railRef.current.style.zIndex = mobile ? "2" : "5";
          railRef.current.style.transform = "translateX(-50%)";
          railRef.current.style.opacity = "1";
          railRef.current.style.filter = "none";
          railRef.current.style.visibility = "visible";
          railRef.current.style.pointerEvents = "none";
          if (mobile) {
            railRef.current.style.top = "52vh";
            railRef.current.style.height = "48vh";
          } else {
            railRef.current.style.top = "";
            railRef.current.style.height = "";
          }
        }
        railRef.current.style.setProperty("--robot-rail-shift", "0");
      }
      if (zoneRef.current) {
        zoneRef.current.style.setProperty("--robot-rail-shift", "0");
        zoneRef.current.style.setProperty(
          "--hero-glow-opacity",
          String(phase === "hero" ? heroFloorGlow(scrub) * 0.9 : 0)
        );
        zoneRef.current.classList.toggle("flow-zone--hero-phase", !splashActiveRef.current && phase === "hero");
        zoneRef.current.classList.toggle("flow-zone--guide-phase", !splashActiveRef.current && phase !== "hero");
        zoneRef.current.classList.toggle("flow-zone--splash", splashActiveRef.current || splashVisible);
        zoneRef.current.classList.toggle("flow-zone--finale-phase", !splashActiveRef.current && finale > 0.35);
      }

      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [splashVisible]);

  const robotFlowBus = useMemo(
    () => ({
      progressRef,
      tintRef,
      anchorsRef,
      hubXRef,
      heroScrubRef,
      phaseRef,
      corridorBlendRef,
      handoffRef,
      finaleRef,
      directorRef,
      deviceTierRef,
      visualPresetRef,
    }),
    []
  );

  return (
    <FlowContext.Provider value={{ progressRef, tintRef, setTint }}>
      <RobotFlowContext.Provider value={robotFlowBus}>
        <div ref={zoneRef} className="flow-zone flow-zone--splash">
          <div className="flow-zone-canvas" aria-hidden>
            <HeroAmbientLayer />
            <div className="flow-zone-glow" />
            <div className="flow-zone-vignette" />
            <RobotFlowCanvas />
          </div>
          <div ref={railRef} className="guide-robot-rail" aria-hidden>
            <Suspense fallback={null}>
              <RobotScene />
            </Suspense>
          </div>
          <OrqisSplash visible={splashVisible} fading={splashFading} />
          <div className="flow-zone-content">{children}</div>
        </div>
      </RobotFlowContext.Provider>
    </FlowContext.Provider>
  );
}
