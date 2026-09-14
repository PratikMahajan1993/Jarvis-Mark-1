"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef } from "react";
import type { OrchestratorMode } from "@/lib/orchestrator";

const Particles = dynamic(() => import("@/components/react-bits/Particles"), { ssr: false });
const LightRays = dynamic(() => import("@/components/react-bits/LightRays"), { ssr: false });

/** Soft dust orbiting the core — light canvas accent (no WebGL). */
function OrbDust({ active, hitl }: { active: boolean; hitl: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = 520;
    canvas.width = size;
    canvas.height = size;
    const count = 36;
    const particles = Array.from({ length: count }, (_, i) => {
      const angle = (i / count) * Math.PI * 2 + Math.random() * 0.4;
      const radius = 120 + Math.random() * 120;
      return {
        angle,
        radius,
        speed: 0.00035 + Math.random() * 0.0005,
        size: 0.55 + Math.random() * 1.2,
        alpha: 0.12 + Math.random() * 0.28,
      };
    });

    let frame = 0;
    let raf = 0;
    const draw = () => {
      frame += 1;
      ctx.clearRect(0, 0, size, size);
      const cx = size / 2;
      const cy = size / 2;
      const boost = hitl ? 0.35 : active ? 1.3 : 1;
      for (const p of particles) {
        p.angle += p.speed * boost;
        const x = cx + Math.cos(p.angle) * p.radius;
        const y = cy + Math.sin(p.angle) * p.radius * 0.92;
        ctx.beginPath();
        ctx.fillStyle = `rgba(125, 255, 224, ${p.alpha * (hitl ? 0.35 : active ? 0.9 : 0.65)})`;
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      const pulse = 0.07 + Math.sin(frame * 0.02) * 0.025;
      const hub = ctx.createRadialGradient(cx, cy, 8, cx, cy, 88);
      hub.addColorStop(0, `rgba(125, 255, 224, ${pulse * (active ? 1.5 : 1)})`);
      hub.addColorStop(1, "rgba(125, 255, 224, 0)");
      ctx.fillStyle = hub;
      ctx.fillRect(0, 0, size, size);
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [active, hitl]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute left-1/2 top-1/2 z-[1] h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 opacity-60"
      aria-hidden
    />
  );
}

export function JarvisCore({ mode }: { mode: OrchestratorMode }) {
  const active = mode === "busy" || mode === "listening";
  const hitl = mode === "hitl";
  return (
    <>
      {/* WebGL wash — kept faint so it doesn't fight the desk */}
      <div
        className={[
          "pointer-events-none absolute inset-0 z-0 overflow-hidden transition-opacity duration-[900ms]",
          hitl ? "opacity-20" : active ? "opacity-55" : "opacity-40",
        ].join(" ")}
      >
        <div className="absolute inset-0 opacity-70">
          <LightRays
            raysOrigin="top-center"
            raysColor="#7dffe0"
            raysSpeed={active ? 0.75 : 0.45}
            lightSpread={1.5}
            rayLength={1.45}
            pulsating
            fadeDistance={1.2}
            saturation={0.8}
            followMouse
            mouseInfluence={0.1}
            noiseAmount={0.06}
            distortion={0.03}
          />
        </div>
        <div className="absolute left-1/2 top-1/2 h-[720px] w-[720px] -translate-x-1/2 -translate-y-1/2 opacity-50">
          <Particles
            particleCount={active ? 150 : 110}
            particleSpread={8.5}
            speed={active ? 0.08 : 0.045}
            particleColors={["#7dffe0", "#9bffe8", "#5ad4c0", "#e8fffa"]}
            alphaParticles
            particleBaseSize={active ? 78 : 62}
            sizeRandomness={0.85}
            cameraDistance={24}
            moveParticlesOnHover={false}
            pixelRatio={1}
          />
        </div>
      </div>

      <div className="pointer-events-none absolute left-1/2 top-1/2 z-[1] flex h-[640px] w-[640px] -translate-x-1/2 -translate-y-1/2 items-center justify-center">
        <div
          className={[
            "orch-core-halo absolute h-[78%] w-[78%] rounded-full",
            active ? "orch-core-halo-active" : "",
            hitl ? "orch-core-halo-hitl" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
        <div
          className={[
            "orch-core h-full w-full rounded-full",
            active ? "orch-core-active" : "",
            hitl ? "orch-core-hitl" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
        <div
          className={[
            "orch-core-nucleus absolute h-[92px] w-[92px] rounded-full",
            active ? "orch-core-nucleus-active" : "",
            hitl ? "orch-core-nucleus-hitl" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
      </div>

      <OrbDust active={active} hitl={hitl} />

      <div
        className={[
          "orch-hud pointer-events-none absolute left-1/2 top-1/2 z-[1] h-[440px] w-[440px] -translate-x-1/2 -translate-y-1/2",
          active ? "orch-hud-active" : "",
          hitl ? "orch-hud-hitl" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div className="orch-ring orch-ring-0" />
        <div className="orch-ring orch-ring-1" />
        <div className="orch-ring orch-ring-2" />
        <div className="orch-ring orch-ring-3" />
        <div className="orch-ring orch-ring-ticks" aria-hidden />
      </div>
    </>
  );
}
