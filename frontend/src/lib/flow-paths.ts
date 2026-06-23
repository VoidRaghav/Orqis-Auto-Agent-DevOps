/** Authored robot-anchored flow paths (Future-State style closed loops). */

import * as THREE from "three";

export type RobotSocket =
  | "crown"
  | "leftShoulder"
  | "rightShoulder"
  | "leftEye"
  | "rightEye"
  | "base";

export type ScreenAnchor = {
  x: number;
  y: number;
  visible: boolean;
};

export type FlowPathDef = {
  id: string;
  start: RobotSocket;
  end: RobotSocket;
  /** Normalized bulge into corridor (-1 left .. 1 right, y in viewport units scaled later) */
  cp1: { x: number; y: number };
  cp2: { x: number; y: number };
  width: number;
  tier: "primary" | "wisp";
  phase: number;
  /** Use in hero 3D tube layer */
  hero3d?: boolean;
};

/** Robot-local 3D anchor positions (attached to robot group origin). */
export const ROBOT_SOCKET_LOCAL: Record<RobotSocket, { x: number; y: number; z: number }> = {
  crown:         { x: 0,    y: 1.95, z: 0.35 },
  leftShoulder:  { x: -0.62, y: 0.35, z: 0.42 },
  rightShoulder: { x: 0.62,  y: 0.35, z: 0.42 },
  leftEye:       { x: -0.27, y: 1.32, z: 0.48 },
  rightEye:      { x: 0.27,  y: 1.32, z: 0.48 },
  base:          { x: 0,    y: -0.58, z: 0.38 },
};

export const FLOW_PATHS: FlowPathDef[] = [
  { id: "p1", start: "crown", end: "base", cp1: { x: -0.55, y: -0.15 }, cp2: { x: -0.35, y: -0.55 }, width: 2.8, tier: "primary", phase: 0, hero3d: true },
  { id: "p2", start: "rightShoulder", end: "base", cp1: { x: -0.42, y: 0.05 }, cp2: { x: -0.22, y: -0.45 }, width: 2.4, tier: "primary", phase: 1.1, hero3d: true },
  { id: "p3", start: "leftShoulder", end: "base", cp1: { x: 0.38, y: 0.08 }, cp2: { x: 0.18, y: -0.42 }, width: 2.2, tier: "primary", phase: 2.3, hero3d: true },
  { id: "p4", start: "crown", end: "rightShoulder", cp1: { x: -0.48, y: 0.35 }, cp2: { x: -0.15, y: 0.12 }, width: 2.0, tier: "primary", phase: 0.7, hero3d: true },
  { id: "p5", start: "leftEye", end: "leftShoulder", cp1: { x: 0.32, y: 0.22 }, cp2: { x: 0.12, y: 0.05 }, width: 1.8, tier: "primary", phase: 3.5 },
  { id: "p6", start: "rightEye", end: "rightShoulder", cp1: { x: -0.36, y: 0.18 }, cp2: { x: -0.08, y: 0.02 }, width: 1.8, tier: "primary", phase: 4.2 },
  { id: "p7", start: "crown", end: "leftShoulder", cp1: { x: 0.45, y: 0.28 }, cp2: { x: 0.2, y: 0.1 }, width: 2.0, tier: "primary", phase: 1.8 },
  { id: "p8", start: "rightShoulder", end: "leftShoulder", cp1: { x: -0.5, y: -0.2 }, cp2: { x: 0.5, y: -0.25 }, width: 2.2, tier: "primary", phase: 2.9 },
  { id: "w1", start: "leftEye", end: "base", cp1: { x: -0.28, y: -0.1 }, cp2: { x: -0.12, y: -0.38 }, width: 1.2, tier: "wisp", phase: 0.4 },
  { id: "w2", start: "rightEye", end: "base", cp1: { x: 0.3, y: -0.08 }, cp2: { x: 0.14, y: -0.36 }, width: 1.2, tier: "wisp", phase: 1.6 },
  { id: "w3", start: "crown", end: "rightEye", cp1: { x: -0.22, y: 0.42 }, cp2: { x: 0.05, y: 0.25 }, width: 1.0, tier: "wisp", phase: 2.1 },
  { id: "w4", start: "crown", end: "leftEye", cp1: { x: 0.24, y: 0.4 }, cp2: { x: -0.04, y: 0.24 }, width: 1.0, tier: "wisp", phase: 3.0 },
  { id: "w5", start: "rightShoulder", end: "rightEye", cp1: { x: -0.32, y: 0.55 }, cp2: { x: -0.08, y: 0.38 }, width: 1.0, tier: "wisp", phase: 4.5 },
  { id: "w6", start: "leftShoulder", end: "leftEye", cp1: { x: 0.28, y: 0.52 }, cp2: { x: 0.06, y: 0.36 }, width: 1.0, tier: "wisp", phase: 5.2 },
];

