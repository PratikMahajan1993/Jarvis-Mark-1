"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { send as deskSend, parkHitl, resumeHitl } from "@/core/desk/controller";
import { loadBatonText, saveBatonText, saveServerDraft } from "@/core/desk/drafts";
import { postSubstrate } from "@/core/root/substrateBridge";
import { getDesk, useDesk } from "@/core/stores/deskStore";
import { requestSection, useSectionState } from "@/core/stores/sectionStore";
import {
  markParked,
  removePending,
  unmarkParked,
  upsertPending,
  useTaskQueue as useTaskQueueStore,
  type TaskQueueState,
} from "@/core/stores/taskQueueStore";
import { pushToast } from "@/core/stores/toastStore";
import { dispatchTurn, getTurn, useTurn, useTurnBusy } from "@/core/stores/turnStore";
import { apiBase } from "@/lib/api";
import { isBusy, type JarvisState } from "@/lib/orchestratorFsm";
import type { PendingAction } from "@/lib/types";
import { speakText } from "@/lib/voice";
import { subscribeTopic } from "./events";
import { isFeatureEnabled } from "./featureFlags";

export function useJarvisState(): {
  mode: JarvisState["mode"];
  workspace: string;
  section: string;
  busy: boolean;
} {
  const turn = useTurn();
  const busy = useTurnBusy();
  const workspace = useSectionState((s) => s.workspace);
  const section = useSectionState((s) => s.active);
  return { mode: turn.mode, workspace, section, busy: busy || isBusy(turn) };
}

export function useJarvisSend(): {
  send: (text: string, opts?: { section?: string }) => Promise<void>;
} {
  return {
    send: async (text, opts) => {
      if (opts?.section) {
        requestSection(opts.section, { source: "user", reason: "feature-send" });
      }
      await deskSend(text);
    },
  };
}

export function useSpeak(): { speak: (text: string) => Promise<void> } {
  return {
    speak: (text) => speakText(text),
  };
}

export function useSection(): {
  active: string;
  progress: number;
  go: (id: string) => void;
  isActive: (id: string) => boolean;
} {
  const active = useSectionState((s) => s.active);
  const progress = useSectionState((s) => s.progress);
  return {
    active,
    progress,
    go: (id: string) => {
      requestSection(id, { source: "user", reason: "sdk-go" });
    },
    isActive: (id: string) => active === id,
  };
}

export function useOrb(): {
  glance: (elementOrPoint: Element | { x: number; y: number }, ms?: number) => void;
  pulse: (kind: "ack" | "warn") => void;
} {
  return {
    glance: (elementOrPoint, ms = 400) => {
      let x = 0.5;
      let y = 0.5;
      if (typeof Element !== "undefined" && elementOrPoint instanceof Element) {
        const r = elementOrPoint.getBoundingClientRect();
        x = (r.left + r.width / 2) / Math.max(1, window.innerWidth);
        y = (r.top + r.height / 2) / Math.max(1, window.innerHeight);
      } else {
        const p = elementOrPoint as { x: number; y: number };
        x = p.x;
        y = p.y;
      }
      postSubstrate({ type: "glance", x, y, ms });
    },
    pulse: (kind) => {
      postSubstrate({ type: "pulse", kind });
    },
  };
}

export function useTaskQueue(): {
  items: PendingAction[];
  park: (actionId?: string) => void;
  resume: (action: PendingAction) => void;
  add: (draft: PendingAction) => void;
  remove: (id: string) => void;
  parkedIds: string[];
} {
  const items = useTaskQueueStore((s: TaskQueueState) => s.items);
  const parkedIds = useTaskQueueStore((s: TaskQueueState) => s.parkedIds);
  return {
    items,
    parkedIds,
    park: (actionId?: string) => {
      if (actionId) {
        markParked(actionId);
        const cur = getTurn();
        if (cur.mode === "AWAITING_HITL" && cur.action.id === actionId) parkHitl();
        return;
      }
      parkHitl();
    },
    resume: (action) => {
      resumeHitl(action);
    },
    add: (draft) => {
      upsertPending(draft);
    },
    remove: (id) => {
      removePending(id);
      unmarkParked(id);
    },
  };
}

