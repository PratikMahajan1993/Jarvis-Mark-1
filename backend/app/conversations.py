from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import db
from .agents import agent_status_payload
from .config import settings
from .hud_state import load_hud, remember_hud
from .ollama_client import OllamaError
from .schemas import AgentStatus, ChatResponse, DrawingChatView, Scene

COMMAND_SESSION = "default"
AMBIENT_SESSION = "default"

# Desk model categories (human: everyday desk / named talks / jobs)
KIND_DISCUSSION = "discussion"
KIND_WORKFLOW = "workflow"
KIND_DRAWING = "drawing"  # engineering drawing job (existing)
DESK_KINDS = frozenset({KIND_DISCUSSION, KIND_WORKFLOW, KIND_DRAWING})


def ambient_session() -> str:
    return AMBIENT_SESSION


def is_desk_kind(category: str) -> bool:
    return (category or "").strip().lower() in DESK_KINDS


def kind_label(category: str) -> str:
    cat = (category or "").strip().lower()
    if cat == KIND_WORKFLOW:
        return "Job"
    if cat == KIND_DRAWING:
        return "Drawing"
    if cat == KIND_DISCUSSION:
        return "Discussion"
    return "Note"


_BRAIN_SEMAPHORE = threading.Semaphore(3)
_SESSION_LOCKS_GUARD = threading.Lock()
_SESSION_LOCKS: dict[str, threading.Lock] = {}
_DEFAULT_BRAIN_SESSION = COMMAND_SESSION


def _session_brain_lock(session_id: str) -> threading.Lock:
    with _SESSION_LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _SESSION_LOCKS[session_id] = lock
        return lock


@contextmanager
def brain_lock(session_id: str | None = None) -> Iterator[None]:
    """One brain turn per session; at most 3 brain turns process-wide."""
    sid = (session_id or _DEFAULT_BRAIN_SESSION).strip() or _DEFAULT_BRAIN_SESSION
    session_lock = _session_brain_lock(sid)
    session_lock.acquire()
    try:
        _BRAIN_SEMAPHORE.acquire()
        try:
            yield
        finally:
            _BRAIN_SEMAPHORE.release()
    finally:
        session_lock.release()


_DRAWING_SYSTEM = (
    "You are Jarvis, Tony's aide. This conversation is about one engineering drawing. "
    "The file is attached. Describe only what you can actually see. "
    "Do not invent dimensions, tolerances, or notes. If a number is unreadable, say so. "
    "Answer in one or two spoken sentences unless they ask for more. "
    "Do not mention tools, JSON, or that you are a model."
)


_CLOSE_DRAWING_RE = re.compile(
    r"\b(?:close|hide|dismiss)\b(?:\s+\w+){0,4}\s+\b(?:drawing|window|viewer|sheet)\b"
    r"|\bclose (?:it|this)\b",
    re.I,
)
_OPEN_DRAWING_RE = re.compile(
    r"\b(?:open|show|view|look at|pull up|review|zoom)\b.{0,48}\b(?:drawing|drawings|sheet|blueprint|pdf)\b",
    re.I,
)
_SHOP_LEAVE_RE = re.compile(
    r"\b(?:quote|rfq|send|draft|mail|e-mail|email|calendar|invoice)\b",
    re.I,
)


def asks_to_close_drawing(message: str) -> bool:
    return bool(_CLOSE_DRAWING_RE.search(message or ""))


def wants_drawing_window(message: str) -> bool:
    text = message or ""
    if _SHOP_LEAVE_RE.search(text):
        return False
    return bool(_OPEN_DRAWING_RE.search(text))


def leaves_drawing_for_shop(message: str) -> bool:
    return bool(_SHOP_LEAVE_RE.search(message or ""))


