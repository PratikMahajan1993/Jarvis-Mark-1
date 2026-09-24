import { Mesh, Program, Triangle } from "ogl";

type GL = ConstructorParameters<typeof Triangle>[0];

const VERTEX = /* glsl */ `
  attribute vec2 position;
  varying vec2 vUv;
  void main() {
    vUv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
  }
`;

const FRAGMENT = /* glsl */ `
  precision highp float;
  uniform float iTime;
  uniform vec2 iResolution;
  uniform vec2 rayPos;
  uniform vec2 rayDir;
  uniform vec3 raysColor;
  uniform float raysSpeed;
  uniform float lightSpread;
  uniform float rayLength;
  uniform float pulsating;
  uniform float fadeDistance;
  uniform float saturation;
  uniform vec2 mousePos;
  uniform float mouseInfluence;
  uniform float noiseAmount;
  uniform float distortion;
  uniform float uOrb;
  varying vec2 vUv;

  float noise(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
  }

  float rayStrength(vec2 raySource, vec2 rayRefDirection, vec2 coord,
    float seedA, float seedB, float speed) {
    vec2 sourceToCoord = coord - raySource;
    vec2 dirNorm = normalize(sourceToCoord);
    float cosAngle = dot(dirNorm, rayRefDirection);
    float distortedAngle = cosAngle + distortion * sin(iTime * 2.0 + length(sourceToCoord) * 0.01) * 0.2;
    float spreadFactor = pow(max(distortedAngle, 0.0), 1.0 / max(lightSpread, 0.001));
    float distance = length(sourceToCoord);
    float maxDistance = iResolution.x * rayLength;
    float lengthFalloff = clamp((maxDistance - distance) / maxDistance, 0.0, 1.0);
    float fadeFalloff = clamp((iResolution.x * fadeDistance - distance) / (iResolution.x * fadeDistance), 0.5, 1.0);
    float pulse = pulsating > 0.5 ? (0.82 + 0.18 * sin(iTime * speed * 3.0)) : 1.0;
    float baseStrength = clamp(
      (0.45 + 0.15 * sin(distortedAngle * seedA + iTime * speed)) +
      (0.3 + 0.2 * cos(-distortedAngle * seedB + iTime * speed)),
      0.0, 1.0
    );
    return baseStrength * lengthFalloff * fadeFalloff * spreadFactor * pulse;
  }

  void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 coord = vec2(fragCoord.x, iResolution.y - fragCoord.y);
    vec2 finalRayDir = rayDir;
    if (mouseInfluence > 0.0) {
      vec2 mouseScreenPos = mousePos * iResolution.xy;
      vec2 mouseDirection = normalize(mouseScreenPos - rayPos);
      finalRayDir = normalize(mix(rayDir, mouseDirection, mouseInfluence));
    }
    vec4 rays1 = vec4(1.0) * rayStrength(rayPos, finalRayDir, coord, 36.2214, 21.11349, 1.5 * raysSpeed);
    vec4 rays2 = vec4(1.0) * rayStrength(rayPos, finalRayDir, coord, 22.3991, 18.0234, 1.1 * raysSpeed);
    fragColor = rays1 * 0.45 + rays2 * 0.35;
    if (noiseAmount > 0.0) {
      float n = noise(coord * 0.01 + iTime * 0.1);
      fragColor.rgb *= (1.0 - noiseAmount + noiseAmount * n);
    }
    float brightness = 1.0 - (coord.y / iResolution.y);
    fragColor.x *= 0.15 + brightness * 0.7;
    fragColor.y *= 0.35 + brightness * 0.55;
    fragColor.z *= 0.45 + brightness * 0.45;
    if (saturation != 1.0) {
      float gray = dot(fragColor.rgb, vec3(0.299, 0.587, 0.114));
      fragColor.rgb = mix(vec3(gray), fragColor.rgb, saturation);
    }
    fragColor.rgb *= raysColor;
    fragColor.a = clamp(max(fragColor.r, max(fragColor.g, fragColor.b)) * 0.55, 0.0, 0.55);
    fragColor.a *= uOrb * 0.7;
    fragColor.rgb *= uOrb * 0.7;
  }

  void main() {
    if (uOrb < 0.01) {
      gl_FragColor = vec4(0.0);
      return;
    }
    vec4 color;
    mainImage(color, gl_FragCoord.xy);
    gl_FragColor = color;
  }
`;

function getAnchorAndDir(
  origin: "top-center",
  w: number,
  h: number,
): { anchor: [number, number]; dir: [number, number] } {
  const outside = 0.2;
  void origin;
  return { anchor: [0.5 * w, -outside * h], dir: [0, 1] };
}

export type RayPass = {
  mesh: Mesh;
  setOrb: (orb: number) => void;
  setTime: (tSec: number) => void;
  setMouse: (x: number, y: number) => void;
  setColor: (rgb: [number, number, number]) => void;
  resize: (glW: number, glH: number) => void;
};

export type RayPassOptions = {
  raysColor?: [number, number, number];
  raysSpeed?: number;
  lightSpread?: number;
  rayLength?: number;
  pulsating?: boolean;
  fadeDistance?: number;
  saturation?: number;
  mouseInfluence?: number;
  noiseAmount?: number;
  distortion?: number;
};

/** Light rays from LightRays.tsx — alpha × uOrb × 0.7. Shares engine Triangle + gl. */
export function createRayPass(
  gl: GL,
  geometry: Triangle,
  options: RayPassOptions = {},
): RayPass {
  const raysColor = options.raysColor ?? ([0.49, 1.0, 0.878] as [number, number, number]);
  const uniforms = {
    iTime: { value: 0 },
    iResolution: { value: [1, 1] as [number, number] },
    rayPos: { value: [0, 0] as [number, number] },
    rayDir: { value: [0, 1] as [number, number] },
    raysColor: { value: [...raysColor] as [number, number, number] },
    raysSpeed: { value: options.raysSpeed ?? 0.55 },
    lightSpread: { value: options.lightSpread ?? 1.35 },
    rayLength: { value: options.rayLength ?? 1.6 },
    pulsating: { value: (options.pulsating ?? true) ? 1.0 : 0.0 },
    fadeDistance: { value: options.fadeDistance ?? 1.15 },
    saturation: { value: options.saturation ?? 0.85 },
    mousePos: { value: [0.5, 0.5] as [number, number] },
    mouseInfluence: { value: options.mouseInfluence ?? 0.12 },
    noiseAmount: { value: options.noiseAmount ?? 0.08 },
    distortion: { value: options.distortion ?? 0.04 },
    uOrb: { value: 0 },
  };

  const program = new Program(gl, { vertex: VERTEX, fragment: FRAGMENT, uniforms });
  const mesh = new Mesh(gl, { geometry, program });

  return {
    mesh,
    setOrb(orb: number) {
      uniforms.uOrb.value = orb;
    },
    setTime(tSec: number) {
      uniforms.iTime.value = tSec;
    },
    setMouse(x: number, y: number) {
      // pointer is −1..1; rays expect 0..1
      uniforms.mousePos.value = [x * 0.5 + 0.5, y * 0.5 + 0.5];
    },
    setColor(rgb: [number, number, number]) {
      uniforms.raysColor.value = [...rgb];
    },
    resize(glW: number, glH: number) {
      const w = Math.max(1, glW);
      const h = Math.max(1, glH);
      uniforms.iResolution.value = [w, h];
      const { anchor, dir } = getAnchorAndDir("top-center", w, h);
      uniforms.rayPos.value = anchor;
      uniforms.rayDir.value = dir;
    },
  };
}
