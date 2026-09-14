"""Human-in-the-loop interceptor — queues external actions for Authorize/Reject."""

from __future__ import annotations

import uuid
from typing import Any

from .. import db
from ..agents import agent_code, agent_for_kind, agent_for_tool
from ..hitl_meta import blast_radius_for, enrich_payload


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
    irreversibility: int | None = None,
    consequence: str | None = None,
) -> dict[str, Any]:
    """
    Stage an external side effect. Never executes connectors.
    Returns the pending action dict including blast-radius fields.
    """
    resolved_agent = agent_id or (agent_for_tool(tool_name) if tool_name else agent_for_kind(kind))
    pending_id = action_id or f"{kind}-{uuid.uuid4().hex[:12]}"
    enriched = enrich_payload(kind, payload)
    if irreversibility is not None or consequence:
        meta = enriched.get("_jarvis") if isinstance(enriched.get("_jarvis"), dict) else {}
        meta = dict(meta)
        if irreversibility is not None:
            meta["irreversibility"] = int(irreversibility)
        if consequence:
            meta["consequence"] = str(consequence)
        enriched["_jarvis"] = meta
    score, cons = blast_radius_for(kind, enriched)
    if isinstance(enriched.get("_jarvis"), dict):
        enriched["_jarvis"].update(
            {
                "agent_id": resolved_agent,
                "agent_code": agent_code(resolved_agent),
                "tool_name": tool_name or "",
                "irreversibility": score,
                "consequence": cons,
            }
        )
    row = db.add_pending(
        pending_id,
        session_id,
        kind,
        title,
        summary,
        enriched,
        agent_id=resolved_agent,
        tool_name=tool_name or "",
    )
    row["irreversibility"] = score
    row["consequence"] = cons
    return row