def is_drawing_session(session_id: str) -> bool:
    row = db.get_conversation_by_session(session_id)
    if not row or row.get("category") != "drawing" or row.get("status") == "archived":
        return False
    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    return focus.get("viewing") is not False


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    session_id = row.get("session_id") or ""
    hud = load_hud(session_id) if session_id else {}
    pending = db.list_focused_pending(session_id) if session_id else []
    turns = db.recent_messages(session_id, 12) if session_id else []
    scene = hud.get("scene") or {}
    category = row.get("category") or "files"
    return {
        "id": row.get("id"),
        "session_id": session_id,
        "category": category,
        "kind": category if is_desk_kind(str(category)) else "discussion",
        "kind_label": kind_label(str(category)),
        "title": row.get("title") or "Conversation",
        "focus": row.get("focus") or {},
        "minimized": bool(row.get("minimized")),
        "status": row.get("status") or "ready",
        "model": row.get("model") or "",
        "updated_at": row.get("updated_at") or "",
        "created_at": row.get("created_at") or "",
        "speak": hud.get("reply") or hud.get("speak") or "",
        "scene": scene if isinstance(scene, dict) else {},
        "pending": pending,
        "turns": turns,
        "waiting": bool(pending),
    }


def list_public() -> list[dict[str, Any]]:
    return [public_row(row) for row in db.list_conversations()]


def list_desk() -> list[dict[str, Any]]:
    """Open discussions + jobs for the desk tray (excludes archived)."""
    items: list[dict[str, Any]] = []
    for row in list_public():
        if row.get("status") == "archived":
            continue
        if is_desk_kind(str(row.get("category") or "")):
            items.append(row)
    return items


def start_discussion(title: str = "", focus: dict[str, Any] | None = None) -> dict[str, Any]:
    stamp = db.utc_now()[11:16]
    label = (title or "").strip() or f"Discussion {stamp}"
    created = create(KIND_DISCUSSION, label, focus or {}, status="ready")
    opening = "I'm with you on this discussion. Leave anytime — we can pick it up again from your open notes."
    db.add_message(created["session_id"], "assistant", opening)
    remember_hud(
        created["session_id"],
        {
            "speak": "Discussion started. What shall we dig into?",
            "reply": "Discussion started. What shall we dig into?",
            "scene": {"title": label, "widgets": []},
            "pending": [],
        },
    )
    return public_row(db.get_conversation(created["id"]) or created)


def start_or_resume_workflow(
    *,
    title: str,
    focus: dict[str, Any] | None = None,
    resume_key: str = "",
) -> dict[str, Any]:
    """Open a job conversation, or resume one that shares the same resume_key."""
    payload = dict(focus or {})
    key = (resume_key or str(payload.get("resume_key") or "")).strip()
    if key:
        payload["resume_key"] = key
        for row in db.list_conversations():
            if row.get("status") == "archived":
                continue
            if row.get("category") not in {KIND_WORKFLOW, KIND_DRAWING}:
                continue
            focus_row = row.get("focus") if isinstance(row.get("focus"), dict) else {}
            if str(focus_row.get("resume_key") or "") == key:
                merged = {**focus_row, **payload}
                db.update_conversation(row["id"], minimized=False, status="ready", focus=merged)
                db.touch_conversation(row["id"])
                return public_row(db.get_conversation(row["id"]) or row)

    label = (title or "Job").strip()[:80] or "Job"
    created = create(KIND_WORKFLOW, label, payload, status="ready")
    opening = (
        f"Job open: {label}. We'll keep drawings, quotes, and decisions here so you can leave and come back."
    )
    db.add_message(created["session_id"], "assistant", opening)
    remember_hud(
        created["session_id"],
        {
            "speak": opening,
            "reply": opening,
            "scene": {"title": label, "widgets": []},
            "pending": [],
        },
    )
    return public_row(db.get_conversation(created["id"]) or created)


def latest_drawing() -> dict[str, Any] | None:
    for row in db.list_conversations():
        if row.get("category") == "drawing" and row.get("status") != "archived":
            return public_row(row)
    return None


def create(
    category: str,
    title: str,
    focus: dict[str, Any] | None = None,
    status: str = "warming",
) -> dict[str, Any]:
    conversation_id = uuid.uuid4().hex[:12]
    session_id = f"conv-{conversation_id}"
    label = (title or "Conversation").strip()[:80] or "Conversation"
    kind = (category or "files").strip().lower() or "files"
    payload = focus or {}
    if (
        kind == "drawing"
        and status == "warming"
        and str(payload.get("grounding") or "").strip()
        and payload.get("saw_drawing")
    ):
        status = "ready"
    row = db.create_conversation(conversation_id, session_id, kind, label, payload, status)
    db.add_audit(session_id, "conversation", f"Opened {label}", "ok")
    return public_row(row)


def patch(conversation_id: str, **fields: Any) -> dict[str, Any] | None:
    row = db.update_conversation(conversation_id, **fields)
    return public_row(row) if row else None


