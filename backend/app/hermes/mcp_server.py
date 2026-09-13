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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
