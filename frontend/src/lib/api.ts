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

export type QuoteOperation = {
  id: string;
  operation: string;
  machine_type: string;
  outsource: number;
  outsource_case: string;
  outsource_vendor: string;
  outsource_price_minor: number | null;
  outsource_received: number;
  special_tooling: string;
  setup_minor: number | null;
  cycle_min: number | null;
  notes: string;
};

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
  quoteScope: (sessionId = "default", customer = "", scope = "") =>
    json<{
      ok: boolean;
      scope?: "labour" | "with_material" | string;
      source?: string;
      need?: string;
      message?: string;
    }>("/api/quote/scope", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, customer, scope }),
    }),
  rmQuotes: (sessionId = "default") =>
    json<{
      ok: boolean;
      requests: {
        id: string;
        material: string;
        supplier: string;
        status: string;
        quoted_price_minor?: number | null;
        currency?: string;
        is_estimate?: number;
        notes?: string;
        quote_date?: string | null;
      }[];
    }>(`/api/quote/rm-quotes?session_id=${encodeURIComponent(sessionId)}`),
  requestRmQuote: (sessionId: string, material: string, supplier: string, supplierEmail: string) =>
    json<{ ok: boolean; sent?: boolean; message?: string; request_id?: string }>("/api/quote/rm-quote/request", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        material,
        supplier,
        supplier_email: supplierEmail,
      }),
    }),
  recordRmQuote: (
    sessionId: string,
    fields: { price_inr: string; quote_date: string; notes: string; is_estimate: boolean; request_id?: string },
  ) =>
    json<{ ok: boolean; message?: string }>("/api/quote/rm-quote/record", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, ...fields }),
    }),
  quoteOperations: (sessionId = "default") =>
    json<{ ok: boolean; operations: QuoteOperation[] }>(
      `/api/quote/operations?session_id=${encodeURIComponent(sessionId)}`,
    ),
  addQuoteOperation: (sessionId: string, template: string) =>
    json<{ ok: boolean; message?: string; operations?: QuoteOperation[] }>("/api/quote/operations", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, template }),
    }),
  updateQuoteOperation: (sessionId: string, operation: QuoteOperation) =>
    json<{ ok: boolean; message?: string; operations?: QuoteOperation[] }>("/api/quote/operations/update", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        operation_id: operation.id,
        operation: operation.operation,
        machine_type: operation.machine_type,
        outsource: Boolean(operation.outsource),
        outsource_case: operation.outsource_case,
        outsource_vendor: operation.outsource_vendor,
        outsource_price_inr:
          operation.outsource_price_minor == null ? "" : String(operation.outsource_price_minor / 100),
        outsource_received: Boolean(operation.outsource_received),
        special_tooling: operation.special_tooling,
        setup_inr: operation.setup_minor == null ? "" : String(operation.setup_minor / 100),
        cycle_min: operation.cycle_min == null ? "" : String(operation.cycle_min),
        notes: operation.notes,
      }),
    }),
  deleteQuoteOperation: (sessionId: string, operationId: string) =>
    json<{ ok: boolean; operations?: QuoteOperation[] }>("/api/quote/operations/delete", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, operation_id: operationId }),
    }),
  reorderQuoteOperations: (sessionId: string, orderedIds: string[]) =>
    json<{ ok: boolean; operations?: QuoteOperation[] }>("/api/quote/operations/reorder", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, ordered_ids: orderedIds }),
    }),
  mhrRates: () =>
    json<{
      ok: boolean;
      message?: string;
      rates: {
        id: string;
        machine_type: string;
        floor_inr: number;
        attested_by: string;
        attested_at: string;
        status: string;
      }[];
    }>("/api/quote/mhr"),
  attestMhr: (machineType: string, attestedBy: string, floorInr: string, rateId = "") =>
    json<{ ok: boolean; message?: string }>("/api/quote/mhr/attest", {
      method: "POST",
      body: JSON.stringify({
        machine_type: machineType,
        attested_by: attestedBy,
        floor_inr: floorInr,
        rate_id: rateId,
      }),
    }),
  verifyQuote: (sessionId = "default", stage = "draft") =>
    json<import("@/lib/pane/quoteContract").QuoteVerifyResult>("/api/quote/verify", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, stage }),
    }),
  drawingIdentity: (sessionId = "default") =>
    json<import("@/lib/pane/knowledge").DrawingIdentity>(
      `/api/knowledge/drawing-identity?session_id=${encodeURIComponent(sessionId)}`,
    ),
  recallDrawing: (sessionId = "default", entityId = "") => {
    const params = new URLSearchParams({ session_id: sessionId });
    if (entityId) params.set("entity_id", entityId);
    return json<import("@/lib/pane/knowledge").RecallPayload>(`/api/knowledge/recall?${params.toString()}`);
  },
  shopFloor: () => json<import("@/lib/pane/knowledge").ShopFloorPayload>("/api/shop/floor"),
  findQuoteDrawing: (sessionId = "default", partHint = "") =>
    json<{
      ok: boolean;
      path?: string;
      filename?: string;
      source?: string;
      need?: string;
      message?: string;
      candidates?: { path?: string; filename?: string; source?: string }[];
    }>("/api/quote/find-drawing", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, part_hint: partHint }),
    }),
  chat: (message: string, sessionId = "default", idempotencyKey?: string) =>
    json<ChatResponse | { turn_id: string; state: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),
  startHermesRun: (message: string, sessionId = "default") =>
    json<{ run_id: string; status: string }>("/api/hermes/runs", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  hermesRunEvents: (runId: string, signal?: AbortSignal) =>
    fetch(`${apiBase()}/api/hermes/runs/${encodeURIComponent(runId)}/events`, {
      signal,
      headers: mutatingAuthHeaders("GET"),
    }),
  stopHermesRun: (runId: string) =>
    json<{ run_id: string; status: string }>(`/api/hermes/runs/${encodeURIComponent(runId)}/stop`, {
      method: "POST",
      body: "{}",
    }),
  approveHermesRun: (runId: string, choice: "once" | "deny", requestId = "") =>
    json<Record<string, unknown>>(`/api/hermes/runs/${encodeURIComponent(runId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ choice, request_id: requestId }),
    }),
  briefingCache: () =>
    json<{ cached?: boolean; speak?: string }>("/api/briefing/cache"),
  extractText: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${apiBase()}/api/extract/text`, {
      method: "POST",
      body,
      headers: mutatingAuthHeaders("POST"),
    });
    if (!response.ok) {
      throw new Error(`Extract failed (${response.status})`);
    }
    return (await response.json()) as {
      ok: boolean;
      drawing?: boolean;
      message?: string;
      text?: string;
      filename?: string;
    };
  },
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
  masterdataList: (entity: string) =>
    json<{ ok: boolean; items: Array<Record<string, unknown>> }>(`/api/masterdata/${entity}`),
  masterdataCreate: (entity: string, fields: Record<string, unknown>) =>
    json<{ ok: boolean; id: string }>(`/api/masterdata/${entity}`, {
      method: "POST",
      body: JSON.stringify({ fields }),
    }),
  masterdataReplace: (entity: string, id: string, fields: Record<string, unknown>) =>
    json<{ ok: boolean; id: string; superseded: string }>(`/api/masterdata/${entity}/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ fields }),
    }),
  masterdataAliases: (kind: string) =>
    json<{ ok: boolean; items: Array<Record<string, unknown>> }>(`/api/masterdata/aliases?kind=${encodeURIComponent(kind)}`),
  masterdataAddAlias: (kind: string, canonicalId: string, alias: string) =>
    json<{ ok: boolean }>(`/api/masterdata/aliases`, {
      method: "POST",
      body: JSON.stringify({ kind, canonical_id: canonicalId, alias, source: "manual" }),
    }),
  masterdataRemoveAlias: (kind: string, alias: string) =>
    json<{ ok: boolean }>(
      `/api/masterdata/aliases?kind=${encodeURIComponent(kind)}&alias=${encodeURIComponent(alias)}`,
      { method: "DELETE" },
    ),
  masterdataResolve: (kind: string, alias: string) =>
    json<{ ok: boolean; canonical_id: string | null; resolved: boolean }>(
      `/api/masterdata/resolve?kind=${encodeURIComponent(kind)}&alias=${encodeURIComponent(alias)}`,
    ),
  masterdataOptions: () =>
    json<{
      ok: boolean;
      machines: Array<{ id: string; name: string; machine_type: string }>;
      materials: Array<{ id: string; grade: string }>;
      customers: Array<{ id: string; name: string }>;
    }>("/api/masterdata/options"),
};