def expand(conversation_id: str) -> dict[str, Any] | None:
    return patch(conversation_id, minimized=False)


def minimize(conversation_id: str) -> dict[str, Any] | None:
    return patch(conversation_id, minimized=True)


def match_named(text: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    low = (text or "").lower()
    items = rows or list_public()
    for row in items:
        title = str(row.get("title") or "").lower()
        category = str(row.get("category") or "").lower()
        if title and title in low:
            return row
        if category and re.search(rf"\b{re.escape(category)}\b", low):
            return row
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        name = str(focus.get("filename") or focus.get("local_name") or "").lower()
        stem = Path(name).stem.lower() if name else ""
        if stem and len(stem) >= 4 and stem in low:
            return row
    return None


def spawn_drawing(focus: dict[str, Any]) -> dict[str, Any]:
    filename = str(focus.get("filename") or focus.get("local_name") or "drawing")
    title = Path(filename).stem or "Drawing"
    existing = None
    for row in db.list_conversations():
        other = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        if row.get("category") == "drawing" and (
            other.get("local_name") == focus.get("local_name")
            or other.get("filename") == focus.get("filename")
        ):
            existing = row
            break
    if existing:
        merged = {**(existing.get("focus") or {}), **focus}
        db.update_conversation(existing["id"], minimized=False, status="warming", focus=merged)
        return prime_drawing(existing["id"])
    created = create("drawing", title, focus, status="warming")
    return prime_drawing(str(created["id"]))


def prime_drawing(conversation_id: str) -> dict[str, Any]:
    row = db.get_conversation(conversation_id)
    if not row:
        raise ValueError("Conversation not found")
    db.update_conversation(conversation_id, status="warming", minimized=False)
    _seed_working_set(row)
    row = db.get_conversation(conversation_id) or row
    with brain_lock(row["session_id"]):
        speak, grounding, model, saw = _see_drawing(row, owner_spend=False)
    row = db.get_conversation(conversation_id) or row
    focus = dict(row.get("focus") or {})
    focus["grounding"] = grounding
    focus["saw_drawing"] = saw
    updated = db.update_conversation(
        conversation_id,
        status="ready",
        model=model,
        focus=focus,
        minimized=False,
    )
    session_id = row["session_id"]
    db.add_message(session_id, "assistant", speak)
    remember_hud(
        session_id,
        {
            "speak": speak,
            "reply": speak,
            "scene": {
                "title": updated.get("title") if updated else row.get("title"),
                "subtitle": "Drawing in focus",
                "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}],
            },
            "pending": [],
        },
    )
    db.touch_conversation(conversation_id)
    return public_row(updated or row)


def _drawing_chat_view(row: dict[str, Any] | None, notes: str, *, open: bool) -> DrawingChatView:
    focus = row.get("focus") if row and isinstance(row.get("focus"), dict) else {}
    filename = str(focus.get("filename") or focus.get("local_name") or "")
    return DrawingChatView(
        open=open,
        notes=notes,
        filename=filename,
        local_name=str(focus.get("local_name") or filename),
        local_path=str(focus.get("local_path") or ""),
        mime=str(focus.get("mime") or ""),
        conversation_id=str(row.get("id") or "") if row else "",
        session_id=str(row.get("session_id") or "") if row else "",
    )


def _vision_block_reason(row: dict[str, Any]) -> str | None:
    """Cloud vision stays deny-by-default. A dropped file is a temporary owner hand-off."""
    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    if focus.get("impromptu_vision"):
        return None
    customer_id = str(focus.get("customer_id") or "").strip()
    if not settings.masterdata_enabled or not customer_id:
        return (
            "I will not send this sheet to the cloud. "
            "There is no attested vision consent for this customer, so I will not invent sizes."
        )
    from .vision.gate import _customer_vision_consent_error

    err = _customer_vision_consent_error(customer_id)
    if err:
        return f"{err} I will not invent sizes."
    return None


def _drawing_row_by_id(conversation_id: str) -> dict[str, Any] | None:
    return db.get_conversation(conversation_id)


def resolve_drawing_for_chat(message: str, session_id: str) -> dict[str, Any] | None:
    """Pick the sheet for a chat window. Named match wins, otherwise the newest drawing."""
    current = db.get_conversation_by_session(session_id)
    if current and current.get("category") == "drawing" and current.get("status") != "archived":
        return current
    named = match_named(message or "")
    if named and named.get("category") == "drawing" and named.get("id"):
        row = _drawing_row_by_id(str(named["id"]))
        if row:
            return row
    low = (message or "").lower()
    for row in db.list_conversations():
        if row.get("category") != "drawing" or row.get("status") == "archived":
            continue
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        name = str(focus.get("filename") or focus.get("local_name") or row.get("title") or "").lower()
        stem = Path(name).stem.lower()
        if stem and len(stem) >= 4 and stem in low:
            return row
    for row in db.list_conversations():
        if row.get("category") == "drawing" and row.get("status") != "archived":
            return row
    return None


def begin_drawing_chat(message: str, desk_session: str) -> ChatResponse:
    """Open the drawing window from whatever note the desk is on. The lens stays put."""
    target = resolve_drawing_for_chat(message, desk_session)
    if not target:
        speak = "Which drawing should I open? I will not guess a sheet."
        scene = {"title": "Drawing", "widgets": []}
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene.model_validate(scene),
            pending=[],
            agents=[AgentStatus(**item) for item in agent_status_payload({})],
            drawing_chat=DrawingChatView(open=False, notes=speak),
        )
    focus = dict(target.get("focus") or {})
    focus["viewing"] = True
    db.update_conversation(target["id"], focus=focus, minimized=False, status="ready")
    result = chat_drawing(str(target["session_id"]), message)
    result.ui_action = {"action": "focus_drawing", "conversation_id": target["id"]}
    return result


