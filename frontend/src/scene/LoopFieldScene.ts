/** Instanced spiral loop graph — scroll-driven topology. */

import * as THREE from "three";
import type { DirectorState } from "@/lib/scroll-director";

export type LoopFieldOptions = {
  nodeCount: number;
};

export class LoopFieldScene {
  readonly group = new THREE.Group();
  private nodes: THREE.InstancedMesh;
  private spiral: THREE.Line;
  private spiralGeo: THREE.BufferGeometry;
  private dummy = new THREE.Object3D();
  private nodeMat: THREE.MeshPhysicalMaterial;
  private spiralMat: THREE.LineBasicMaterial;
  private readonly count: number;

  constructor(opts: LoopFieldOptions) {
    this.count = opts.nodeCount;
    const nodeGeo = new THREE.SphereGeometry(0.055, 10, 10);
    this.nodeMat = new THREE.MeshPhysicalMaterial({
      color: 0x3ddc97,
      emissive: new THREE.Color(0x2a9d6a),
      emissiveIntensity: 0.8,
      metalness: 0.4,
      roughness: 0.25,
      transparent: true,
      opacity: 0.85,
    });
    this.nodes = new THREE.InstancedMesh(nodeGeo, this.nodeMat, this.count);
    this.nodes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    this.spiralGeo = new THREE.BufferGeometry();
    this.spiralMat = new THREE.LineBasicMaterial({
      color: 0x5ecfb8,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending,
    });
    this.spiral = new THREE.Line(this.spiralGeo, this.spiralMat);

    this.group.add(this.nodes);
    this.group.add(this.spiral);
    this.group.position.set(-0.8, -0.15, -1.2);
  }

  private spiralPoint(i: number, total: number, spin: number, fracture: number): THREE.Vector3 {
    const t = i / total;
    const turns = 3.2 + spin * 0.8;
    const angle = t * Math.PI * 2 * turns + spin * 0.4;
    const radius = 0.35 + t * 1.8 + Math.sin(t * 12 + spin) * 0.12;
    const y = (t - 0.5) * 2.4 + Math.cos(t * 8) * 0.15;
    const fractureOff = fracture > 0.01 ? Math.sin(i * 2.1 + spin * 3) * fracture * 0.35 : 0;
    return new THREE.Vector3(
      Math.cos(angle) * radius + fractureOff,
      y,
      Math.sin(angle) * radius * 0.55
    );
  }

  update(director: DirectorState, time: number) {
    const { loopIntensity, loopSpin, loopFracture, fluidUniforms } = director;
    const heat = fluidUniforms.heat;
    const crystallize = fluidUniforms.crystallize;

    const positions: number[] = [];
    for (let i = 0; i < this.count; i++) {
      const p = this.spiralPoint(i, this.count, loopSpin + time * 0.08, loopFracture);
      const pulse = 1 + Math.sin(time * 2.5 + i * 0.4) * 0.12 * loopIntensity;
      const scale = (0.35 + loopIntensity * 0.85) * pulse * (1 + heat * 0.35);
      this.dummy.position.copy(p);
      this.dummy.scale.setScalar(scale);
      this.dummy.updateMatrix();
      this.nodes.setMatrixAt(i, this.dummy.matrix);
      positions.push(p.x, p.y, p.z);
    }
    this.nodes.instanceMatrix.needsUpdate = true;

    this.spiralGeo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    this.spiralGeo.computeBoundingSphere();

    const heal = fluidUniforms.colorA;
    const amber = fluidUniforms.colorB;
    const mix = heat;
    this.nodeMat.color.setRGB(
      heal[0] * (1 - mix) + amber[0] * mix,
      heal[1] * (1 - mix) + amber[1] * mix,
      heal[2] * (1 - mix) + amber[2] * mix
    );
    this.nodeMat.emissiveIntensity = 0.5 + loopIntensity * 0.9 + heat * 0.6;
    this.nodeMat.opacity = 0.25 + loopIntensity * 0.65;
    this.nodes.visible = loopIntensity > 0.04;

    this.spiralMat.opacity = (0.15 + loopIntensity * 0.45) * (1 - crystallize * 0.35);
    this.spiralMat.color.setRGB(
      fluidUniforms.colorB[0],
      fluidUniforms.colorB[1],
      fluidUniforms.colorB[2]
    );
    this.spiral.visible = loopIntensity > 0.06;

    this.group.rotation.y = time * 0.06 * loopSpin * 0.15;
  }

  dispose() {
    this.nodes.geometry.dispose();
    this.nodeMat.dispose();
    this.spiralGeo.dispose();
    this.spiralMat.dispose();
  }
}
