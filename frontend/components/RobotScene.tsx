"use client";

/**
 * Cursor-following robot — Spline-style aesthetic in Three.js.
 *
 * Lighting strategy (matches Spline reference):
 *   - HemisphereLight: purple sky / pink floor → broad ambient gradient
 *   - DirectionalLights: colored key lights (no distance falloff)
 *     • Red key from back-top    → red top-edge highlight
 *     • Purple from top-left     → blue-purple left rim
 *     • Pink from below-front    → floor reflection on body base
 *     • Orange from right        → warm right-side accent
 *     • Soft purple front fill   → readable face
 *   - SpotLight from above       → focused stage spotlight effect
 *
 * Material: low metalness (plastic, not mirror) + high clearcoat for the
 * lacquered glossy look, with a brighter base color so it reads on black bg.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";

// Rounded box via ExtrudeGeometry with bevel
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
    depth:          d - r * 2,
    bevelEnabled:   true,
    bevelThickness: r,
    bevelSize:      r,
    bevelOffset:    0,
    bevelSegments:  segs,
  });
  geo.center();
  return geo;
}

// Radial gradient canvas → texture for floor glow
function radialCanvas(
  inner: string, mid: string, px = 512
): THREE.CanvasTexture {
  const cv  = document.createElement("canvas");
  cv.width  = px;
  cv.height = px;
  const ctx = cv.getContext("2d")!;
  const g   = ctx.createRadialGradient(px / 2, px / 2, 0, px / 2, px / 2, px / 2);
  g.addColorStop(0,    inner);
  g.addColorStop(0.55, mid);
  g.addColorStop(1,    "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, px, px);
  return new THREE.CanvasTexture(cv);
}

export default function RobotScene() {
  const mountRef = useRef<HTMLDivElement>(null);
  const mouse    = useRef({ x: 0, y: 0 });
  const rafRef   = useRef(0);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const getSize = () => ({
      w: container.clientWidth  || Math.round(window.innerWidth  * 0.58),
      h: container.clientHeight || window.innerHeight,
    });
    const { w: W, h: H } = getSize();

    // ── Renderer ──────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping         = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.4;
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    // ── Scene + camera ────────────────────────────────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, W / H, 0.1, 100);
    camera.position.set(0, 0.5, 6.4);
    camera.lookAt(0, 0.5, 0);

    // ── MATERIALS ─────────────────────────────────────────────
    // Body — metallic near-black with subtle indigo undertone.
    // Higher metalness means surface mostly reflects light source colors,
    // not its own color → appears black in shadow, lit colors on edges.
    const bodyMat = new THREE.MeshPhysicalMaterial({
      color:              0x0a0814,   // near-black with faint indigo
      metalness:          0.7,
      roughness:          0.22,
      clearcoat:          1.0,
      clearcoatRoughness: 0.06,
      reflectivity:       0.7,
    });

    // Screen panel — even darker, glass-like inset
    const screenMat = new THREE.MeshPhysicalMaterial({
      color:              0x040206,
      metalness:          0.65,
      roughness:          0.04,
      clearcoat:          1.0,
      clearcoatRoughness: 0.02,
      reflectivity:       1.0,
    });

    // Eye material — emissive white spheres
    const eyeMat = new THREE.MeshPhysicalMaterial({
      color:             0xeeeeee,
      emissive:          new THREE.Color(0xffffff),
      emissiveIntensity: 1.6,
      roughness:         0.05,
      metalness:         0.0,
      clearcoat:         1.0,
    });

    // ── ROBOT ─────────────────────────────────────────────────
    const robot = new THREE.Group();
    scene.add(robot);

    // Body cube
    const body = new THREE.Mesh(
      roundedBox(1.10, 1.10, 1.10, 0.09, 10),
      bodyMat
    );
    body.position.y = 0;
    robot.add(body);

    // Neck — tapered cone (wider at bottom, narrow at top)
    const neckCone = new THREE.Mesh(
      new THREE.CylinderGeometry(0.10, 0.24, 0.36, 32),
      bodyMat
    );
    neckCone.position.y = 0.71;
    robot.add(neckCone);

    // Sphere joint between cone and head
    const neckJoint = new THREE.Mesh(
      new THREE.SphereGeometry(0.13, 32, 32),
      bodyMat
    );
    neckJoint.position.y = 0.92;
    robot.add(neckJoint);

    // ── Head group (tracks cursor) ─────────────────────────────
    const headGroup = new THREE.Group();
    headGroup.position.y = 1.30;
    robot.add(headGroup);

    // Main head box — wide landscape rounded rectangle
    const head = new THREE.Mesh(
      roundedBox(1.50, 0.94, 0.70, 0.13, 10),
      bodyMat
    );
    headGroup.add(head);

    // Screen panel — inset darker face panel
    const screen = new THREE.Mesh(
      roundedBox(1.22, 0.68, 0.04, 0.08, 6),
      screenMat
    );
    screen.position.set(0, 0.02, 0.355);
    headGroup.add(screen);

    // Eyes
    const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.11, 32, 32), eyeMat);
    const eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.11, 32, 32), eyeMat);
    eyeL.position.set(-0.27, 0.02, 0.41);
    eyeR.position.set( 0.27, 0.02, 0.41);
    headGroup.add(eyeL, eyeR);

    // ── FLOOR GLOW ────────────────────────────────────────────
    const pinkTex   = radialCanvas("rgba(255,30,110,1.0)", "rgba(180,15,65,0.45)");
    const purpleTex = radialCanvas("rgba(100,40,240,0.5)", "rgba(40,10,100,0.12)");

    const glowPlane = (tex: THREE.Texture, size: number, y: number) => {
      const m = new THREE.Mesh(
        new THREE.PlaneGeometry(size, size),
        new THREE.MeshBasicMaterial({
          map: tex, transparent: true,
          blending:   THREE.AdditiveBlending,
          depthWrite: false,
          side:       THREE.DoubleSide,
        })
      );
      m.rotation.x = -Math.PI / 2;
      m.position.y = y;
      return m;
    };

    const glow1 = glowPlane(pinkTex,   4.3, -0.65);
    const glow2 = glowPlane(purpleTex, 7.5, -0.64);
    scene.add(glow1, glow2);

    // ── LIGHTING ──────────────────────────────────────────────
    // Strategy: metallic black body shows the color of any light hitting it.
    // Keep ambient/hemisphere LOW so unlit areas stay black; use strong
    // colored direct lights for rim highlights ONLY where they land.

    // Faint hemisphere — subtle color gradient, not enough to wash surfaces
    const hemi = new THREE.HemisphereLight(0x4422aa, 0xff2266, 0.18);
    scene.add(hemi);

    // Faint ambient — keeps detail in shadows but no overall purple tint
    scene.add(new THREE.AmbientLight(0x1a1428, 0.35));

    // Warm white spotlight from above-front — creates the red/orange top edge
    // when combined with the red key behind
    const spot = new THREE.SpotLight(0xfff0e0, 8, 12, Math.PI / 5.5, 0.55, 1.2);
    spot.position.set(0.5, 5, 3);
    spot.target.position.set(0, 0.5, 0);
    scene.add(spot);
    scene.add(spot.target);

    // Red back-top key → red top-edge highlight
    const redKey = new THREE.DirectionalLight(0xff2233, 3.2);
    redKey.position.set(1, 4, -3);
    scene.add(redKey);

    // Purple top-left key → purple-blue rim on left side & top-left edges
    const purpleKey = new THREE.DirectionalLight(0x7733ff, 4.2);
    purpleKey.position.set(-4, 3.5, 2);
    scene.add(purpleKey);

    // Pink magenta from below-front — strong floor reflection on body base
    const pinkLight = new THREE.PointLight(0xff0066, 14, 8);
    pinkLight.position.set(0, -1.5, 2.2);
    scene.add(pinkLight);

    // Warm orange from right side — warm side accent
    const warmRight = new THREE.DirectionalLight(0xff5522, 2.0);
    warmRight.position.set(4, 0.5, 2);
    scene.add(warmRight);

    // Cool soft white front fill — face visibility, no color tint
    const frontFill = new THREE.DirectionalLight(0xddddff, 0.9);
    frontFill.position.set(0, 1, 5);
    scene.add(frontFill);

    // Cool blue rim on back edges
    const blueBack = new THREE.DirectionalLight(0x3355ff, 1.2);
    blueBack.position.set(-1.5, 2, -5);
    scene.add(blueBack);

    // ── MOUSE / RESIZE ────────────────────────────────────────
    const onMouseMove = (e: MouseEvent) => {
      mouse.current = {
        x:  (e.clientX / window.innerWidth  - 0.5) * 2,
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

    // ── ANIMATION ─────────────────────────────────────────────
    let headY = 0, headX = 0;
    const clock = new THREE.Clock();

    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      const t = clock.getElapsedTime();

      // Head tracks cursor — clamped smooth lerp
      headY += (Math.max(-0.55, Math.min(0.55, mouse.current.x * 0.7))  - headY) * 0.07;
      headX += (Math.max(-0.28, Math.min(0.28, mouse.current.y * 0.4))  - headX) * 0.07;
      headGroup.rotation.y = headY;
      headGroup.rotation.x = headX;

      // Idle float
      robot.position.y = Math.sin(t * 0.7) * 0.05;

      // Body sway with mouse
      robot.rotation.y = Math.sin(t * 0.35) * 0.022 + mouse.current.x * 0.03;

      // Eye pulse
      eyeMat.emissiveIntensity = 1.5 + Math.sin(t * 2.2) * 0.35;

      // Floor glow breathes
      const gs = 1 + Math.sin(t * 0.8) * 0.04;
      glow1.scale.set(gs, gs, gs);

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize",    onResize);
      pinkTex.dispose();
      purpleTex.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{ width: "100%", height: "100vh", display: "block" }}
    />
  );
}
