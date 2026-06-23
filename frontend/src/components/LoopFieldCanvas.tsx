"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useRobotFlowOptional } from "@/components/RobotFlowContext";
import { resolveDirector } from "@/lib/scroll-director";
import { LoopFieldScene } from "@/scene/LoopFieldScene";
import { OrganicFluidPass } from "@/scene/OrganicFluidPass";
import { applyPostFxUniforms, createBloomQuad } from "@/scene/postfx";
import { detectDeviceTier, tierConfig } from "@/lib/device-tier";

export default function LoopFieldCanvas() {
  const mountRef = useRef<HTMLDivElement>(null);
  const flow = useRobotFlowOptional();

  useEffect(() => {
    const container = mountRef.current;
    if (!container || !flow) return;

    const tier = detectDeviceTier();
    const cfg = tierConfig(tier);
    flow.deviceTierRef.current = tier;

    if (tier === "low") {
      container.classList.add("loop-field-canvas--low");
      return;
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const W = window.innerWidth;
    const H = window.innerHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, cfg.pixelRatio));
    renderer.setClearColor(0x050a08, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    const fluid = new OrganicFluidPass(cfg.fluidSim && !reducedMotion);
    scene.add(fluid.mesh);

    const loopField = new LoopFieldScene({ nodeCount: cfg.loopNodes });
    const loopCam = new THREE.PerspectiveCamera(42, W / H, 0.1, 50);
    loopCam.position.set(0, 0, 4.5);
    const loopScene = new THREE.Scene();
    loopScene.add(loopField.group);

    const loopRt = new THREE.WebGLRenderTarget(W, H, { depthBuffer: true });
    const loopMat = new THREE.MeshBasicMaterial({ map: loopRt.texture, transparent: true, opacity: 0.85 });
    const loopQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), loopMat);
    loopQuad.position.z = -0.01;
    scene.add(loopQuad);

    const bloom = cfg.postFx ? createBloomQuad() : null;
    if (bloom) scene.add(bloom);

    const clock = new THREE.Clock();
    let raf = 0;

    const onResize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setSize(w, h);
      fluid.setSize(w, h);
      loopCam.aspect = w / h;
      loopCam.updateProjectionMatrix();
      loopRt.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    const tick = () => {
      raf = requestAnimationFrame(tick);
      const progress = flow.progressRef.current ?? 0;
      const director = flow.directorRef.current ?? resolveDirector(progress);
      flow.directorRef.current = director;

      const t = reducedMotion ? 0 : clock.getElapsedTime();
      fluid.applyUniforms(director.fluidUniforms, t);
      loopField.update(director, t);

      loopCam.position.x = -0.4 + director.loopFracture * 0.3;
      loopCam.lookAt(-0.5, 0, 0);

      renderer.setRenderTarget(loopRt);
      renderer.clear();
      renderer.render(loopScene, loopCam);
      renderer.setRenderTarget(null);

      loopMat.opacity = 0.35 + director.loopIntensity * 0.55;

      if (bloom) {
        applyPostFxUniforms(bloom, {
          bloom: director.bloomIntensity,
          chromatic: director.chromaticAberration,
          vignette: 0.4,
        });
      }

      renderer.render(scene, camera);

      const chroma = director.chromaticAberration;
      container.style.filter =
        chroma > 0.02 ? `saturate(1.08) brightness(1.02)` : "none";
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      fluid.dispose();
      loopField.dispose();
      loopRt.dispose();
      loopMat.dispose();
      loopQuad.geometry.dispose();
      if (bloom) {
        bloom.geometry.dispose();
        (bloom.material as THREE.Material).dispose();
      }
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [flow]);

  return <div ref={mountRef} className="loop-field-canvas" aria-hidden />;
}
