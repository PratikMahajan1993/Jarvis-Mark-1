"use client";

import { LayoutGroup, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { EngineeringDeck, engineeringTasks } from "./EngineeringDeck";
import { stageMorphLayoutId } from "./deckCardMeta";
import type { DropIntent } from "./dropIntent";
import * as desk from "@/core/desk/controller";
import { registerServerDraft } from "@/core/desk/drafts";
import { ConverseStrip } from "@/components/bench/ConverseStrip";
import { DrawingStage, type StageFocusMode } from "@/components/bench/DrawingStage";
import { QuoteSheet, quoteSheetRowsForScene } from "@/components/bench/QuoteSheet";
import type { AgentNode } from "@/lib/orchestrator";
import { SPRING } from "@/lib/pane/springs";
import { conversationToAttachment } from "@/lib/viewerMatch";
import type { SectionProps } from "@/core/sections/defineSection";
import { sectionVoiceLine } from "@/core/desk/sectionVoice";
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

function DropIntentPrompt({ onChoose }: { onChoose: (intent: DropIntent) => void }) {
  return (
    <div
      className="pointer-events-auto absolute bottom-24 left-1/2 z-[3] w-[min(420px,90%)] -translate-x-1/2 rounded-2xl border border-[color:var(--border)] bg-black/75 p-4 text-center shadow-[0_18px_40px_rgba(0,0,0,0.45)]"
      role="dialog"
      aria-label="Drawing drop intent"
      data-deck-drop-prompt
    >
      <p className="font-display text-base text-[color:var(--fg)]">
        Start a quote workflow, or only view the drawing and discuss it?
      </p>
      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          className="rounded-full border border-[color:var(--accent)]/50 bg-[color:var(--accent)]/15 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--accent)]"
          onClick={() => onChoose("quote")}
        >
          Start quote
        </button>
        <button
          type="button"
          className="rounded-full border border-[color:var(--border)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]"
          onClick={() => onChoose("discuss")}
        >
          View and discuss
        </button>
      </div>
    </div>
  );
}

const AREAS: Record<StageFocusMode, { stage: string; sheet: string; strip: string }> = {
  normal: { stage: "1 / 1 / 7 / 9", sheet: "1 / 9 / 9 / 13", strip: "7 / 1 / 9 / 9" },
  stage: { stage: "1 / 1 / 7 / 12", sheet: "1 / 12 / 9 / 13", strip: "7 / 1 / 9 / 12" },
};

/** Idle: the bench keeps the stage; the task deck sits under it, above the baton. */
const IDLE_AREAS: Record<StageFocusMode, { stage: string; sheet: string; strip: string; deck: string }> = {
  normal: { stage: "1 / 1 / 6 / 9", deck: "6 / 1 / 8 / 9", sheet: "1 / 9 / 9 / 13", strip: "8 / 1 / 9 / 9" },
  stage: { stage: "1 / 1 / 6 / 12", deck: "6 / 1 / 8 / 12", sheet: "1 / 12 / 9 / 13", strip: "8 / 1 / 9 / 12" },
};

/** Engineering (order 300): the drawing stage and the quote sheet; the orb is a dim side light. */
export default function EngineeringSection({ id }: SectionProps) {
  const active = useSectionState((s) => s.active === id);
  const reduced = useReducedMotion();
  const scene = useDesk((s) => s.scene);
  const focus = useDesk((s) => s.conversationFocus);
  const voice = useDesk((s) => s.voice);
  const voiceVisible = useDesk((s) => s.voiceVisible);
  const focusTitle = useDesk((s) => s.focusTitle);
  const agents = useDesk((s) => s.agents);
  const sessionId = useDesk((s) => s.activeSession);
  const drawingChat = useDesk((s) => s.drawingChat);
  const [focusMode, setFocusMode] = useState<StageFocusMode>("normal");
  const [dropHighlight, setDropHighlight] = useState(false);
  const [dropPrompt, setDropPrompt] = useState(false);
  const conversations = useDesk((s) => s.desk);
  const tasks = engineeringTasks(conversations);
  const activeConversationId = useDesk((s) => s.activeConversationId);

  useEffect(
    () =>
      registerServerDraft(() =>
        activeConversationId ? { key: `engineering-${activeConversationId}`, body: { focusMode } } : null,
      ),
    [activeConversationId, focusMode],
  );

  useEffect(() => {
    if (!dropHighlight) return;
    const timer = window.setTimeout(() => setDropHighlight(false), 2400);
    return () => window.clearTimeout(timer);
  }, [dropHighlight]);

  const focusAttachment = conversationToAttachment(focus);
  const chatAttachment =
    drawingChat?.open === false
      ? null
      : conversationToAttachment({
          filename: drawingChat?.filename,
          local_name: drawingChat?.local_name,
          local_path: drawingChat?.local_path,
          mime: drawingChat?.mime,
        });
  const hasDrawing = Boolean(chatAttachment || focusAttachment);
  const noActiveTask = !hasDrawing;
  const areas = noActiveTask ? IDLE_AREAS[focusMode] : AREAS[focusMode];
  /** Active stage task leaves the pile so shared layoutId is unique (X9 morph). */
  const deckItems =
    hasDrawing && activeConversationId ? tasks.filter((t) => t.id !== activeConversationId) : tasks;
  const morphLayoutId =
    !reduced && hasDrawing && activeConversationId ? stageMorphLayoutId(activeConversationId) : undefined;

  const onDropOpened = () => {
    setDropHighlight(true);
    setDropPrompt(true);
  };

  const onDropIntent = (intent: DropIntent) => {
    setDropPrompt(false);
    void desk.resolveEngineeringDropIntent(intent);
  };

  return (
    <LayoutGroup id="engineering">
      <div className="relative grid h-full grid-cols-12 grid-rows-8 gap-3" data-focus={focusMode}>
        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.stage }}>
          <DrawingStage
            scene={scene}
            focus={focus}
            pinRows={quoteSheetRowsForScene(scene)}
            active={active}
            focusMode={focusMode}
            onFocusModeChange={setFocusMode}
            morphLayoutId={morphLayoutId}
            highlight={dropHighlight}
          />
        </motion.div>

        {noActiveTask ? (
          <div
            className="pointer-events-auto relative z-[2] min-h-0 min-w-0 overflow-visible"
            style={{ gridArea: IDLE_AREAS[focusMode].deck }}
            data-slot="engineering.deck-empty"
          >
            <EngineeringDeck items={deckItems} hero onDropOpened={onDropOpened} />
          </div>
        ) : deckItems.length ? (
          <div className="absolute bottom-16 left-2 z-[2] h-52 w-40" data-slot="engineering.side">
            <EngineeringDeck items={deckItems} hero={false} onDropOpened={onDropOpened} />
          </div>
        ) : null}

        {dropPrompt ? <DropIntentPrompt onChoose={onDropIntent} /> : null}

        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.sheet }}>
          <QuoteSheet scene={scene} hasDrawing={hasDrawing} sessionId={sessionId} focused={focusMode === "stage"} />
        </motion.div>

        <motion.div layout transition={SPRING.pane} className="relative min-h-0 min-w-0" style={{ gridArea: areas.strip }}>
          <div className="flex h-full min-h-0 items-center gap-4">
            <AgentDots agents={agents} />
            <div className="min-w-0 flex-1">
              <ConverseStrip line={sectionVoiceLine(voiceVisible ? voice : "", focusTitle)} />
            </div>
          </div>
        </motion.div>
      </div>
    </LayoutGroup>
  );
}
