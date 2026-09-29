"use client";

import { useState } from "react";
import { SceneBoard } from "@/components/SceneBoard";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { ConversationRail } from "@/components/orchestrator/ConversationRail";
import { Orchestra } from "@/components/orchestrator/Orchestra";
import { SuggestedTasksPanel } from "@/components/orchestrator/SuggestedTasksPanel";
import { WeatherCard } from "@/components/orchestrator/WeatherCard";
import * as desk from "@/core/desk/controller";
import { useTurnView } from "@/core/desk/useTurnView";
import type { SectionProps } from "@/core/sections/defineSection";
import {
  AMBIENT_SESSION,
  IDLE_VOICE,
  MAX_OPEN_CONVERSATIONS,
  sceneHasBoardContent,
  useDesk,
} from "@/core/stores/deskStore";

function CasualVoiceLine() {
  const { thinking, hitlAction, composeDraft } = useTurnView();
  const voice = useDesk((s) => s.voice);
  const voiceVisible = useDesk((s) => s.voiceVisible);
  const scene = useDesk((s) => s.scene);
  const runStatus = useDesk((s) => s.runStatus);
  const boardOwnsCenter = sceneHasBoardContent(scene) || Boolean(composeDraft);
  const showCenterVoice = voiceVisible && !boardOwnsCenter;

  // While a run is live, keep the tool or spoken line. Never fall back to idle.
  const spoken = (showCenterVoice && voice && voice !== IDLE_VOICE ? voice : "").trim();
  const liveLine = (spoken || runStatus || "Orchestrating…").trim();
  const line =
    (thinking ? liveLine : spoken || (boardOwnsCenter ? "On the board" : IDLE_VOICE)).trim() || IDLE_VOICE;
  const shortLine = line.length > 96 || line.includes("\n") ? `${line.slice(0, 96).trim()}…` : line;

  return (
    <p
      className={[
        "font-display text-[1.35rem] leading-snug tracking-[-0.01em] text-[color:var(--fg)] [text-shadow:0_1px_12px_rgba(0,0,0,0.65)]",
        hitlAction ? "opacity-20 blur-[2px]" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {shortLine}
    </p>
  );
}

/** Casual (order 200): the Cortex orb as the centre, notes left, suggestions right. */
export function CasualSection(_props: SectionProps) {
  const { hitl, hitlAction } = useTurnView();
  const items = useDesk((s) => s.desk);
  const activeSession = useDesk((s) => s.activeSession);
  const activeConversationId = useDesk((s) => s.activeConversationId);
  const dockHidden = useDesk((s) => s.dockHidden);
  const weatherLine = useDesk((s) => s.weatherLine);
  const suggested = useDesk((s) => s.suggested);
  const agents = useDesk((s) => s.agents);
  const scene = useDesk((s) => s.scene);
  const extractCard = useDesk((s) => s.extractCard);
  const [dropHot, setDropHot] = useState(false);
  const hasBoard = sceneHasBoardContent(scene);

  return (
    <>
      {/* The orb centre is viewport-relative; these two layers sit on it, outside the content grid. */}
      <div
        className={[
          "absolute left-1/2 top-[47%] z-[1] h-[min(420px,52vh)] w-[min(420px,52vh)] -translate-x-1/2 -translate-y-1/2 rounded-full transition-shadow",
          dropHot ? "ring-2 ring-[color:var(--accent)]/70" : "",
        ].join(" ")}
        aria-label="Drop a drawing on the orb"
        onDragEnter={(event) => {
          event.preventDefault();
          setDropHot(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDropHot(true);
        }}
        onDragLeave={() => setDropHot(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDropHot(false);
          const file = event.dataTransfer.files?.[0];
          if (file) void desk.dropDrawing(file);
        }}
      />
      <div className="pointer-events-none absolute left-1/2 top-[47%] z-[2] w-[min(420px,70%)] -translate-x-1/2 -translate-y-1/2 px-4 text-center">
        <CasualVoiceLine />
      </div>

      <div className="pointer-events-none relative z-[3] grid h-full grid-cols-12 grid-rows-8 gap-3 [&>*]:pointer-events-auto">
        <div className="col-span-3 col-start-1 row-span-6 row-start-1 min-h-0">
          <ConversationRail
            className="relative"
            items={items}
            openCount={items.length}
            maxOpen={MAX_OPEN_CONVERSATIONS}
            ambientActive={activeSession === AMBIENT_SESSION && !activeConversationId}
            dimmed={hitl}
            hidden={dockHidden}
            onSelectAmbient={() => void desk.focusAmbient()}
            onSelect={(id) => void desk.selectConversation(id)}
            onNewDiscussion={() => void desk.startNewDiscussion()}
          />
        </div>

        <div className="col-span-3 col-start-1 row-start-8 flex items-end">
          <label className="cursor-pointer rounded-md border border-white/15 bg-black/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)] transition hover:border-[color:var(--accent)]/40 hover:text-[color:var(--accent)]">
            Read a document
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void desk.extractDocument(file);
              }}
            />
          </label>
        </div>

        {weatherLine ? (
          <div className="col-span-3 col-start-10 row-span-2 row-start-1 min-h-0">
            <WeatherCard line={weatherLine} />
          </div>
        ) : null}

        <div className="col-span-3 col-start-10 row-span-6 row-start-3 flex min-h-0 flex-col">
          {hitl ? null : (
            <SuggestedTasksPanel
              variant="suggested"
              tasks={suggested}
              onDismiss={desk.taskDismiss}
              onAction={desk.taskAction}
            />
          )}
        </div>

        <div className="col-span-6 col-start-4 row-span-2 row-start-6 flex min-h-0 flex-col justify-end gap-2 !pointer-events-none [&>*]:pointer-events-auto">
          {extractCard ? (
            <div className="min-h-0 shrink overflow-hidden rounded-2xl border border-[color:var(--border)] bg-black/55">
              <div data-lenis-prevent className="max-h-[22vh] overflow-y-auto overscroll-contain p-4">
                <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--accent)]">
                  {extractCard.title}
                </p>
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[color:var(--fg)]/90">
                  {extractCard.text}
                </pre>
              </div>
            </div>
          ) : null}
          {hasBoard ? (
            <div data-lenis-prevent className="min-h-0 shrink">
              <SpotlightCard
                className="orch-board w-full rounded-2xl border border-[color:var(--border)] bg-black/35"
                bodyClassName="max-h-[22vh] overflow-y-auto overscroll-contain p-3"
              >
                <SceneBoard scene={scene} compact />
              </SpotlightCard>
            </div>
          ) : null}
        </div>

        <div className="col-span-6 col-start-4 row-start-8 flex items-end justify-center">
          <Orchestra agents={agents} dimmed={Boolean(hitlAction)} />
        </div>
      </div>
    </>
  );
}
