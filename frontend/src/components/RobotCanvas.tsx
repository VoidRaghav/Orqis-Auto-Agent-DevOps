"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  /** "panel" = right-side column; "bg" = full-screen background layer */
  mode?: "panel" | "bg";
}

export default function RobotCanvas({ mode = "panel" }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (!mountRef.current) return;

    const container = mountRef.current;
    const width  = container.clientWidth;
    const height = container.clientHeight;

    const scene  = new THREE.Scene();

    // Slight fog adds depth in bg mode
    if (mode === "bg") {
      scene.fog = new THREE.FogExp2(0x000000, 0.06);
    }

    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 120);
    camera.position.set(mode === "bg" ? 2 : 0, 0, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    // ── Robot head (icosahedron) ──────────────────────────────
    const headGeo = new THREE.IcosahedronGeometry(1, 1);
    const headMat = new THREE.MeshStandardMaterial({
      color: 0x0a0a0a,
      metalness: 0.92,
      roughness: 0.12,
      emissive: 0x001408,
      emissiveIntensity: 0.5,
    });
    const head = new THREE.Mesh(headGeo, headMat);
    // In bg mode shift the robot right so text can live on the left
    head.position.x = mode === "bg" ? 1.5 : 0;
    scene.add(head);

    // Wireframe overlay
    const wireGeo = new THREE.IcosahedronGeometry(1.01, 1);
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88,
      wireframe: true,
      transparent: true,
      opacity: mode === "bg" ? 0.05 : 0.08,
    });
    head.add(new THREE.Mesh(wireGeo, wireMat));

    // ── Eyes ──────────────────────────────────────────────────
    const eyeGeo = new THREE.SphereGeometry(0.12, 16, 16);
    const eyeMat = new THREE.MeshStandardMaterial({
      color: 0x00ff88,
      emissive: 0x00ff88,
      emissiveIntensity: 2.5,
    });
    const leftEye = new THREE.Mesh(eyeGeo, eyeMat);
    leftEye.position.set(-0.28, 0.12, 0.88);
    head.add(leftEye);

    const rightEye = new THREE.Mesh(eyeGeo, eyeMat);
    rightEye.position.set(0.28, 0.12, 0.88);
    head.add(rightEye);

    // Eye glow halos
    const eyeGlowGeo = new THREE.SphereGeometry(0.24, 8, 8);
    const eyeGlowMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88, transparent: true, opacity: 0.07,
    });
    const leftGlow = new THREE.Mesh(eyeGlowGeo, eyeGlowMat);
    leftGlow.position.copy(leftEye.position);
    head.add(leftGlow);
    const rightGlow = new THREE.Mesh(eyeGlowGeo, eyeGlowMat);
    rightGlow.position.copy(rightEye.position);
    head.add(rightGlow);

    // ── Orbiting rings ────────────────────────────────────────
    const makeRing = (r: number, tube: number, color: number, opacity: number, rx: number, rz: number) => {
      const mesh = new THREE.Mesh(
        new THREE.TorusGeometry(r, tube, 16, 120),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity })
      );
      mesh.rotation.x = rx;
      mesh.rotation.z = rz;
      return mesh;
    };

    const ring1 = makeRing(1.65, 0.018, 0xffffff, 0.15, Math.PI / 2.5, 0);
    const ring2 = makeRing(2.15, 0.011, 0x4d94ff, 0.28, Math.PI / 3, Math.PI / 6);
    const ring3 = makeRing(2.7,  0.007, 0x00ff88, 0.12, Math.PI / 1.8, Math.PI / 4);
    scene.add(ring1, ring2, ring3);

    // Orbiting dots
    const makeDot = (r: number, color: number) => {
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(r, 8, 8),
        new THREE.MeshBasicMaterial({ color })
      );
      scene.add(m);
      return m;
    };
    const dot1 = makeDot(0.06, 0x00ff88);
    const dot2 = makeDot(0.04, 0x4d94ff);
    const dot3 = makeDot(0.03, 0xffffff);

    // ── Particles ─────────────────────────────────────────────
    const particleCount = mode === "bg" ? 320 : 180;
    const positions     = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      const r     = (mode === "bg" ? 3.5 : 2.5) + Math.random() * 2.5;
      positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta) + (mode === "bg" ? 1.5 : 0);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }

    const particleGeo = new THREE.BufferGeometry();
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const particleMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: mode === "bg" ? 0.028 : 0.035,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // ── Data stream lines (bg only) ───────────────────────────
    const streamMeshes: THREE.Line[] = [];
    if (mode === "bg") {
      for (let s = 0; s < 6; s++) {
        const points: THREE.Vector3[] = [];
        const startX = -8 + Math.random() * 16;
        const startY = -4 + Math.random() * 8;
        for (let p = 0; p < 12; p++) {
          points.push(new THREE.Vector3(startX + p * 0.6, startY + (Math.random() - 0.5) * 0.4, -3 + Math.random() * 2));
        }
        const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
        const lineMat = new THREE.LineBasicMaterial({
          color: 0x00ff88,
          transparent: true,
          opacity: 0.04 + Math.random() * 0.06,
        });
        const line = new THREE.Line(lineGeo, lineMat);
        scene.add(line);
        streamMeshes.push(line);
      }
    }

    // ── Lights ────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x050505, 2));

    const greenLight = new THREE.PointLight(0x00ff88, mode === "bg" ? 6 : 4, 10);
    greenLight.position.set(2, 2, 3);
    scene.add(greenLight);

    const blueLight = new THREE.PointLight(0x4d94ff, 2.5, 10);
    blueLight.position.set(-2, -1, 2);
    scene.add(blueLight);

    scene.add(new THREE.PointLight(0xffffff, 1, 6));

    // ── Mouse tracking ────────────────────────────────────────
    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current = {
        x: (e.clientX / window.innerWidth  - 0.5) * 2,
        y: -(e.clientY / window.innerHeight - 0.5) * 2,
      };
    };
    window.addEventListener("mousemove", handleMouseMove);

    const handleResize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // ── Animation loop ────────────────────────────────────────
    let rotX = 0, rotY = 0;
    const clock = new THREE.Clock();

    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Smooth mouse follow — subtle in bg mode
      const sensitivity = mode === "bg" ? 0.25 : 0.5;
      rotY += (mouseRef.current.x * sensitivity - rotY) * 0.05;
      rotX += (mouseRef.current.y * 0.3 - rotX) * 0.05;

      head.rotation.y = rotY;
      head.rotation.x = rotX;
      head.position.y = Math.sin(t * 0.7) * 0.06 + (mode === "bg" ? 0 : 0);

      ring1.rotation.y  = t * 0.38;
      ring2.rotation.z  = t * 0.22;
      ring3.rotation.x += 0.003;

      dot1.position.set(
        Math.cos(t * 0.8) * 1.65 + (mode === "bg" ? 1.5 : 0),
        Math.sin(t * 0.8) * Math.sin(ring1.rotation.x) * 1.65,
        Math.sin(t * 0.8) * Math.cos(ring1.rotation.x) * 1.65,
      );
      dot2.position.set(
        Math.cos(t * 0.5 + Math.PI) * 2.15 + (mode === "bg" ? 1.5 : 0),
        Math.sin(t * 0.5 + Math.PI) * 0.9,
        Math.sin(t * 0.5 + Math.PI) * 1.3,
      );
      dot3.position.set(
        Math.cos(t * 0.3 + 1) * 2.7 + (mode === "bg" ? 1.5 : 0),
        Math.sin(t * 0.3 + 1) * 1.2,
        Math.cos(t * 0.3 + 1) * 0.8,
      );

      particles.rotation.y = t * 0.04;
      particles.rotation.x = t * 0.015;

      eyeMat.emissiveIntensity = 2 + ((Math.sin(t * 2) + 1) / 2) * 1.8;

      greenLight.position.x = Math.sin(t * 0.5) * 3.5;
      greenLight.position.z = Math.cos(t * 0.5) * 3.5;

      // Animate data streams in bg mode
      streamMeshes.forEach((line, i) => {
        (line.material as THREE.LineBasicMaterial).opacity =
          0.03 + Math.abs(Math.sin(t * 0.4 + i)) * 0.07;
      });

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [mode]);

  return <div ref={mountRef} className="w-full h-full" />;
}
