"use client";

/**
 * ORQIS robot — slam-dunk scroll rig, depth field, guide lookAt.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";
import {
  HERO_3D_PATHS,
  ROBOT_SOCKET_LOCAL,
  resolvePath3D,
  type RobotSocket,
  type ScreenAnchor,
} from "@/lib/flow-paths";
import { applyHeroScrollRig, applyGuideScrollRig, applyFinaleScrollRig, blendScrollRigs, guideBodyOffset, robotBodyOpacity, scrollAliveDrift } from "@/lib/hero-scroll-rig";
import { sampleCameraSpline, applyCameraPose } from "@/lib/camera-spline-rig";
import { resolveDirector } from "@/lib/scroll-director";
import { getActiveLookAtTarget } from "@/lib/panel-registry";
import { createScrollDepthField } from "@/lib/scroll-depth-field";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";

function roundedBox(
  w: number, h: number, d: number, r: number, segs = 8
): THREE.BufferGeometry {
  const hw = w / 2 - r;
  const hh = h / 2 - r;
  const shape = new THREE.Shape();
  shape.moveTo(-hw, -(hh + r));
  shape.lineTo( hw, -(hh + r));
  shape.quadraticCurveTo( hw + r, -(hh + r),  hw + r, -hh);
  shape.lineTo( hw + r,  hh);
  shape.quadraticCurveTo( hw + r,  hh + r,  hw,  hh + r);
  shape.lineTo(-hw,  hh + r);
  shape.quadraticCurveTo(-(hw + r),  hh + r, -(hw + r),  hh);
  shape.lineTo(-(hw + r), -hh);
  shape.quadraticCurveTo(-(hw + r), -(hh + r), -hw, -(hh + r));
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: d - r * 2, bevelEnabled: true, bevelThickness: r,
    bevelSize: r, bevelOffset: 0, bevelSegments: segs,
  });
  geo.center();
  return geo;
}

function radialCanvas(inner: string, mid: string, px = 1024): THREE.CanvasTexture {
  const cv = document.createElement("canvas");
  cv.width = cv.height = px;
  const ctx = cv.getContext("2d")!;
  const g = ctx.createRadialGradient(px / 2, px / 2, 0, px / 2, px / 2, px / 2);
  g.addColorStop(0, inner);
  g.addColorStop(0.28, mid);
  g.addColorStop(0.58, "rgba(0,0,0,0)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, px, px);
  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearFilter;
  return tex;
}

const SOCKETS: RobotSocket[] = [
  "crown", "leftShoulder", "rightShoulder", "leftEye", "rightEye", "base",
];

function easeInOutGuide(t: number) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export default function RobotScene({
  height = "100vh",
  variant = "default",
}: {
  height?: string;
  variant?: "default" | "face";
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const mouse = useRef({ x: 0, y: 0 });
  const rafRef = useRef(0);
  const flow = useRobotFlowOptional();

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const getSize = () => {
      const rail = container.closest(".dashboard-face-bg") as HTMLElement | null;
      const w = container.clientWidth || rail?.clientWidth || Math.round(window.innerWidth * 0.44);
      const h = container.clientHeight || rail?.clientHeight || Math.round(window.innerHeight * 0.55);
      return { w: Math.max(w, 280), h: Math.max(h, 320) };
    };
    const { w: W, h: H } = getSize();

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.55;
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x000000, 0.055);

    const camera = new THREE.PerspectiveCamera(34, W / H, 0.1, 100);
    camera.position.set(0, 0.5, 6.4);
    camera.lookAt(0, 0.5, 0);

    const depthField = createScrollDepthField(scene);

    const bodyMat = new THREE.MeshPhysicalMaterial({
      color: 0x0a0814, metalness: 0.7, roughness: 0.22,
      clearcoat: 1.0, clearcoatRoughness: 0.06, reflectivity: 0.7,
    });
    const screenMat = new THREE.MeshPhysicalMaterial({
      color: 0x040206, metalness: 0.65, roughness: 0.04,
      clearcoat: 1.0, clearcoatRoughness: 0.02, reflectivity: 1.0,
    });
    const eyeMat = new THREE.MeshPhysicalMaterial({
      color: 0xeeeeee, emissive: new THREE.Color(0xffffff),
      emissiveIntensity: 1.6, roughness: 0.05, metalness: 0, clearcoat: 1.0,
    });
    const tubeMat = new THREE.MeshPhysicalMaterial({
      color: 0x00e5ff, emissive: new THREE.Color(0x00b8d4),
      emissiveIntensity: 0.85, metalness: 0.2, roughness: 0.35,
      transparent: true, opacity: 0.72, depthWrite: false,
    });

    const scrollRig = new THREE.Group();
    scene.add(scrollRig);

    const floorGroup = new THREE.Group();
    scrollRig.add(floorGroup);

    const robot = new THREE.Group();
    scrollRig.add(robot);

    robot.add(new THREE.Mesh(roundedBox(1.10, 1.10, 1.10, 0.09, 10), bodyMat));
    const bodyMesh = robot.children[0] as THREE.Mesh;

    const neckCone = new THREE.Mesh(new THREE.CylinderGeometry(0.10, 0.24, 0.36, 32), bodyMat);
    neckCone.position.y = 0.71;
    robot.add(neckCone);

    const neckJoint = new THREE.Mesh(new THREE.SphereGeometry(0.13, 32, 32), bodyMat);
    neckJoint.position.y = 0.92;
    robot.add(neckJoint);

    const headGroup = new THREE.Group();
    headGroup.position.y = 1.30;
    robot.add(headGroup);

    headGroup.add(new THREE.Mesh(roundedBox(1.50, 0.94, 0.70, 0.13, 10), bodyMat));
    const headMesh = headGroup.children[0] as THREE.Mesh;
    const screen = new THREE.Mesh(roundedBox(1.22, 0.68, 0.04, 0.08, 6), screenMat);
    screen.position.set(0, 0.02, 0.355);
    headGroup.add(screen);

    const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.11, 32, 32), eyeMat);
    const eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.11, 32, 32), eyeMat);
    eyeL.position.set(-0.27, 0.02, 0.41);
    eyeR.position.set(0.27, 0.02, 0.41);
    headGroup.add(eyeL, eyeR);

    const anchorEmpties: Record<RobotSocket, THREE.Object3D> = {} as Record<RobotSocket, THREE.Object3D>;
    for (const socket of SOCKETS) {
      const pos = ROBOT_SOCKET_LOCAL[socket];
      const empty = new THREE.Object3D();
      empty.position.set(pos.x, pos.y, pos.z);
      if (socket === "crown" || socket === "leftEye" || socket === "rightEye") {
        headGroup.add(empty);
      } else {
        robot.add(empty);
      }
      anchorEmpties[socket] = empty;
    }

    const tendrilGroup = new THREE.Group();
    tendrilGroup.position.y = -0.55;
    tendrilGroup.renderOrder = -3;
    floorGroup.add(tendrilGroup);

    type TubeEntry = { mesh: THREE.Mesh; def: (typeof HERO_3D_PATHS)[number] };
    const tubes: TubeEntry[] = [];
    for (const def of HERO_3D_PATHS) {
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(),
      ]);
      const geo = new THREE.TubeGeometry(curve, 48, def.width * 0.012, 8, false);
      const mesh = new THREE.Mesh(geo, tubeMat.clone());
      mesh.renderOrder = -2;
      tendrilGroup.add(mesh);
      tubes.push({ mesh, def });
    }

    const pinkTex = radialCanvas("rgba(255,30,110,0.75)", "rgba(180,15,65,0.14)");
    const purpleTex = radialCanvas("rgba(100,40,240,0.32)", "rgba(40,10,100,0.04)");
    const glowDisc = (tex: THREE.Texture, radius: number, y: number) => {
      const m = new THREE.Mesh(
        new THREE.CircleGeometry(radius, 72),
        new THREE.MeshBasicMaterial({
          map: tex, transparent: true, blending: THREE.AdditiveBlending,
          depthWrite: false, depthTest: false, side: THREE.DoubleSide,
        })
      );
      m.rotation.x = -Math.PI / 2;
      m.position.y = y;
      m.renderOrder = -4;
      return m;
    };
    const glow1 = glowDisc(pinkTex, 3.8, -0.72);
    const glow2 = glowDisc(purpleTex, 6.2, -0.7);
    floorGroup.add(glow1, glow2);

    const hemi = new THREE.HemisphereLight(0x4422aa, 0xff2266, 0.18);
    scene.add(hemi);
    const ambient = new THREE.AmbientLight(0x1a1428, 0.35);
    scene.add(ambient);

    const spot = new THREE.SpotLight(0xfff0e0, 8, 12, Math.PI / 5.5, 0.55, 1.2);
    spot.position.set(0.5, 5, 3);
    spot.target.position.set(0, 0.5, 0);
    scene.add(spot, spot.target);

    const dirIntensities = [3.2, 4.2, 2.0, 0.9, 1.2];
    const dirLights: THREE.DirectionalLight[] = [];
    [
      [0xff2233, 3.2, [1, 4, -3]],
      [0x7733ff, 4.2, [-4, 3.5, 2]],
      [0xff5522, 2.0, [4, 0.5, 2]],
      [0xddddff, 0.9, [0, 1, 5]],
      [0x3355ff, 1.2, [-1.5, 2, -5]],
    ].forEach(([color, intensity, pos], i) => {
      const l = new THREE.DirectionalLight(color as number, intensity as number);
      l.position.set(...(pos as [number, number, number]));
      scene.add(l);
      dirLights.push(l);
      dirIntensities[i] = intensity as number;
    });
    const pinkLight = new THREE.PointLight(0xff0066, 14, 14);
    pinkLight.position.set(0, -1.5, 2.2);
    scene.add(pinkLight);

    const faceKey = new THREE.DirectionalLight(0xf0f4ff, 0);
    faceKey.position.set(0.2, 1.2, 5);
    scene.add(faceKey);
    const faceFill = new THREE.DirectionalLight(0x5ecfb8, 0);
    faceFill.position.set(-3, 0.5, 4);
    scene.add(faceFill);
    const faceRim = new THREE.PointLight(0x88ddff, 0, 12);
    faceRim.position.set(1.5, 0.8, 2.5);
    scene.add(faceRim);

    const projectAnchors = (): Partial<Record<RobotSocket, ScreenAnchor>> => {
      const rect = container.getBoundingClientRect();
      const out: Partial<Record<RobotSocket, ScreenAnchor>> = {};
      const v = new THREE.Vector3();
      for (const socket of SOCKETS) {
        anchorEmpties[socket].getWorldPosition(v);
        v.project(camera);
        const x = rect.left + (v.x * 0.5 + 0.5) * rect.width;
        const y = rect.top + (-v.y * 0.5 + 0.5) * rect.height;
        out[socket] = {
          x, y,
          visible: v.z < 1 && x >= rect.left - 40 && x <= rect.right + 40 &&
            y >= rect.top - 80 && y <= rect.bottom + 80,
        };
      }
      return out;
    };

    const screenToWorld = (sx: number, sy: number, dist = 6): THREE.Vector3 => {
      const rect = container.getBoundingClientRect();
      const nx = ((sx - rect.left) / rect.width) * 2 - 1;
      const ny = -((sy - rect.top) / rect.height) * 2 + 1;
      const v = new THREE.Vector3(nx, ny, 0.5);
      v.unproject(camera);
      const dir = v.sub(camera.position).normalize();
      return camera.position.clone().add(dir.multiplyScalar(dist));
    };

    const onMouseMove = (e: MouseEvent) => {
      mouse.current = {
        x: (e.clientX / window.innerWidth - 0.5) * 2,
        y: -(e.clientY / window.innerHeight - 0.5) * 2,
      };
    };
    window.addEventListener("mousemove", onMouseMove);

    const onResize = () => {
      const { w, h } = getSize();
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);
    onResize();

    const resizeObserver = new ResizeObserver(() => onResize());
    resizeObserver.observe(container);
    const rail = container.closest(".dashboard-face-bg");
    if (rail) resizeObserver.observe(rail);

    const eyeBaseL = new THREE.Vector3(-0.27, 0.02, 0.41);
    const eyeBaseR = new THREE.Vector3(0.27, 0.02, 0.41);
    let headY = 0, headX = 0;
    let guideLookY = 0, guideLookX = 0;
    let bodyGuideX = 0, bodyGuideY = 0;
    let aliveX = 0, aliveY = 0;
    let eyeOffX = 0, eyeOffY = 0;
    const clock = new THREE.Clock();
    const baseCamZ = 6.4;
    const HEAD_LOCAL_Y = 1.3;
    const savedBodyMetal = bodyMat.metalness;
    const savedBodyRough = bodyMat.roughness;

    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      const t = reducedMotion ? 0 : clock.getElapsedTime();

      if (variant === "face") {
        const { w: fw, h: fh } = getSize();
        const aspect = fw / Math.max(fh, 1);
        const headCenterY = 0.28;
        const camZ = aspect > 1.05 ? 2.72 : 2.52;

        bodyMesh.visible = false;
        headMesh.visible = true;
        screen.visible = true;
        neckCone.visible = false;
        neckJoint.visible = false;
        floorGroup.visible = false;
        tendrilGroup.visible = false;
        depthField.group.visible = false;
        glow1.visible = false;
        glow2.visible = false;

        scrollRig.position.set(0, 0, 0);
        scrollRig.rotation.set(0, 0, 0);
        scrollRig.scale.setScalar(1);
        scrollRig.visible = true;

        robot.position.y = -HEAD_LOCAL_Y + headCenterY + (reducedMotion ? 0 : Math.sin(t * 0.45) * 0.01);
        robot.rotation.y = 0;

        bodyMat.metalness = 0.35;
        bodyMat.roughness = 0.42;
        bodyMat.color.setHex(0x182030);
        bodyMat.emissive.setHex(0x243850);
        bodyMat.emissiveIntensity = 0.35;
        screenMat.metalness = 0.4;
        screenMat.roughness = 0.25;
        screenMat.color.setHex(0x060a12);
        screenMat.emissive.setHex(0x0c1828);
        screenMat.emissiveIntensity = 0.12;

        hemi.intensity = 0.22;
        ambient.intensity = 0.55;
        ambient.color.setHex(0x1a2838);
        for (const [i, l] of dirLights.entries()) {
          l.intensity = 0;
        }

        headY += (Math.max(-0.35, Math.min(0.35, mouse.current.x * 0.42)) - headY) * 0.08;
        headX += (Math.max(-0.18, Math.min(0.18, mouse.current.y * 0.26)) - headX) * 0.08;
        const tEyeX = Math.max(-0.12, Math.min(0.12, mouse.current.x * 0.12));
        const tEyeY = Math.max(-0.06, Math.min(0.06, mouse.current.y * 0.08));
        eyeOffX += (tEyeX - eyeOffX) * 0.14;
        eyeOffY += (tEyeY - eyeOffY) * 0.14;
        headGroup.rotation.y = headY;
        headGroup.rotation.x = headX;
        eyeL.position.set(eyeBaseL.x + eyeOffX, eyeBaseL.y + eyeOffY, eyeBaseL.z + eyeOffY * 0.15);
        eyeR.position.set(eyeBaseR.x + eyeOffX, eyeBaseR.y + eyeOffY, eyeBaseR.z + eyeOffY * 0.15);

        eyeMat.emissiveIntensity = 1.45 + Math.sin(t * 1.6) * 0.1;
        pinkLight.intensity = 2.5;
        pinkLight.position.set(0, headCenterY - 0.9, 2.8);
        spot.intensity = 1.8;
        spot.target.position.set(0, headCenterY, 0);
        faceKey.intensity = 2.2;
        faceFill.intensity = 1.4;
        faceRim.intensity = 3.2;
        renderer.toneMappingExposure = 1.65;

        camera.position.set(0, headCenterY + 0.14, camZ);
        camera.lookAt(0, headCenterY - 0.04, 0);
        camera.fov = aspect > 1.1 ? 27 : 31;
        camera.updateProjectionMatrix();

        scene.fog = null;
        container.style.opacity = "1";

        if (flow) {
          const rect = container.getBoundingClientRect();
          flow.hubXRef.current = rect.left + rect.width * 0.5;
        }

        renderer.render(scene, camera);
        return;
      }

      bodyMesh.visible = true;
      headMesh.visible = true;
      screen.visible = true;
      neckCone.visible = true;
      bodyMat.metalness = savedBodyMetal;
      bodyMat.roughness = savedBodyRough;
      bodyMat.color.setHex(0x0a0814);
      bodyMat.emissive.setHex(0x000000);
      bodyMat.emissiveIntensity = 0;
      screenMat.metalness = 0.65;
      screenMat.roughness = 0.04;
      screenMat.color.setHex(0x040206);
      screenMat.emissive.setHex(0x000000);
      screenMat.emissiveIntensity = 0;
      hemi.intensity = 0.18;
      ambient.intensity = 0.35;
      ambient.color.setHex(0x1a1428);
      for (const [i, l] of dirLights.entries()) {
        l.intensity = dirIntensities[i] ?? 1;
      }
      faceKey.intensity = 0;
      faceFill.intensity = 0;
      faceRim.intensity = 0;
      pinkLight.intensity = 14;
      pinkLight.position.set(0, -1.5, 2.2);
      spot.intensity = 8;
      spot.target.position.set(0, 0.5, 0);
      renderer.toneMappingExposure = 1.55;
      if (!scene.fog) {
        scene.fog = new THREE.FogExp2(0x000000, 0.055);
      }

      const progress = flow?.progressRef.current ?? 0;
      const heroScrub = flow?.heroScrubRef.current ?? 0;
      const director = flow?.directorRef.current ?? resolveDirector(progress);
      const phase = flow?.phaseRef.current ?? "hero";
      const corridorBlend = flow?.corridorBlendRef.current ?? 0;
      const visualPreset = flow?.visualPresetRef.current ?? "hero";
      const finale = flow?.finaleRef?.current ?? 0;
      const isCleanRobot =
        (visualPreset === "guide" || visualPreset === "splash") && finale < 0.22;
      const isSplash = visualPreset === "splash";
      const isGuideBg = phase === "guide" || phase === "corridor";
      const heroRig = applyHeroScrollRig(heroScrub, reducedMotion);
      const guideRig = applyGuideScrollRig(corridorBlend);
      let rig = heroRig;
      if (phase === "guide" || phase === "corridor") {
        if (finale > 0.02) {
          const finaleRig = applyFinaleScrollRig(finale);
          rig = blendScrollRigs(guideRig, finaleRig, easeInOutGuide(finale));
        } else {
          rig = guideRig;
        }
      }

      const trackPanels = phase === "hero" && heroScrub >= 0.92;
      const lookTarget = trackPanels ? getActiveLookAtTarget() : null;

      let finalX = rig.posX;
      let finalY = rig.posY;
      if (lookTarget) {
        const shift = guideBodyOffset(lookTarget, lookTarget.strength);
        const bodyLerp = phase === "guide" ? 0.085 : 0.06;
        bodyGuideX += (shift.x - bodyGuideX) * bodyLerp;
        bodyGuideY += (shift.y - bodyGuideY) * bodyLerp;
        finalX += bodyGuideX;
        finalY += bodyGuideY;
      } else {
        bodyGuideX *= 0.94;
        bodyGuideY *= 0.94;
      }

      const drift = scrollAliveDrift(progress, phase, t, reducedMotion);
      const aliveLerp = phase === "guide" ? 0.055 : 0.04;
      if (phase !== "hero") {
        aliveX += (drift.x - aliveX) * aliveLerp;
        aliveY += (drift.y - aliveY) * aliveLerp;
        finalX += aliveX;
        finalY += aliveY;
      } else {
        aliveX *= 0.9;
        aliveY *= 0.9;
      }

      scrollRig.position.set(finalX, finalY, rig.posZ);
      const bodyTilt =
        phase === "guide" || phase === "corridor"
          ? 0
          : bodyGuideX * 0.15 + (phase !== "hero" ? aliveX * 0.22 : 0);
      scrollRig.rotation.y = rig.rotY + bodyTilt;
      scrollRig.rotation.x = rig.rotX;
      floorGroup.rotation.y = -bodyTilt;
      floorGroup.rotation.x = -rig.rotX;
      const guideBaseScale =
        phase === "guide" ? 0.94 - corridorBlend * 0.12 :
        phase === "corridor" ? 0.82 - corridorBlend * 0.14 :
        1;
      const guideScale =
        finale > 0.02
          ? guideBaseScale + (1 - guideBaseScale) * easeInOutGuide(finale)
          : guideBaseScale;
      scrollRig.scale.setScalar(rig.scale * guideScale);

      const bodyOp = robotBodyOpacity(phase, corridorBlend);
      const visibilityBoost = isSplash ? 1 : isCleanRobot ? 1 : 1;
      const alphaMul = rig.robotAlpha;
      scrollRig.visible = bodyOp > 0.03 && alphaMul > 0.04;
      const guideFloor = 0.38 + finale * 0.1;
      const floor = phase === "guide" || phase === "corridor" ? guideFloor : 0.12;
      container.style.opacity = String(
        Math.min(phase === "guide" || phase === "corridor" ? 0.92 : 0.85, Math.max(floor, bodyOp * visibilityBoost * alphaMul))
      );

      if (lookTarget) {
        const world = screenToWorld(lookTarget.x, lookTarget.y);
        headGroup.updateWorldMatrix(true, false);
        const headWorld = new THREE.Vector3();
        headGroup.getWorldPosition(headWorld);
        const dx = world.x - headWorld.x;
        const dy = world.y - headWorld.y;
        const dz = world.z - headWorld.z;
        const targetY = Math.atan2(dx, dz);
        const targetX = Math.atan2(-dy, Math.hypot(dx, dz));
        const headLerp = phase === "guide" ? 0.095 : 0.07;
        guideLookY += (Math.max(-0.75, Math.min(0.75, targetY)) - guideLookY) * headLerp;
        guideLookX += (Math.max(-0.38, Math.min(0.38, targetX)) - guideLookX) * headLerp;
        headY = guideLookY;
        headX = guideLookX;

        const local = headGroup.worldToLocal(world.clone());
        const tEyeX = Math.max(-0.14, Math.min(0.14, local.x * 0.22));
        const tEyeY = Math.max(-0.07, Math.min(0.07, local.y * 0.18));
        const eyeLerp = phase === "guide" ? 0.15 : 0.12;
        eyeOffX += (tEyeX - eyeOffX) * eyeLerp;
        eyeOffY += (tEyeY - eyeOffY) * eyeLerp;
      } else if (phase === "hero" && heroScrub < 0.92) {
        headY += (Math.max(-0.4, Math.min(0.4, mouse.current.x * 0.55)) - headY) * 0.06;
        headX += (Math.max(-0.22, Math.min(0.22, mouse.current.y * 0.35)) - headX) * 0.06;
        eyeOffX *= 0.9;
        eyeOffY *= 0.9;
      } else if (phase === "guide" || phase === "corridor") {
        headY *= 0.88;
        headX *= 0.88;
        guideLookY *= 0.88;
        guideLookX *= 0.88;
        eyeOffX *= 0.85;
        eyeOffY *= 0.85;
      } else {
        headY *= 0.96;
        headX *= 0.96;
        eyeOffX *= 0.9;
        eyeOffY *= 0.9;
      }

      headGroup.rotation.y = headY;
      headGroup.rotation.x = headX;
      eyeL.position.set(eyeBaseL.x + eyeOffX, eyeBaseL.y + eyeOffY, eyeBaseL.z + eyeOffY * 0.15);
      eyeR.position.set(eyeBaseR.x + eyeOffX, eyeBaseR.y + eyeOffY, eyeBaseR.z + eyeOffY * 0.15);

      if (phase === "hero" && heroScrub < 0.08) {
        robot.position.y = reducedMotion ? 0 : Math.sin(t * 0.7) * 0.03;
      } else {
        robot.position.y = 0;
      }
      const microSway =
        phase === "hero" && heroScrub >= 0.85
          ? Math.sin(t * 0.55) * 0.012
          : 0;
      robot.rotation.y =
        phase === "hero" && heroScrub < 0.08
          ? (reducedMotion ? 0 : Math.sin(t * 0.35) * 0.015) + mouse.current.x * 0.02
          : microSway;

      eyeMat.emissiveIntensity = rig.eyeIntensity + (lookTarget ? 0.15 : Math.sin(t * 2.2) * 0.12);
      const glowWide = isCleanRobot && !isGuideBg ? 0 : phase === "guide" || phase === "corridor" ? 1.05 : 1;
      glow1.visible = (!isCleanRobot || isGuideBg) && rig.floorGlow > 0.06;
      glow2.visible = (!isCleanRobot || isGuideBg) && rig.floorGlow > 0.06;
      glow1.scale.setScalar(rig.glowScale * 1.1 * glowWide);
      glow2.scale.setScalar(rig.glowScale * 1.35 * glowWide);
      const g1 = glow1.material as THREE.MeshBasicMaterial;
      const g2 = glow2.material as THREE.MeshBasicMaterial;
      g1.opacity = 0.82 * rig.floorGlow;
      g2.opacity = 0.68 * rig.floorGlow;
      pinkLight.intensity = (isCleanRobot ? 2 : 10 + rig.portalFlash * 8) * rig.floorGlow;

      const inHeroCamera = phase === "hero" && heroScrub < 0.995;
      if (inHeroCamera) {
        camera.position.set(0, 0.5, baseCamZ - progress * 0.18);
        camera.lookAt(0, 0.5, 0);
        camera.fov = 34;
        camera.updateProjectionMatrix();
      } else {
        const camPose = sampleCameraSpline(director.progress, director.chapter, director.chapterT);
        applyCameraPose(camera, camPose, 0.1);
      }

      if (scene.fog instanceof THREE.FogExp2) {
        scene.fog.density = isCleanRobot ? 0.028 : 0.045 + progress * 0.012;
      }

      depthField.update(
        heroScrub,
        progress,
        t,
        reducedMotion,
        isCleanRobot ? 0 : phase === "guide" ? 0.55 : phase === "corridor" ? 0.4 : 1
      );
      depthField.group.visible = !isCleanRobot;

      const showTubes = false;
      const tubeOpacity = 0;
      tendrilGroup.visible = false;

      for (const { mesh, def } of tubes) {
        if (tubeOpacity < 0.04) continue;
        const pts = resolvePath3D(def, Math.max(progress, heroScrub * 0.3), t, rig.formation);
        const curve = new THREE.CatmullRomCurve3(pts);
        mesh.geometry.dispose();
        mesh.geometry = new THREE.TubeGeometry(curve, 48, def.width * 0.012, 8, false);
        (mesh.material as THREE.MeshPhysicalMaterial).opacity =
          tubeOpacity * (def.tier === "wisp" ? 0.55 : 0.72);
      }

      if (flow) {
        const anchors = projectAnchors();
        flow.anchorsRef.current = anchors;
        const base = anchors.base;
        const crown = anchors.crown;
        const cx =
          base?.visible ? base.x :
          crown?.visible ? crown.x :
          container.getBoundingClientRect().left + container.clientWidth * 0.5;
        flow.hubXRef.current = cx;
      }

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize", onResize);
      resizeObserver.disconnect();
      depthField.dispose();
      for (const { mesh } of tubes) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      pinkTex.dispose();
      purpleTex.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [flow, variant]);

  return (
    <div
      ref={mountRef}
      style={{ width: "100%", height, display: "block", pointerEvents: "none", overflow: "visible" }}
    />
  );
}
