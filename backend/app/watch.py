from __future__ import annotations

import threading
import time
from typing import Any

from . import db
from .connectors import gmail as gmail_conn
from .familiarity import facts_from_body, first_name, join_facts, remember_person

WATCH_SECONDS = 20 * 60
POLL_GAP = 12

_lock = threading.Lock()
_running = False
_last_poll: dict[str, float] = {}
_backoff_until = 0.0


def start_gemini_watch(session_id: str, thread_id: str, after_id: str = "") -> None:
    if not thread_id:
        db.set_watch(session_id, "gemini", "", "", "error", {"error": "No thread to watch."})
        return
    db.set_watch(session_id, "gemini", thread_id, after_id, "waiting", {})
    if session_id != "default":
        db.set_watch("default", "gemini", thread_id, after_id, "waiting", {})
    _ensure_loop()


def resume_watches() -> None:
    revived = False
    for item in db.list_watches():
        thread_id = item.get("thread_id") or ""
        if not thread_id or thread_id.startswith("sent-"):
            continue
        status = item.get("status") or ""
        if status == "waiting" or _retryable(item):
            if status != "waiting":
                db.set_watch(item["session_id"], item["kind"], thread_id, item.get("after_id") or "", "waiting", {})
            revived = True
    if revived:
        _ensure_loop()


def _ensure_loop() -> None:
    global _running
    with _lock:
        if _running:
            return
        _running = True
        thread = threading.Thread(target=_loop, name="jarvis-watch", daemon=True)
        thread.start()


def _retryable(item: dict[str, Any]) -> bool:
    payload = item.get("payload") or {}
    error = str(payload.get("error") or "").lower()
    return any(token in error for token in ("quota", "403", "429", "rate", "timeout", "unavailable", "internal"))


def _transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("quota", "403", "429", "rate", "timeout", "unavailable", "internal", "timed out"))


def _loop() -> None:
    global _running
    started: dict[str, float] = {}
    try:
        while True:
            waiting = db.list_waiting_watches()
            if not waiting:
                break
            now = time.time()
            seen_threads: set[str] = set()
            for item in waiting:
                session_id = item["session_id"]
                started.setdefault(session_id, now)
                if now - started[session_id] > WATCH_SECONDS:
                    db.set_watch(session_id, item["kind"], item["thread_id"], item.get("after_id") or "", "timeout", {})
                    continue
                thread_id = item.get("thread_id") or ""
                if thread_id in seen_threads:
                    continue
                seen_threads.add(thread_id)
                _poll_and_store(item)
            time.sleep(20)
    finally:
        with _lock:
            _running = False


def _poll_and_store(item: dict[str, Any]) -> dict[str, Any] | None:
    global _backoff_until
    now = time.time()
    thread_id = item.get("thread_id") or ""
    if now < _backoff_until:
        return None
    last = _last_poll.get(thread_id) or 0
    if now - last < POLL_GAP:
        return None
    _last_poll[thread_id] = now
    if not gmail_conn.live():
        return None
    try:
        reply = _find_reply(item)
    except Exception as exc:
        if _transient(exc):
            _backoff_until = time.time() + 45
            return None
        db.set_watch(item["session_id"], item["kind"], thread_id, item.get("after_id") or "", "error", {"error": str(exc)})
        return None
    if not reply:
        return None
    _mark_ready(item, reply)
    return reply


def _find_reply(item: dict[str, Any]) -> dict[str, Any] | None:
    thread_id = item.get("thread_id") or ""
    after_id = item.get("after_id") or ""
    if thread_id:
        reply = gmail_conn.newer_in_thread(thread_id, after_id)
        if reply and not _same_message(reply, after_id):
            return reply
    rows = gmail_conn.list_messages(query='subject:"Task for Gemini"', limit=6)
    for row in rows:
        subject = (row.get("subject") or "").lower()
        if not subject.startswith("re:"):
            continue
        if _same_message(row, after_id):
            continue
        return row
    return None


def _same_message(row: dict[str, Any], after_id: str) -> bool:
    if not after_id:
        return False
    return after_id in {row.get("gmail_id"), row.get("id"), str(row.get("id") or "").removeprefix("gmail-")}