_DRAWING_DROPS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def _drawing_by_sha(digest: str) -> dict[str, Any] | None:
    for row in db.list_conversations():
        if row.get("category") != "drawing" or row.get("status") == "archived":
            continue
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        if str(focus.get("file_sha256") or "") == digest:
            return row
    return None


def ingest_dropped_drawing(filename: str, data: bytes) -> ChatResponse:
    """Save a dropped sheet once, or reopen the same bytes. The drop is a test look."""
    name = Path(filename or "drawing").name
    suffix = Path(name).suffix.lower()
    if suffix not in _DRAWING_DROPS or not data:
        speak = "Drop a PDF or an image of the drawing."
        scene = {"title": "Drawing", "widgets": []}
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene.model_validate(scene),
            pending=[],
            agents=[AgentStatus(**item) for item in agent_status_payload({})],
            drawing_chat=DrawingChatView(open=False, notes=speak),
        )
    digest = hashlib.sha256(data).hexdigest()
    mime = "application/pdf" if suffix == ".pdf" else "image/png"
    existing = _drawing_by_sha(digest)
    if existing:
        focus = dict(existing.get("focus") or {})
        path = Path(str(focus.get("local_path") or ""))
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        focus["viewing"] = True
        focus["impromptu_vision"] = True
        focus["file_sha256"] = digest
        db.update_conversation(existing["id"], focus=focus, minimized=False, status="ready")
        target = db.get_conversation(existing["id"]) or existing
        stored_name = path.name
    else:
        folder = settings.exports_dir / "drawings"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest}{suffix}"
        if not path.is_file():
            path.write_bytes(data)
        stored_name = path.name
        focus = {
            "filename": name,
            "local_name": stored_name,
            "local_path": str(path),
            "mime": mime,
            "file_sha256": digest,
            "viewing": True,
            "impromptu_vision": True,
        }
        created = create("drawing", Path(name).stem or "Drawing", focus, status="ready")
        db.add_artifact(str(created["id"]), "drawing", name, str(path))
        target = db.get_conversation(str(created["id"])) or created
    db.remember_dropped_drawing(
        sha256=digest,
        filename=name,
        stored_name=stored_name,
        path=str(path),
        mime=mime,
        byte_size=len(data),
    )
    result = chat_drawing(
        str(target["session_id"]),
        "Look at this drawing. Say only what you can actually see.",
    )
    result.ui_action = {"action": "focus_drawing", "conversation_id": str(target["id"])}
    return result


