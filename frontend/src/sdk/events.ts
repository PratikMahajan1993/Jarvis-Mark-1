/** One multiplexed EventSource for the tab — topics are filtered client-side. */

type TopicHandler = (data: unknown) => void;

const handlers = new Map<string, Set<TopicHandler>>();
let es: EventSource | null = null;
let connecting = false;

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
}

function ensureStream() {
  if (typeof window === "undefined" || es || connecting) return;
  if (handlers.size === 0) return;
  connecting = true;
  try {
    // Empty topics filter ⇒ server sends every topic; we demux locally.
    const next = new EventSource(`${apiBase()}/api/events`);
    next.onopen = () => {
      connecting = false;
    };
    next.onerror = () => {
      connecting = false;
      next.close();
      if (es === next) es = null;
      if (handlers.size > 0) {
        window.setTimeout(() => ensureStream(), 1500);
      }
    };
    // Catch-all: named events use addEventListener; also listen for message.
    next.onmessage = (e) => {
      // Heartbeats / unnamed — ignore.
      void e;
    };
    const route = (topic: string) => (e: Event) => {
      const set = handlers.get(topic);
      if (!set || set.size === 0) return;
      let data: unknown = null;
      try {
        data = JSON.parse((e as MessageEvent).data);
      } catch {
        data = (e as MessageEvent).data;
      }
      for (const h of [...set]) h(data);
    };
    // Attach listeners for currently subscribed topics and any that arrive later via proxy.
    const attached = new Set<string>();
    const attach = (topic: string) => {
      if (attached.has(topic)) return;
      attached.add(topic);
      next.addEventListener(topic, route(topic) as EventListener);
    };
    for (const topic of handlers.keys()) attach(topic);
    // Monkey-patch subscribe to attach new topics on the live ES.
    (next as EventSource & { __attach?: (t: string) => void }).__attach = attach;
    es = next;
  } catch {
    connecting = false;
  }
}

function attachTopic(topic: string) {
  const live = es as (EventSource & { __attach?: (t: string) => void }) | null;
  live?.__attach?.(topic);
}

/** Subscribe to a server topic. Shares one EventSource for the tab. */
export function subscribeTopic(topic: string, handler: TopicHandler): () => void {
  if (!topic) return () => undefined;
  let set = handlers.get(topic);
  if (!set) {
    set = new Set();
    handlers.set(topic, set);
  }
  set.add(handler);
  ensureStream();
  attachTopic(topic);
  return () => {
    const cur = handlers.get(topic);
    if (!cur) return;
    cur.delete(handler);
    if (cur.size === 0) handlers.delete(topic);
    if (handlers.size === 0 && es) {
      es.close();
      es = null;
    }
  };
}
