"""Jarvis MCP server — Hermes calls these tools; writes queue HITL."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow `python -m app.hermes.mcp_server` from backend/
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from mcp.server.fastmcp import FastMCP

from app.agents import agent_for_tool
from app.tools.registry import execute_tool

mcp = FastMCP("jarvis")


def _session() -> str:
    return (os.environ.get("JARVIS_SESSION_ID") or "default").strip() or "default"


def _dump(result: dict[str, Any]) -> str:
    return json.dumps(result, default=str)


@mcp.tool()
def jarvis_get_briefing() -> str:
    """Gather a short operations briefing (mail + calendar facts)."""
    return _dump(execute_tool("get_briefing", {}, _session()))


@mcp.tool()
def jarvis_search_emails(query: str = "", unread_only: bool = False) -> str:
    """Search the inbox. Read-only."""
    return _dump(execute_tool("search_emails", {"query": query, "unread_only": unread_only}, _session()))


@mcp.tool()
def jarvis_read_email(email_id: str = "", query: str = "", last: bool = False) -> str:
    """Open one email by id, query, or last message. Read-only."""
    return _dump(
        execute_tool("read_email", {"email_id": email_id, "query": query, "last": last}, _session())
    )


@mcp.tool()
def jarvis_draft_email(to: str, subject: str, body: str, in_reply_to: str = "") -> str:
    """Draft an email and queue HITL approval to send. Does not send until the human Authorizes."""
    return _dump(
        execute_tool(
            "draft_email",
            {"to": to, "subject": subject, "body": body, "in_reply_to": in_reply_to},
            _session(),
        )
    )


@mcp.tool()
def jarvis_list_calendar(days: int = 7, span: str = "") -> str:
    """List calendar events. Read-only."""
    return _dump(execute_tool("list_calendar", {"days": days, "span": span}, _session()))


@mcp.tool()
def jarvis_create_calendar_event(
    title: str,
    start_at: str,
    end_at: str = "",
    location: str = "",
    notes: str = "",
) -> str:
    """Queue a calendar event for HITL approval. Does not create until Authorizes."""
    return _dump(
        execute_tool(
            "create_calendar_event",
            {
                "title": title,
                "start_at": start_at,
                "end_at": end_at,
                "location": location,
                "notes": notes,
            },
            _session(),
        )
    )


@mcp.tool()
def jarvis_research(query: str) -> str:
    """Web research for a query."""
    return _dump(execute_tool("research", {"query": query}, _session()))


@mcp.tool()
def jarvis_read_shop_sheet(sheet_name: str = "") -> str:
    """Read bound shop spreadsheet / OEE. Read-only; never invent numbers."""
    return _dump(execute_tool("read_shop_sheet", {"sheet_name": sheet_name}, _session()))


@mcp.tool()
def jarvis_update_shop_sheet(message: str = "", sheet_name: str = "", updates: str = "") -> str:
    """Queue shop sheet cell writes for HITL. updates is JSON list of {cell,value} if known."""
    args: dict[str, Any] = {"message": message, "sheet_name": sheet_name}
    if updates.strip():
        try:
            args["updates"] = json.loads(updates)
        except json.JSONDecodeError:
            args["message"] = f"{message} {updates}".strip()
    return _dump(execute_tool("update_shop_sheet", args, _session()))


@mcp.tool()
def jarvis_create_document(title: str, body: str = "", bullets: str = "") -> str:
    """Create a local document artifact (inspection notes, reports)."""
    bullet_list = [b.strip() for b in bullets.split("\n") if b.strip()] if bullets else []
    return _dump(
        execute_tool(
            "create_document",
            {"title": title, "body": body, "bullets": bullet_list},
            _session(),
        )
    )


@mcp.tool()
def jarvis_agent_for_tool(tool_name: str) -> str:
    """Return which orchestra agent owns a Jarvis tool name."""
    return json.dumps({"tool": tool_name, "agent_id": agent_for_tool(tool_name)})


@mcp.tool()
def jarvis_memory_search(query: str, namespace: str = "", limit: int = 8) -> str:
    """Search local dual-write memory / RAG. Read-only."""
    return _dump(
        execute_tool(
            "memory_search",
            {"query": query, "namespace": namespace, "limit": limit},
            _session(),
        )
    )


@mcp.tool()
def jarvis_memory_upsert(text: str, namespace: str = "corpus", key: str = "") -> str:
    """Upsert a durable fact/doc into local memory (mirrored for offline RAG)."""
    return _dump(
        execute_tool(
            "memory_upsert",
            {"text": text, "namespace": namespace, "key": key},
            _session(),
        )
    )


@mcp.tool()
def jarvis_memory_forget(
    namespace: str = "",
    key: str = "",
    doc_id: str = "",
    wipe_namespace: bool = False,
) -> str:
    """Forget a local memory doc. Namespace wipe queues HITL Authorize."""
    return _dump(
        execute_tool(
            "memory_forget",
            {
                "namespace": namespace,
                "key": key,
                "doc_id": doc_id,
                "wipe_namespace": wipe_namespace,
            },
            _session(),
        )
    )


@mcp.tool()
def jarvis_memory_summary() -> str:
    """Summarize local memory (what Jarvis knows offline)."""
    return _dump(execute_tool("memory_summary", {}, _session()))


@mcp.tool()
def jarvis_save_mail_attachments(
    email_id: str = "",
    attachment_ids: str = "",
    filenames: str = "",
    query: str = "",
) -> str:
    """Save selected mail attachments locally (and Drive when connected)."""
    ids = [x.strip() for x in attachment_ids.split(",") if x.strip()] if attachment_ids else []
    names = [x.strip() for x in filenames.split(",") if x.strip()] if filenames else []
    return _dump(
        execute_tool(
            "save_mail_attachments",
            {
                "email_id": email_id,
                "attachment_ids": ids,
                "filenames": names,
                "query": query,
            },
            _session(),
        )
    )


@mcp.tool()
def jarvis_reason_rfq(mail_id: str = "", conversation_id: str = "", message: str = "") -> str:
    """Intake / reason a drawing RFQ from mail."""
    return _dump(
        execute_tool(
            "reason_rfq",
            {"mail_id": mail_id, "conversation_id": conversation_id, "message": message},
            _session(),
        )
    )


@mcp.tool()
def jarvis_create_pdf(title: str, body: str) -> str:
    """Create a local PDF artifact."""
    return _dump(execute_tool("create_pdf", {"title": title, "body": body}, _session()))


@mcp.tool()
def jarvis_create_spreadsheet(title: str, columns: str = "Item,Qty", rows: str = "") -> str:
    """Create a local spreadsheet artifact. columns is comma-separated; rows is optional JSON list of lists."""
    cols = [c.strip() for c in columns.split(",") if c.strip()] or ["Item", "Qty"]
    args: dict[str, Any] = {"title": title, "columns": cols, "rows": []}
    if rows.strip():
        try:
            args["rows"] = json.loads(rows)
        except json.JSONDecodeError:
            pass
    return _dump(execute_tool("create_spreadsheet", args, _session()))


@mcp.tool()
def jarvis_quote_analyze_drawing(path: str, prompt: str = "") -> str:
    """Gemini vision dimensional analysis of a local drawing file path."""
    return _dump(execute_tool("quote_analyze_drawing", {"path": path, "prompt": prompt}, _session()))


@mcp.tool()
def jarvis_quote_build(
    part_name: str,
    material: str = "",
    vision_summary: str = "",
    customer: str = "",
    scope: str = "",
    rm_source: str = "",
    rm_source_note: str = "",
    rm_price: str = "",
    machine: str = "",
    machining_rate: str = "",
) -> str:
    """Build a quotation spreadsheet from part + vision notes.

    Optional scope (labour or with_material), rm_source, rm_source_note, rm_price, machine, and machining_rate must come from the owner or tools — never invented; machining_rate must not be below the demo minimum in playbooks/quote/files/mhr-demo.md.
    """
    return _dump(
        execute_tool(
            "quote_build",
            {
                "part_name": part_name,
                "material": material,
                "vision_summary": vision_summary,
                "customer": customer,
                "scope": scope,
                "rm_source": rm_source,
                "rm_source_note": rm_source_note,
                "rm_price": rm_price,
                "machine": machine,
                "machining_rate": machining_rate,
            },
            _session(),
        )
    )


@mcp.tool()
def jarvis_quote_pdf(part_name: str = "") -> str:
    """Create a PDF artifact for the current quotation."""
    return _dump(execute_tool("quote_pdf", {"part_name": part_name}, _session()))


@mcp.tool()
def jarvis_quote_verify() -> str:
    """Deterministic quote proof checklist before send. Does not invent numbers."""
    return _dump(execute_tool("quote_verify", {}, _session()))


@mcp.tool()
def jarvis_quote_playbook_note(what_went_wrong: str, change: str, layer: str = "process") -> str:
    """Append a dated correction line to the quote playbook notes.md."""
    return _dump(
        execute_tool(
            "quote_playbook_note",
            {"what_went_wrong": what_went_wrong, "layer": layer, "change": change},
            _session(),
        )
    )


@mcp.tool()
def jarvis_quote_send(to: str, subject: str = "", body: str = "", pdf_path: str = "") -> str:
    """Queue quote PDF email for HITL Authorize (does not send). Refuses when proof stop=true."""
    return _dump(
        execute_tool(
            "quote_send",
            {"to": to, "subject": subject, "body": body, "pdf_path": pdf_path},
            _session(),
        )
    )


@mcp.tool()
def jarvis_office_refresh_tasks() -> str:
    """Refresh morning suggested-task cards (RFQ + production)."""
    return _dump(execute_tool("office_refresh_tasks", {}, _session()))


@mcp.tool()
def jarvis_get_weather(city: str = "Pune") -> str:
    """Current weather for the office city (Open-Meteo)."""
    return _dump(execute_tool("get_weather", {"city": city}, _session()))


@mcp.tool()
def jarvis_browser_record_evidence(url: str, title: str = "", notes: str = "") -> str:
    """Record evidence for a novel browser task (path + notes; screenshot optional later)."""
    return _dump(
        execute_tool(
            "browser_record_evidence",
            {"url": url, "title": title, "notes": notes},
            _session(),
        )
    )


@mcp.tool()
def jarvis_browser_queue_action(title: str, summary: str, url: str, evidence_id: str = "") -> str:
    """Queue a consequential browser action for HITL Authorize."""
    return _dump(
        execute_tool(
            "browser_queue_action",
            {"title": title, "summary": summary, "url": url, "evidence_id": evidence_id},
            _session(),
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
