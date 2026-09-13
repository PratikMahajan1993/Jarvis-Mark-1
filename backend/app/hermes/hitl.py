"""Human-in-the-loop interceptor — queues external actions for Authorize/Reject."""

from __future__ import annotations

import uuid
from typing import Any

from .. import db
from ..agents import agent_code, agent_for_kind, agent_for_tool


def request_human_approval(
    *,
    session_id: str,
    kind: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    action_id: str | None = None,
    tool_name: str = "",
    agent_id: str = "",
) -> dict[str, Any]:
    """
    Stage an external side effect. Never executes connectors.
    Returns the pending action dict (id, kind, title, summary, payload, agent_id, tool_name).
    """
    resolved_agent = agent_id or (agent_for_tool(tool_name) if tool_name else agent_for_kind(kind))
    pending_id = action_id or f"{kind}-{uuid.uuid4().hex[:12]}"
    enriched = dict(payload or {})
    enriched.setdefault("_jarvis", {})
    if isinstance(enriched.get("_jarvis"), dict):
        enriched["_jarvis"].update(
            {
                "agent_id": resolved_agent,
                "agent_code": agent_code(resolved_agent),
                "tool_name": tool_name or "",
            }
        )
    return db.add_pending(
        pending_id,
        session_id,
        kind,
        title,
        summary,
        enriched,
        agent_id=resolved_agent,
        tool_name=tool_name or "",
    )