def close_drawing_view(session_id: str) -> ChatResponse:
    row = db.get_conversation_by_session(session_id)
    speak = "Drawing closed."
    if row:
        focus = dict(row.get("focus") or {})
        focus["viewing"] = False
        db.update_conversation(row["id"], focus=focus)
        db.add_message(session_id, "assistant", speak)
        db.touch_conversation(row["id"])
    scene = {"title": "", "widgets": []}
    remember_hud(session_id, {"speak": speak, "reply": speak, "scene": scene, "pending": []})
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=Scene.model_validate(scene),
        pending=[],
        agents=[AgentStatus(**item) for item in agent_status_payload({})],
        drawing_chat=_drawing_chat_view(row, "", open=False),
    )


def chat_drawing(session_id: str, message: str) -> ChatResponse:
    row = db.get_conversation_by_session(session_id)
    if not row:
        speak = "That conversation is gone."
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene(title="", widgets=[]),
            agents=[AgentStatus(**item) for item in agent_status_payload({})],
        )
    history = [item for item in db.recent_messages(session_id, 12) if item.get("content") != message][-8:]
    system = _DRAWING_SYSTEM
    grounding = str((row.get("focus") or {}).get("grounding") or "").strip()
    if grounding:
        system += f"\nWhat you already saw:\n{grounding}"
    used = (row.get("model") or settings.gemini_model).strip()
    blocked = _vision_block_reason(row)
    if blocked:
        speak = blocked
    else:
        try:
            response = _chat_drawing_media(row, history, message, system, used, owner_spend=True)
            speak = (response.get("content") or "").strip()
            speak = re.sub(r"<think>.*?</think>", "", speak, flags=re.S).strip()
            speak = speak[:600] or "I have the drawing. What do you need?"
        except OllamaError as exc:
            speak = "I could not read the drawing just then."
            db.add_audit(session_id, "conversation", str(exc)[:400], "error")
    db.add_message(session_id, "assistant", speak)
    notes = speak
    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    if focus.get("impromptu_vision") and not blocked:
        notes = "Unattested test look. You handed Jarvis this file.\n\n" + speak
    scene = {
        "title": "",
        "widgets": [],
    }
    remember_hud(session_id, {"speak": speak, "reply": notes, "scene": scene, "pending": []})
    db.touch_conversation(row["id"])
    return ChatResponse(
        speak=speak,
        reply=notes,
        scene=Scene.model_validate(scene),
        pending=[],
        agents=[AgentStatus(**item) for item in agent_status_payload({})],
        drawing_chat=_drawing_chat_view(row, notes, open=True),
    )


def _see_drawing(row: dict[str, Any], *, owner_spend: bool = False) -> tuple[str, str, str, bool]:
    if not owner_spend:
        caption = _pdf_caption(row)
        speak = (
            "The drawing is on the bench locally. Cloud vision waits until you explicitly spend a unit."
        )
        if caption:
            speak = "The drawing is in focus from local text. Cloud vision waits for your explicit request."
        return speak[:240], (caption or "")[:1200], "local", bool(caption)
    prompt = (
        "Look at this engineering drawing. "
        "Reply JSON only: "
        '{"speak":"one spoken sentence that the drawing is in focus",'
        '"grounding":"title block, views, and readable notes only",'
        '"saw_drawing":true}'
    )
    system = (
        "You look at engineering drawings. Do not invent dimensions. "
        "If you only received text and cannot see the sheet, set saw_drawing false."
    )
    models = [settings.gemini_model]
    drawing_model = (settings.gemini_drawing_model or "").strip()
    if drawing_model and drawing_model not in models:
        models.append(drawing_model)
    last_error = ""
    for media, kind in _media_variants(row):
        for model in models:
            try:
                from . import gemini_client

                message = gemini_client.generate_parts(
                    [*media, {"text": prompt}],
                    system=system,
                    format_json=True,
                    timeout=120,
                    options={"temperature": 0.2, "num_predict": 400},
                    model=model,
                )
                parsed = _parse_json(message.get("content") or "")
                grounding = str(parsed.get("grounding") or "").strip()
                speak = str(parsed.get("speak") or "").strip() or "The drawing is in focus."
                saw = parsed.get("saw_drawing")
                if saw is None:
                    saw = _looks_visual(grounding)
                text_only = _looks_text_extract(grounding) and kind != "image/png"
                if (saw is False or not grounding or text_only) and model == settings.gemini_model and drawing_model:
                    continue
                if kind == "image/png":
                    _mark_raster(row)
                return speak[:240], grounding[:1200], model, bool(saw) and not text_only
            except OllamaError as exc:
                last_error = str(exc)
                continue
    caption = _pdf_caption(row)
    speak = "The drawing is in the conversation, but I could not see the sheet clearly."
    if last_error:
        db.add_audit(row.get("session_id") or "default", "conversation", last_error[:400], "error")
    return speak, caption, settings.gemini_model, False


