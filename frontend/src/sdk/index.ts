import { useEffect, useState } from "react";
import { getSection, useSectionState } from "@/core/stores/sectionStore";
import { useDesk } from "@/core/stores/deskStore";
import { useTaskQueue } from "@/core/stores/taskQueueStore";
import { loadBatonText, saveBatonText } from "@/core/desk/drafts";

export { useTaskQueue };
export { Slot } from "./Slot";
export { defineFeature, defineCard, getCardsForSlot, registeredFeatures } from "./featureRegistry";
export type { CardDef, FeatureDef } from "./featureRegistry";

export function useWeatherLine(): string {
  return useDesk((s) => s.weatherLine);
}

export function useSection() {
  return useSectionState((s) => s);
}

/** Subscribe to a backend topic on /api/events (SSE). */
export function useTopic<T = unknown>(topic: string): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
    const es = new EventSource(`${base}/api/events?topics=${encodeURIComponent(topic)}`);
    es.addEventListener(topic, (e) => {
      try {
        setValue(JSON.parse((e as MessageEvent).data) as T);
      } catch {}
    });
    return () => es.close();
  }, [topic]);
  return value;
}

export function useDraft(key: string): [string, (v: string) => void] {
  const [text, setText] = useState(() => loadBatonText(key));
  return [
    text,
    (v) => {
      setText(v);
      saveBatonText(key, v);
    },
  ];
}
