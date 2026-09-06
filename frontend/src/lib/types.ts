export type Widget = {
  type: "kpi" | "table" | "markdown" | "chart" | "timeline" | "quote";
  label?: string;
  value?: string | number;
  hint?: string;
  title?: string;
  columns?: string[];
  rows?: Array<Array<string | number>>;
  text?: string;
  chart_type?: "bar" | "line";
  points?: Array<{ label: string; value: number }>;
  items?: Array<{ time?: string; title?: string; detail?: string }>;
  cite?: string;
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

export type ChatResponse = {
  speak: string;
  reply: string;
  scene: Scene;
  artifacts: Artifact[];
  pending: PendingAction[];
  offline: boolean;
  more?: number;
  watching?: boolean;
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
  google?: { configured: boolean; connected: boolean; account: string; task_to: string };
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
