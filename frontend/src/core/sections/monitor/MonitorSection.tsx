"use client";

import { ActivityStream } from "@/components/orchestrator/ActivityStream";
import { AgentOrbit } from "@/components/orchestrator/monitor/AgentOrbit";
import { SuggestedTasksPanel } from "@/components/orchestrator/SuggestedTasksPanel";
import { WeatherCard } from "@/components/orchestrator/WeatherCard";
import * as desk from "@/core/desk/controller";
import { useTurnView } from "@/core/desk/useTurnView";
import type { SectionProps } from "@/core/sections/defineSection";
import { useDesk } from "@/core/stores/deskStore";

/** Monitor (order 100): the tall ASCI orb in the centre, findings on the right. */
export function MonitorSection(_props: SectionProps) {
  const { hitl, hitlAction, mode } = useTurnView();
  const voice = useDesk((s) => s.voice);
  const voiceVisible = useDesk((s) => s.voiceVisible);
  const focusTitle = useDesk((s) => s.focusTitle);
  const weatherLine = useDesk((s) => s.weatherLine);
  const suggested = useDesk((s) => s.suggested);
  const agents = useDesk((s) => s.agents);
  const activity = useDesk((s) => s.activity);
  const line = (voiceVisible && voice ? voice : focusTitle).slice(0, 120);

  return (
    <div className="grid h-full grid-cols-12 grid-rows-8 gap-3">
      <div className="relative col-span-3 col-start-1 row-span-3 row-start-1">
        {activity.length > 0 ? <ActivityStream items={activity} className="relative" /> : null}
      </div>

      {weatherLine ? (
        <div className="col-span-3 col-start-10 row-span-2 row-start-1 min-h-0">
          <WeatherCard line={weatherLine} />
        </div>
      ) : null}

      <div className="col-span-3 col-start-10 row-span-6 row-start-3 flex min-h-0 flex-col">
        {hitl ? null : (
          <SuggestedTasksPanel
            variant="findings"
            tasks={suggested}
            onDismiss={desk.taskDismiss}
            onAction={desk.taskAction}
          />
        )}
      </div>

      <div className="pointer-events-none col-span-6 col-start-4 row-start-7 flex items-end justify-center">
        <p className="max-w-[min(520px,90%)] px-3 text-center font-display text-base leading-snug text-[color:var(--fg)]/90 [text-shadow:0_1px_10px_rgba(0,0,0,0.55)]">
          {line}
        </p>
      </div>

      <div className="col-span-6 col-start-4 row-start-8 flex items-end justify-center">
        <AgentOrbit
          agents={agents}
          activity={activity}
          dimmed={Boolean(hitlAction)}
          idlePresence={!hitl && mode === "idle"}
        />
      </div>
    </div>
  );
}
