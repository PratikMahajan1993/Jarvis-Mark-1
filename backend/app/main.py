from __future__ import annotations

import base64
import binascii
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from . import db
from .agent import next_thought, resolve_pending, run_agent, run_attachment_reply, run_attachment_save
from .briefing import build_briefing, build_glance
from .config import settings
from .connectors.calendar import live as calendar_live, seed_calendar
from .familiarity import ensure_demo_people
from .connectors.email import seed_mailbox
from .connectors.gmail import live as gmail_live
from .connectors import google_auth
from .brain import health
from .mail_attachments import safe_drawing_path, save_marked_drawing
from .schemas import (
    CANVAS_ITEM_BASE_FIELDS,
    CanvasBoardCreate,
    CanvasBoardUpdate,
    ComposeUpdateRequest,
    ConversationCreate,
    ConversationPatch,
    DrawingSpawn,
    MailAttachmentAction,
    MailReplyAttachmentAction,
    MarkedDrawingSave,
    ChatRequest,
    ConfirmRequest,
    Preferences,
    PreferencesUpdate,
)
from .tools.documents import read_export_text
from .hud_state import load_hud, remember_hud
from .snapshot import kick as kick_snapshot
from .watch import ack_watch, resume_watches, watch_payload

app = FastAPI(title="Jarvis Command Center", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list or ["http://localhost:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|(\d{1,3}\.){3}\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    if not gmail_live():
        seed_mailbox()
        ensure_demo_people()
    if not calendar_live():
        seed_calendar()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    resume_watches()
    kick_snapshot()
    if settings.hermes_enabled:
        try:
            from .hermes.bridge import ensure_jarvis_mcp_registered, hermes_available

            if hermes_available():
                ensure_jarvis_mcp_registered()
        except Exception:
            pass


@app.get("/api/agents")
def api_agents() -> dict:
    from .agents import agent_status_payload

    return {"items": agent_status_payload()}


@app.get("/api/health")
def api_health() -> dict:
    status = health()
    status["ok"] = True
    status["google"] = google_auth.status()
    try:
        from .hermes.bridge import hermes_available, hermes_cli_available, hermes_gateway_reachable

        gateway_up = hermes_gateway_reachable()
        status["hermes"] = {
            "enabled": bool(settings.hermes_enabled),
            "available": hermes_available(),
            "bin": settings.hermes_bin,
            "gateway_url": settings.hermes_gateway_url,
            "gateway": gateway_up,
            "cli": hermes_cli_available(),
            "prefer_gateway": bool(settings.hermes_prefer_gateway),
            "transport": "gateway" if (settings.hermes_prefer_gateway and gateway_up) else "cli",
        }
    except Exception:
        status["hermes"] = {"enabled": bool(settings.hermes_enabled), "available": False}
    return status


@app.get("/api/google/status")
def api_google_status() -> dict:
    return google_auth.status()


@app.get("/api/google/auth")
def api_google_auth():
    try:
        return RedirectResponse(google_auth.auth_url())
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/google/callback")
def api_google_callback(code: str = "", state: str = ""):
    try:
        google_auth.finish_auth(code, state)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(f"{settings.hud_url}/?gmail=1")


@app.get("/api/watch")
def api_watch(session_id: str = "default") -> dict:
    return watch_payload(session_id)


@app.post("/api/watch/ack")
def api_watch_ack(session_id: str = "default") -> dict:
    return ack_watch(session_id)


@app.get("/api/session")
def api_session(session_id: str = "default") -> dict:
    return load_hud(session_id)


@app.post("/api/mail/attachments/save")
def api_mail_attachments_save(payload: MailAttachmentAction) -> dict:
    result = run_attachment_save(payload.session_id, payload.email_id, payload.attachment_ids, payload.filenames)
    data = result.model_dump()
    remember_hud(payload.session_id, data)
    return data


@app.post("/api/mail/attachments/reply")
def api_mail_attachments_reply(payload: MailReplyAttachmentAction) -> dict:
    result = run_attachment_reply(payload.session_id, payload.email_id, payload.attachment_ids, payload.filenames)
    data = result.model_dump()
    remember_hud(payload.session_id, data)
    return data


@app.post("/api/chat")
def api_chat(payload: ChatRequest) -> dict:
    result = run_agent(payload.message.strip(), payload.session_id)
    data = result.model_dump()
    remember_hud(payload.session_id, data)
    return data


@app.post("/api/confirm")
def api_confirm(payload: ConfirmRequest) -> dict:
    result = resolve_pending(payload.action_id, payload.approved, payload.session_id)
    data = result.model_dump()
    remember_hud(payload.session_id, data)
    return data


@app.post("/api/pending/{action_id}/update")
def api_pending_update(action_id: str, payload: ComposeUpdateRequest) -> dict:
    from .mail_compose import update_compose_fields

    result = update_compose_fields(
        payload.session_id,
        action_id,
        to_addr=payload.to,
        subject=payload.subject,
        body=payload.body,
    )
    data = result.model_dump()
    remember_hud(payload.session_id, data)
    return data


@app.get("/api/briefing")
def api_briefing() -> dict:
    return build_briefing()


@app.get("/api/glance")
def api_glance() -> dict:
    from .rfq import glance_critical

    kick_snapshot()
    payload = build_glance()
    critical = glance_critical()
    if not critical:
        from .shop_log import glance_efficiency_critical

        critical = glance_efficiency_critical()
    if critical:
        payload["critical"] = critical
    return payload


@app.get("/api/snapshot")
def api_snapshot() -> dict:
    from .snapshot import status as snapshot_status

    kick_snapshot()
    return snapshot_status()


@app.get("/api/artifacts")
def api_artifacts() -> dict:
    return {"items": db.list_artifacts()}


@app.get("/api/artifacts/{artifact_id}")
def api_artifact_download(artifact_id: str):
    item = db.get_artifact(artifact_id)
    if not item:
        raise HTTPException(404, "Artifact not found")
    path = Path(item["path"]).resolve()
    if settings.exports_dir.resolve() not in path.parents and path.parent != settings.exports_dir.resolve():
        raise HTTPException(400, "Invalid artifact path")
    if not path.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=item["name"])


@app.get("/api/drawings/{filename}")
def api_drawing_download(filename: str):
    try:
        path = safe_drawing_path(filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.exists():
        raise HTTPException(404, "Drawing not found")
    suffix = path.suffix.lower()
    media = "application/pdf" if suffix == ".pdf" else None
    return FileResponse(path, media_type=media)


@app.post("/api/drawings/marked")
def api_drawing_marked(payload: MarkedDrawingSave) -> dict:
    raw = payload.image_base64.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    if not raw:
        raise HTTPException(400, "Missing image data")
    try:
        png_bytes = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "Invalid image data") from exc
    if not png_bytes:
        raise HTTPException(400, "Empty image")
    result = save_marked_drawing(payload.session_id, payload.source_name, png_bytes)
    return {
        "ok": True,
        "speak": result["speak"],
        "artifact": result["artifact"],
        "drive_link": result.get("drive_link"),
    }


@app.get("/api/audit")
def api_audit() -> dict:
    return {"items": db.list_audit()}


@app.get("/api/preferences", response_model=Preferences)
def api_preferences() -> dict:
    return db.get_preferences()


@app.patch("/api/preferences", response_model=Preferences)
def api_update_preferences(payload: PreferencesUpdate) -> dict:
    return db.update_preferences(payload.model_dump(exclude_none=True))


@app.get("/api/pending")
def api_pending(session_id: str = "default") -> dict:
    return {"items": db.list_focused_pending(session_id)}


class RfqIntake(BaseModel):
    mail_id: str = ""
    conversation_id: str = ""
    message: str = ""
    session_id: str = "default"


@app.get("/api/rfqs")
def api_rfqs() -> dict:
    from .rfq import list_public

    return {"items": list_public()}


@app.get("/api/rfqs/{rfq_id}")
def api_rfq(rfq_id: str) -> dict:
    from .rfq import get_public

    row = get_public(rfq_id)
    if not row:
        raise HTTPException(404, "RFQ not found")
    return row


@app.post("/api/rfqs/intake")
def api_rfq_intake(payload: RfqIntake) -> dict:
    from .rfq import intake

    return intake(
        mail_id=payload.mail_id or "",
        conversation_id=payload.conversation_id or "",
        message=payload.message or "",
        session_id=payload.session_id or "default",
    )


@app.get("/api/thought")
def api_thought(session_id: str = "default") -> dict:
    return next_thought(session_id).model_dump()


@app.get("/api/conversations")
def api_conversations() -> dict:
    from . import conversations as convs

    return {"items": convs.list_public()}


@app.post("/api/conversations")
def api_conversation_create(payload: ConversationCreate) -> dict:
    from . import conversations as convs

    return convs.create(payload.category, payload.title, payload.focus)


@app.patch("/api/conversations/{conversation_id}")
def api_conversation_patch(conversation_id: str, payload: ConversationPatch) -> dict:
    from . import conversations as convs

    fields = payload.model_dump(exclude_none=True)
    row = convs.patch(conversation_id, **fields)
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row


@app.post("/api/conversations/drawing")
def api_conversation_drawing(payload: DrawingSpawn) -> dict:
    from . import conversations as convs

    focus = {
        "filename": payload.filename or payload.local_name,
        "local_name": payload.local_name or payload.filename,
        "local_path": payload.local_path,
        "mime": payload.mime,
        "drive_link": payload.drive_link,
    }
    return convs.spawn_drawing(focus)


@app.get("/api/memory")
def api_memory(session_id: str = "default") -> dict:
    return {"items": db.list_memories(session_id)}


@app.post("/api/inbox")
async def api_inbox(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    inbox_dir = settings.data_dir / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    temp = inbox_dir / f"{uuid.uuid4().hex}{suffix}"
    temp.write_bytes(raw)
    try:
        text = read_export_text(temp)
    except Exception:
        text = ""
    if suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".tif", ".tiff"}:
        text = ""
    file_id = uuid.uuid4().hex[:12]
    db.add_inbox_file(file_id, file.filename or temp.name, text, str(temp))
    db.add_audit("default", "inbox", f"Ingested {file.filename}", "ok")
    return {"id": file_id, "name": file.filename, "preview": text[:500]}


@app.get("/api/canvas/boards")
def api_canvas_boards() -> dict:
    return {"items": db.list_canvas_boards()}


@app.post("/api/canvas/boards")
def api_canvas_create_board(payload: CanvasBoardCreate) -> dict:
    board = db.upsert_canvas_board(payload.id or uuid.uuid4().hex[:12], payload.name)
    board["items"] = []
    return board


@app.get("/api/canvas/boards/{board_id}")
def api_canvas_board(board_id: str) -> dict:
    board = db.get_canvas_board(board_id) or db.upsert_canvas_board(board_id)
    board["items"] = db.list_canvas_items(board_id)
    return board


@app.put("/api/canvas/boards/{board_id}")
def api_canvas_save_board(board_id: str, payload: CanvasBoardUpdate) -> dict:
    rows = []
    for item in payload.items:
        raw = item.model_dump()
        rows.append(
            {
                **{key: raw[key] for key in CANVAS_ITEM_BASE_FIELDS},
                "data": {key: value for key, value in raw.items() if key not in CANVAS_ITEM_BASE_FIELDS},
            }
        )
    db.upsert_canvas_board(board_id, payload.name, payload.camera.model_dump())
    count = db.replace_canvas_items(board_id, rows)
    return {"ok": True, "count": count}


@app.post("/api/canvas/files")
async def api_canvas_upload(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    suffix = Path(file.filename or "drop").suffix.lower()
    settings.canvas_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    target = settings.canvas_dir / f"{file_id}{suffix}"
    target.write_bytes(raw)
    width = height = 0.0
    page_count = 0
    if suffix == ".pdf":
        # Page geometry so the board can place the drawing at true aspect ratio.
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(target))
            page_count = len(reader.pages)
            box = reader.pages[0].mediabox
            width = float(box.width)
            height = float(box.height)
        except Exception:
            page_count = 0
    record = db.add_canvas_file(
        file_id,
        file.filename or target.name,
        file.content_type or "",
        str(target),
        width,
        height,
        page_count,
    )
    db.add_audit("canvas", "canvas_upload", f"Placed {file.filename} on the board", "ok")
    return record


@app.get("/api/canvas/files/{file_id}")
def api_canvas_file(file_id: str):
    record = db.get_canvas_file(file_id)
    if not record:
        raise HTTPException(404, "Canvas file not found")
    path = Path(record["path"]).resolve()
    root = settings.canvas_dir.resolve()
    if root not in path.parents and path.parent != root:
        raise HTTPException(400, "Invalid canvas file path")
    if not path.exists():
        raise HTTPException(404, "File missing")
    # No filename= here: an attachment disposition would stop <img> from showing it.
    return FileResponse(path, media_type=record.get("mime") or None)
