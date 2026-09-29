"use client";

import { Profiler, useEffect, useState } from "react";
import { PerfOverlay } from "@/components/pane/PerfOverlay";
import { isJarvisPerfMode, recordOrchestratorShellCommit } from "@/lib/pane/perf";
import "@/lib/pane/perf";
import type { ChatResponse, PendingAction, Scene } from "@/lib/types";
import type { ActivityItem, AgentNode, OrchestratorMode } from "@/lib/orchestrator";
import { isBusy, type JarvisState } from "@/lib/orchestratorFsm";
import { SceneBoard } from "../SceneBoard";
import ClickSpark from "@/components/react-bits/ClickSpark";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { ConverseStrip } from "@/components/bench/ConverseStrip";
import { DrawingViewer } from "@/components/DrawingViewer";
import { conversationToAttachment } from "@/lib/viewerMatch";
import { DrawingStage } from "@/components/bench/DrawingStage";
import { QuoteSheet, quoteSheetRowsForScene } from "@/components/bench/QuoteSheet";
import { ActivityStream } from "./ActivityStream";
import { CommandBaton } from "./CommandBaton";
import { ConversationRail } from "./ConversationRail";
import { DraftComposeModal } from "./DraftComposeModal";
import { JarvisCore } from "./JarvisCore";
import { HitlModal } from "./HitlModal";
import { AgentOrbit } from "./monitor/AgentOrbit";
import { Orchestra } from "./Orchestra";
import { SuggestedTasksPanel, type SuggestedTask } from "./SuggestedTasksPanel";
import { ConnectGoogleModal } from "./ConnectGoogleModal";
import { PreferencesPanel } from "./PreferencesPanel";
import { WeatherCard } from "./WeatherCard";
import { TurnStageLine, type TurnEventPayload } from "./TurnStageLine";
import { Pane } from "@/components/pane/Pane";
import { useDisplayLens, useLens, usePane } from "@/lib/pane/paneStore";
import { useWatchFindingsGlance } from "@/components/pane/useWatchFindingsGlance";
import { useValueWhenSettled } from "@/lib/pane/useLensSettled";
import { DeskController } from "@/core/desk/DeskController";
import * as desk from "@/core/desk/controller";
import {
  AMBIENT_SESSION,
  MAX_OPEN_CONVERSATIONS,
  sceneHasBoardContent,
  setDesk,
  useDesk,
} from "@/core/stores/deskStore";
import { sectionStore, setWorkspace, togglePinned, useSectionState } from "@/core/stores/sectionStore";
import { useTurn } from "@/core/stores/turnStore";

const IDLE_VOICE = "Awaiting instruction.";

function LensSparkShell({ children }: { children: React.ReactNode }) {
  const lens = useLens();
  const sparkColor = lens === "watch" ? "#FF6F37" : "#7dffe0";
  return (
    <ClickSpark className="relative flex h-screen flex-col overflow-hidden" sparkColor={sparkColor}>
      {children}
    </ClickSpark>
  );
}

function BenchStagePanel({
  scene,
  focus,
}: {
  scene: Scene;
  focus: Record<string, unknown>;
}) {
  const gatedScene = useValueWhenSettled(scene);
  const pinRows = quoteSheetRowsForScene(gatedScene);
  return (
    <DrawingStage scene={gatedScene} focus={focus} pinRows={pinRows} />
  );
}

function BenchQuotePanel({
  scene,
  hasDrawing,
  sessionId,
}: {
  scene: Scene;
  hasDrawing: boolean;
  sessionId: string;
}) {
  const gatedScene = useValueWhenSettled(scene);
  return <QuoteSheet scene={gatedScene} hasDrawing={hasDrawing} sessionId={sessionId} />;
}

