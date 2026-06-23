"use client";

import { createContext, useContext } from "react";
import type { RobotSocket, ScreenAnchor } from "@/lib/flow-paths";
import type { DirectorState } from "@/lib/scroll-director";
import type { DeviceTier } from "@/lib/device-tier";

export type FlowPhase = "hero" | "guide" | "corridor";
export type VisualPreset = "hero" | "guide" | "splash";

export type RobotFlowBus = {
  progressRef: React.RefObject<number>;
  tintRef: React.RefObject<string>;
  anchorsRef: React.MutableRefObject<Partial<Record<RobotSocket, ScreenAnchor>>>;
  hubXRef: React.MutableRefObject<number>;
  heroScrubRef: React.MutableRefObject<number>;
  phaseRef: React.MutableRefObject<FlowPhase>;
  corridorBlendRef: React.MutableRefObject<number>;
  /** 0→1 as hero scrub crosses 0.85–1.0 for story crossfade */
  handoffRef: React.MutableRefObject<number>;
  finaleRef: React.MutableRefObject<number>;
  directorRef: React.MutableRefObject<DirectorState | null>;
  deviceTierRef: React.MutableRefObject<DeviceTier>;
  visualPresetRef: React.MutableRefObject<VisualPreset>;
};

const RobotFlowContext = createContext<RobotFlowBus | null>(null);

export function useRobotFlow() {
  const ctx = useContext(RobotFlowContext);
  if (!ctx) throw new Error("useRobotFlow must be used inside FlowZone");
  return ctx;
}

export function useRobotFlowOptional() {
  return useContext(RobotFlowContext);
}

export { RobotFlowContext };
