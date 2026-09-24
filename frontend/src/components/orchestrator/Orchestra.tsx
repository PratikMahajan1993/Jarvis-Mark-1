"use client";

import Magnet from "@/components/react-bits/Magnet";
import type { AgentNode } from "@/lib/orchestrator";

/** Casual agents — small status dots only (codes live in title for hover). */
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
        "flex items-end justify-center gap-8 transition-opacity duration-[1200ms]",
        dimmed ? "pointer-events-none opacity-10" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {agents.map((agent) => (
        <Magnet
          key={agent.id}
          padding={20}
          magnetStrength={6}
          disabled={dimmed}
          wrapperClassName="inline-flex"
        >
          <div
            className={`orch-agent flex items-center justify-center ${agent.state}`.trim()}
            title={agent.code}
          >
            <div className="orch-agent-dot h-1.5 w-1.5 rounded-full bg-[color:var(--muted)]" />
          </div>
        </Magnet>
      ))}
    </div>
  );
}
