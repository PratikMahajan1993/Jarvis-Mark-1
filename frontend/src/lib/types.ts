export type Widget = {
  type: "kpi" | "table" | "markdown" | "chart" | "timeline" | "quote" | "attachments";
  label?: string;
  value?: string | number;
  hint?: string;
  title?: string;
  columns?: string[];
  rows?: Array<Array<string | number>>;
  text?: string;
  chart_type?: "bar" | "line";
  points?: Array<{ label: string; value: number }>;
  items?: Array<Record<string, unknown>>;
  cite?: string;
  email_id?: string;
};

export type MailAttachment = {
  attachment_id: string;
  filename: string;
  mime?: string;
  size?: number;
  readable?: boolean;
  cad?: boolean;
  status: "gmail" | "local" | "drive" | "both";
  local_path?: string | null;
  local_name?: string | null;
  drive_link?: string | null;
  artifact_id?: string | null;
};

export type Scene = {
  title: string;
  subtitle?: string | null;
  widgets: Widget[];
};

export type Artifact = {
  id: string;
  kind: string;
  name: string;
  path: string;
  created_at: string;
};

export type PendingAction = {
  id: string;
  kind: string;
  title: string;
  summary: string;
  payload: Record<string, unknown>;
};

export type ConversationTurn = {
  role: string;
  content: string;
};

export type Conversation = {
  id: string;
  session_id: string;
  category: string;
  title: string;
  focus: Record<string, unknown>;
  minimized: boolean;
  status: string;
  model?: string;
  updated_at?: string;
  speak?: string;
  scene?: Scene;
  pending?: PendingAction[];
  turns?: ConversationTurn[];
  waiting?: boolean;
};

export type SimilarJob = {
  id: string;
  part_name: string;
  material: string;
  machine: string;
  cycle_min: number | null;
  geometry_notes: string;
};

export type RfqPublic = {
  id: string;
  status: string;
  mail_id: string;
  conversation_id: string;
  extract: Record<string, unknown>;
  similar_jobs: SimilarJob[];
  pending_reply: string;
  deadline_iso: string;
  catch: string;
  updated_at: string;
};

export type RfqIntakeRequest = {
  mail_id?: string;
  conversation_id?: string;
  message?: string;
};

export type RfqIntakeResponse = {
  rfq: RfqPublic;
  conversation: Conversation;
  speak: string;
};

export type CriticalKind = "rfq" | "efficiency" | "shift";
export type CriticalTone = "cyan" | "amber" | "red";

export type CriticalAlert = {
  kind: CriticalKind;
  title: string;
  detail?: string;
  tone?: CriticalTone;
  sourceId?: string;
};

export type Glance = {
  line: string;
  whisper: string;
  speak: string;
  key: string;
  minutes: number | null;
  critical?: CriticalAlert | null;
};

export type ChatResponse = {
  speak: string;
  reply: string;
  scene: Scene;
  artifacts: Artifact[];
  pending: PendingAction[];
  attachments?: MailAttachment[];
  mail_id?: string | null;
  offline: boolean;
  more?: number;
  watching?: boolean;
  critical?: CriticalAlert | null;
};

export type Preferences = {
  display_name: string;
  assistant_name: string;
  persona: string;
  verbosity: "concise" | "normal" | "detailed";
  timezone: string;
  job_context: string;
  sign_off: string;
  voice_enabled: boolean;
  email_enabled: boolean;
  calendar_enabled: boolean;
  files_enabled: boolean;
  research_enabled: boolean;
  hud_density: "comfortable" | "dense";
};

export type Health = {
  ok: boolean;
  ollama: boolean;
  model: string;
  models: string[];
  model_ready?: boolean;
  provider?: string;
  google?: { configured: boolean; connected: boolean; calendar?: boolean; calendar_list?: boolean; sheets?: boolean; account: string; task_to: string };
};

export type AuditEntry = {
  id: number;
  created_at: string;
  session_id: string;
  tool: string;
  detail: string;
  status: string;
};

export type TranscriptItem = {
  role: "user" | "jarvis";
  text: string;
};
