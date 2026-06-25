"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import RobotScene from "@/components/RobotScene";
import { RobotFlowContext, type FlowPhase, type VisualPreset } from "@/components/RobotFlowContext";
import { resolveDirector } from "@/lib/scroll-director";
import { detectDeviceTier } from "@/lib/device-tier";
import { colors } from "@/lib/tokens";
import type { RobotSocket, ScreenAnchor } from "@/lib/flow-paths";
import type { OpsMood } from "./ops-ambient";

const MOOD_TINT: Record<OpsMood, string> = {
  offline: "#6a7a74",
  standby: colors.glow,
  live: colors.green,
  alert: colors.amber,
};

/** Ghost robot — signature Orqis presence behind ops UI */
export default function OpsAmbientRobot({ mood }: { mood: OpsMood }) {
  const [show, setShow] = useState(false);
  const progressRef = useRef(0.42);
  const heroScrubRef = useRef(1);
  const phaseRef = useRef<FlowPhase>("guide");
  const corridorBlendRef = useRef(0.62);
  const visualPresetRef = useRef<VisualPreset>("guide");
  const finaleRef = useRef(0);
  const handoffRef = useRef(1);
  const tintRef = useRef(MOOD_TINT[mood]);
  const anchorsRef = useRef<Partial<Record<RobotSocket, ScreenAnchor>>>({});
  const hubXRef = useRef(0);
  const directorRef = useRef(resolveDirector(0.42));
  const deviceTierRef = useRef(detectDeviceTier());

  useEffect(() => {
    tintRef.current = MOOD_TINT[mood];
  }, [mood]);

  useEffect(() => {
    const tier = detectDeviceTier();
    setShow(tier !== "low" && window.innerWidth >= 640);
  }, []);

  const bus = useMemo(
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
    [],
  );

  if (!show) return null;

  return (
    <div className={`ops-ambient-robot ops-ambient-robot--${mood}`} aria-hidden>
      <div className="ops-ambient-robot-glow" />
      <div className="ops-ambient-robot-canvas">
        <RobotFlowContext.Provider value={bus}>
          <RobotScene height="100%" variant="face" />
        </RobotFlowContext.Provider>
      </div>
    </div>
  );
}