def _chat_drawing_media(
    row: dict[str, Any],
    history: list[dict[str, str]],
    message: str,
    system: str,
    preferred: str,
    *,
    owner_spend: bool = False,
) -> dict[str, Any]:
    last: OllamaError | None = None
    for media, kind in _media_variants(row):
        try:
            response = _chat_with_fallback(
                history, message, media, system, preferred, owner_spend=owner_spend
            )
            if kind == "image/png":
                _mark_raster(row)
            return response
        except OllamaError as exc:
            last = exc
            if _is_media_reject(exc):
                continue
            raise
    if last:
        raise last
    raise OllamaError("Gemini did not answer.")


def _media_has_drawing_bytes(media: list[dict[str, Any]]) -> bool:
    for part in media:
        if part.get("inline_data") or part.get("file_data"):
            return True
    return False


def _chat_with_fallback(
    history: list[dict[str, str]],
    message: str,
    media: list[dict[str, Any]],
    system: str,
    preferred: str,
    *,
    owner_spend: bool = False,
) -> dict[str, Any]:
    from . import gemini_client

    effective_media = media
    if _media_has_drawing_bytes(media) and not owner_spend:
        effective_media = [
            {
                "text": (
                    "(Drawing bytes withheld — cloud vision requires an explicit owner spend. "
                    "Answer from local context and conversation only.)"
                )
            }
        ]
        system = system + "\nYou do not have the drawing image; do not invent dimensions."

    models = [preferred or settings.gemini_model]
    drawing_model = (settings.gemini_drawing_model or "").strip()
    if drawing_model and drawing_model not in models and owner_spend:
        models.append(drawing_model)
    last: OllamaError | None = None
    for model in models:
        try:
            return gemini_client.chat_multimodal(
                history,
                message,
                effective_media,
                system=system,
                model=model,
                timeout=180,
                options={"temperature": 0.3, "num_predict": 400},
            )
        except OllamaError as exc:
            last = exc
            continue
    if last:
        raise last
    raise OllamaError("Gemini did not answer.")


def _media_for(row: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    uri = str(focus.get("file_uri") or "")
    mime = str(focus.get("mime") or _guess_mime(str(focus.get("filename") or focus.get("local_name") or "")))
    path = _local_path(focus)
    if uri and not focus.get("prefer_raster"):
        return ([{"file_data": {"mime_type": mime, "file_uri": uri}}], mime)
    if path and path.is_file() and not focus.get("prefer_raster"):
        uploaded = _try_upload(path, mime)
        if uploaded:
            focus["file_uri"] = uploaded
            db.update_conversation(row["id"], focus=focus)
            return ([{"file_data": {"mime_type": mime, "file_uri": uploaded}}], mime)
        raw = path.read_bytes()
        if len(raw) <= 12 * 1024 * 1024:
            b64 = base64.b64encode(raw).decode("ascii")
            return ([{"inline_data": {"mime_type": mime, "data": b64}}], mime)
    return ([{"text": f"(No file bytes. Filename: {focus.get('filename') or 'drawing'}.)"}], mime)


def _media_variants(row: dict[str, Any]) -> list[tuple[list[dict[str, Any]], str]]:
    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    variants: list[tuple[list[dict[str, Any]], str]] = []
    rasters = _raster_parts(row)
    if focus.get("prefer_raster") and rasters:
        variants.append((rasters, "image/png"))
        return variants
    native, mime = _media_for(row)
    variants.append((native, mime))
    if rasters and mime == "application/pdf":
        variants.append((rasters, "image/png"))
    return variants


def _raster_parts(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = _local_path(row.get("focus") if isinstance(row.get("focus"), dict) else {})
    if not path or path.suffix.lower() != ".pdf":
        return []
    parts: list[dict[str, Any]] = []
    for raw in _render_pdf_pages(path, 3):
        if not raw or len(raw) > 8 * 1024 * 1024:
            continue
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(raw).decode("ascii")}})
    return parts


