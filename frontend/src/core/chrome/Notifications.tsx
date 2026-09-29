"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { hitlApprovalLayoutId } from "@/core/chrome/hitlLayout";
import * as desk from "@/core/desk/controller";
import {
  dismissOverlay,
  overlayItem,
  removeNotification,
  togglePanel,
  unreadCount,
  useNotificationStore,
  type DeskNotification,
  type NotificationPriority,
} from "@/core/stores/notificationStore";
import { startParkedExpiryWatcher, useTaskQueue } from "@/core/stores/taskQueueStore";
import { SPRING } from "@/lib/pane/springs";

const PRIORITY_LABEL: Record<NotificationPriority, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

function overlayClass(priority: NotificationPriority): string {
  if (priority === "high") {
    return "rounded-sm border-[color:oklch(78%_0.16_55)] bg-[oklch(22%_0.06_55)]/90 text-[oklch(88%_0.08_75)] shadow-[0_12px_28px_rgba(80,40,0,0.45)]";
  }
  if (priority === "medium") {
    return "rounded-xl border-[color:var(--accent)]/50 bg-black/80 text-[color:var(--fg)]";
  }
  return "rounded-full border-[color:var(--border)] bg-black/70 text-[color:var(--muted)]";
}

function BellIcon({ lit }: { lit: boolean }) {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <path d="M3.2 10.2V7.1a4.8 4.8 0 0 1 9.6 0v3.1l1 1.4H2.2l1-1.4Z" />
      <path d="M6.2 12.4a1.8 1.8 0 0 0 3.6 0" />
      {lit ? <circle cx="12.2" cy="3.2" r="1.3" fill="currentColor" stroke="none" /> : null}
    </svg>
  );
}

export function Notifications() {
  const items = useNotificationStore((s) => s.items);
  const overlayId = useNotificationStore((s) => s.overlayId);
  const panelOpen = useNotificationStore((s) => s.panelOpen);
  const pending = useTaskQueue((s) => s.items);
  const parkedIds = useTaskQueue((s) => s.parkedIds);
  const rootRef = useRef<HTMLDivElement>(null);
  const overlay = overlayItem({ items, overlayId, panelOpen });
  const unread = unreadCount(items);

  useEffect(() => {
    startParkedExpiryWatcher({
      onTtlExpired: (action) => {
        desk.resumeHitl(action);
      },
    });
  }, []);

  useEffect(() => {
    if (!panelOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) togglePanel(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") togglePanel(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [panelOpen]);

  const onActivate = (item: DeskNotification) => {
    dismissOverlay();
    if (item.actionId) {
      const action = pending.find((a) => a.id === item.actionId);
      if (action) desk.resumeHitl(action);
    }
    togglePanel(false);
  };

  return (
    <div ref={rootRef} className="relative" data-chrome="notifications">
      <AnimatePresence>
        {overlay ? (
          <motion.button
            key={overlay.id}
            type="button"
            initial={{ opacity: 0, x: 12, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 8 }}
            transition={SPRING.chip}
            onClick={() => onActivate(overlay)}
            className={[
              "absolute right-full top-1/2 z-toast mr-2 max-w-[240px] -translate-y-1/2 border px-3 py-2 text-left shadow-lg backdrop-blur",
              overlayClass(overlay.priority),
            ].join(" ")}
            data-notification-overlay={overlay.priority}
            aria-label={`${PRIORITY_LABEL[overlay.priority]} notification: ${overlay.title}`}
          >
            <span className="block font-mono text-[8px] uppercase tracking-[0.16em] opacity-70">
              {PRIORITY_LABEL[overlay.priority]}
            </span>
            <span className="mt-0.5 block font-display text-[13px] leading-snug">{overlay.title}</span>
          </motion.button>
        ) : null}
      </AnimatePresence>

      <button
        type="button"
        aria-expanded={panelOpen}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        title="Notifications"
        onClick={() => togglePanel()}
        className={[
          "relative flex h-7 w-7 items-center justify-center rounded-full border transition",
          unread
            ? "border-[color:var(--accent)]/45 bg-[color:var(--accent)]/12 text-[color:var(--accent)]"
            : "border-[color:var(--border)] bg-black/40 text-[color:var(--muted)] hover:border-[color:var(--accent)]/25 hover:text-[color:var(--accent)]/85",
        ].join(" ")}
        data-notification-bell
      >
        <BellIcon lit={unread > 0} />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-[14px] rounded-full bg-[color:var(--accent)] px-1 text-center font-mono text-[8px] leading-[14px] text-black">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      <AnimatePresence>
        {panelOpen ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={SPRING.chip}
            className="absolute right-0 top-[calc(100%+8px)] z-toast w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-[color:var(--border)] bg-black/85 shadow-[0_18px_40px_rgba(0,0,0,0.5)] backdrop-blur-md"
            role="dialog"
            aria-label="Notifications"
            data-notification-panel
          >
            <div className="flex items-center justify-between border-b border-[color:var(--border)] px-3 py-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]">Notifications</p>
              <button
                type="button"
                className="font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)] hover:text-[color:var(--fg)]"
                onClick={() => togglePanel(false)}
              >
                Close
              </button>
            </div>
            <ul className="max-h-[min(420px,60vh)] overflow-y-auto overscroll-contain" data-lenis-prevent>
              {items.length === 0 ? (
                <li className="px-3 py-6 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]/70">
                  Nothing waiting
                </li>
              ) : (
                items.map((item) => {
                  const parked = item.actionId ? parkedIds.includes(item.actionId) : false;
                  return (
                    <li key={item.id} className="border-b border-[color:var(--border)]/60 last:border-0">
                      <motion.div
                        layoutId={item.actionId ? hitlApprovalLayoutId(item.actionId) : undefined}
                        transition={SPRING.chip}
                        className="flex gap-2 px-3 py-2.5"
                      >
                        <span
                          className={[
                            "mt-1 h-2 w-2 shrink-0",
                            item.priority === "high"
                              ? "rotate-45 bg-[oklch(78%_0.16_55)]"
                              : item.priority === "medium"
                                ? "rounded-sm bg-[color:var(--accent)]"
                                : "rounded-full bg-[color:var(--muted)]",
                          ].join(" ")}
                          aria-hidden
                        />
                        <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onActivate(item)}>
                          <span className="block font-mono text-[8px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
                            {PRIORITY_LABEL[item.priority]}
                            {parked ? " · Authorize" : ""}
                          </span>
                          <span className="mt-0.5 block font-display text-sm leading-snug text-[color:var(--fg)]">
                            {item.title}
                          </span>
                          {item.body ? (
                            <span className="mt-0.5 line-clamp-2 block font-mono text-[10px] text-[color:var(--muted)]">
                              {item.body}
                            </span>
                          ) : null}
                        </button>
                        <button
                          type="button"
                          className="shrink-0 self-start font-mono text-[11px] text-[color:var(--muted)] hover:text-[color:var(--fg)]"
                          aria-label="Remove notification"
                          onClick={() => removeNotification(item.id)}
                        >
                          ×
                        </button>
                      </motion.div>
                    </li>
                  );
                })
              )}
            </ul>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
