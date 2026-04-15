"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function RobotCanvas() {
  const mountRef = useRef<HTMLDivElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (!mountRef.current) return;

    const container = mountRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100);
    camera.position.set(0, 0, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    // ── Robot head (icosahedron) ──
    const headGeo = new THREE.IcosahedronGeometry(1, 1);
    const headMat = new THREE.MeshStandardMaterial({
      color: 0x0a0a0a,
      metalness: 0.9,
      roughness: 0.15,
      emissive: 0x001a0a,
      emissiveIntensity: 0.4,
    });
    const head = new THREE.Mesh(headGeo, headMat);
    scene.add(head);

    // Wireframe overlay — white at low opacity
    const wireGeo = new THREE.IcosahedronGeometry(1.01, 1);
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      wireframe: true,
      transparent: true,
      opacity: 0.08,
    });
    const wireframe = new THREE.Mesh(wireGeo, wireMat);
    head.add(wireframe);

    // ── Eyes (green) ──
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

    // Eye glow
    const eyeGlowGeo = new THREE.SphereGeometry(0.22, 8, 8);
    const eyeGlowMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88,
      transparent: true,
      opacity: 0.08,
    });
    const leftGlow = new THREE.Mesh(eyeGlowGeo, eyeGlowMat);
    leftGlow.position.copy(leftEye.position);
    head.add(leftGlow);
    const rightGlow = new THREE.Mesh(eyeGlowGeo, eyeGlowMat);
    rightGlow.position.copy(rightEye.position);
    head.add(rightGlow);

    // ── Orbiting rings — white/blue ──
    const ringGeo = new THREE.TorusGeometry(1.6, 0.02, 16, 100);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.18,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 2.5;
    scene.add(ring);

    const ring2Geo = new THREE.TorusGeometry(2.1, 0.012, 16, 100);
    const ring2Mat = new THREE.MeshBasicMaterial({
      color: 0x4d94ff,
      transparent: true,
      opacity: 0.3,
    });
    const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2.rotation.x = Math.PI / 3;
    ring2.rotation.z = Math.PI / 6;
    scene.add(ring2);

    // Orbiting dot (green)
    const dotGeo = new THREE.SphereGeometry(0.06, 8, 8);
    const dotMat = new THREE.MeshBasicMaterial({ color: 0x00ff88 });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    scene.add(dot);

    // Orbiting dot 2 (blue)
    const dot2Geo = new THREE.SphereGeometry(0.04, 8, 8);
    const dot2Mat = new THREE.MeshBasicMaterial({ color: 0x4d94ff });
    const dot2 = new THREE.Mesh(dot2Geo, dot2Mat);
    scene.add(dot2);

    // ── Particles — white ──
    const particleCount = 180;
    const positions = new Float32Array(particleCount * 3);
    const particleSizes = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 2.5 + Math.random() * 1.8;
      positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      particleSizes[i] = Math.random() * 2 + 0.5;
    }

    const particleGeo = new THREE.BufferGeometry();
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute("size", new THREE.BufferAttribute(particleSizes, 1));

    const particleMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.035,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });

    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // ── Lights ──
    scene.add(new THREE.AmbientLight(0x050505, 2));

    const greenLight = new THREE.PointLight(0x00ff88, 4, 8);
    greenLight.position.set(2, 2, 3);
    scene.add(greenLight);

    const blueLight = new THREE.PointLight(0x4d94ff, 2, 8);
    blueLight.position.set(-2, -1, 2);
    scene.add(blueLight);

    const whiteLight = new THREE.PointLight(0xffffff, 1, 6);
    whiteLight.position.set(0, 3, 3);
    scene.add(whiteLight);

    // Mouse tracking
    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouseRef.current = {
        x: ((e.clientX - rect.left) / width - 0.5) * 2,
        y: -((e.clientY - rect.top) / height - 0.5) * 2,
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

    // Animation loop
    let currentRotX = 0;
    let currentRotY = 0;
    const clock = new THREE.Clock();

    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth cursor tracking
      currentRotY += (mouseRef.current.x * 0.5 - currentRotY) * 0.06;
      currentRotX += (mouseRef.current.y * 0.3 - currentRotX) * 0.06;

      head.rotation.y = currentRotY;
      head.rotation.x = currentRotX;
      head.position.y = Math.sin(elapsed * 0.8) * 0.05;

      ring.rotation.y  = elapsed * 0.4;
      ring2.rotation.z = elapsed * 0.25;

      dot.position.set(
        Math.cos(elapsed * 0.8) * 1.6,
        Math.sin(elapsed * 0.8) * Math.sin(ring.rotation.x) * 1.6,
        Math.sin(elapsed * 0.8) * Math.cos(ring.rotation.x) * 1.6
      );

      dot2.position.set(
        Math.cos(elapsed * 0.5 + Math.PI) * 2.1,
        Math.sin(elapsed * 0.5 + Math.PI) * 0.8,
        Math.sin(elapsed * 0.5 + Math.PI) * 1.2
      );

      particles.rotation.y = elapsed * 0.05;
      particles.rotation.x = elapsed * 0.02;

      // Eye pulse
      eyeMat.emissiveIntensity = 2 + ((Math.sin(elapsed * 2) + 1) / 2) * 1.5;

      // Light orbit
      greenLight.position.x = Math.sin(elapsed * 0.5) * 3;
      greenLight.position.z = Math.cos(elapsed * 0.5) * 3;

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
  }, []);

  return (
    <div ref={mountRef} className="w-full h-full" style={{ minHeight: "460px" }} />
  );
}
