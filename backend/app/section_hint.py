"""Server-side scroll hints (X4): which HUD section a turn belongs to. Pure text rules, no tools."""

from __future__ import annotations

import re
from typing import Any

_ENGINEERING = re.compile(
    r"\b(drawing|drawings|rfq|quote|machin(?:e|ing)|strategy|cnc|nc program|tolerance|fixture|"
    r"job shop|engineering|g[- ]?code|solidworks|step file|dxf)\b",
    re.I,
)
_CASUAL = re.compile(
    r"\b(mail|email|inbox|gmail|reply|send|discuss|chat|calendar|meeting|note|remember|remind|"
    r"hello|thanks|thank you)\b",
    re.I,
)
_BACK_TO_CHAT = re.compile(r"\b(back to (?:the )?chat|leave engineering|close (?:the )?bench)\b", re.I)
_STATUS = re.compile(
    r"^(what(?:'s| is| are)|how(?:'s| is| are)|is|are|any)\b.*"
    r"\b(status|running|updates?|triaged|happening|doing|progress|idle|watch)\b",
    re.I,
)


def ui_hint(message: str, route_intent: str | None = None) -> dict[str, Any] | None:
    text = (message or "").strip()
    if not text or route_intent == "ui_command":
        return None
    if _BACK_TO_CHAT.search(text):
        return {"section": "casual", "reason": "explicit"}
    if len(text) <= 80 and _STATUS.search(text):
        return None
    from .intent import is_quote_start

    if is_quote_start(text):
        return {"section": "engineering", "reason": "quote"}
    if _ENGINEERING.search(text):
        return {"section": "engineering", "reason": "drawing"}
    if _CASUAL.search(text) or route_intent == "casual_chat":
        return {"section": "casual", "reason": "chat"}
    return None
