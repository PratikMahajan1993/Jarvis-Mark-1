import { Camera, Geometry, Mesh, Program } from "ogl";

type GL = ConstructorParameters<typeof Geometry>[0];

const DEFAULT_COLORS = ["#7dffe0", "#9bffe8", "#5ad4c0"];

function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace(/^#/, "");
  if (h.length === 3) {
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  }
  const int = parseInt(h.slice(0, 6), 16);
  return [((int >> 16) & 255) / 255, ((int >> 8) & 255) / 255, (int & 255) / 255];
}

const VERTEX = /* glsl */ `
  attribute vec3 position;
  attribute vec4 random;
  attribute vec3 color;
  uniform mat4 modelMatrix;
  uniform mat4 viewMatrix;
  uniform mat4 projectionMatrix;
  uniform float uTime;
  uniform float uSpread;
  uniform float uBaseSize;
  uniform float uSizeRandomness;
  varying vec4 vRandom;
  varying vec3 vColor;
  void main() {
    vRandom = random;
    vColor = color;
    vec3 pos = position * uSpread;
    pos.z *= 10.0;
    vec4 mPos = modelMatrix * vec4(pos, 1.0);
    float t = uTime;
    mPos.x += sin(t * random.z + 6.28 * random.w) * mix(0.1, 1.5, random.x);
    mPos.y += sin(t * random.y + 6.28 * random.x) * mix(0.1, 1.5, random.w);
    mPos.z += sin(t * random.w + 6.28 * random.y) * mix(0.1, 1.5, random.z);
    vec4 mvPos = viewMatrix * mPos;
    if (uSizeRandomness == 0.0) {
      gl_PointSize = uBaseSize;
    } else {
      gl_PointSize = (uBaseSize * (1.0 + uSizeRandomness * (random.x - 0.5))) / length(mvPos.xyz);
    }
    gl_Position = projectionMatrix * mvPos;
  }
`;

const FRAGMENT = /* glsl */ `
  precision highp float;
  uniform float uTime;
  uniform float uAlphaParticles;
  uniform float uOrb;
  varying vec4 vRandom;
  varying vec3 vColor;
  void main() {
    if (uOrb < 0.01) discard;
    vec2 uv = gl_PointCoord.xy;
    float d = length(uv - vec2(0.5));
    if (uAlphaParticles < 0.5) {
      if (d > 0.5) discard;
      gl_FragColor = vec4(vColor + 0.15 * sin(uv.yxx + uTime + vRandom.y * 6.28), uOrb);
    } else {
      float circle = smoothstep(0.5, 0.35, d) * 0.75 * uOrb;
      gl_FragColor = vec4(vColor + 0.12 * sin(uv.yxx + uTime + vRandom.y * 6.28), circle);
    }
  }
`;

export type ParticlePass = {
  mesh: Mesh;
  camera: Camera;
  setOrb: (orb: number) => void;
  setTime: (t: number) => void;
  resize: (cssW: number, cssH: number, dpr: number) => void;
  /** Advance drift/rotation; no-op when frozen (reducedMotion). */
  tick: (deltaMs: number, frozen: boolean) => void;
};

export type ParticlePassOptions = {
  particleCount?: number;
  particleSpread?: number;
  speed?: number;
  particleBaseSize?: number;
  sizeRandomness?: number;
  cameraDistance?: number;
  disableRotation?: boolean;
  particleColors?: string[];
};

/** Point sprites from Particles.tsx — alpha × uOrb. Shares the engine Renderer.gl. */
export function createParticlePass(
  gl: GL,
  options: ParticlePassOptions = {},
): ParticlePass {
  const particleCount = options.particleCount ?? 120;
  const particleSpread = options.particleSpread ?? 9;
  const speed = options.speed ?? 0.06;
  const particleBaseSize = options.particleBaseSize ?? 70;
  const sizeRandomness = options.sizeRandomness ?? 0.9;
  const cameraDistance = options.cameraDistance ?? 22;
  const disableRotation = options.disableRotation ?? false;
  const palette = options.particleColors?.length ? options.particleColors : DEFAULT_COLORS;

  const positions = new Float32Array(particleCount * 3);
  const randoms = new Float32Array(particleCount * 4);
  const colors = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i++) {
    let x = 0;
    let y = 0;
    let z = 0;
    let len = 0;
    do {
      x = Math.random() * 2 - 1;
      y = Math.random() * 2 - 1;
      z = Math.random() * 2 - 1;
      len = x * x + y * y + z * z;
    } while (len > 1 || len === 0);
    const r = Math.cbrt(Math.random());
    positions.set([x * r, y * r, z * r], i * 3);
    randoms.set([Math.random(), Math.random(), Math.random(), Math.random()], i * 4);
    colors.set(hexToRgb(palette[Math.floor(Math.random() * palette.length)]!), i * 3);
  }

  const geometry = new Geometry(gl, {
    position: { size: 3, data: positions },
    random: { size: 4, data: randoms },
    color: { size: 3, data: colors },
  });

  const program = new Program(gl, {
    vertex: VERTEX,
    fragment: FRAGMENT,
    uniforms: {
      uTime: { value: 0 },
      uSpread: { value: particleSpread },
      uBaseSize: { value: particleBaseSize },
      uSizeRandomness: { value: sizeRandomness },
      uAlphaParticles: { value: 1 },
      uOrb: { value: 0 },
    },
    transparent: true,
    depthTest: false,
  });

  const mesh = new Mesh(gl, { mode: gl.POINTS, geometry, program });
  const camera = new Camera(gl, { fov: 15 });
  camera.position.set(0, 0, cameraDistance);

  let elapsed = 0;
  let dpr = 1;

  return {
    mesh,
    camera,
    setOrb(orb: number) {
      program.uniforms.uOrb.value = orb;
    },
    setTime(t: number) {
      program.uniforms.uTime.value = t;
    },
    resize(cssW: number, cssH: number, nextDpr: number) {
      dpr = Math.max(0.1, nextDpr);
      program.uniforms.uBaseSize.value = particleBaseSize * dpr;
      const w = Math.max(1, cssW * dpr);
      const h = Math.max(1, cssH * dpr);
      camera.perspective({ aspect: w / h });
    },
    tick(deltaMs: number, frozen: boolean) {
      if (frozen) return;
      elapsed += deltaMs * speed;
      program.uniforms.uTime.value = elapsed * 0.001;
      if (!disableRotation) {
        mesh.rotation.x = Math.sin(elapsed * 0.0002) * 0.08;
        mesh.rotation.y = Math.cos(elapsed * 0.0005) * 0.12;
        mesh.rotation.z += 0.006 * speed;
      }
    },
  };
}