export const HERO_3D_PATHS = FLOW_PATHS.filter((p) => p.hero3d);

export type ResolvedPath2D = {
  id: string;
  tier: "primary" | "wisp";
  width: number;
  phase: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  x3: number;
  y3: number;
};

export type VirtualHub = {
  x: number;
  topY: number;
  bottomY: number;
  active: boolean;
};

const SOCKET_CORRIDOR_FRAC: Record<RobotSocket, number> = {
  crown: 0.03,
  leftEye: 0.1,
  rightEye: 0.14,
  leftShoulder: 0.42,
  rightShoulder: 0.48,
  base: 0.94,
};

function clamp(v: number, lo = 0, hi = 1) {
  return Math.max(lo, Math.min(hi, v));
}

/** 0 = robot-local, 1 = full vertical corridor spine */
export function corridorBlend(scrollProgress: number, anyAnchorVisible = true): number {
  if (!anyAnchorVisible) return 1;
  return clamp((scrollProgress - 0.02) / 0.12, 0, 1);
}

function corridorSocketXY(
  socket: RobotSocket,
  hub: VirtualHub,
  viewportH: number
): ScreenAnchor {
  const span = hub.bottomY - hub.topY;
  const y = hub.topY + SOCKET_CORRIDOR_FRAC[socket] * span;
  const spread = viewportH * 0.018;
  const xOffset =
    socket === "leftShoulder" || socket === "leftEye" ? -spread :
    socket === "rightShoulder" || socket === "rightEye" ? spread : 0;
  return { x: hub.x + xOffset, y, visible: true };
}

function blendSocketXY(
  live: ScreenAnchor,
  corridor: ScreenAnchor,
  blend: number
): ScreenAnchor {
  if (!live.visible) return corridor;
  if (blend <= 0) return live;
  if (blend >= 1) return corridor;
  return {
    x: live.x + (corridor.x - live.x) * blend,
    y: live.y + (corridor.y - live.y) * blend,
    visible: true,
  };
}

export function getAnchor(
  anchors: Partial<Record<RobotSocket, ScreenAnchor>>,
  socket: RobotSocket,
  hub: VirtualHub
): ScreenAnchor {
  const a = anchors[socket];
  if (a?.visible) return a;
  if (hub.active) {
    if (socket === "crown" || socket === "leftEye" || socket === "rightEye") {
      return { x: hub.x, y: hub.topY, visible: true };
    }
    return { x: hub.x, y: hub.bottomY, visible: true };
  }
  return EMPTY_ANCHOR;
}

const EMPTY_ANCHOR: ScreenAnchor = { x: 0, y: 0, visible: false };

export function computeVirtualHub(
  anchors: Partial<Record<RobotSocket, ScreenAnchor>>,
  viewportW: number,
  viewportH: number,
  scrollProgress: number,
  fallbackX?: number
): VirtualHub {
  const anyVisible = Object.values(anchors).some((a) => a?.visible);
  const forceHub = scrollProgress >= 0.05 || !anyVisible;
  const base = anchors.base;
  const crown = anchors.crown;
  const cx =
    forceHub && fallbackX ? fallbackX :
    base?.visible ? base.x :
    crown?.visible ? crown.x :
    fallbackX ?? viewportW * 0.72;
  return {
    x: cx,
    topY: -56,
    bottomY: viewportH + 56,
    active: forceHub || !anyVisible,
  };
}

