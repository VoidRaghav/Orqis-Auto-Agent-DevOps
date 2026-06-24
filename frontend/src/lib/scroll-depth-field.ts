/** Calm scroll depth background — single ring, sparse particles. */

import * as THREE from "three";

export type DepthFieldHandles = {
  group: THREE.Group;
  update: (
    heroScrub: number,
    globalProgress: number,
    time: number,
    reducedMotion: boolean,
    guideDim?: number
  ) => void;
  dispose: () => void;
};

export function createScrollDepthField(scene: THREE.Scene): DepthFieldHandles {
  const group = new THREE.Group();
  scene.add(group);

  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x88c4e8,
    transparent: true,
    opacity: 0.035,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
  });

  const rings: THREE.Mesh[] = [];
  for (let i = 0; i < 2; i++) {
    const geo = new THREE.TorusGeometry(2.1 + i * 0.5, 0.008, 6, 48);
    const mesh = new THREE.Mesh(geo, ringMat.clone());
    mesh.rotation.x = Math.PI / 2;
    mesh.position.set(0.5, -0.1 - i * 0.15, -2.8 - i * 0.6);
    group.add(mesh);
    rings.push(mesh);
  }

  const particleCount = 48;
  const positions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const angle = Math.random() * Math.PI * 2;
    const r = 1.2 + Math.random() * 1.4;
    positions[i * 3] = 0.5 + Math.cos(angle) * r;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 2.5;
    positions[i * 3 + 2] = -2 - Math.random() * 2.5;
  }

  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const pMat = new THREE.PointsMaterial({
    color: 0xa8d4ff,
    size: 0.028,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const particles = new THREE.Points(pGeo, pMat);
  group.add(particles);

  const update = (
    heroScrub: number,
    globalProgress: number,
    time: number,
    reducedMotion: boolean,
    guideDim = 1
  ) => {
    const t = reducedMotion ? 0 : time;
    const slam = heroScrub > 0.88 ? (heroScrub - 0.88) / 0.12 : 0;
    const dim = Math.max(0.35, guideDim);

    rings.forEach((ring, i) => {
      ring.rotation.z = t * (0.025 + i * 0.01) + globalProgress * 0.15;
      ring.scale.setScalar(1 + heroScrub * 0.04 + slam * 0.08);
      (ring.material as THREE.MeshBasicMaterial).opacity =
        (0.028 + heroScrub * 0.015 + slam * 0.02) * dim;
    });

    particles.rotation.y = t * 0.012 + globalProgress * 0.06;
    pMat.opacity = (0.18 + globalProgress * 0.06 + slam * 0.06) * dim;
    group.position.y = globalProgress * -0.12;
  };

  const dispose = () => {
    rings.forEach((r) => {
      r.geometry.dispose();
      (r.material as THREE.Material).dispose();
    });
    pGeo.dispose();
    pMat.dispose();
    scene.remove(group);
  };

  return { group, update, dispose };
}
