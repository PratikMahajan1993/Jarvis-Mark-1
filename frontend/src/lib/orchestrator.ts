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

/** Map backend ``target_agent`` orchestra code → AgentId. */
export function agentIdFromTarget(code: string | null | undefined): AgentId | null {
  switch ((code || "").trim().toUpperCase()) {
    case "RES.01":
      return "research";
    case "SEC.02":
      return "sec";
    case "DAT.03":
      return "data";
    case "OPS.04":
      return "ops";
    default:
      return null;
  }
}

export function shallICopy(action: PendingAction): {
  title: string;
  summary: string;
  meta: string;
  consequence: string;
  irreversibility: number;
} {
  const score = Math.min(5, Math.max(1, Number(action.irreversibility) || 2));
  const consequence =
    (action.consequence || "").trim() ||
    "Queued action — review before authorizing.";
  const risk = `Irreversibility ${score}/5`;
  if (action.kind === "cnc_promote") {
    return {
      title: (action.title || "").trim() || "Promote draft NC?",
      summary: "This is a draft program, not proven. It is not for the machine until you authorize it.",
      meta: `Authorization Required // ${agentCode(agentForPending(action))} // ${risk}`,
      consequence,
      irreversibility: score,
    };
  }
  if (action.kind === "sheets_write") {
    return {
      title: (action.title || "").trim() || "Overwrite production numbers?",
      summary: "This overwrites production numbers in the bound Google Sheet. Google will autosave.",
      meta: `Authorization Required // ${agentCode(agentForPending(action))} // ${risk}`,
      consequence,
      irreversibility: score,
    };
  }
  return {
    title: action.title || "Authorize action",
    summary: action.summary || "The operations agent requests authorization to proceed.",
    meta: `Authorization Required // ${agentCode(agentForPending(action))} // ${risk}`,
    consequence,
    irreversibility: score,
  };
}
