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

/** Owner fields to the draft endpoint. `keepalive` lets it finish during pagehide. */
export async function saveServerDraft(key: string, body: Record<string, unknown>, beacon = false) {
  const url = `${apiBase()}/api/drafts/${encodeURIComponent(key)}`;
  const payload = JSON.stringify({ body });
  if (beacon && typeof navigator.sendBeacon === "function") {
    navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
    return;
  }
  await fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: payload, keepalive: true }).catch(
    () => undefined,
  );
}

type DraftSource = () => { key: string; body: Record<string, unknown> } | null;

/** Register a server draft source: saved on autosave triggers, a 2 s debounce and pagehide (X10). */
export function registerServerDraft(source: DraftSource): () => void {
  const flush = (beacon = false) => {
    const d = source();
    if (d) void saveServerDraft(d.key, d.body, beacon);
  };
  const off = registerAutosave(() => flush());
  const onHide = () => flush(true);
  window.addEventListener("pagehide", onHide);
  return () => {
    off();
    window.removeEventListener("pagehide", onHide);
  };
}