def _mark_ready(item: dict[str, Any], reply: dict[str, Any]) -> None:
    db.upsert_email(reply)
    remember_person(item["session_id"], reply.get("sender") or "", reply.get("id"), reply.get("subject"))
    facts = facts_from_body(reply.get("body") or "")
    name = first_name(reply.get("sender") or "") or "Gemini"
    if name.lower() in {"pratik", "you", "me"}:
        name = "Gemini"
    speak = f"Here is what {name} replied: {join_facts(facts)}."
    payload = {"mail": reply, "speak": speak}
    db.set_watch(item["session_id"], item["kind"], item["thread_id"], item.get("after_id") or "", "ready", payload)
    if item["session_id"] != "default":
        db.set_watch("default", item["kind"], item["thread_id"], item.get("after_id") or "", "ready", payload)
    from .hud_state import remember_hud

    scene = {
        "title": name,
        "subtitle": reply.get("subject") or "Task for Gemini",
        "widgets": [{"type": "kpi", "label": "From", "value": name}, {"type": "markdown", "title": "Reply", "text": reply.get("body") or ""}],
    }
    remember_hud(
        item["session_id"],
        {"speak": speak, "reply": speak, "scene": scene, "watching": False, "artifacts": [], "pending": [], "more": 0},
    )
    if item["session_id"] != "default":
        remember_hud(
            "default",
            {"speak": speak, "reply": speak, "scene": scene, "watching": False, "artifacts": [], "pending": [], "more": 0},
        )


def _hud_item(session_id: str) -> dict[str, Any] | None:
    item = db.get_watch(session_id)
    if item and (item.get("thread_id") or "").startswith("sent-") is False:
        return item
    if session_id != "default":
        return item
    for other in db.list_watches():
        if other.get("kind") != "gemini":
            continue
        if (other.get("thread_id") or "").startswith("sent-"):
            continue
        if other.get("status") in {"waiting", "ready"} or _retryable(other):
            return other
    return item


def watch_payload(session_id: str) -> dict[str, Any]:
    item = _hud_item(session_id)
    if not item:
        return {"watching": False, "ready": False}
    status = item.get("status") or ""
    if status == "waiting" or _retryable(item):
        if status != "waiting":
            db.set_watch(item["session_id"], item["kind"], item["thread_id"], item.get("after_id") or "", "waiting", {})
            item = db.get_watch(item["session_id"]) or item
        _ensure_loop()
        _poll_and_store(item)
        item = db.get_watch(item["session_id"]) or item
        status = item.get("status") or ""
    payload = item.get("payload") or {}
    mail = payload.get("mail") if isinstance(payload.get("mail"), dict) else {}
    if status == "waiting":
        return {"watching": True, "ready": False, "status": "waiting"}
    if status == "seen":
        return {"watching": False, "ready": False, "status": "seen"}
    if status == "ready":
        who = first_name(mail.get("sender") or "") or "Gemini"
        if who.lower() in {"pratik", "you", "me"}:
            who = "Gemini"
        from .tables import widgets_from_body

        body = mail.get("body") or ""
        gmail_id = mail.get("gmail_id") or ""
        if gmail_id and gmail_conn.live() and "|" not in body and "<table" not in body.lower():
            try:
                fresh = gmail_conn.get_message(gmail_id)
                if fresh and fresh.get("body"):
                    body = fresh["body"]
                    mail = {**mail, "body": body}
            except Exception:
                pass
        facts = facts_from_body(body)
        speak = f"Here is what {who} replied: {join_facts(facts)}."
        scene = {
            "title": who,
            "subtitle": mail.get("subject") or "Task for Gemini",
            "widgets": [
                {"type": "kpi", "label": "From", "value": who},
                *widgets_from_body(body, mail.get("subject") or "Reply"),
            ],
        }
        if not payload.get("hud"):
            from .hud_state import remember_hud

            remember_hud(
                item["session_id"],
                {"speak": speak, "reply": speak, "scene": scene, "watching": False, "artifacts": [], "pending": [], "more": 0},
            )
            if item["session_id"] != "default":
                remember_hud(
                    "default",
                    {"speak": speak, "reply": speak, "scene": scene, "watching": False, "artifacts": [], "pending": [], "more": 0},
                )
            payload = {**payload, "mail": mail, "speak": speak, "hud": True}
            db.set_watch(item["session_id"], item["kind"], item["thread_id"], item.get("after_id") or "", "ready", payload)
        return {
            "watching": False,
            "ready": True,
            "status": "ready",
            "key": f"gemini:ready:{mail.get('gmail_id') or mail.get('id') or speak}",
            "speak": speak,
            "scene": scene,
        }
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


def ack_watch(session_id: str = "default") -> dict[str, Any]:
    targets: list[str] = [session_id]
    if session_id != "default":
        targets.append("default")
    item = _hud_item(session_id)
    if item and item.get("session_id") not in targets:
        targets.append(item["session_id"])
    acked = False
    for sid in targets:
        row = db.get_watch(sid)
        if not row:
            continue
        status = row.get("status") or ""
        if status not in {"ready", "timeout", "error"}:
            continue
        payload = dict(row.get("payload") or {})
        payload["acked"] = True
        db.set_watch(sid, row["kind"], row.get("thread_id") or "", row.get("after_id") or "", "seen", payload)
        acked = True
    return {"ok": True, "acked": acked}
