/** Lusion-inspired organic fluid fullscreen pass. */

import * as THREE from "three";
import type { FluidUniforms } from "@/lib/scroll-director";

const VERT = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const FRAG = `
precision highp float;
uniform float uTime;
uniform vec2 uResolution;
uniform float uDensity;
uniform float uSpeed;
uniform float uTurbulence;
uniform vec3 uColorA;
uniform vec3 uColorB;
uniform vec3 uColorC;
uniform float uOpacity;
uniform float uCrystallize;
uniform float uHeat;
uniform float uFog;
uniform bool uAnimated;
varying vec2 vUv;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.1;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = vUv;
  vec2 p = (uv - 0.5) * vec2(uResolution.x / uResolution.y, 1.0);
  float t = uAnimated ? uTime * uSpeed : 0.0;

  vec2 flow = vec2(
    fbm(p * 2.0 + vec2(t * 0.3, t * 0.15)),
    fbm(p * 2.0 + vec2(-t * 0.2, t * 0.25) + 4.0)
  );
  float n = fbm(p * (1.5 + uTurbulence) + flow * (1.2 + uTurbulence));
  float ridge = pow(abs(sin(n * 6.28 + t)), 1.4 + uHeat);

  vec3 col = mix(uColorA, uColorB, smoothstep(0.2, 0.85, n));
  col = mix(col, uColorC, ridge * (0.35 + uHeat * 0.4));
  col += vec3(0.08, 0.12, 0.1) * uCrystallize * smoothstep(0.55, 0.95, n);

  float alpha = uOpacity * smoothstep(0.0, 0.25, n) * (1.0 - uFog * 0.15);
  alpha *= mix(1.0, 0.65, uCrystallize * 0.5);
  alpha *= uDensity;

  gl_FragColor = vec4(col, alpha);
}
`;

export class OrganicFluidPass {
  readonly mesh: THREE.Mesh;
  private mat: THREE.ShaderMaterial;

  constructor(animated = true) {
    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new THREE.Vector2(1, 1) },
        uDensity: { value: 0.3 },
        uSpeed: { value: 0.2 },
        uTurbulence: { value: 0.3 },
        uColorA: { value: new THREE.Vector3(0.1, 0.24, 0.19) },
        uColorB: { value: new THREE.Vector3(0.2, 0.72, 0.68) },
        uColorC: { value: new THREE.Vector3(0.96, 0.94, 0.91) },
        uOpacity: { value: 0.4 },
        uCrystallize: { value: 0 },
        uHeat: { value: 0 },
        uFog: { value: 0.3 },
        uAnimated: { value: animated },
      },
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = -10;
  }

  setSize(w: number, h: number) {
    (this.mat.uniforms.uResolution.value as THREE.Vector2).set(w, h);
  }

  applyUniforms(u: FluidUniforms, time: number) {
    const m = this.mat.uniforms;
    m.uTime.value = time;
    m.uDensity.value = u.density;
    m.uSpeed.value = u.speed;
    m.uTurbulence.value = u.turbulence;
    (m.uColorA.value as THREE.Vector3).set(...u.colorA);
    (m.uColorB.value as THREE.Vector3).set(...u.colorB);
    (m.uColorC.value as THREE.Vector3).set(...u.colorC);
    m.uOpacity.value = u.opacity;
    m.uCrystallize.value = u.crystallize;
    m.uHeat.value = u.heat;
    m.uFog.value = u.fog;
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.mat.dispose();
  }
}
