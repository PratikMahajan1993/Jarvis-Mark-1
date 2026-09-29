"use client";

export type AutosaveHandler = (reason: string) => void | Promise<void>;

const handlers = new Set<AutosaveHandler>();
const AUTOSAVE_WAIT_MS = 300;

/** Register a draft saver (Engineering stage, baton text). Returns an unregister. */
export function registerAutosave(handler: AutosaveHandler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

/** Run every saver, waiting at most 300 ms. Never sends or queues anything external. */
export async function runAutosave(reason: string): Promise<void> {
  if (handlers.size === 0) return;
  const all = Promise.allSettled([...handlers].map((h) => Promise.resolve().then(() => h(reason))));
  await Promise.race([all, new Promise((r) => setTimeout(r, AUTOSAVE_WAIT_MS))]);
}
