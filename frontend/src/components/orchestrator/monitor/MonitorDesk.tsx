"use client";

import dynamic from "next/dynamic";
import type { ActivityItem, AgentNode, OrchestratorMode } from "@/lib/orchestrator";
import { AgentOrbit } from "./AgentOrbit";

const EvilEye = dynamic(() => import("@/components/react-bits/EvilEye"), { ssr: false });

export function MonitorDesk({
  mode = "idle",
  agents = [],
  activity = [],
  orbitOn = true,
}: {
  mode?: OrchestratorMode;
  agents?: AgentNode[];
  activity?: ActivityItem[];
  orbitOn?: boolean;
}) {
  const active = mode === "busy" || mode === "listening";
  const hitl = mode === "hitl";

  return (
    <div
      className={[
        "pointer-events-none absolute left-1/2 top-1/2 z-[1] h-[min(640px,72vh)] w-[min(920px,96vw)] -translate-x-1/2 -translate-y-1/2 overflow-visible",
        hitl ? "opacity-35" : active ? "opacity-100" : "opacity-88",
      ].join(" ")}
    >
      <div
        className={[
          "absolute inset-0 z-[11] transition-opacity duration-[800ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
          orbitOn ? "opacity-100" : "opacity-0",
        ].join(" ")}
      >
        <AgentOrbit agents={agents} activity={activity} dimmed={hitl} />
      </div>
      <div className="absolute left-1/2 top-1/2 z-[10] h-[min(640px,72vh)] w-[min(640px,72vw)] -translate-x-1/2 -translate-y-1/2 overflow-visible">
        <EvilEye
          eyeColor="#FF6F37"
          intensity={1.5}
          pupilSize={0.6}
          irisWidth={0.25}
          glowIntensity={0.3}
          scale={0.8}
          noiseScale={1}
          pupilFollow={1}
          flameSpeed={1}
          backgroundColor="#120F17"
        />
      </div>
    </div>
  );
}
