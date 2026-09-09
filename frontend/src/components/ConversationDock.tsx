"use client";

import { useState } from "react";
import type { Conversation, PendingAction, Scene, Widget } from "@/lib/types";
import { shallICopy } from "./ConfirmBar";
import { SceneBoard } from "./SceneBoard";
import { HudButton, Panel, StatusDot } from "./hud/Hud";

const LABELS: Record<string, string> = {
  drawing: "Drawings",
  mail: "Mail",
  research: "Research",
  files: "Files",
};

const ORDER = ["drawing", "mail", "research", "files"];

function group(rows: Conversation[]): [string, Conversation[]][] {
  const buckets = new Map<string, Conversation[]>();
  for (const row of rows) {
    const key = row.category || "files";
    const list = buckets.get(key) || [];
    list.push(row);
    buckets.set(key, list);
  }
  const ordered: [string, Conversation[]][] = [];
  for (const key of ORDER) {
    const list = buckets.get(key);
    if (list?.length) ordered.push([key, list]);
  }
  for (const [key, list] of buckets) {
    if (!ORDER.includes(key)) ordered.push([key, list]);
  }
  return ordered;
}

function asJobs(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object");
}

function drawingRfqScene(row: Conversation): Scene {
  const scene = row.scene || { title: "", widgets: [] };
  const widgets: Widget[] = [...(scene.widgets || [])];
  if (row.category !== "drawing") {
    return { title: scene.title, subtitle: scene.subtitle, widgets };
  }
  const focus = row.focus || {};
  const extra = row as Conversation & { catch?: unknown; similar_jobs?: unknown };
  const catchLine = [focus.catch, extra.catch].find((value) => typeof value === "string" && value.trim()) as
    | string
    | undefined;
  const similar = asJobs(focus.similar_jobs ?? extra.similar_jobs);
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
    title: scene.title || row.title,
    subtitle: scene.subtitle,
    widgets,
  };
}

export function ConversationDock({
  conversations,
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
  const expanded = conversations.filter((row) => !row.minimized).slice(0, 2);
  const collapsed = conversations.filter((row) => row.minimized);
  return (
    <aside className="pointer-events-auto relative z-10 flex w-72 shrink-0 flex-col justify-start gap-3 overflow-auto py-2 pr-3">
      {expanded.map((row) => (
        <ConversationCard
          key={row.id}
          row={row}
          focused={focusedId === row.id}
          busy={busyId === row.id}
          onFocus={() => onFocus(row.id)}
          onMinimize={() => onMinimize(row.id)}
          onSend={(message) => onSend(row.id, message)}
          onConfirm={(actionId, approved) => onConfirm(row.id, actionId, approved)}
        />
      ))}
      {collapsed.length ? (
        <div className="space-y-3 overflow-auto">
          {group(collapsed).map(([category, rows]) => (
            <div key={category}>
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-white/25">{LABELS[category] || category}</p>
              <div className="flex flex-col gap-1.5">
                {rows.map((row) => (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => onExpand(row.id)}
                    className={`flex items-center justify-between rounded-full border px-3 py-1.5 text-left text-xs transition-colors ${
                      focusedId === row.id ? "border-cyan/40 text-white" : "border-white/10 text-white/55 hover:text-white"
                    }`}
                  >
                    <span className="truncate">{row.title}</span>
                    {row.waiting || row.status === "warming" || busyId === row.id ? (
                      <StatusDot accent="amber" pulse className="ml-2 shrink-0" />
                    ) : null}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </aside>
  );
}

function ConversationCard({
  row,
  focused,
  busy,
  onFocus,
  onMinimize,
  onSend,
  onConfirm,
}: {
  row: Conversation;
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
  const scene = drawingRfqScene(row);
  const turns = (row.turns || []).slice(-6);
  return (
    <div onClick={onFocus}>
      <Panel
        accent={focused ? "cyan" : "white"}
        className="flex max-h-[36vh] min-h-0 flex-col overflow-hidden"
        bodyClassName="flex min-h-0 flex-1 flex-col p-3"
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
        <div className="min-h-0 flex-1 space-y-2 overflow-auto text-xs text-white/55">
          {turns.map((turn, index) => (
            <p key={`${turn.role}-${index}`}>
              <span className="text-white/30">{turn.role === "user" ? "You" : "Jarvis"} · </span>
              {String(turn.content || "").slice(0, 160)}
              {String(turn.content || "").length > 160 ? "…" : ""}
            </p>
          ))}
          {scene.title || (scene.widgets || []).length ? <SceneBoard scene={scene} compact /> : null}
        </div>
        {pending && pendingCopy ? (
          <div className="mt-2 border-l-2 border-amber/30 bg-amber/5 px-3 py-2 text-center">
            <p className="text-xs text-white/70">Shall I? {pendingCopy.title}</p>
            {pendingCopy.summary ? <p className="mt-1 text-[11px] text-white/40">{pendingCopy.summary}</p> : null}
            <div className="mt-2 flex justify-center gap-3 text-xs">
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
            className="mt-2"
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
              className="w-full bg-transparent text-center text-sm text-white outline-none placeholder:text-white/20"
            />
          </form>
        )}
      </Panel>
    </div>
  );
}
