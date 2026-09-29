"use client";

import { LayoutGroup, motion } from "motion/react";
import { useState } from "react";
import { ConverseStrip } from "@/components/bench/ConverseStrip";
import { DrawingStage, type StageFocusMode } from "@/components/bench/DrawingStage";
import { QuoteSheet, quoteSheetRowsForScene } from "@/components/bench/QuoteSheet";
import type { AgentNode } from "@/lib/orchestrator";
import { SPRING } from "@/lib/pane/springs";
import { conversationToAttachment } from "@/lib/viewerMatch";
import type { SectionProps } from "@/core/sections/defineSection";
import { useDesk } from "@/core/stores/deskStore";
import { useSectionState } from "@/core/stores/sectionStore";

function AgentDots({ agents }: { agents: AgentNode[] }) {
  return (
    <div className="flex items-center gap-1.5" data-agents-status>
      {agents.slice(0, 4).map((agent) => (
        <span
          key={agent.id}
          className={[
            "h-1.5 w-1.5 rounded-full bg-[color:var(--muted)]",
            agent.state ? "bg-[color:var(--accent)] shadow-[0_0_6px_color-mix(in_oklch,var(--accent)_50%,transparent)]" : "",
          ].join(" ")}
          title={agent.code}
        />
      ))}
    </div>
  );
}

const AREAS: Record<StageFocusMode, { stage: string; sheet: string; strip: string }> = {
  normal: { stage: "1 / 1 / 7 / 9", sheet: "1 / 9 / 9 / 13", strip: "7 / 1 / 9 / 9" },
  stage: { stage: "1 / 1 / 7 / 12", sheet: "1 / 12 / 9 / 13", strip: "7 / 1 / 9 / 12" },
};

/** Engineering (order 300): the drawing stage and the quote sheet; the orb is a dim side light. */
export default function EngineeringSection({ id }: SectionProps) {
  const active = useSectionState((s) => s.active === id);
  const scene = useDesk((s) => s.scene);
  const focus = useDesk((s) => s.conversationFocus);
  const voice = useDesk((s) => s.voice);
  const voiceVisible = useDesk((s) => s.voiceVisible);
  const focusTitle = useDesk((s) => s.focusTitle);
  const agents = useDesk((s) => s.agents);
  const sessionId = useDesk((s) => s.activeSession);
  const drawingChat = useDesk((s) => s.drawingChat);
  const [focusMode, setFocusMode] = useState<StageFocusMode>("normal");
  const areas = AREAS[focusMode];

  const hasDrawing = Boolean(
    drawingChat?.open !== false &&
      conversationToAttachment({
        filename: drawingChat?.filename,
        local_name: drawingChat?.local_name,
        local_path: drawingChat?.local_path,
        mime: drawingChat?.mime,
      }),
  );

  return (
    <LayoutGroup id="engineering">
      <div className="grid h-full grid-cols-12 grid-rows-8 gap-3" data-focus={focusMode}>
        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.stage }}>
          <DrawingStage
            scene={scene}
            focus={focus}
            pinRows={quoteSheetRowsForScene(scene)}
            active={active}
            focusMode={focusMode}
            onFocusModeChange={setFocusMode}
          />
        </motion.div>

        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.sheet }}>
          <QuoteSheet scene={scene} hasDrawing={hasDrawing} sessionId={sessionId} focused={focusMode === "stage"} />
        </motion.div>

        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.strip }}>
          <div className="flex h-full min-h-0 items-center gap-4">
            <AgentDots agents={agents} />
            <div className="min-w-0 flex-1">
              <ConverseStrip line={voiceVisible ? voice : focusTitle} />
            </div>
          </div>
        </motion.div>
      </div>
    </LayoutGroup>
  );
}