function BenchAgentDots({ agents }: { agents: AgentNode[] }) {
  return (
    <div className="flex items-center gap-1.5">
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

function TasksDockPanel({
  tasks,
  hitl,
  onDismiss,
  onAction,
}: {
  tasks: SuggestedTask[];
  hitl: boolean;
  onDismiss: (id: string) => void;
  onAction: (task: SuggestedTask, actionId: string) => void;
}) {
  const displayLens = useDisplayLens();
  const watchFindings = displayLens === "watch" && !hitl;
  useWatchFindingsGlance(tasks, watchFindings);
  if (hitl) {
    return <div className="h-full min-h-[120px]" aria-hidden />;
  }
  return (
    <div className="flex h-full max-h-full min-h-0 flex-col overflow-hidden p-2">
      <SuggestedTasksPanel
        variant={displayLens === "watch" ? "findings" : "suggested"}
        tasks={tasks}
        onDismiss={onDismiss}
        onAction={onAction}
      />
    </div>
  );
}

function AgentsDockPanel({
  agents,
  activity,
  hitl,
}: {
  agents: AgentNode[];
  activity: ActivityItem[];
  hitl: boolean;
}) {
  const displayLens = useDisplayLens();
  const presenceMode = usePane((s) => s.mode);
  if (displayLens === "watch") {
    return (
      <div className="flex h-full items-end justify-center pb-3">
        <AgentOrbit
          agents={agents}
          activity={activity}
          dimmed={hitl}
          idlePresence={!hitl && presenceMode === "idle"}
        />
      </div>
    );
  }
  if (displayLens === "converse") {
    return (
      <div className="flex h-full w-full items-end justify-center pb-2">
        <Orchestra agents={agents} dimmed={hitl} />
      </div>
    );
  }
  return null;
}

function VoiceDockPanel({
  voice,
  voiceVisible,
  showCenterVoice,
  boardOwnsCenter,
  hitlAction,
  scene,
  sending,
  ledgerTurnId,
  error,
  focusTitle,
  prefsName,
  orchestratorMode,
  onLedgerTurnComplete,
  onLedgerTurnFailed,
  onLedgerReconcile,
  compose,
  listening,
  batonDisabled,
  batonHidden,
  onComposeChange,
  onComposeSubmit,
  onMic,
  onDropDrawing,
  thinking,
  runStatus = "",
  onCancel,
  extractCard,
  onExtractFile,
}: {
  voice: string;
  voiceVisible: boolean;
  showCenterVoice: boolean;
  boardOwnsCenter: boolean;
  hitlAction: PendingAction | null;
  scene: Scene;
  sending: boolean;
  ledgerTurnId: string | null;
  error: string;
  focusTitle: string;
  prefsName: string;
  orchestratorMode: OrchestratorMode;
  onLedgerTurnComplete: (output: ChatResponse) => void;
  onLedgerTurnFailed: (info: { error?: string; stage?: string; state?: string }) => void;
  onLedgerReconcile: (turnId: string, payload: TurnEventPayload) => void;
  compose: string;
  listening: boolean;
  batonDisabled?: boolean;
  batonHidden?: boolean;
  onComposeChange: (value: string) => void;
  onComposeSubmit: (value: string) => void;
  onMic: () => void;
  onDropDrawing: (file: File) => void;
  thinking?: boolean;
  runStatus?: string;
  onCancel?: () => void;
  extractCard?: { title: string; text: string } | null;
  onExtractFile?: (file: File) => void;
}) {
  const activeLens = useDisplayLens();
  const [dropHot, setDropHot] = useState(false);
  const gatedScene = useValueWhenSettled(scene);
  const extras = (
    <>
      {thinking ? (
        <button
          type="button"
          className="pointer-events-auto absolute bottom-6 right-4 z-[6] rounded-md border border-[color:var(--accent)]/60 bg-black/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[color:var(--accent)]"
          onClick={() => onCancel?.()}
        >
          Cancel
        </button>
      ) : null}
      {activeLens === "converse" ? (
        <label className="pointer-events-auto absolute bottom-6 left-4 z-[6] cursor-pointer rounded-md border border-white/15 bg-black/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]">
          Read a document
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) onExtractFile?.(file);
            }}
          />
        </label>
      ) : null}
      {activeLens === "converse" && extractCard ? (
        <div className="pointer-events-auto absolute inset-x-8 bottom-16 z-[5] max-h-[34%] overflow-hidden rounded-2xl border border-[color:var(--border)] bg-black/55">
          <div className="max-h-[28vh] overflow-y-auto p-4">
            <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--accent)]">
              {extractCard.title}
            </p>
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[color:var(--fg)]/90">
              {extractCard.text}
            </pre>
          </div>
        </div>
      ) : null}
    </>
  );

  if (activeLens === "watch") {
    const line = (voiceVisible && voice ? voice : focusTitle).slice(0, 120);
    return (
      <div className="relative flex h-full min-h-0 items-end justify-center pb-1">
        <p className="max-w-[min(520px,90%)] px-3 text-center font-display text-base leading-snug text-[color:var(--fg)]/90 [text-shadow:0_1px_10px_rgba(0,0,0,0.55)]">
          {line}
        </p>
        {extras}
      </div>
    );
  }

  if (activeLens === "bench") {
    const line = voiceVisible ? voice : focusTitle;
    return (
      <div className="relative h-full min-h-0">
      <ConverseStrip
        line={line}
        baton={
          <CommandBaton
            value={compose}
            onChange={onComposeChange}
            onSubmit={onComposeSubmit}
            onMic={onMic}
            listening={listening}
            disabled={batonDisabled}
            hidden={batonHidden}
            absolute={false}
          />
        }
      />
      {extras}
      </div>
    );
  }

  /* Converse: while a run is live, keep the tool or spoken line. Never fall back to idle. */
  const spoken = (showCenterVoice && voice && voice !== IDLE_VOICE ? voice : "").trim();
  const liveLine = (spoken || runStatus || "Orchestrating…").trim();
  const line = (
    thinking ? liveLine : spoken || (boardOwnsCenter ? "On the board" : IDLE_VOICE)
  ).trim() || IDLE_VOICE;
  const shortLine = line.length > 96 || line.includes("\n") ? `${line.slice(0, 96).trim()}…` : line;
  return (
    <div className="pointer-events-none relative flex h-full min-h-0 w-full items-center justify-center overflow-visible">
      <JarvisCore mode={orchestratorMode} />
      <div
        className={[
          "pointer-events-auto absolute left-1/2 top-1/2 z-[2] h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full",
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
          if (file) onDropDrawing(file);
        }}
      />
      <div className="pointer-events-none relative z-[2] max-w-[min(420px,70%)] px-4 text-center">
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
      </div>
      {sceneHasBoardContent(gatedScene) ? (
        <div className="pointer-events-auto absolute inset-x-4 bottom-2 z-[3] max-h-[28%] overflow-hidden">
          <SpotlightCard
            className="orch-board w-full rounded-2xl border border-[color:var(--border)] bg-black/35"
            bodyClassName="max-h-[22vh] overflow-y-auto p-3"
          >
            <SceneBoard scene={gatedScene} compact />
          </SpotlightCard>
        </div>
      ) : null}
      {sending ? (
        <div className="pointer-events-none absolute bottom-6 z-[3] flex flex-col items-center gap-2" aria-live="polite">
          <div className="orch-sending-ring" />
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--accent)]/80">
            Transmitting…
          </p>
        </div>
      ) : null}
      <div className="pointer-events-none absolute bottom-2 left-1/2 z-[3] -translate-x-1/2">
        <TurnStageLine
          turnId={ledgerTurnId}
          onComplete={onLedgerTurnComplete}
          onFailed={onLedgerTurnFailed}
          onReconcile={onLedgerReconcile}
        />
      </div>
      {error ? (
        <p className="pointer-events-none absolute bottom-10 z-[3] max-w-md px-4 text-center font-mono text-xs text-red-300/80">
          {error}
        </p>
      ) : null}
      <span className="sr-only">
        {prefsName} · {focusTitle}
      </span>
      {extras}
    </div>
  );
}