export function resolvePath2D(
  def: FlowPathDef,
  anchors: Partial<Record<RobotSocket, ScreenAnchor>>,
  hub: VirtualHub,
  viewportW: number,
  viewportH: number,
  scrollProgress: number,
  time: number,
  formation = 1
): ResolvedPath2D | null {
  const anyVisible = Object.values(anchors).some((a) => a?.visible);
  const blend = corridorBlend(scrollProgress, anyVisible);
  const liveStart = anchors[def.start];
  const liveEnd = anchors[def.end];
  const corridorStart = corridorSocketXY(def.start, hub, viewportH);
  const corridorEnd = corridorSocketXY(def.end, hub, viewportH);

  const start = blend > 0
    ? blendSocketXY(liveStart ?? EMPTY_ANCHOR, corridorStart, blend)
    : getAnchor(anchors, def.start, hub);
  const end = blend > 0
    ? blendSocketXY(liveEnd ?? EMPTY_ANCHOR, corridorEnd, blend)
    : getAnchor(anchors, def.end, hub);

  if (!start.visible && !end.visible && !hub.active && blend <= 0) return null;

  const elong = (0.35 + scrollProgress * 2.1) * clamp(formation, 0.08, 1);
  const sway = Math.sin(time * 0.55 + def.phase) * viewportW * 0.014 * (0.35 + blend * 0.65);
  const bulgeScale = 0.22 + blend * 0.14;
  const bulgeX = def.cp1.x * viewportW * bulgeScale * elong + sway;
  const bulgeX2 = def.cp2.x * viewportW * (bulgeScale * 0.85) * elong + sway * 0.6;

  const mx = (start.x + end.x) / 2;
  const my = (start.y + end.y) / 2;
  const span = Math.abs(end.y - start.y);
  const midLift = blend * viewportH * 0.08;

  const bulgeY = blend > 0.2
    ? my + def.cp1.y * span * 0.55 + midLift
    : my + def.cp1.y * viewportH * 0.55 * elong;
  const bulgeY2 = blend > 0.2
    ? my + def.cp2.y * span * 0.65 + midLift * 1.2
    : my + def.cp2.y * viewportH * 0.65 * elong + scrollProgress * viewportH * 0.35;

  return {
    id: def.id,
    tier: def.tier,
    width: def.width,
    phase: def.phase,
    x0: start.x,
    y0: start.y,
    x1: mx + bulgeX,
    y1: bulgeY,
    x2: mx + bulgeX2,
    y2: bulgeY2,
    x3: end.x,
    y3: end.y,
  };
}

export function resolveAllPaths2D(
  anchors: Partial<Record<RobotSocket, ScreenAnchor>>,
  viewportW: number,
  viewportH: number,
  scrollProgress: number,
  time: number,
  fallbackHubX?: number,
  formation = 1
): ResolvedPath2D[] {
  const hub = computeVirtualHub(anchors, viewportW, viewportH, scrollProgress, fallbackHubX);
  return FLOW_PATHS.map((def) =>
    resolvePath2D(def, anchors, hub, viewportW, viewportH, scrollProgress, time, formation)
  ).filter((p): p is ResolvedPath2D => p !== null);
}

/** 3D world-space points for tube geometry (robot-local). */
export function resolvePath3D(
  def: FlowPathDef,
  scrollProgress: number,
  time: number,
  formation = 1
): THREE.Vector3[] {
  const start = ROBOT_SOCKET_LOCAL[def.start];
  const end = ROBOT_SOCKET_LOCAL[def.end];
  const elong = 0.4 + scrollProgress * 1.2;
  const sway = Math.sin(time * 0.6 + def.phase) * 0.08;

  const mx = (start.x + end.x) / 2;
  const my = (start.y + end.y) / 2;
  const mz = (start.z + end.z) / 2;

  const p0 = new THREE.Vector3(start.x, start.y, start.z);
  const p1 = new THREE.Vector3(
    mx + def.cp1.x * 0.85 * elong + sway,
    my + def.cp1.y * 0.9 * elong,
    mz + 0.15
  );
  const p2 = new THREE.Vector3(
    mx + def.cp2.x * 0.75 * elong + sway * 0.5,
    my + def.cp2.y * 1.1 * elong - scrollProgress * 0.4,
    mz + 0.08
  );
  const p3 = new THREE.Vector3(end.x, end.y, end.z);

  const form = clamp(formation, 0.05, 1);
  const shrink = (p: THREE.Vector3) => p0.clone().lerp(p, form);

  return [p0, shrink(p1), shrink(p2), shrink(p3)];
}
