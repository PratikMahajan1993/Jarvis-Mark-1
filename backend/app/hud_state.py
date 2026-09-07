from __future__ import annotations

from typing import Any

from . import db

_SKIP = {"", "…", "...", "listening…", "listening..."}


def remember_hud(session_id: str, payload: dict[str, Any]) -> None:
    speak = str(payload.get("speak") or payload.get("reply") or "").strip()
    if speak.lower() in _SKIP or speak.lower().startswith("chrome needs"):
        return
    scene = payload.get("scene") or {}
    if not scene.get("title") and not scene.get("widgets") and not speak:
        return
    db.save_hud_state(
        session_id,
        {
            "speak": speak,
            "reply": payload.get("reply") or speak,
            "scene": scene,
            "watching": bool(payload.get("watching")),
            "artifacts": payload.get("artifacts") or [],
            "pending": payload.get("pending") or [],
            "more": payload.get("more") or 0,
            "offline": bool(payload.get("offline")),
        },
    )


def load_hud(session_id: str) -> dict[str, Any]:
    return db.get_hud_state(session_id)