function modeToOrchestratorMode(state: JarvisState): OrchestratorMode {
  switch (state.mode) {
    case "LISTENING":
      return "listening";
    case "AWAITING_HITL":
      return "hitl";
    case "THINKING":
    case "SPEAKING":
    case "EXECUTING":
      return "busy";
    default:
      return "idle";
  }
}

export function OrchestratorShell() {
  const state = useTurn();
  const d = useDesk((s) => s);
  const workspace = useSectionState((s) => s.workspace);
  const workspacePinned = useSectionState((s) => s.pinned);

  // Until the scroll engine lands, a section request just switches the lens.
  useEffect(
    () =>
      sectionStore.subscribe(() => {
        const req = sectionStore.get().request;
        if (!req) return;
        const ws = req.section as typeof workspace;
        if (ws !== sectionStore.get().workspace) setWorkspace(ws, req.reason);
        if (sectionStore.get().active !== ws) sectionStore.set({ active: ws });
      }),
    [],
  );

  const hitlAction: PendingAction | null =
    state.mode === "AWAITING_HITL" && state.action.kind !== "email_compose" ? state.action : null;
  const composeDraft: PendingAction | null =
    state.mode === "AWAITING_HITL" && state.action.kind === "email_compose" ? state.action : null;
  const hitl = state.mode === "AWAITING_HITL";
  const confirmListening = state.mode === "AWAITING_HITL" && state.listening;
  const sending = state.mode === "EXECUTING";
  const listening = state.mode === "LISTENING";
  const busy = isBusy(state);
  const shownError = d.error || (state.mode === "IDLE" && state.error ? state.error : "");
  const mode: OrchestratorMode = modeToOrchestratorMode(state);
  const boardOwnsCenter = sceneHasBoardContent(d.scene) || Boolean(composeDraft);
  const showCenterVoice = d.voiceVisible && !boardOwnsCenter;
  const setCompose = (value: string) => setDesk({ compose: value });
  const drawingChat = d.drawingChat;
  const drawingAttachment =
    drawingChat?.open === false
      ? null
      : conversationToAttachment({
          filename: drawingChat?.filename,
          local_name: drawingChat?.local_name,
          local_path: drawingChat?.local_path,
          mime: drawingChat?.mime,
        });

  const shellTree = (
    <LensSparkShell>
      <DeskController />
      <Pane
        workspace={workspace}
        workspacePinned={workspacePinned}
        orchestratorMode={mode}
        assistantName={d.prefs?.assistant_name || "Jarvis"}
        focusTitle={d.focusTitle}
        dimmed={hitl}
        batonHidden={hitl}
        batonDisabled={busy || hitl}
        compose={d.compose}
        listening={listening}
        onComposeChange={setCompose}
        onComposeSubmit={(value) => void desk.send(value)}
        onMic={() => void desk.startMic()}
        onSelectWorkspace={(ws) => desk.goToSection(ws, "switcher")}
        onTogglePin={() => togglePinned(d.activeSession)}
        onOpenPrefs={() => setDesk({ prefsOpen: true })}
        className="flex-1"
        panels={{
          voice: (
            <VoiceDockPanel
              voice={d.voice}
              voiceVisible={d.voiceVisible}
              showCenterVoice={showCenterVoice}
              boardOwnsCenter={boardOwnsCenter}
              hitlAction={hitlAction}
              scene={d.scene}
              sending={sending}
              ledgerTurnId={d.ledgerTurnId}
              error={shownError}
              focusTitle={d.focusTitle}
              prefsName={d.prefs?.assistant_name || "Jarvis"}
              orchestratorMode={mode}
              onLedgerTurnComplete={desk.onLedgerTurnComplete}
              onLedgerTurnFailed={desk.onLedgerTurnFailed}
              onLedgerReconcile={desk.onLedgerReconcile}
              compose={d.compose}
              listening={listening}
              batonDisabled={busy || hitl}
              batonHidden={hitl}
              onComposeChange={setCompose}
              onComposeSubmit={(value) => void desk.send(value)}
              onMic={() => void desk.startMic()}
              onDropDrawing={(file) => void desk.dropDrawing(file)}
              thinking={state.mode === "THINKING"}
              runStatus={d.runStatus}
              onCancel={() => void desk.cancelRun()}
              extractCard={d.extractCard}
              onExtractFile={(file) => void desk.extractDocument(file)}
            />
          ),
          notes: (
            <ConversationRail
              items={d.desk}
              openCount={d.desk.length}
              maxOpen={MAX_OPEN_CONVERSATIONS}
              ambientActive={d.activeSession === AMBIENT_SESSION && !d.activeConversationId}
              dimmed={hitl}
              hidden={d.dockHidden}
              onSelectAmbient={() => void desk.focusAmbient()}
              onSelect={(id) => void desk.selectConversation(id)}
              onNewDiscussion={() => void desk.startNewDiscussion()}
            />
          ),
          weather: d.weatherLine ? (
            <div className="p-2">
              <WeatherCard line={d.weatherLine} />
            </div>
          ) : null,
          tasks: (
            <TasksDockPanel tasks={d.suggested} hitl={hitl} onDismiss={desk.taskDismiss} onAction={desk.taskAction} />
          ),
          agents: <AgentsDockPanel agents={d.agents} activity={d.activity} hitl={Boolean(hitlAction)} />,
          agentsStatus: <BenchAgentDots agents={d.agents} />,
          activity: d.activity.length > 0 ? <ActivityStream items={d.activity} /> : null,
          stage: <BenchStagePanel scene={d.scene} focus={d.conversationFocus} />,
          sheet: <BenchQuotePanel scene={d.scene} hasDrawing={Boolean(drawingAttachment)} sessionId={d.activeSession} />,
        }}
      />

      <HitlModal
        action={hitlAction}
        visible={Boolean(hitlAction)}
        listening={confirmListening}
        busy={busy}
        onDecide={(id, approved) => void desk.decide(id, approved)}
      />

      <ConnectGoogleModal
        status={d.googleStatus}
        visible={d.googleConnectOpen}
        onLater={() => setDesk({ googleConnectOpen: false })}
        onOpenPreferences={() => setDesk({ googleConnectOpen: false, prefsOpen: true })}
        onPromptInteract={() => {
          if (d.googleStatus) desk.announceGoogleConnect(d.googleStatus);
        }}
      />

      <PreferencesPanel
        open={d.prefsOpen}
        prefs={d.prefs}
        onClose={() => setDesk({ prefsOpen: false })}
        onSave={desk.savePreferences}
      />

      <DraftComposeModal
        action={composeDraft}
        visible={Boolean(composeDraft)}
        listening={confirmListening}
        busy={busy}
        onFieldsChange={desk.setComposeFields}
        onDecide={(id, approved, fields) => void desk.decide(id, approved, fields)}
      />

      {drawingAttachment && drawingChat ? (
        <DrawingViewer
          chatMode
          notes={drawingChat.notes || ""}
          attachment={drawingAttachment}
          onClose={desk.closeDrawing}
          onWhisper={(line) => desk.showVoice(line)}
        />
      ) : null}
    </LensSparkShell>
  );

  return (
    <>
      {isJarvisPerfMode() ? (
        <>
          <Profiler id="OrchestratorShell" onRender={recordOrchestratorShellCommit}>
            <span data-orch-shell-probe hidden aria-hidden />
          </Profiler>
          <PerfOverlay />
        </>
      ) : null}
      {shellTree}
    </>
  );
}
