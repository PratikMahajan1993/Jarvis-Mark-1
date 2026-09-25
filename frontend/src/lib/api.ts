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

export function apiBase(): string {
  const fallback = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  if (typeof window === "undefined") return fallback;
  try {
    return new URL(fallback, window.location.origin).origin;
  } catch {
    return fallback;
  }
}

function mutatingAuthHeaders(method?: string): Record<string, string> {
  const verb = (method || "GET").toUpperCase();
  if (verb === "GET" || verb === "HEAD" || verb === "OPTIONS") return {};
  const token = (process.env.NEXT_PUBLIC_JARVIS_API_TOKEN || "").trim();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...mutatingAuthHeaders(init?.method),
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
    json<ChatResponse | { turn_id: string; state: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  dropDrawing: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${apiBase()}/api/chat/drawing`, {
      method: "POST",
      body,
      headers: mutatingAuthHeaders("POST"),
    });
    if (!response.ok) {
      throw new Error(`Drop failed (${response.status})`);
    }
    return (await response.json()) as ChatResponse;
  },
  closeDrawing: (sessionId = "default") =>
    json<ChatResponse>("/api/chat/drawing/close", {
      method: "POST",
      body: JSON.stringify({ message: "close the drawing", session_id: sessionId }),
    }),
  getTurn: (turnId: string) =>
    json<{
      id: string;
      state: string;
      stage?: string;
      output?: ChatResponse | null;
      error?: string;
    }>(`/api/turns/${encodeURIComponent(turnId)}`),
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
  conversations: (desk = false) =>
    json<{ items: Conversation[]; ambient_session?: string }>(
      `/api/conversations${desk ? "?desk=true" : ""}`,
    ),
  createConversation: (category: string, title: string, focus: Record<string, unknown> = {}) =>
    json<Conversation>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ category, title, focus }),
    }),
  startDiscussion: (title = "", focus: Record<string, unknown> = {}) =>
    json<Conversation>("/api/conversations/discussion", {
      method: "POST",
      body: JSON.stringify({ title, focus }),
    }),
  startOrResumeWorkflow: (
    title: string,
    focus: Record<string, unknown> = {},
    resumeKey = "",
  ) =>
    json<Conversation>("/api/conversations/workflow", {
      method: "POST",
      body: JSON.stringify({ title, focus, resume_key: resumeKey }),
    }),
  patchConversation: (id: string, patch: { minimized?: boolean; title?: string; status?: string }) =>
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
    const response = await fetch(`${apiBase()}/api/inbox`, {
      method: "POST",
      body,
      headers: mutatingAuthHeaders("POST"),
    });
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
      const response = await fetch(`${apiBase()}/api/canvas/files`, {
        method: "POST",
        body,
        headers: mutatingAuthHeaders("POST"),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json() as Promise<CanvasFile>;
    },
    fileUrl: (fileId: string) => `${apiBase()}/api/canvas/files/${fileId}`,
  },
  suggestedTasks: (refresh = false, sessionId = "default") =>
    json<{ items: Array<Record<string, unknown>>; weather?: { speak?: string } }>(
      `/api/suggested-tasks?refresh=${refresh ? "true" : "false"}&session_id=${encodeURIComponent(sessionId)}`,
    ),
  setSuggestedTaskStatus: (taskId: string, status = "dismissed") =>
    json<Record<string, unknown>>(`/api/suggested-tasks/${encodeURIComponent(taskId)}/status?status=${encodeURIComponent(status)}`, {
      method: "POST",
    }),
  officeRefresh: (sessionId = "default") =>
    json<Record<string, unknown>>(`/api/office/refresh?session_id=${encodeURIComponent(sessionId)}`, {
      method: "POST",
    }),
  hermesWarm: (sessionId = "default", force = false) =>
    json<{ ok: boolean; started?: boolean; fresh?: boolean; status?: string; gateway?: boolean }>(
      `/api/hermes/warm?session_id=${encodeURIComponent(sessionId)}&force=${force ? "true" : "false"}`,
      { method: "POST" },
    ),
  metrics: () => json<Record<string, unknown>>("/api/metrics"),
  quoteVarianceErosion: (limit = 20) =>
    json<{
      items: Array<{
        quote_line_id: string;
        kind: string;
        description: string;
        erosion_minor: number;
        quoted_amount_minor: number;
        actual_amount_minor: number;
        source_ref: string;
        recorded_at: string;
      }>;
    }>(`/api/quote-variance/erosion?limit=${encodeURIComponent(String(limit))}`),
  toolwatchCapture: (body: {
    utterance: string;
    open_job_machine?: string;
    tool_instance_id?: string;
  }) =>
    json<Record<string, unknown>>("/api/toolwatch/capture", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
