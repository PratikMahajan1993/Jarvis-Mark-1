from __future__ import annotations

import threading
import time
from typing import Any

from . import db
from .connectors import gmail as gmail_conn
from .familiarity import facts_from_body, first_name, join_facts, remember_person

_lock = threading.Lock()
_running = False


def start_gemini_watch(session_id: str, thread_id: str, after_id: str = "") -> None:
    if not thread_id:
        db.set_watch(session_id, "gemini", "", "", "error", {"error": "No thread to watch."})
        return
    db.set_watch(session_id, "gemini", thread_id, after_id, "waiting", {})
    _ensure_loop()


def _ensure_loop() -> None:
    global _running
    with _lock:
        if _running:
            return
        _running = True
        thread = threading.Thread(target=_loop, name="jarvis-watch", daemon=True)
        thread.start()


def _loop() -> None:
    global _running
    deadline_by_session: dict[str, float] = {}
    try:
        while True:
            waiting = db.list_waiting_watches()
            if not waiting:
                break
            now = time.time()
            for item in waiting:
                session_id = item["session_id"]
                deadline_by_session.setdefault(session_id, now + 180)
                if now > deadline_by_session[session_id]:
                    db.set_watch(session_id, item["kind"], item["thread_id"], item.get("after_id") or "", "timeout", {})
                    continue
                if not gmail_conn.live():
                    db.set_watch(
                        session_id,
                        item["kind"],
                        item["thread_id"],
                        item.get("after_id") or "",
                        "error",
                        {"error": "Gmail is not connected."},
                    )
                    continue
                try:
                    reply = gmail_conn.newer_in_thread(item["thread_id"], item.get("after_id") or "")
                except Exception as exc:
                    db.set_watch(session_id, item["kind"], item["thread_id"], item.get("after_id") or "", "error", {"error": str(exc)})
                    continue
                if not reply:
                    continue
                db.upsert_email(reply)
                remember_person(session_id, reply.get("sender") or "", reply.get("id"), reply.get("subject"))
                facts = facts_from_body(reply.get("body") or "")
                name = first_name(reply.get("sender") or "") or "Gemini"
                speak = f"Here is what {name} replied: {join_facts(facts)}."
                db.set_watch(
                    session_id,
                    item["kind"],
                    item["thread_id"],
                    item.get("after_id") or "",
                    "ready",
                    {"mail": reply, "speak": speak},
                )
            time.sleep(20)
    finally:
        with _lock:
            _running = False


def watch_payload(session_id: str) -> dict[str, Any]:
    item = db.get_watch(session_id)
    if not item:
        return {"watching": False, "ready": False}
    status = item.get("status") or ""
    payload = item.get("payload") or {}
    mail = payload.get("mail") if isinstance(payload.get("mail"), dict) else {}
    if status == "waiting":
        return {"watching": True, "ready": False, "status": "waiting"}
    if status == "ready":
        speak = payload.get("speak") or "Gemini replied. The note is on the board."
        scene = {
            "title": first_name(mail.get("sender") or "") or "Gemini",
            "subtitle": mail.get("subject") or "Task for Gemini",
            "widgets": [
                {"type": "kpi", "label": "From", "value": first_name(mail.get("sender") or "") or "Gemini"},
                {"type": "markdown", "title": mail.get("subject") or "Reply", "text": mail.get("body") or ""},
            ],
        }
        return {"watching": False, "ready": True, "status": "ready", "speak": speak, "scene": scene}
    if status == "timeout":
        return {
            "watching": False,
            "ready": True,
            "status": "timeout",
            "speak": "Gemini has not replied yet. I stopped watching.",
            "scene": {
                "title": "Still waiting",
                "widgets": [{"type": "quote", "text": "Gemini has not replied yet.", "cite": "Jarvis"}],
            },
        }
    return {
        "watching": False,
        "ready": True,
        "status": status,
        "speak": payload.get("error") or "Gmail did not take it.",
        "scene": {
            "title": "Watch failed",
            "widgets": [{"type": "quote", "text": payload.get("error") or "Gmail did not take it.", "cite": "Jarvis"}],
        },
    }
