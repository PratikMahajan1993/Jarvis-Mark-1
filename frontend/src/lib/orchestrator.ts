import type { PendingAction } from "./types";

export type AgentId = "research" | "sec" | "data" | "ops";
export type AgentNodeState = "" | "active" | "waiting";

export type AgentNode = {
  id: AgentId;
  code: string;
  label: string;
  state: AgentNodeState;
};

export type ActivityItem = {
  id: string;
  time: string;
  agent: string;
  message: string;
};

export type OrchestratorMode = "idle" | "listening" | "busy" | "hitl";

export const DEFAULT_AGENTS: AgentNode[] = [
  { id: "research", code: "RES.01", label: "Research", state: "" },
  { id: "sec", code: "SEC.02", label: "Mail", state: "" },
  { id: "data", code: "DAT.03", label: "Data", state: "" },
  { id: "ops", code: "OPS.04", label: "Ops", state: "" },
];

export function formatClock(date = new Date()): string {
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function agentForPending(action: PendingAction | undefined): AgentId {
  const kind = (action?.kind || "").toLowerCase();
  if (kind.includes("sheet") || kind.includes("cnc") || kind.includes("rfq")) return "data";
  if (kind.includes("email") || kind.includes("mail") || kind.includes("handoff") || kind.includes("clarify")) {
    return "ops";
  }
  if (kind.includes("calendar")) return "ops";
  return "ops";
}

export function agentCode(id: AgentId): string {
  return DEFAULT_AGENTS.find((a) => a.id === id)?.code || "SYS";
}

export function inferBusyAgents(message: string, toolHint = ""): AgentId[] {
  const text = `${message} ${toolHint}`.toLowerCase();
  const ids: AgentId[] = [];
  if (/\b(research|brief|search web|look up)\b/.test(text)) ids.push("research");
  if (/\b(email|inbox|mail|gmail|forward|reply)\b/.test(text)) ids.push("sec");
  if (/\b(sheet|shop|oee|spreadsheet|excel|document|pdf|rfq|cnc)\b/.test(text)) ids.push("data");
  if (/\b(send|deploy|create event|calendar|schedule|write|update)\b/.test(text)) ids.push("ops");
  if (!ids.length) ids.push("research");
  return ids;
}

export function shallICopy(action: PendingAction): { title: string; summary: string; meta: string } {
  if (action.kind === "cnc_promote") {
    return {
      title: (action.title || "").trim() || "Promote draft NC?",
      summary: "This is a draft program, not proven. It is not for the machine until you authorize it.",
      meta: `Authorization Required // ${agentCode(agentForPending(action))}`,
    };
  }
  if (action.kind === "sheets_write") {
    return {
      title: (action.title || "").trim() || "Overwrite production numbers?",
      summary: "This overwrites production numbers in the bound Google Sheet. Google will autosave.",
      meta: `Authorization Required // ${agentCode(agentForPending(action))}`,
    };
  }
  return {
    title: action.title || "Authorize action",
    summary: action.summary || "The operations agent requests authorization to proceed.",
    meta: `Authorization Required // ${agentCode(agentForPending(action))}`,
  };
}
