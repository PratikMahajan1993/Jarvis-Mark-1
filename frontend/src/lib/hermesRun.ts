import type { ChatResponse, PendingAction } from "@/lib/types";

export type HermesRunEvent = {
  event?: string;
  delta?: string;
  message?: string;
  error?: string;
  pending?: PendingAction;
  response?: ChatResponse;
};

/** Speak a sentence only after its closing punctuation is followed by whitespace. */
export function takeSentences(buffer: string): { ready: string[]; rest: string } {
  const ready: string[] = [];
  let start = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    const ch = buffer[i];
    if (ch !== "." && ch !== "!" && ch !== "?") continue;
    const next = buffer[i + 1];
    if (next === undefined || !/\s/.test(next)) continue;
    const sentence = buffer.slice(start, i + 1).trim();
    if (sentence) ready.push(sentence);
    start = i + 1;
    while (start < buffer.length && /\s/.test(buffer[start])) start += 1;
    i = start - 1;
  }
  return { ready, rest: buffer.slice(start) };
}

export async function readHermesEventStream(
  response: Response,
  onEvent: (event: HermesRunEvent) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No event stream");
  const decoder = new TextDecoder();
  let carry = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    carry += decoder.decode(value, { stream: true });
    const lines = carry.split("\n");
    carry = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      if (!trimmed.startsWith("data:")) continue;
      const raw = trimmed.slice(5).trim();
      if (!raw) continue;
      let event: HermesRunEvent;
      try {
        event = JSON.parse(raw) as HermesRunEvent;
      } catch {
        continue;
      }
      const name = String(event.event || "");
      if (name.startsWith("reasoning")) continue;
      onEvent(event);
    }
  }
}
