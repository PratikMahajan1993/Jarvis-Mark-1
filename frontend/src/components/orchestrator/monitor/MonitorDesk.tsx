"use client";

import type { ActivityItem, AgentNode, OrchestratorMode } from "@/lib/orchestrator";
import { AgentOrbit } from "./AgentOrbit";

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
    </div>
  );
}
