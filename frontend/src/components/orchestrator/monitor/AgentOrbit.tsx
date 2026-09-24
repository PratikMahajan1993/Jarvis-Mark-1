"use client";

import type { ActivityItem, AgentNode } from "@/lib/orchestrator";

function latestForAgent(activity: ActivityItem[], code: string): string | undefined {
  const hit = activity.find((item) => item.agent === code);
  return hit?.message;
}

export function AgentOrbit({
  agents,
  activity = [],
  dimmed = false,
  idlePresence = false,
}: {
  agents: AgentNode[];
  activity?: ActivityItem[];
  dimmed?: boolean;
  idlePresence?: boolean;
  active?: boolean;
}) {
  const count = agents.length;
  if (!count) return null;

  return (
    <div
      className={[
        "agent-orbit pointer-events-none relative z-[11] flex w-full items-end justify-center gap-10 px-4 transition-opacity duration-[800ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
        dimmed ? "opacity-35" : idlePresence ? "opacity-[0.42]" : "opacity-100",
      ].join(" ")}
      aria-hidden
    >
      {agents.map((agent) => {
        const caption = latestForAgent(activity, agent.code);
        const stateClass = agent.state || "idle";
        return (
          <div key={agent.id} className="flex w-[4.5rem] flex-col items-center gap-2">
            <div
              className={[
                "agent-sun relative rounded-full",
                stateClass === "active"
                  ? "agent-sun-active h-[18px] w-[18px]"
                  : stateClass === "waiting"
                    ? "agent-sun-waiting h-[16px] w-[16px]"
                    : "agent-sun-idle h-[14px] w-[14px]",
              ].join(" ")}
              title={caption || agent.code}
            />
            <span
              className={[
                "font-mono text-[0.58rem] uppercase tracking-[0.18em]",
                stateClass === "active"
                  ? "text-[#d4a056]/85"
                  : stateClass === "waiting"
                    ? "text-[#c49248]/70"
                    : "text-[color:var(--muted)]/45",
              ].join(" ")}
            >
              {agent.code}
            </span>
          </div>
        );
      })}
    </div>
  );
}
