import type { ChatResponse, Health, Preferences, Artifact, AuditEntry, PendingAction } from "./types";
import type { CanvasBoard, CanvasCamera, CanvasFile, CanvasItem } from "./canvas/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export const api = {
  health: () => json<Health>("/api/health"),
  chat: (message: string, sessionId = "default") =>
    json<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  confirm: (actionId: string, approved: boolean, sessionId = "default") =>
    json<ChatResponse>("/api/confirm", {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, approved, session_id: sessionId }),
    }),
  briefing: () => json<ChatResponse & { speak: string }>("/api/briefing"),
  glance: () =>
    json<{ line: string; whisper: string; speak: string; key: string; minutes: number | null }>("/api/glance"),
  artifacts: () => json<{ items: Artifact[] }>("/api/artifacts"),
  audit: () => json<{ items: AuditEntry[] }>("/api/audit"),
  preferences: () => json<Preferences>("/api/preferences"),
  updatePreferences: (patch: Partial<Preferences>) =>
    json<Preferences>("/api/preferences", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  pending: () => json<{ items: PendingAction[] }>("/api/pending"),
  nextThought: (sessionId = "default") => json<ChatResponse>(`/api/thought?session_id=${sessionId}`),
  googleStatus: () => json<{ configured: boolean; connected: boolean; account: string; task_to: string }>("/api/google/status"),
  googleAuthUrl: () => `${API}/api/google/auth`,
  watch: (sessionId = "default") =>
    json<{ watching: boolean; ready: boolean; status?: string; speak?: string; scene?: ChatResponse["scene"] }>(
      `/api/watch?session_id=${sessionId}`,
    ),
  downloadUrl: (id: string) => `${API}/api/artifacts/${id}`,
  uploadInbox: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${API}/api/inbox`, { method: "POST", body });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<{ id: string; name: string; preview: string }>;
  },
  canvas: {
    board: (boardId: string) => json<CanvasBoard>(`/api/canvas/boards/${boardId}`),
    saveBoard: (boardId: string, payload: { name: string; camera: CanvasCamera; items: CanvasItem[] }) =>
      json<{ ok: boolean; count: number }>(`/api/canvas/boards/${boardId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    upload: async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API}/api/canvas/files`, { method: "POST", body });
      if (!response.ok) throw new Error(await response.text());
      return response.json() as Promise<CanvasFile>;
    },
    fileUrl: (fileId: string) => `${API}/api/canvas/files/${fileId}`,
  },
};
