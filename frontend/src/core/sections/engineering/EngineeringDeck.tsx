"use client";

import { AnimatePresence, motion, useReducedMotion, type PanInfo } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import * as desk from "@/core/desk/controller";
import type { RailConversation } from "@/components/orchestrator/ConversationRail";
import { SPRING } from "@/lib/pane/springs";

const MAX_VISIBLE = 5;
const TASK_KINDS = new Set(["drawing", "workflow", "job"]);

export function engineeringTasks(items: RailConversation[]): RailConversation[] {
  return items.filter((c) => TASK_KINDS.has((c.kindLabel || "").toLowerCase()));
}

function Card({ item, depth, fanned, front, onOpen }: {
  item: RailConversation;
  depth: number;
  fanned: boolean;
  front: boolean;
  onOpen: () => void;
}) {
  const spread = fanned ? 46 : 14;
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
      className="absolute inset-x-0 bottom-0 flex h-36 flex-col justify-between rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-4 text-left shadow-[0_18px_40px_rgba(0,0,0,0.45)]"
      aria-label={front ? `Resume ${item.title}` : item.title}
      data-deck-card
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--accent)]">
        {item.kindLabel || "Task"}
        {item.waiting ? " · approval parked" : ""}
      </span>
      <span className="line-clamp-2 font-display text-lg leading-snug text-[color:var(--fg)]">{item.title}</span>
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">
        {item.time || "Waiting"}
      </span>
    </motion.button>
  );
}

/** X9: stacked-card carousel of engineering tasks. Hero when idle, a pile when a task is active. */
export function EngineeringDeck({ items, hero }: { items: RailConversation[]; hero: boolean }) {
  const reduced = useReducedMotion();
  const [order, setOrder] = useState<string[]>([]);
  const [fanned, setFanned] = useState(false);
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
          {visible.map((item, i) => (
            <Card
              key={item.id}
              item={item}
              depth={i}
              fanned={fanned}
              front={i === 0}
              onOpen={() => void desk.selectConversation(item.id)}
            />
          ))}
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
