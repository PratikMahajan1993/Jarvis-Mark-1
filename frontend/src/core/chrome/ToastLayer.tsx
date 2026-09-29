"use client";

import { createPortal } from "react-dom";
import { useEffect, useState } from "react";
import { dismissToast, useToastStore } from "@/core/stores/toastStore";

/** X8: parked-approval expiry and server drops surface here (z-toast). */
export function ToastLayer() {
  const [root, setRoot] = useState<HTMLElement | null>(null);
  const items = useToastStore((s) => s.items);

  useEffect(() => {
    setRoot(document.getElementById("jarvis-toast"));
  }, []);

  if (!root) return null;

  return createPortal(
    <ul className="pointer-events-none fixed bottom-24 right-3 z-toast flex max-w-sm flex-col gap-2">
      {items.map((toast) => (
        <li
          key={toast.id}
          className="pointer-events-auto rounded-xl border border-[color:var(--accent)]/35 bg-black/75 px-4 py-3 font-mono text-[11px] leading-snug text-[color:var(--fg)] shadow-lg backdrop-blur"
          data-toast
        >
          <div className="flex items-start gap-3">
            <p className="min-w-0 flex-1">{toast.message}</p>
            <button
              type="button"
              className="shrink-0 text-[color:var(--muted)] hover:text-[color:var(--fg)]"
              aria-label="Dismiss"
              onClick={() => dismissToast(toast.id)}
            >
              ×
            </button>
          </div>
        </li>
      ))}
    </ul>,
    root,
  );
}
