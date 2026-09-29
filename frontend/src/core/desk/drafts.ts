"use client";

import { apiBase } from "@/lib/api";
import { registerAutosave } from "./autosave";

const BATON_KEY = (section: string) => `jarvis.baton.${section}`;

export function saveBatonText(section: string, text: string) {
  try {
    if (text) localStorage.setItem(BATON_KEY(section), text);
    else localStorage.removeItem(BATON_KEY(section));
  } catch {
    /* ignore */
  }
}

export function loadBatonText(section: string): string {
  try {
    return localStorage.getItem(BATON_KEY(section)) ?? "";
  } catch {
    return "";
  }
}

/** Owner fields to the draft endpoint. Beacon uses CORS-simple text/plain; keepalive falls back. */
export async function saveServerDraft(key: string, body: Record<string, unknown>, beacon = false) {
  const url = `${apiBase()}/api/drafts/${encodeURIComponent(key)}`;
  const payload = JSON.stringify({ body });
  if (beacon) {
    let sent = false;
    if (typeof navigator.sendBeacon === "function") {
      sent = navigator.sendBeacon(url, new Blob([payload], { type: "text/plain" }));
    }
    if (!sent) {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: payload,
        keepalive: true,
      }).catch(() => undefined);
    }
    return;
  }
  await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: payload,
    keepalive: true,
  }).catch(() => undefined);
}

type DraftSource = () => { key: string; body: Record<string, unknown> } | null;

/** Register a server draft source: saved on autosave triggers and pagehide (X10). Returns the save promise from autosave. */
export function registerServerDraft(source: DraftSource): () => void {
  const flush = (beacon = false): void | Promise<void> => {
    const d = source();
    if (!d) return;
    return saveServerDraft(d.key, d.body, beacon);
  };
  const off = registerAutosave(() => flush());
  const onHide = () => {
    void flush(true);
  };
  window.addEventListener("pagehide", onHide);
  return () => {
    void flush();
    off();
    window.removeEventListener("pagehide", onHide);
  };
}
