"""Fixed specialist agent map for the Orchestrator orchestra."""

from __future__ import annotations

from typing import Literal

AgentId = Literal["research", "sec", "data", "ops"]

AGENTS: dict[AgentId, dict[str, str]] = {
    "research": {"id": "research", "code": "RES.01", "label": "Research", "domain": "web/brief synthesis"},
    "sec": {"id": "sec", "code": "SEC.02", "label": "Mail", "domain": "inbox read / attachment triage"},
    "data": {"id": "data", "code": "DAT.03", "label": "Data", "domain": "shop sheets, local data, inspection drafts"},
    "ops": {"id": "ops", "code": "OPS.04", "label": "Ops", "domain": "outbound mail, calendar, sheet writes, CNC"},
}

# Pending kinds / tool names → orchestra node
KIND_TO_AGENT: dict[str, AgentId] = {
    "email_send": "ops",
    "email_compose": "ops",
    "email_forward": "ops",
    "quote_send": "ops",
    "memory_wipe": "ops",
    "browser_action": "ops",
    "calendar_create": "ops",
    "sheets_write": "data",
    "cnc_promote": "data",
    "handoff_gemini": "ops",
    "clarify": "ops",
}

TOOL_TO_AGENT: dict[str, AgentId] = {
    "get_briefing": "research",
    "research": "research",
    "search_emails": "sec",
    "read_email": "sec",
    "save_mail_attachments": "sec",
    "review_inbox": "sec",
    "draft_email": "ops",
    "send_email": "ops",
    "forward_email": "ops",
    "reply_with_attachments": "ops",
    "task_for_gemini": "ops",
    "list_calendar": "ops",
    "create_calendar_event": "ops",
    "create_spreadsheet": "data",
    "create_document": "data",
    "create_pdf": "data",
    "bind_shop_sheet": "data",
    "ensure_shop_sheet": "data",
    "read_shop_sheet": "data",
    "update_shop_sheet": "data",
    "reason_rfq": "data",
    "cnc_suggest": "data",
    "quote_analyze_drawing": "data",
    "quote_build": "data",
    "quote_pdf": "data",
    "quote_send": "ops",
    "memory_search": "research",
    "memory_upsert": "research",
    "memory_forget": "ops",
    "memory_summary": "research",
    "memory_reindex_mail": "sec",
    "office_refresh_tasks": "ops",
    "office_list_tasks": "ops",
    "get_weather": "research",
    "browser_record_evidence": "ops",
    "browser_queue_action": "ops",
    "show_artifact": "data",
    "open_artifact": "data",
    "drive_upload": "ops",
    "drive_find": "data",
}


def agent_for_kind(kind: str) -> AgentId:
    return KIND_TO_AGENT.get((kind or "").strip().lower(), "ops")


def agent_for_tool(tool_name: str) -> AgentId:
    return TOOL_TO_AGENT.get((tool_name or "").strip(), "ops")


def agent_code(agent_id: AgentId | str) -> str:
    row = AGENTS.get(agent_id)  # type: ignore[arg-type]
    if row:
        return row["code"]
    return "SYS"


def agent_status_payload(states: dict[str, str] | None = None) -> list[dict[str, str]]:
    states = states or {}
    out: list[dict[str, str]] = []
    for agent_id, meta in AGENTS.items():
        out.append(
            {
                "id": meta["id"],
                "code": meta["code"],
                "label": meta["label"],
                "domain": meta["domain"],
                "state": states.get(agent_id, ""),
            }
        )
    return out
