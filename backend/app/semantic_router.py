"""Thin semantic router — ultra-fast Gemini structured intent classification.

Sits in front of Hermes / local tool paths so the HUD gets a reliable
``target_agent`` and coarse route (ui / chat / vision / tools).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import settings

logger = logging.getLogger(__name__)

ROUTER_MODEL = "gemini-3.6-flash"

SYSTEM = """You are Jarvis's thin semantic router for a machine-shop work HUD.
Classify the operator utterance into exactly one intent and one orchestra agent.

intents:
- ui_command: desk/window actions only (open/minimize conversation, show/hide dock, switch notes)
- casual_chat: greetings, small talk, definitions, general Q&A with no tool side effects
  (e.g. "what is an RFQ?", "what does RFQ mean?", "explain RFQ" — knowledge only, no inbox/tools)
- vision_task: drawings, PDFs, images, dimensions, markups, "look at this print"
- tool_ops: mail, calendar, sheets, process/work RFQ or quote, send/draft email, search inbox, shop OEE, files, Drive
  (NOT definitional "what is an RFQ" — that is casual_chat)

target_agent codes:
- RES.01 Research — brief, web, casual synthesis
- SEC.02 Mail — inbox read / attachment triage
- DAT.03 Data — sheets, drawings, RFQ/CNC data
- OPS.04 Ops — outbound mail, calendar writes, authorize-path actions
- SYS — UI / system only

Pick the best single agent. confidence is 0.0–1.0.
"""


class IntentClassification(BaseModel):
    intent: Literal["ui_command", "casual_chat", "vision_task", "tool_ops"]
    target_agent: Literal["RES.01", "SEC.02", "DAT.03", "OPS.04", "SYS"]
    confidence: float = Field(ge=0.0, le=1.0)


def _casual_definition(message: str) -> bool:
    """Definitional RFQ asks are chat, not tool_ops (reuse intent.py rules)."""
    from .intent import is_rfq_definition

    return is_rfq_definition(message)


_WORK_MARKERS = (
    "email",
    "mail",
    "inbox",
    "gmail",
    "calendar",
    "schedule",
    "sheet",
    "oee",
    "quote",
    "send",
    "draft",
    "reply",
    "drive",
    "attachment",
    "authorize",
    "authorise",
    "rfq",
    "cnc",
    "drawing",
    "pdf",
    "blueprint",
    "inbox",
    "unread",
    "brief me",
    "briefing",
)


def try_obvious_casual(message: str) -> IntentClassification | None:
    """Skip router Gemini for tight small-talk heuristics only."""
    text = (message or "").strip()
    if not text:
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=1.0)
    if _casual_definition(text):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.98)
    low = text.lower()
    if re.search(r"\b(tell me a joke|make me laugh|say something funny)\b", low):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.96)
    if re.search(r"\bjoke\b", low) and re.search(r"\b(about|on|regarding)\b", low):
        if not any(m in low for m in ("mail", "email", "quote", "rfq", "send", "draft", "invoice")):
            return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.94)
    if any(marker in low for marker in _WORK_MARKERS):
        return None
    if re.match(
        r"^(hi|hello|hey|yo|good\s+(morning|afternoon|evening|night))\b",
        low,
    ):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.97)
    if re.search(r"\b(thanks|thank you|cheers|much obliged)\b", low) and len(low.split()) <= 12:
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.96)
    if re.search(
        r"\bhow\s+(?:'s|'re|are|is)\s+(?:your|you|the)\b",
        low,
    ) or re.search(r"\bhow\s+are\s+you\b", low):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.96)
    return None


def _fallback(message: str) -> IntentClassification:
    """Local heuristic when Gemini is unavailable — keep the desk alive."""
    low = (message or "").strip().lower()
    if not low:
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.2)
    if _casual_definition(message):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.85)
    if any(
        phrase in low
        for phrase in (
            "minimize",
            "minimise",
            "hide the dock",
            "show the dock",
            "hide conversations",
            "show conversations",
            "open notes",
            "maximize",
            "maximise",
            "expand the",
        )
    ):
        return IntentClassification(intent="ui_command", target_agent="SYS", confidence=0.55)
    if any(word in low for word in ("drawing", "pdf", "dimension", "blueprint", "print ", "markup", "vision")):
        return IntentClassification(intent="vision_task", target_agent="DAT.03", confidence=0.5)
    if any(
        word in low
        for word in (
            "email",
            "mail",
            "inbox",
            "gmail",
            "calendar",
            "schedule",
            "sheet",
            "oee",
            "rfq",
            "quote",
            "send",
            "draft",
            "reply",
            "drive",
        )
    ) and not _casual_definition(message):
        agent: Literal["RES.01", "SEC.02", "DAT.03", "OPS.04", "SYS"] = "OPS.04"
        if any(word in low for word in ("inbox", "unread", "read", "open", "from", "attachment")):
            agent = "SEC.02"
        if any(word in low for word in ("sheet", "oee", "rfq", "cnc", "drawing")):
            agent = "DAT.03"
        return IntentClassification(intent="tool_ops", target_agent=agent, confidence=0.45)
    return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.4)


async def classify_intent(message: str) -> IntentClassification:
    """Ultra-fast structured classification via gemini-3.6-flash + response_schema."""
    text = (message or "").strip()
    if not text:
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=1.0)
    if _casual_definition(text):
        return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.95)
    if not settings.gemini_api_key:
        return _fallback(text)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=ROUTER_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                temperature=0.0,
                max_output_tokens=64,
                response_mime_type="application/json",
                response_schema=IntentClassification,
            ),
        )
        parsed = response.parsed
        if isinstance(parsed, IntentClassification):
            result = parsed
        elif isinstance(parsed, dict):
            result = IntentClassification.model_validate(parsed)
        else:
            raw = (response.text or "").strip()
            result = IntentClassification.model_validate_json(raw) if raw else None
        if result is not None:
            if _casual_definition(text) and result.intent != "casual_chat":
                return IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.95)
            return result
    except Exception as exc:
        logger.warning("semantic_router fallback: %s", exc)

    return _fallback(text)


def classify_intent_sync(message: str) -> IntentClassification:
    """Sync wrapper for non-async call sites."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(classify_intent(message))

    # Already inside an event loop (e.g. some test runners) — run in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(classify_intent(message))).result(timeout=20)


