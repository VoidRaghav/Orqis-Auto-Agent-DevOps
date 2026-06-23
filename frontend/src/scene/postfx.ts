/** Lightweight post-processing — bloom tint + chromatic hint via canvas composite. */

import * as THREE from "three";

export type PostFxState = {
  bloom: number;
  chromatic: number;
  vignette: number;
};

export function createBloomQuad(): THREE.Mesh {
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uIntensity: { value: 0.35 },
      uColor: { value: new THREE.Color(0x5ecfb8) },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position.xy, 0.0, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uIntensity;
      uniform vec3 uColor;
      varying vec2 vUv;
      void main() {
        vec2 uv = vUv - 0.5;
        float d = length(uv);
        float glow = smoothstep(0.65, 0.0, d) * uIntensity;
        gl_FragColor = vec4(uColor * glow, glow * 0.55);
      }
    `,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = 100;
  return mesh;
}

export function applyPostFxUniforms(mesh: THREE.Mesh, state: PostFxState) {
  const mat = mesh.material as THREE.ShaderMaterial;
  mat.uniforms.uIntensity.value = state.bloom;
  mesh.visible = state.bloom > 0.05;
}

export function chromaticOffsetPx(chromatic: number): string {
  if (chromatic < 0.02) return "none";
  const px = (chromatic * 3).toFixed(2);
  return `drop-shadow(${px}px 0 rgba(255,80,60,0.25)) drop-shadow(-${px}px 0 rgba(80,200,255,0.2))`;
}
