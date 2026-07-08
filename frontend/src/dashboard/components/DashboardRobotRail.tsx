"use client";

import RobotScene from "@/components/RobotScene";
import { RobotFlowContext, type FlowPhase, type VisualPreset } from "@/components/RobotFlowContext";
import { useMemo, useRef } from "react";
import { resolveDirector } from "@/lib/scroll-director";
import { detectDeviceTier } from "@/lib/device-tier";
import { colors } from "@/lib/tokens";
import type { RobotSocket, ScreenAnchor } from "@/lib/flow-paths";

/** Big robot face behind the main terminal workspace */
export default function DashboardRobotRail() {
  const progressRef = useRef(0.42);
  const heroScrubRef = useRef(1);
  const phaseRef = useRef<FlowPhase>("guide");
  const corridorBlendRef = useRef(0.62);
  const visualPresetRef = useRef<VisualPreset>("guide");
  const finaleRef = useRef(0);
  const handoffRef = useRef(1);
  const tintRef = useRef(colors.glow);
  const anchorsRef = useRef<Partial<Record<RobotSocket, ScreenAnchor>>>({});
  const hubXRef = useRef(0);
  const directorRef = useRef(resolveDirector(0.42));
  const deviceTierRef = useRef(detectDeviceTier());

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

  return (
    <div className="dashboard-face-bg" aria-hidden>
      <div className="dashboard-face-bg-glow" />
      <div className="dashboard-face-bg-canvas">
        <RobotFlowContext.Provider value={bus}>
          <RobotScene height="100%" variant="face" />
        </RobotFlowContext.Provider>
      </div>
    </div>
  );
}
