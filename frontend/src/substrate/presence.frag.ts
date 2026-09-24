/** Merged eye + orb glow fragment (uEye / uOrb weights on one program). */

export const PRESENCE_VERTEX = /* glsl */ `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

/**
 * Stock EvilEye body plus orb nucleus/bloom.
 * Weights: uEye (watch), uOrb (converse / bench pilot).
 * Placement: uCenter, uPresenceScale. Tint: uAccent, uDim.
 */
export const PRESENCE_FRAGMENT = /* glsl */ `
precision mediump float;

uniform float uTime;
uniform vec3 uResolution;
uniform sampler2D uNoiseTexture;
uniform float uPupilSize;
uniform float uIrisWidth;
uniform float uGlowIntensity;
uniform float uIntensity;
uniform float uScale;
uniform float uNoiseScale;
uniform vec2 uMouse;
uniform float uPupilFollow;
uniform float uFlameSpeed;
uniform vec3 uEyeColor;
uniform vec3 uBgColor;
uniform bool uLightMode;
uniform float uEye;
uniform float uOrb;
uniform vec2 uCenter;
uniform float uPresenceScale;
uniform vec3 uAccent;
uniform float uDim;

void main() {
  if (uEye < 0.01 && uOrb < 0.01) {
    gl_FragColor = vec4(0.0);
    return;
  }

  // uCenter is top-left normalised (status cluster); gl_FragCoord is bottom-left.
  vec2 centerPx = vec2(uCenter.x * uResolution.x, (1.0 - uCenter.y) * uResolution.y);
  float fit = max(uPresenceScale, 0.001);
  vec2 uv = (gl_FragCoord.xy * 2.0 - 2.0 * centerPx) / (uResolution.y * fit);
  uv /= uScale;

  vec4 eyeOut = vec4(0.0);
  if (uEye >= 0.01) {
    float ft = uTime * uFlameSpeed;

    float polarRadius = length(uv) * 2.0;
    float polarAngle = (2.0 * atan(uv.x, uv.y)) / 6.28 * 0.3;
    vec2 polarUv = vec2(polarRadius, polarAngle);

    vec4 noiseA = texture2D(uNoiseTexture, polarUv * vec2(0.2, 7.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));
    vec4 noiseB = texture2D(uNoiseTexture, polarUv * vec2(0.3, 4.0) * uNoiseScale + vec2(-ft * 0.2, 0.0));
    vec4 noiseC = texture2D(uNoiseTexture, polarUv * vec2(0.1, 5.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));

    float distanceMask = 1.0 - length(uv);

    float innerRing = clamp(-1.0 * ((distanceMask - 0.7) / uIrisWidth), 0.0, 1.0);
    innerRing = (innerRing * distanceMask - 0.2) / 0.28;
    innerRing += noiseA.r - 0.5;
    innerRing *= 1.3;
    innerRing = clamp(innerRing, 0.0, 1.0);

    float outerRing = clamp(-1.0 * ((distanceMask - 0.5) / 0.2), 0.0, 1.0);
    outerRing = (outerRing * distanceMask - 0.1) / 0.38;
    outerRing += noiseC.r - 0.5;
    outerRing *= 1.3;
    outerRing = clamp(outerRing, 0.0, 1.0);

    innerRing += outerRing;

    float innerEye = distanceMask - 0.1 * 2.0;
    innerEye *= noiseB.r * 2.0;

    // Closing lid feel as orb rises: pupil grows toward a shut eye.
    float lid = mix(1.0, 1.85, clamp(uOrb, 0.0, 1.0));
    vec2 pupilOffset = uMouse * uPupilFollow * 0.12 * (1.0 - uOrb);
    vec2 pupilUv = uv - pupilOffset;
    float pupil = 1.0 - length(pupilUv * vec2(9.0, 2.3));
    pupil *= uPupilSize * lid;
    pupil = clamp(pupil, 0.0, 1.0);
    pupil /= 0.35;

    float outerEyeGlow = 1.0 - length(uv * vec2(0.5, 1.5));
    outerEyeGlow = clamp(outerEyeGlow + 0.5, 0.0, 1.0);
    outerEyeGlow += noiseC.r - 0.5;
    float outerBgGlow = outerEyeGlow;
    outerEyeGlow = pow(outerEyeGlow, 2.0);
    outerEyeGlow += distanceMask;
    outerEyeGlow *= uGlowIntensity;
    outerEyeGlow = clamp(outerEyeGlow, 0.0, 1.0);
    outerEyeGlow *= pow(1.0 - distanceMask, 2.0) * 2.5;

    outerBgGlow += distanceMask;
    outerBgGlow = pow(outerBgGlow, 0.5);
    outerBgGlow *= 0.15;

    vec3 eyeEnergy = uEyeColor * uIntensity * clamp(max(innerRing + innerEye, outerEyeGlow + outerBgGlow) - pupil, 0.0, 3.0);
    vec3 color;
    if (uLightMode) {
      vec3 mapped = vec3(1.0) - exp(-max(eyeEnergy, vec3(0.0)) * 1.3);
      float energy = clamp(max(mapped.r, max(mapped.g, mapped.b)), 0.0, 1.0);
      vec3 hue = mapped / max(energy, 0.0001);
      hue = pow(clamp(hue, 0.0, 1.0), vec3(1.2));
      color = mix(uBgColor, hue, smoothstep(0.02, 0.82, energy) * 0.96);
    } else {
      color = eyeEnergy;
    }

    float alpha = smoothstep(1.18, 0.72, length(uv)) * uEye;
    eyeOut = vec4(color * uEye, alpha);
  }

  vec4 orbOut = vec4(0.0);
  if (uOrb >= 0.01) {
    // Same centre / fit as the eye. Soft falloff so scale 0.07 reads as a clear mint pilot bead.
    vec2 ou = (gl_FragCoord.xy - centerPx) / (uResolution.y * fit);
    float r = length(ou);
    // Bench pilot is tiny (scale ~0.07) — keep a lit floor. Full-size converse honors uDim
    // so the mint orb does not blow out into a white disk under the DOM rings.
    float benchPilot = step(uPresenceScale, 0.2);
    float nucleusGain = mix(0.35, 1.8, benchPilot);
    float bloomGain = mix(0.32, 0.85, benchPilot);
    float haloGain = mix(0.12, 0.4, benchPilot);
    float nucleus = exp(-r * r * 7.5) * nucleusGain;
    float bloom = exp(-r * r * 1.35) * bloomGain;
    float halo = exp(-r * r * 0.35) * haloGain;
    float ring = smoothstep(1.0, 0.5, r) * smoothstep(0.14, 0.48, r) * mix(0.7, 0.4, benchPilot);
    float breath = 0.92 + 0.08 * sin(uTime * 1.4);
    float lit = mix(uDim, max(uDim, 0.75), benchPilot);
    float energy = (nucleus + bloom + halo + ring) * lit * breath;
    vec3 col = uAccent * energy;
    float a = clamp(energy, 0.0, 1.0) * uOrb;
    orbOut = vec4(col * uOrb, a);
  }

  vec3 rgb = eyeOut.rgb + orbOut.rgb;
  float a = clamp(eyeOut.a + orbOut.a, 0.0, 1.0);
  gl_FragColor = vec4(rgb, a);
}
`;

/** Stock MonitorDesk EvilEye props (Appendix A item 2). */
export const STOCK_EYE = {
  eyeColor: "#FF6F37",
  intensity: 1.5,
  pupilSize: 0.6,
  irisWidth: 0.25,
  glowIntensity: 0.35,
  scale: 0.8,
  noiseScale: 1,
  pupilFollow: 1,
  flameSpeed: 1,
  backgroundColor: "#120F17",
  lightMode: false,
} as const;

/** Internal pixels vs CSS size — 1.0 keeps Watch iris edges sharp (was 0.6 upscale). */
export const EYE_INTERNAL_SCALE = 1.0;

export function hexToVec3(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}