def agent_id_from_code(code: str) -> str:
    """Map orchestra code → internal agent id used by AgentStatus."""
    mapping = {
        "RES.01": "research",
        "SEC.02": "sec",
        "DAT.03": "data",
        "OPS.04": "ops",
        "SYS": "ops",
    }
    return mapping.get((code or "").strip().upper(), "research")


def stamp_route(result: Any, classification: IntentClassification) -> Any:
    """Attach router fields + highlight the target orchestra node on a ChatResponse."""
    from .agents import agent_status_payload
    from .schemas import AgentStatus, ChatResponse

    if not isinstance(result, ChatResponse):
        return result

    agent_code = classification.target_agent
    states: dict[str, str] = {}
    if agent_code != "SYS":
        states[agent_id_from_code(agent_code)] = "active"

    agents = list(result.agents or [])
    has_live = any((getattr(a, "state", None) or "") in {"active", "waiting"} for a in agents)
    if result.pending:
        # HITL waiting states win; still stamp target_agent below
        pass
    elif not has_live:
        agents = [AgentStatus(**row) for row in agent_status_payload(states)]

    return result.model_copy(
        update={
            "target_agent": classification.target_agent,
            "route_intent": classification.intent,
            "agents": agents,
        }
    )


def handle_ui_command(message: str, session_id: str, classification: IntentClassification | None = None) -> Any:
    """Resolve desk/window commands in FastAPI without Hermes."""
    from . import db
    from .agents import agent_status_payload
    from .conversation_voice import match_query, parse_window_command
    from .conversations import list_desk, list_public
    from .schemas import ActivityEvent, AgentStatus, ChatResponse, Scene

    classification = classification or IntentClassification(
        intent="ui_command", target_agent="SYS", confidence=1.0
    )
    cmd = parse_window_command(message)
    agents = [AgentStatus(**row) for row in agent_status_payload({})]

    if not cmd:
        speak = "I can open, minimize, or switch conversations — say which note."
        return stamp_route(
            ChatResponse(
                speak=speak,
                reply=speak,
                scene=Scene(title="", widgets=[]),
                agents=agents,
                activity=[
                    ActivityEvent(id="ui-miss", time="", agent="SYS", message="UI command not matched"),
                ],
            ),
            classification,
        )

    action = cmd.get("action") or ""
    query = cmd.get("query") or ""
    ui_action: dict[str, Any] = {"action": action, "query": query, "session_id": session_id}

    if action == "hide_dock":
        speak = "Hiding open notes."
    elif action == "show_dock":
        speak = "Showing open notes."
    elif action == "minimize":
        rows = list_desk()
        row = match_query(query, rows)
        if row:
            db.update_conversation(row["id"], minimized=True)
            ui_action["conversation_id"] = row["id"]
            speak = f"Minimized {row.get('title') or 'that note'}."
        else:
            speak = "I could not find that conversation to minimize."
            ui_action["action"] = "noop"
    elif action == "expand":
        all_rows = [r for r in list_public() if r.get("status") != "archived"]
        row = match_query(query, all_rows) or match_query(query, list_desk())
        if row:
            db.update_conversation(row["id"], minimized=False)
            ui_action["conversation_id"] = row["id"]
            ui_action["session_id"] = row.get("session_id") or session_id
            speak = f"Opening {row.get('title') or 'that note'}."
        else:
            speak = "I could not find that conversation."
            ui_action["action"] = "noop"
    else:
        speak = "Done."

    db.add_message(session_id, "user", message)
    db.add_message(session_id, "assistant", speak)
    return stamp_route(
        ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene(title="", widgets=[]),
            agents=agents,
            ui_action=ui_action,
            activity=[
                ActivityEvent(id=f"ui-{action}", time="", agent="SYS", message=speak),
            ],
        ),
        classification,
    )