def _render_pdf_pages(path: Path, max_pages: int = 3) -> list[bytes]:
    try:
        import pymupdf

        doc = pymupdf.open(str(path))
        pages: list[bytes] = []
        for index in range(min(len(doc), max_pages)):
            pix = doc[index].get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            pages.append(pix.tobytes("png"))
        return pages
    except Exception:
        pass
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        pages = []
        for index in range(min(len(pdf), max_pages)):
            bitmap = pdf[index].render(scale=1.6)
            pil = bitmap.to_pil()
            from io import BytesIO

            buf = BytesIO()
            pil.save(buf, format="PNG")
            pages.append(buf.getvalue())
        return pages
    except Exception:
        return []


def _mark_raster(row: dict[str, Any]) -> None:
    focus = dict(row.get("focus") or {})
    if focus.get("prefer_raster"):
        return
    focus["prefer_raster"] = True
    db.update_conversation(row["id"], focus=focus)
    row["focus"] = focus


def _is_media_reject(exc: Exception) -> bool:
    low = str(exc or "").lower()
    hints = (
        "invalid argument",
        "unsupported",
        "unable to process",
        "cannot process",
        "failed to parse",
        "inline_data",
        "inline data",
        "file_data",
        "mime type",
        "mimetype",
        "request payload",
        "payload size",
        "too large",
        "no pages",
    )
    return any(token in low for token in hints)


def _looks_text_extract(grounding: str) -> bool:
    low = (grounding or "").lower()
    if not low:
        return False
    if _looks_visual(low):
        return False
    hints = ("extracted text", "no image", "cannot see", "text only", "ocr", "no visual")
    return any(token in low for token in hints)


def _seed_working_set(row: dict[str, Any]) -> None:
    from .familiarity import remember_artifact, remember_drive

    session_id = str(row.get("session_id") or "")
    if not session_id:
        return
    focus = dict(row.get("focus") or {})
    path = _local_path(focus)
    if path and path.is_file():
        existing = db.get_artifact_by_name(path.name)
        if existing and Path(str(existing.get("path") or "")) == path:
            art = existing
        else:
            art = db.add_artifact(f"draw-{row['id']}", "drawing", path.name, str(path))
        remember_artifact(session_id, art, str(row.get("title") or path.stem))
        focus["artifact_id"] = art["id"]
    link = str(focus.get("drive_link") or "")
    if link:
        remember_drive(
            session_id,
            {
                "id": focus.get("drive_id") or row.get("id"),
                "name": focus.get("filename") or row.get("title"),
                "title": row.get("title") or focus.get("filename"),
                "link": link,
            },
        )
    db.update_conversation(str(row["id"]), focus=focus)


def _try_upload(path: Path, mime: str) -> str:
    try:
        from . import gemini_client

        uploaded = gemini_client.upload_file(str(path), mime=mime, display_name=path.name)
        return uploaded.get("uri") or ""
    except Exception:
        return ""


def _local_path(focus: dict[str, Any]) -> Path | None:
    raw = str(focus.get("local_path") or "")
    name = str(focus.get("local_name") or focus.get("filename") or "")
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw))
    if name:
        from .mail_attachments import safe_drawing_path

        try:
            candidates.append(safe_drawing_path(name))
        except ValueError:
            pass
        candidates.append(settings.exports_dir / name)
        candidates.append(settings.exports_dir / "drawings" / Path(name).name)
    for item in candidates:
        try:
            path = item.resolve()
        except OSError:
            continue
        if path.is_file():
            return path
    return None


def _guess_mime(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".png"}:
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix in {".webp"}:
        return "image/webp"
    return "application/octet-stream"


def _pdf_caption(row: dict[str, Any]) -> str:
    path = _local_path(row.get("focus") if isinstance(row.get("focus"), dict) else {})
    if not path or path.suffix.lower() != ".pdf":
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:2]:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)
        return " ".join(pages)[:800]
    except Exception:
        return ""


def _looks_visual(grounding: str) -> bool:
    low = (grounding or "").lower()
    if not low or len(low) < 20:
        return False
    hints = ("view", "section", "title block", "drawing", "dimension", "projection", "sheet", "scale")
    return any(word in low for word in hints)


def _parse_json(text: str) -> dict[str, Any]:
    blob = (text or "").strip()
    blob = re.sub(r"<think>.*?</think>", "", blob, flags=re.S).strip()
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", blob, re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
