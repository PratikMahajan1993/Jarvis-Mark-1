import type { Conversation } from "./types";

export type WindowCommand =
  | { action: "hide_dock" }
  | { action: "show_dock" }
  | { action: "minimize"; query: string }
  | { action: "expand"; query: string };

export function parseWindowCommand(message: string): WindowCommand | null {
  const low = (message || "").trim().toLowerCase();
  if (!low) return null;
  if (/\b(hide|close) (the )?(conversations?|dock|windows)\b/.test(low)) {
    return { action: "hide_dock" };
  }
  if (/\b(show|open) (the )?(conversations?|dock|windows)\b/.test(low)) {
    return { action: "show_dock" };
  }
  const mini = low.match(
    /\b(minimize|minimise|collapse|hide)\b.+\b(drawing|chat|window|conversation|thread)\b|\b(minimize|minimise|collapse)\b(?:\s+the)?\s+(.+)$/,
  );
  if (mini && !/\b(conversations?|dock|windows)\b/.test(low)) {
    return { action: "minimize", query: (mini[4] || mini[2] || "").replace(/[.\s]+$/, "") };
  }
  const opened = low.match(
    /\b(open|show|maximize|maximise|expand)\b.+\b(drawing|chat|window|conversation|thread)\b|\b(open|show|maximize|maximise|expand)\b(?:\s+the)?\s+(.+?)\s+(chat|window|conversation)\b/,
  );
  if (opened) {
    return { action: "expand", query: (opened[4] || opened[2] || "").replace(/[.\s]+$/, "") };
  }
  return null;
}

export function matchConversation(query: string, rows: Conversation[]): Conversation | null {
  const needle = (query || "").toLowerCase().trim();
  if (!needle) return rows[0] || null;
  for (const row of rows) {
    const title = (row.title || "").toLowerCase();
    const category = (row.category || "").toLowerCase();
    const focus = row.focus || {};
    const name = String(focus.filename || focus.local_name || "").toLowerCase();
    const blob = `${title} ${category} ${name}`;
    if (blob.includes(needle) || needle.includes(category) || needle.includes(title)) return row;
  }
  return null;
}

export function namesConversation(text: string, rows: Conversation[]): Conversation | null {
  const low = (text || "").toLowerCase();
  if (!/\b(drawing|chat|window|conversation|thread|piston)\b/.test(low) && !/\bin the \b/.test(low)) {
    return null;
  }
  return matchConversation(low, rows);
}
