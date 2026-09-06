from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import db
from .agent import next_thought, resolve_pending, run_agent
from .briefing import build_briefing, build_glance
from .config import settings
from .connectors.calendar import seed_calendar
from .familiarity import ensure_demo_people
from .connectors.email import seed_mailbox
from .connectors import google_auth
from .ollama_client import health
from .schemas import (
    CANVAS_ITEM_BASE_FIELDS,
    CanvasBoardCreate,
    CanvasBoardUpdate,
    ChatRequest,
    ConfirmRequest,
    Preferences,
    PreferencesUpdate,
)
from .tools.documents import read_export_text
from .watch import watch_payload

app = FastAPI(title="Jarvis Command Center", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    seed_mailbox()
    seed_calendar()
    ensure_demo_people()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def api_health() -> dict:
    status = health()
    status["ok"] = True
    status["google"] = google_auth.status()
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


@app.post("/api/chat")
def api_chat(payload: ChatRequest) -> dict:
    result = run_agent(payload.message.strip(), payload.session_id)
    return result.model_dump()


@app.post("/api/confirm")
def api_confirm(payload: ConfirmRequest) -> dict:
    result = resolve_pending(payload.action_id, payload.approved, payload.session_id)
    return result.model_dump()


@app.get("/api/briefing")
def api_briefing() -> dict:
    return build_briefing()


@app.get("/api/glance")
def api_glance() -> dict:
    return build_glance()


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


@app.get("/api/thought")
def api_thought(session_id: str = "default") -> dict:
    return next_thought(session_id).model_dump()


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
