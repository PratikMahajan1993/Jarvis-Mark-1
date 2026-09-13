import type {
  Artifact,
  AuditEntry,
  ChatResponse,
  Conversation,
  Glance,
  Health,
  PendingAction,
  Preferences,
  RfqIntakeRequest,
  RfqIntakeResponse,
  RfqPublic,
} from "./types";
import type { CanvasBoard, CanvasCamera, CanvasFile, CanvasItem } from "./canvas/types";

function apiBase(): string {
  const fallback = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  if (typeof window === "undefined") return fallback;
  try {
    const configured = new URL(fallback, window.location.origin);
    const pageHost = window.location.hostname;
    const loopback = configured.hostname === "localhost" || configured.hostname === "127.0.0.1";
    if (loopback && pageHost !== "localhost" && pageHost !== "127.0.0.1") {
      return `${window.location.protocol}//${pageHost}:8000`;
    }
    return configured.origin;
  } catch {
    return fallback;
  }
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
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
  saveMailAttachments: (emailId: string, attachmentIds: string[], filenames: string[], sessionId = "default") =>
    json<ChatResponse>("/api/mail/attachments/save", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        email_id: emailId,
        attachment_ids: attachmentIds,
        filenames,
      }),
    }),
  replyWithAttachments: (emailId: string, attachmentIds: string[], filenames: string[], sessionId = "default") =>
    json<ChatResponse>("/api/mail/attachments/reply", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        email_id: emailId,
        attachment_ids: attachmentIds,
        filenames,
      }),
    }),
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
  glance: () => json<Glance>("/api/glance"),
  listRfqs: async () => {
    try {
      const data = await json<{ items?: RfqPublic[] }>("/api/rfqs");
      return { items: Array.isArray(data?.items) ? data.items : [] };
    } catch {
      return { items: [] as RfqPublic[] };
    }
  },
  getRfq: (id: string) => json<RfqPublic>(`/api/rfqs/${encodeURIComponent(id)}`),
  intakeRfq: (body: RfqIntakeRequest = {}) =>
    json<RfqIntakeResponse>("/api/rfqs/intake", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  artifacts: () => json<{ items: Artifact[] }>("/api/artifacts"),
  audit: () => json<{ items: AuditEntry[] }>("/api/audit"),
  preferences: () => json<Preferences>("/api/preferences"),
  updatePreferences: (patch: Partial<Preferences>) =>
    json<Preferences>("/api/preferences", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  pending: (sessionId = "default") => json<{ items: PendingAction[] }>(`/api/pending?session_id=${sessionId}`),
  updatePending: (
    actionId: string,
    fields: { to?: string; subject?: string; body?: string },
    sessionId = "default",
  ) =>
    json<ChatResponse>(`/api/pending/${encodeURIComponent(actionId)}/update`, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, ...fields }),
    }),
  session: (sessionId = "default") =>
    json<Partial<ChatResponse>>(`/api/session?session_id=${sessionId}`),
  nextThought: (sessionId = "default") => json<ChatResponse>(`/api/thought?session_id=${sessionId}`),
  googleStatus: () => json<{ configured: boolean; connected: boolean; calendar: boolean; calendar_list: boolean; sheets?: boolean; account: string; task_to: string }>("/api/google/status"),
  googleAuthUrl: () => `${apiBase()}/api/google/auth`,
  watch: (sessionId = "default") =>
    json<{ watching: boolean; ready: boolean; status?: string; speak?: string; key?: string; scene?: ChatResponse["scene"] }>(
      `/api/watch?session_id=${sessionId}`,
    ),
  ackWatch: (sessionId = "default") =>
    json<{ ok: boolean; acked: boolean }>(`/api/watch/ack?session_id=${sessionId}`, { method: "POST" }),
  conversations: () => json<{ items: Conversation[] }>("/api/conversations"),
  createConversation: (category: string, title: string, focus: Record<string, unknown> = {}) =>
    json<Conversation>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ category, title, focus }),
    }),
  patchConversation: (id: string, patch: { minimized?: boolean; title?: string }) =>
    json<Conversation>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  spawnDrawingConversation: (focus: {
    filename?: string;
    local_name?: string;
    local_path?: string;
    mime?: string;
    drive_link?: string;
  }) =>
    json<Conversation>("/api/conversations/drawing", {
      method: "POST",
      body: JSON.stringify(focus),
    }),
  downloadUrl: (id: string) => `${apiBase()}/api/artifacts/${id}`,
  drawingUrl: (name: string) => `${apiBase()}/api/drawings/${encodeURIComponent(name)}`,
  saveMarkedDrawing: (sourceName: string, imageBase64: string, sessionId = "default") =>
    json<{ ok: boolean; speak: string; artifact: Artifact; drive_link?: string | null }>(
      "/api/drawings/marked",
      {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          source_name: sourceName,
          image_base64: imageBase64,
        }),
      },
    ),
  uploadInbox: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${apiBase()}/api/inbox`, { method: "POST", body });
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
      const response = await fetch(`${apiBase()}/api/canvas/files`, { method: "POST", body });
      if (!response.ok) throw new Error(await response.text());
      return response.json() as Promise<CanvasFile>;
    },
    fileUrl: (fileId: string) => `${apiBase()}/api/canvas/files/${fileId}`,
  },
};
