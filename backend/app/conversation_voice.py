from __future__ import annotations

import re
from typing import Any


def parse_window_command(message: str) -> dict[str, str] | None:
    low = (message or "").strip().lower()
    if not low:
        return None
    if re.search(r"\b(hide|close) (the )?(conversations?|dock|windows)\b", low):
        return {"action": "hide_dock"}
    if re.search(r"\b(show|open) (the )?(conversations?|dock|windows)\b", low):
        return {"action": "show_dock"}
    match = re.search(
        r"\b(minimize|minimise|collapse|hide)\b.+\b(drawing|chat|window|conversation|thread)\b"
        r"|\b(minimize|minimise|collapse)\b(?:\s+the)?\s+(.+)$",
        low,
    )
    if match and not re.search(r"\b(conversations?|dock|windows)\b", low):
        query = (match.group(4) or match.group(2) or "").strip(" .")
        return {"action": "minimize", "query": query}
    match = re.search(
        r"\b(open|show|maximize|maximise|expand)\b.+\b(drawing|chat|window|conversation|thread)\b"
        r"|\b(open|show|maximize|maximise|expand)\b(?:\s+the)?\s+(.+?)\s+(chat|window|conversation)\b",
        low,
    )
    if match:
        query = (match.group(4) or match.group(2) or "").strip(" .")
        return {"action": "expand", "query": query}
    return None


def match_query(query: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = (query or "").lower().strip()
    if not needle:
        return rows[0] if rows else None
    for row in rows:
        title = str(row.get("title") or "").lower()
        category = str(row.get("category") or "").lower()
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        name = str(focus.get("filename") or focus.get("local_name") or "").lower()
        blob = f"{title} {category} {name}"
        if needle in blob or category in needle or title in needle:
            return row
    return None
