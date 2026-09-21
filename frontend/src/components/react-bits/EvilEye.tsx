"use client";

import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Texture, Triangle } from "ogl";

interface EvilEyeProps {
  eyeColor?: string;
  intensity?: number;
  pupilSize?: number;
  irisWidth?: number;
  glowIntensity?: number;
  scale?: number;
  noiseScale?: number;
  pupilFollow?: number;
  flameSpeed?: number;
  backgroundColor?: string;
  lightMode?: boolean;
  className?: string;
}

/** Internal pixels vs CSS size. Fire upscales cleanly; 0.55 ≈ 3× fewer fragments. */
const EYE_INTERNAL_SCALE = 0.55;
const EYE_FRAME_MS = 1000 / 30;
const EYE_NOISE_SIZE = 128;

function hexToVec3(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255
  ];
}

function generateNoiseTexture(size = EYE_NOISE_SIZE): Uint8Array {
  const data = new Uint8Array(size * size * 4);

  function hash(x: number, y: number, s: number): number {
    let n = x * 374761393 + y * 668265263 + s * 1274126177;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }

  function noise(px: number, py: number, freq: number, seed: number): number {
    const fx = (px / size) * freq;
    const fy = (py / size) * freq;
    const ix = Math.floor(fx);
    const iy = Math.floor(fy);
    const tx = fx - ix;
    const ty = fy - iy;
    const w = freq | 0;
    const v00 = hash(((ix % w) + w) % w, ((iy % w) + w) % w, seed);
    const v10 = hash((((ix + 1) % w) + w) % w, ((iy % w) + w) % w, seed);
    const v01 = hash(((ix % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    const v11 = hash((((ix + 1) % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    return v00 * (1 - tx) * (1 - ty) + v10 * tx * (1 - ty) + v01 * (1 - tx) * ty + v11 * tx * ty;
  }

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let v = 0;
      let amp = 0.4;
      let totalAmp = 0;
      for (let o = 0; o < 8; o++) {
        const f = 32 * (1 << o);
        v += amp * noise(x, y, f, o * 31);
        totalAmp += amp;
        amp *= 0.65;
      }
      v /= totalAmp;
      v = (v - 0.5) * 2.2 + 0.5;
      v = Math.max(0, Math.min(1, v));
      const val = Math.round(v * 255);
      const i = (y * size + x) * 4;
      data[i] = val;
      data[i + 1] = val;
      data[i + 2] = val;
      data[i + 3] = 255;
    }
  }

  return data;
}

const vertexShader = `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

const fragmentShader = `
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

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution.xy) / uResolution.y;
  uv /= uScale;
  float ft = uTime * uFlameSpeed;

  float polarRadius = length(uv) * 2.0;
  float polarAngle = (2.0 * atan(uv.x, uv.y)) / 6.28 * 0.3;
  vec2 polarUv = vec2(polarRadius, polarAngle);

  vec4 noiseA = texture2D(uNoiseTexture, polarUv * vec2(0.2, 7.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));
  vec4 noiseB = texture2D(uNoiseTexture, polarUv * vec2(0.3, 4.0) * uNoiseScale + vec2(-ft * 0.2, 0.0));
  vec4 noiseC = texture2D(uNoiseTexture, polarUv * vec2(0.1, 5.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));

  float distanceMask = 1.0 - length(uv);

  // Inner ring
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

  // Inner eye
  float innerEye = distanceMask - 0.1 * 2.0;
  innerEye *= noiseB.r * 2.0;

  // Pupil with cursor tracking
  vec2 pupilOffset = uMouse * uPupilFollow * 0.12;
  vec2 pupilUv = uv - pupilOffset;
  float pupil = 1.0 - length(pupilUv * vec2(9.0, 2.3));
  pupil *= uPupilSize;
  pupil = clamp(pupil, 0.0, 1.0);
  pupil /= 0.35;

  // Outer eye
  float outerEyeGlow = 1.0 - length(uv * vec2(0.5, 1.5));
  outerEyeGlow = clamp(outerEyeGlow + 0.5, 0.0, 1.0);
  outerEyeGlow += noiseC.r - 0.5;
  float outerBgGlow = outerEyeGlow;
  outerEyeGlow = pow(outerEyeGlow, 2.0);
  outerEyeGlow += distanceMask;
  outerEyeGlow *= uGlowIntensity;
  outerEyeGlow = clamp(outerEyeGlow, 0.0, 1.0);
  outerEyeGlow *= pow(1.0 - distanceMask, 2.0) * 2.5;

  // Outer eye bg glow
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

  float alpha = smoothstep(1.18, 0.72, length(uv));
  gl_FragColor = vec4(color, alpha);
}
`;

/** React Bits — Evil Eye (TS + ogl). Monitor workspace center accent. */
export default function EvilEye({
  eyeColor = "#FF6F37",
  intensity = 1.5,
  pupilSize = 0.6,
  irisWidth = 0.25,
  glowIntensity = 0.35,
  scale = 0.8,
  noiseScale = 1.0,
  pupilFollow = 1.0,
  flameSpeed = 1.0,
  backgroundColor = "#000000",
  lightMode = false,
  className = "",
}: EvilEyeProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frozen = reduceMotion.matches || document.hidden;
    let frozenTime = performance.now();
    const renderer = new Renderer({
      alpha: true,
      depth: false,
      antialias: false,
      premultipliedAlpha: false,
      dpr: EYE_INTERNAL_SCALE,
      powerPreference: "high-performance",
    });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.canvas.style.width = "100%";
    gl.canvas.style.height = "100%";
    gl.canvas.style.display = "block";
    gl.canvas.style.background = "transparent";
    gl.canvas.style.imageRendering = "auto";

    const noiseData = generateNoiseTexture(EYE_NOISE_SIZE);
    const noiseTexture = new Texture(gl, {
      image: noiseData,
      width: EYE_NOISE_SIZE,
      height: EYE_NOISE_SIZE,
      generateMipmaps: false,
      flipY: false,
    });
    noiseTexture.minFilter = gl.LINEAR;
    noiseTexture.magFilter = gl.LINEAR;
    noiseTexture.wrapS = gl.REPEAT;
    noiseTexture.wrapT = gl.REPEAT;

    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };

    function onMouseMove(e: MouseEvent) {
      const rect = container.getBoundingClientRect();
      mouse.tx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.ty = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    }

    function onMouseLeave() {
      mouse.tx = 0;
      mouse.ty = 0;
    }

    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseleave', onMouseLeave);

    const geometry = new Triangle(gl);
    const program = new Program(gl, {
      vertex: vertexShader,
      fragment: fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: [gl.canvas.width, gl.canvas.height, gl.canvas.width / gl.canvas.height] },
        uNoiseTexture: { value: noiseTexture },
        uPupilSize: { value: pupilSize },
        uIrisWidth: { value: irisWidth },
        uGlowIntensity: { value: glowIntensity },
        uIntensity: { value: intensity },
        uScale: { value: scale },
        uNoiseScale: { value: noiseScale },
        uMouse: { value: [0, 0] },
        uPupilFollow: { value: pupilFollow },
        uFlameSpeed: { value: flameSpeed },
        uEyeColor: { value: hexToVec3(eyeColor) },
        uBgColor: { value: hexToVec3(backgroundColor) },
        uLightMode: { value: lightMode }
      }
    });

    function resize() {
      const width = container.offsetWidth || 1;
      const height = container.offsetHeight || 1;
      renderer.setSize(width, height);
      program.uniforms.uResolution.value = [gl.canvas.width, gl.canvas.height, gl.canvas.width / gl.canvas.height];
    }
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    window.addEventListener("resize", resize);
    resize();

    const mesh = new Mesh(gl, { geometry, program });
    container.appendChild(gl.canvas);

    let animationFrameId = 0;
    let lastFrame = 0;
    const presenceHost = container.closest("[data-hud-presence]");

    const isOffscreen = () =>
      reduceMotion.matches ||
      document.hidden ||
      presenceHost?.getAttribute("aria-hidden") === "true";

    const renderFrame = (time: number) => {
      if (!frozen) {
        mouse.x += (mouse.tx - mouse.x) * 0.05;
        mouse.y += (mouse.ty - mouse.y) * 0.05;
      }
      program.uniforms.uMouse.value = [mouse.x, mouse.y];
      program.uniforms.uTime.value = (frozen ? frozenTime : time) * 0.001;
      renderer.render({ scene: mesh });
    };

    const stopLoop = () => {
      if (!animationFrameId) return;
      cancelAnimationFrame(animationFrameId);
      animationFrameId = 0;
    };

    const startLoop = () => {
      stopLoop();
      lastFrame = 0;
      const tick = (time: number) => {
        animationFrameId = requestAnimationFrame(tick);
        if (frozen) return;
        if (time - lastFrame < EYE_FRAME_MS) return;
        lastFrame = time;
        renderFrame(time);
      };
      animationFrameId = requestAnimationFrame(tick);
    };

    const syncMotion = () => {
      const nextFrozen = isOffscreen();
      if (nextFrozen && !frozen) frozenTime = performance.now();
      frozen = nextFrozen;
      if (frozen) {
        stopLoop();
        renderFrame(frozenTime);
      } else {
        startLoop();
      }
    };

    const presenceObserver = presenceHost
      ? new MutationObserver(syncMotion)
      : null;
    presenceObserver?.observe(presenceHost as Element, {
      attributes: true,
      attributeFilter: ["class", "aria-hidden"],
    });

    document.addEventListener("visibilitychange", syncMotion);
    reduceMotion.addEventListener("change", syncMotion);
    syncMotion();

    return () => {
      stopLoop();
      presenceObserver?.disconnect();
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", syncMotion);
      reduceMotion.removeEventListener("change", syncMotion);
      window.removeEventListener("resize", resize);
      container.removeEventListener("mousemove", onMouseMove);
      container.removeEventListener("mouseleave", onMouseLeave);
      container.removeChild(gl.canvas);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, [eyeColor, intensity, pupilSize, irisWidth, glowIntensity, scale, noiseScale, pupilFollow, flameSpeed, backgroundColor, lightMode]);

  return (
    <div
      ref={containerRef}
      className={`relative h-full w-full ${className}`.trim()}
      aria-hidden="true"
    />
  );
}
