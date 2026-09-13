"use client";

import { useState } from "react";
import type { Conversation, PendingAction, RfqPublic, Scene, Widget } from "@/lib/types";
import { shallICopy } from "./ConfirmBar";
import { SceneBoard } from "./SceneBoard";
import { HudButton, Panel, Ring, StatusDot, type Accent } from "./hud/Hud";

const LABELS: Record<string, string> = {
  drawing: "Drawings",
  mail: "Mail",
  research: "Research",
  files: "Files",
};

const CATEGORY_ACCENT: Record<string, Accent> = {
  drawing: "cyan",
  mail: "violet",
  research: "magenta",
  files: "white",
};

const CORE_GLOW: Record<Accent, string> = {
  cyan: "bg-cyan/80 shadow-[0_0_28px_rgba(62,224,212,0.35)]",
  violet: "bg-violet/80 shadow-[0_0_28px_rgba(164,140,242,0.35)]",
  magenta: "bg-magenta/80 shadow-[0_0_28px_rgba(232,121,249,0.35)]",
  amber: "bg-amber/80 shadow-[0_0_28px_rgba(245,193,108,0.4)]",
  red: "bg-red/80 shadow-[0_0_28px_rgba(248,113,113,0.35)]",
  green: "bg-green/80 shadow-[0_0_28px_rgba(74,222,128,0.35)]",
  white: "bg-white/50 shadow-[0_0_24px_rgba(255,255,255,0.2)]",
};

function asJobs(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object");
}

const EPHEMERAL_SCENE = new Set(["cancelled", "alright", "sent"]);

function drawingRfqScene(row: Conversation, rfqs: ReadonlyArray<RfqPublic> = []): Scene {
  const scene = row.scene || { title: "", widgets: [] };
  const ephemeral = EPHEMERAL_SCENE.has((scene.title || "").trim().toLowerCase());
  const dropScene = row.category === "drawing" && ephemeral;
  const widgets: Widget[] = dropScene ? [] : [...(scene.widgets || [])];
  if (row.category !== "drawing") {
    return { title: scene.title, subtitle: scene.subtitle, widgets };
  }
  const focus = row.focus || {};
  const extract =
    focus.extract && typeof focus.extract === "object" ? (focus.extract as Record<string, unknown>) : {};
  const matched = rfqs.find((item) => item.conversation_id === row.id);
  const extra = row as Conversation & { catch?: unknown; similar_jobs?: unknown };
  const catchLine = [focus.catch, extra.catch, extract.catch, matched?.catch].find(
    (value) => typeof value === "string" && value.trim(),
  ) as string | undefined;
  const similar = asJobs(focus.similar_jobs ?? extra.similar_jobs ?? extract.similar_jobs ?? matched?.similar_jobs);
  const hasCatch = widgets.some((widget) => {
    const label = `${widget.title || ""} ${widget.label || ""}`.toLowerCase();
    return label.includes("catch") || (catchLine && (widget.text === catchLine || String(widget.value ?? "") === catchLine));
  });
  if (catchLine && !hasCatch) {
    widgets.unshift({ type: "markdown", title: "Catch", text: catchLine.trim() });
  }
  const hasSimilar = widgets.some((widget) => /similar/i.test(`${widget.title || ""} ${widget.label || ""}`));
  if (similar.length && !hasSimilar) {
    widgets.push({
      type: "table",
      title: "Similar jobs",
      columns: ["Part", "Material", "Machine", "Cycle", "Notes"],
      rows: similar.map((job) => [
        String(job.part_name ?? ""),
        String(job.material ?? ""),
        String(job.machine ?? ""),
        job.cycle_min == null || job.cycle_min === "" ? "" : String(job.cycle_min),
        String(job.geometry_notes ?? ""),
      ]),
    });
  }
  return {
    title: dropScene ? row.title : scene.title || row.title,
    subtitle: dropScene ? undefined : scene.subtitle,
    widgets,
  };
}

