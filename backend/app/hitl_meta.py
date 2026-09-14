"""Blast-radius metadata for HITL pending actions (foundation v0)."""

from __future__ import annotations

from typing import Any

# kind → (irreversibility 1–5, short consequence)
_KIND_DEFAULTS: dict[str, tuple[int, str]] = {
    "email_send": (5, "Sends email via your Gmail account (public broadcast)."),
    "email_compose": (2, "Opens a draft for review; nothing is sent until Authorize."),
    "calendar_create": (3, "Creates a calendar event on your connected calendar."),
    "sheets_write": (4, "Overwrites cells in a bound Google Sheet (autosaved)."),
    "cnc_promote": (5, "Promotes NC to machine-ready; not undoable from Jarvis."),
    "drive_upload": (3, "Uploads a file to Google Drive."),
    "memory_wipe": (4, "Deletes local memory namespace data."),
    "quote_send": (5, "Sends quote PDF email via Gmail."),
    "browser_action": (4, "Performs a consequential browser/web action."),
}


def blast_radius_for(kind: str, payload: dict[str, Any] | None = None) -> tuple[int, str]:
    """Return (irreversibility 1–5, one-line consequence)."""
    payload = payload or {}
    jarvis = payload.get("_jarvis") if isinstance(payload.get("_jarvis"), dict) else {}
    if isinstance(jarvis.get("irreversibility"), int) and jarvis.get("consequence"):
        return int(jarvis["irreversibility"]), str(jarvis["consequence"])
    if isinstance(payload.get("irreversibility"), int) and payload.get("consequence"):
        return int(payload["irreversibility"]), str(payload["consequence"])

    key = (kind or "").strip().lower()
    if key in _KIND_DEFAULTS:
        return _KIND_DEFAULTS[key]
    if "email" in key or "mail" in key or "send" in key:
        return 5, "External send or mail write — authorize carefully."
    if "sheet" in key or "write" in key:
        return 4, "Writes external data that may be hard to undo."
    if "calendar" in key or "event" in key:
        return 3, "Creates or changes a calendar event."
    return 2, "Queued action — review before authorizing."


def enrich_payload(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach blast-radius fields under payload['_jarvis']."""
    enriched = dict(payload or {})
    score, consequence = blast_radius_for(kind, enriched)
    meta = enriched.get("_jarvis") if isinstance(enriched.get("_jarvis"), dict) else {}
    meta = dict(meta)
    meta["irreversibility"] = score
    meta["consequence"] = consequence
    enriched["_jarvis"] = meta
    return enriched
