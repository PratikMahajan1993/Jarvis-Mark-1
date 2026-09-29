"use client";

import { AnimatePresence, motion, useReducedMotion, type PanInfo } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import * as desk from "@/core/desk/controller";
import type { RailConversation } from "@/components/orchestrator/ConversationRail";
import { parkedApprovalForConversation } from "@/core/sections/engineering/deckCardMeta";
import { useTaskQueue } from "@/core/stores/taskQueueStore";
import { SPRING } from "@/lib/pane/springs";

const MAX_VISIBLE = 5;
const TASK_KINDS = new Set(["drawing", "workflow", "job"]);

export function engineeringTasks(items: RailConversation[]): RailConversation[] {
  return items.filter((c) => TASK_KINDS.has((c.kindLabel || "").toLowerCase()));
}

function DrawingPlaceholder() {
  return (
    <div
      className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-[color:var(--border)] bg-black/30 text-[color:var(--muted)]"
      aria-hidden
      data-deck-thumb="placeholder"
    >
      <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="1.25">
        <path d="M4 20V4l8 4 8-4v16l-8-4-8 4z" />
        <path d="M12 8v12" />
      </svg>
    </div>
  );
}

function Card({
  item,
  depth,
  fanned,
  front,
  onOpen,
  parkedTitle,
}: {
  item: RailConversation;
  depth: number;
  fanned: boolean;
  front: boolean;
  onOpen: () => void;
  parkedTitle?: string;
}) {
  const spread = fanned ? 46 : 14;
  const subline = [item.customer, item.drawingNumber, item.revision ? `Rev ${item.revision}` : ""]
    .filter(Boolean)
    .join(" · ");
  const verifyParts: string[] = [];
  if (item.verifyBlockers != null) verifyParts.push(`${item.verifyBlockers} blocker${item.verifyBlockers === 1 ? "" : "s"}`);
  if (item.verifyWarnings != null) verifyParts.push(`${item.verifyWarnings} warn`);

  return (
    <motion.button
      type="button"
      layout
      drag={front ? "x" : false}
      dragSnapToOrigin
      dragElastic={0.5}
      onDragEnd={(_e: unknown, info: PanInfo) => {
        if (Math.abs(info.offset.x) > 90 || Math.abs(info.velocity.x) > 500) document.dispatchEvent(new CustomEvent("deck:cycle"));
      }}
      onClick={front ? onOpen : undefined}
      animate={{
        y: -spread * depth,
        scale: Math.pow(0.94, depth),
        filter: `brightness(${1 - 0.12 * depth}) blur(${depth > 2 ? 2 : 0}px)`,
        zIndex: MAX_VISIBLE - depth,
      }}
      transition={SPRING.pane}
      className="absolute inset-x-0 bottom-0 flex h-44 flex-col rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-3 text-left shadow-[0_18px_40px_rgba(0,0,0,0.45)]"
      aria-label={front ? `Resume ${item.title}` : item.title}
      data-deck-card
    >
      <div className="flex gap-3">
        {item.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- deck thumb is tool-owned blob/data URL when present
          <img
            src={item.thumbnailUrl}
            alt=""
            className="h-14 w-14 shrink-0 rounded-lg border border-[color:var(--border)] object-cover"
            data-deck-thumb="image"
          />
        ) : (
          <DrawingPlaceholder />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {item.quoteStep ? (
              <span className="rounded-full border border-[color:var(--accent)]/40 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-[color:var(--accent)]">
                {item.quoteStep}
              </span>
            ) : null}
            {parkedTitle ? (
              <span
                className="rounded-full bg-[color:var(--accent)]/15 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-[color:var(--accent)]"
                title={parkedTitle}
              >
                Approval parked
              </span>
            ) : null}
          </div>
          <span className="mt-1 line-clamp-2 font-display text-base leading-snug text-[color:var(--fg)]">{item.title}</span>
          {subline ? (
            <span className="mt-0.5 line-clamp-1 font-mono text-[9px] uppercase tracking-[0.1em] text-[color:var(--muted)]">
              {subline}
            </span>
          ) : null}
        </div>
      </div>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">
          {item.kindLabel || "Task"}
          {item.time ? ` · ${item.time}` : " · Waiting"}
        </span>
        {verifyParts.length ? (
          <span className="font-mono text-[9px] text-[color:var(--muted)]">{verifyParts.join(" · ")}</span>
        ) : null}
        {item.draftTotal ? (
          <span className="font-mono text-[9px] text-[color:var(--accent)]">Draft {item.draftTotal}</span>
        ) : null}
      </div>
    </motion.button>
  );
}

/** X9: stacked-card carousel of engineering tasks. Hero when idle, a pile when a task is active. */
export function EngineeringDeck({ items, hero }: { items: RailConversation[]; hero: boolean }) {
  const reduced = useReducedMotion();
  const [order, setOrder] = useState<string[]>([]);
  const [fanned, setFanned] = useState(false);
  const pendingItems = useTaskQueue((s) => s.items);
  const parkedIds = useTaskQueue((s) => s.parkedIds);
  const ids = useMemo(() => items.map((i) => i.id), [items]);

  useEffect(() => {
    setOrder((prev) => [...prev.filter((id) => ids.includes(id)), ...ids.filter((id) => !prev.includes(id))]);
  }, [ids]);

  useEffect(() => {
    const cycle = () => setOrder((o) => (o.length > 1 ? [...o.slice(1), o[0]!] : o));
    const back = () => setOrder((o) => (o.length > 1 ? [o[o.length - 1]!, ...o.slice(0, -1)] : o));
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el?.closest("input,textarea,[contenteditable]")) return;
      if (e.key === "ArrowRight") cycle();
      else if (e.key === "ArrowLeft") back();
    };
    document.addEventListener("deck:cycle", cycle);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("deck:cycle", cycle);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const byId = new Map(items.map((i) => [i.id, i]));
  const ordered = order.map((id) => byId.get(id)).filter((i): i is RailConversation => Boolean(i));

  if (!ordered.length) {
    return hero ? (
      <div className="flex h-full items-center justify-center" data-deck-empty>
        <p className="font-display text-lg text-[color:var(--fg)]/70">No engineering tasks waiting</p>
      </div>
    ) : null;
  }

  if (reduced) {
    return (
      <ul className="flex gap-3 overflow-x-auto" data-lenis-prevent>
        {ordered.map((item) => (
          <li key={item.id} className="w-56 shrink-0">
            <button type="button" className="w-full rounded-xl border border-[color:var(--border)] p-3 text-left" onClick={() => void desk.selectConversation(item.id)}>
              {item.title}
            </button>
          </li>
        ))}
      </ul>
    );
  }

  const visible = ordered.slice(0, MAX_VISIBLE);
  return (
    <div
      className={hero ? "flex h-full items-center justify-center" : "h-full"}
      onMouseEnter={() => setFanned(true)}
      onMouseLeave={() => setFanned(false)}
      data-deck={hero ? "hero" : "pile"}
    >
      <div className={["relative h-52", hero ? "w-[min(420px,80%)]" : "w-40"].join(" ")} style={{ perspective: 1200 }}>
        <AnimatePresence initial={false}>
          {visible.map((item, i) => {
            const parked = parkedApprovalForConversation(pendingItems, parkedIds, item);
            return (
              <Card
                key={item.id}
                item={item}
                depth={i}
                fanned={fanned}
                front={i === 0}
                onOpen={() => void desk.selectConversation(item.id)}
                parkedTitle={parked?.title}
              />
            );
          })}
        </AnimatePresence>
        {ordered.length > MAX_VISIBLE ? (
          <span className="absolute -top-8 right-0 rounded-full bg-black/60 px-2 py-0.5 font-mono text-[10px] text-[color:var(--muted)]">
            +{ordered.length - MAX_VISIBLE}
          </span>
        ) : null}
      </div>
    </div>
  );
}