function bubbleInitials(title: string): string {
  const parts = title
    .trim()
    .split(/[\s._-]+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function categoryAccent(category: string): Accent {
  return CATEGORY_ACCENT[category] || "white";
}

export function ConversationDock({
  conversations,
  rfqs = [],
  focusedId,
  busyId,
  hidden,
  onFocus,
  onMinimize,
  onExpand,
  onSend,
  onConfirm,
}: {
  conversations: Conversation[];
  rfqs?: ReadonlyArray<RfqPublic>;
  focusedId: string | null;
  busyId: string | null;
  hidden?: boolean;
  onFocus: (id: string) => void;
  onMinimize: (id: string) => void;
  onExpand: (id: string) => void;
  onSend: (id: string, message: string) => void;
  onConfirm: (id: string, actionId: string, approved: boolean) => void;
}) {
  if (hidden || !conversations.length) return null;
  const maximized = conversations.find((row) => !row.minimized) || null;

  return (
    <>
      {maximized ? (
        <div
          className="pointer-events-auto fixed inset-0 z-20 grid place-items-center bg-black/45 backdrop-blur-[2px] animate-[conv-fade_180ms_ease-out]"
          onClick={() => onMinimize(maximized.id)}
        >
          <div
            className="h-[70vh] w-[70vw] max-w-5xl animate-[conv-pop_220ms_ease-out]"
            onClick={(event) => event.stopPropagation()}
          >
            <ConversationWindow
              row={maximized}
              rfqs={rfqs}
              focused={focusedId === maximized.id}
              busy={busyId === maximized.id}
              onFocus={() => onFocus(maximized.id)}
              onMinimize={() => onMinimize(maximized.id)}
              onSend={(message) => onSend(maximized.id, message)}
              onConfirm={(actionId, approved) => onConfirm(maximized.id, actionId, approved)}
            />
          </div>
        </div>
      ) : null}

      <aside className="pointer-events-none absolute inset-y-0 right-0 z-30 flex w-28 flex-col items-end justify-start gap-3 overflow-y-auto overflow-x-visible py-3 pr-4">
        {conversations.map((row) => {
          const active = busyId === row.id || row.waiting || row.status === "warming";
          const open = !row.minimized;
          const focused = focusedId === row.id;
          const accent = active ? "amber" : open || focused ? "cyan" : categoryAccent(row.category);
          return (
            <button
              key={row.id}
              type="button"
              title={row.title}
              onClick={() => (open ? onFocus(row.id) : onExpand(row.id))}
              className="conv-bubble pointer-events-auto relative h-20 w-20 shrink-0 rounded-full border-0 bg-transparent p-0 transition-transform duration-200 hover:scale-105"
              aria-label={`${open ? "Focus" : "Open"} ${row.title}`}
            >
              <Ring
                size={80}
                accent={accent}
                thickness={1.5}
                spinning={active}
                className="pointer-events-none absolute inset-0"
              />
              <span className="pointer-events-none absolute inset-0 grid place-items-center">
                <span
                  className={`grid h-10 w-10 place-items-center rounded-full font-mono text-[11px] tracking-wide text-[#020508] ${CORE_GLOW[accent]}`}
                >
                  {bubbleInitials(row.title)}
                </span>
              </span>
              {active ? <StatusDot accent="amber" pulse className="absolute right-1 top-1" /> : null}
            </button>
          );
        })}
      </aside>
    </>
  );
}

function ConversationWindow({
  row,
  rfqs,
  focused,
  busy,
  onFocus,
  onMinimize,
  onSend,
  onConfirm,
}: {
  row: Conversation;
  rfqs: ReadonlyArray<RfqPublic>;
  focused: boolean;
  busy: boolean;
  onFocus: () => void;
  onMinimize: () => void;
  onSend: (message: string) => void;
  onConfirm: (actionId: string, approved: boolean) => void;
}) {
  const [draft, setDraft] = useState("");
  const pending = (row.pending || [])[0] as PendingAction | undefined;
  const pendingCopy = pending ? shallICopy(pending) : null;
  const scene = drawingRfqScene(row, rfqs);
  const turns = (row.turns || []).slice(-12);
  return (
    <div className="flex h-full min-h-0 flex-col" onClick={onFocus}>
      <Panel
        accent={focused ? "cyan" : "white"}
        className="flex h-full min-h-0 flex-col overflow-hidden"
        bodyClassName="flex min-h-0 flex-1 flex-col p-5"
        eyebrow={row.status === "warming" ? "Warming" : busy ? "Working" : LABELS[row.category] || row.category}
        title={row.title}
        right={
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onMinimize();
            }}
            className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-white/35 hover:text-white"
          >
            Min
          </button>
        }
      >
        <div className="min-h-0 flex-1 space-y-3 overflow-auto text-sm text-white/60">
          {turns.map((turn, index) => (
            <p key={`${turn.role}-${index}`}>
              <span className="text-white/30">{turn.role === "user" ? "You" : "Jarvis"} · </span>
              {String(turn.content || "")}
            </p>
          ))}
          {scene.title || (scene.widgets || []).length ? <SceneBoard scene={scene} compact /> : null}
        </div>
        {pending && pendingCopy ? (
          <div className="mt-4 border-l-2 border-amber/30 bg-amber/5 px-4 py-3 text-center">
            <p className="text-sm text-white/70">Shall I? {pendingCopy.title}</p>
            {pendingCopy.summary ? <p className="mt-1 text-xs text-white/40">{pendingCopy.summary}</p> : null}
            <div className="mt-3 flex justify-center gap-3 text-xs">
              <HudButton variant="ghost" className="px-3 py-1" onClick={() => onConfirm(pending.id, false)}>
                No
              </HudButton>
              <HudButton
                variant="primary"
                className="border-amber/50 px-3 py-1 text-amber hover:border-amber hover:bg-amber/15 hover:shadow-glow-amber"
                onClick={() => onConfirm(pending.id, true)}
              >
                Yes
              </HudButton>
            </div>
          </div>
        ) : (
          <form
            className="mt-4"
            onSubmit={(event) => {
              event.preventDefault();
              const value = draft.trim();
              if (!value || busy || row.status === "warming") return;
              onSend(value);
              setDraft("");
            }}
          >
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onFocus={onFocus}
              placeholder={row.status === "warming" ? "Priming…" : "Speak to this"}
              disabled={busy || row.status === "warming"}
              className="w-full bg-transparent text-left font-display text-lg text-white outline-none placeholder:text-white/20"
            />
          </form>
        )}
      </Panel>
    </div>
  );
}
