/** Catmull-Rom camera spline keyed to scroll-film chapters. */

import * as THREE from "three";
import type { FilmChapter } from "@/lib/scroll-director";

export type CameraPose = {
  position: [number, number, number];
  lookAt: [number, number, number];
  fov: number;
};

type CamKeyframe = CameraPose & { progress: number };

const KEYFRAMES: CamKeyframe[] = [
  { progress: 0, position: [0, 0.8, 8.2], lookAt: [0, 0.2, 0], fov: 36 },
  { progress: 0.08, position: [0, 0.6, 7.4], lookAt: [0, 0.3, 0], fov: 34 },
  { progress: 0.25, position: [0.2, 0.45, 6.8], lookAt: [0, 0.35, 0], fov: 32 },
  { progress: 0.4, position: [1.1, 0.35, 7.2], lookAt: [-0.3, 0.2, 0], fov: 30 },
  { progress: 0.55, position: [1.4, 0.25, 7.0], lookAt: [-0.5, 0.15, 0], fov: 30 },
  { progress: 0.7, position: [0.8, 0.3, 6.6], lookAt: [-0.2, 0.25, 0], fov: 31 },
  { progress: 0.85, position: [0.5, 0.35, 6.9], lookAt: [0, 0.3, 0], fov: 32 },
  { progress: 0.95, position: [0, 0.42, 6.2], lookAt: [0, 0.35, 0], fov: 33 },
  { progress: 1, position: [0, 0.48, 5.8], lookAt: [0, 0.38, 0], fov: 34 },
];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function lerp3(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

function easeInOut(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export function sampleCameraSpline(filmProgress: number, chapter?: FilmChapter, chapterT = 0): CameraPose {
  const p = Math.max(0, Math.min(1, filmProgress));

  let i = 0;
  while (i < KEYFRAMES.length - 2 && KEYFRAMES[i + 1].progress < p) i++;

  const a = KEYFRAMES[i];
  const b = KEYFRAMES[Math.min(i + 1, KEYFRAMES.length - 1)];
  const span = Math.max(0.0001, b.progress - a.progress);
  const raw = easeInOut(Math.max(0, Math.min(1, (p - a.progress) / span)));

  const base: CameraPose = {
    position: lerp3(a.position, b.position, raw),
    lookAt: lerp3(a.lookAt, b.lookAt, raw),
    fov: lerp(a.fov, b.fov, raw),
  };

  if (!chapter) return base;

  const micro: Partial<Record<FilmChapter, [number, number, number]>> = {
    burn: [0.15 * Math.sin(chapterT * Math.PI), 0.08 * chapterT, -0.2 * chapterT],
    patch: [-0.1 * chapterT, 0.05, 0.1 * chapterT],
    finale: [0, 0.06 * easeInOut(chapterT), -0.35 * easeInOut(chapterT)],
  };
  const offset = micro[chapter];
  if (offset) {
    base.position = [
      base.position[0] + offset[0],
      base.position[1] + offset[1],
      base.position[2] + offset[2],
    ];
  }

  return base;
}

export function applyCameraPose(
  camera: THREE.PerspectiveCamera,
  pose: CameraPose,
  lerpFactor = 1
) {
  if (lerpFactor >= 0.99) {
    camera.position.set(...pose.position);
    camera.lookAt(...pose.lookAt);
    camera.fov = pose.fov;
    camera.updateProjectionMatrix();
    return;
  }
  const cx = camera.position.x + (pose.position[0] - camera.position.x) * lerpFactor;
  const cy = camera.position.y + (pose.position[1] - camera.position.y) * lerpFactor;
  const cz = camera.position.z + (pose.position[2] - camera.position.z) * lerpFactor;
  camera.position.set(cx, cy, cz);
  camera.lookAt(...pose.lookAt);
  camera.fov += (pose.fov - camera.fov) * lerpFactor;
  camera.updateProjectionMatrix();
}
