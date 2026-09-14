"use client";

import Magnet from "@/components/react-bits/Magnet";
import type { AgentNode } from "@/lib/orchestrator";

export function Orchestra({
  agents,
  dimmed = false,
}: {
  agents: AgentNode[];
  dimmed?: boolean;
}) {
  return (
    <div
      className={[
        "absolute bottom-32 left-1/2 z-[2] flex -translate-x-1/2 gap-12 transition-opacity duration-[1200ms]",
        dimmed ? "pointer-events-none opacity-10" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {agents.map((agent) => (
        <Magnet
          key={agent.id}
          padding={40}
          magnetStrength={6}
          disabled={dimmed}
          wrapperClassName="inline-flex"
        >
          <div className={`orch-agent flex flex-col items-center gap-3 ${agent.state}`.trim()}>
            <div className="orch-agent-dot h-1.5 w-1.5 rounded-full bg-[color:var(--muted)]" />
            <div className="orch-agent-name font-mono text-[0.65rem] uppercase tracking-[0.1em] text-[color:var(--muted)]">
              [{agent.code}]
            </div>
          </div>
        </Magnet>
      ))}
    </div>
  );
}