/** Queue a pending HITL action. External work must wait for Authorize — never executes. */
export async function requestApproval(
  kind: string,
  payload: Record<string, unknown> = {},
): Promise<PendingAction> {
  const sessionId = getDesk().activeSession || "default";
  const res = await fetch(`${apiBase()}/api/approvals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, payload, session_id: sessionId }),
  });
  if (!res.ok) {
    throw new Error(`requestApproval failed (${res.status})`);
  }
  const action = (await res.json()) as PendingAction;
  upsertPending(action);
  const turn = getTurn();
  if (turn.mode === "IDLE" || turn.mode === "LISTENING") {
    dispatchTurn({ type: "AWAIT_HITL", action });
  }
  return action;
}

export function useTopic<T = unknown>(topic: string, handler?: (data: T) => void): T | null {
  const [value, setValue] = useState<T | null>(null);
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  useEffect(() => {
    if (!topic) return;
    return subscribeTopic(topic, (data) => {
      const next = data as T;
      setValue(next);
      handlerRef.current?.(next);
    });
  }, [topic]);
  return value;
}

export function useFeatureQuery<T>(
  key: QueryKey | string,
  fn: () => Promise<T>,
  opts?: {
    topics?: string[];
    interval?: number;
  } & Omit<UseQueryOptions<T, Error, T, QueryKey>, "queryKey" | "queryFn">,
) {
  const queryKey: QueryKey = Array.isArray(key) ? key : [key];
  const qc = useQueryClient();
  const topicsKey = opts?.topics?.join(",") ?? "";
  const queryKeyStr = JSON.stringify(queryKey);
  useEffect(() => {
    const topics = topicsKey ? topicsKey.split(",") : [];
    if (!topics.length) return;
    const offs = topics.map((t) =>
      subscribeTopic(t, () => {
        void qc.invalidateQueries({ queryKey });
      }),
    );
    return () => offs.forEach((off) => off());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- invalidate when key/topics change
  }, [qc, topicsKey, queryKeyStr]);

  const { topics: _topics, interval, ...rest } = opts ?? {};
  return useQuery({
    queryKey,
    queryFn: fn,
    refetchInterval: interval,
    ...rest,
  });
}

export function useFeatureMutation<TData = unknown, TVariables = void>(
  fn: (vars: TVariables) => Promise<TData>,
  opts?: {
    invalidates?: QueryKey[];
  } & Omit<UseMutationOptions<TData, Error, TVariables>, "mutationFn">,
) {
  const qc = useQueryClient();
  const { invalidates, ...rest } = opts ?? {};
  return useMutation({
    mutationFn: fn,
    ...rest,
    onSuccess: async (data, vars, onMutateResult, context) => {
      if (invalidates?.length) {
        await Promise.all(invalidates.map((k) => qc.invalidateQueries({ queryKey: k })));
      }
      await rest.onSuccess?.(data, vars, onMutateResult, context);
    },
  });
}

export function useActiveSession(): {
  sessionId: string;
  conversationId: string | null;
} {
  const sessionId = useDesk((s) => s.activeSession);
  const conversationId = useDesk((s) => s.activeConversationId);
  return { sessionId, conversationId };
}

export function useFeatureFlag(id: string): boolean {
  const [on, setOn] = useState(() => isFeatureEnabled(id));
  useEffect(() => {
    setOn(isFeatureEnabled(id));
    const onStorage = (e: StorageEvent) => {
      if (e.key === `jarvis.feature.${id}`) setOn(isFeatureEnabled(id));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [id]);
  return on;
}

export function useToast(): { toast: (message: string, id?: string) => string } {
  return {
    toast: (message, id) => pushToast(message, id),
  };
}

export function useDraft(key: string, opts?: { server?: boolean }): [string, (v: string) => void] {
  const [text, setText] = useState(() => loadBatonText(key));
  return [
    text,
    (v) => {
      setText(v);
      saveBatonText(key, v);
      if (opts?.server) {
        void saveServerDraft(key, { text: v });
      }
    },
  ];
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  return reduced;
}

export function useWeatherLine(): string {
  return useDesk((s) => s.weatherLine);
}
