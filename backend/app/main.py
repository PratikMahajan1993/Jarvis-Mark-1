from __future__ import annotations

import base64
import binascii
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
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
    DiscussionCreate,
    DrawingSpawn,
    WorkflowCreate,
    MailAttachmentAction,
    MailReplyAttachmentAction,
    MarkedDrawingSave,
    ChatRequest,
    ConfirmRequest,
    Preferences,
    PreferencesUpdate,
    TtsRequest,
)
from .tools.documents import read_export_text
from .hud_state import load_hud, remember_hud
from .mail_sync import get_state as mail_sync_state, kick_bulk as kick_mail_bulk, maybe_kick_on_startup
from .snapshot import kick as kick_snapshot
from .watch import ack_watch, resume_watches, watch_payload

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .turns.reaper import start_reaper_daemon

    _reaper_stop = start_reaper_daemon()
    startup()
    yield
    _reaper_stop.set()


app = FastAPI(title="Jarvis Command Center", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list or ["http://localhost:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|(\d{1,3}\.){3}\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    maybe_kick_on_startup()
    try:
        from .memory.store import _ensure_schema

        _ensure_schema()
    except Exception:
        pass
    if settings.hermes_enabled:
        # Never block API readiness on MCP registration (can take minutes).
        import threading

        def _mcp_bg() -> None:
            try:
                from .hermes.bridge import (
                    ensure_jarvis_mcp_registered,
                    ensure_playbooks_installed,
                    hermes_available,
                )

                ensure_playbooks_installed()
                if hermes_available():
                    ensure_jarvis_mcp_registered()
            except Exception:
                pass

        threading.Thread(target=_mcp_bg, name="jarvis-mcp-register", daemon=True).start()
    else:
        try:
            from .hermes.bridge import ensure_playbooks_installed

            ensure_playbooks_installed()
        except Exception:
            pass
    try:
        from .voicebox import warm_voicebox

        warm_voicebox()
    except Exception:
        pass
    try:
        from .hermes.bridge import warm_hermes

        warm_hermes("default")
    except Exception:
        pass
    try:
        from .live_log import record as live_record

        boot_status = health()
        live_record(
            source="api",
            kind="health_once",
            fields={
                "ok": boot_status.get("ok"),
                "model_ready": boot_status.get("model_ready"),
            },
        )
    except Exception:
        pass


@app.get("/api/agents")
def api_agents() -> dict:
    from .agents import agent_status_payload

    return {"items": agent_status_payload()}


@app.get("/api/health")
def api_health() -> dict:
    status = health()
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
    try:
        from . import voicebox as vb

        status["voicebox"] = vb.status_payload()
    except Exception:
        status["voicebox"] = {"enabled": bool(settings.voicebox_enabled), "available": False}

    # `ok` used to be hardcoded True, so a dead Ollama or a missing Gemini key could never
    # surface as unhealthy. A live chat turn actually succeeds if *either* the brain provider
    # (Gemini/Ollama) is ready, *or* Hermes is enabled and reachable (agent.py falls back to
    # the brain whenever Hermes is unavailable, and routes through Hermes directly when it is
    # up) — so Hermes being down with a healthy brain fallback is a real "ok", not a failure.
    # Voicebox never gates this: `frontend/src/lib/voice.ts` always has a browser-TTS fallback,
    # so a Voicebox outage is a documented degraded-speech state, not an outage of the app.
    brain_ready = bool(status.get("ok")) and bool(status.get("model_ready"))
    hermes_status = status.get("hermes") or {}
    hermes_ready = bool(hermes_status.get("enabled")) and bool(hermes_status.get("available"))
    status["ok"] = brain_ready or hermes_ready
    return status


@app.get("/api/voicebox/status")
def api_voicebox_status() -> dict:
    from . import voicebox as vb

    return vb.status_payload()


class LiveLogRequest(BaseModel):
    source: Literal["api", "hud"] = "hud"
    kind: str
    session_id: str = "default"
    latency_ms: int | None = None
    fields: dict[str, Any] | None = None


@app.post("/api/live-log")
def api_live_log(payload: LiveLogRequest) -> dict:
    try:
        from .live_log import record as live_record

        live_record(
            source=payload.source,
            kind=payload.kind,
            session_id=payload.session_id,
            latency_ms=payload.latency_ms,
            fields=payload.fields,
        )
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/live-log/recent")
def api_live_log_recent(limit: int = 80) -> dict:
    from .live_log import log_paths, recent_events

    return {"items": recent_events(limit=limit), "paths": log_paths()}


@app.post("/api/tts")
def api_tts(payload: TtsRequest) -> Response:
    """Proxy local Voicebox TTS so the browser avoids CORS to :17493."""
    from . import voicebox as vb

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "Empty text")
    t0 = time.perf_counter()
    ok = False
    err_msg = ""
    try:
        wav = vb.synthesize(text, profile=payload.profile or None, language=payload.language or "en")
        ok = True
        return Response(content=wav, media_type="audio/wav")
    except Exception as exc:
        err_msg = str(exc)[:200]
        # 503 (not 502): Voicebox unreachable or synthesis failed — HUD falls back to browser TTS.
        raise HTTPException(503, err_msg) from exc
    finally:
        try:
            from .live_log import record as live_record

            live_record(
                source="api",
                kind="tts",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                fields={
                    "text_len": len(text),
                    "text_preview": text[:80],
                    "profile": payload.profile or None,
                    "ok": ok,
                    "error": err_msg or None,
                },
            )
        except Exception:
            pass


@app.get("/api/metrics")
def api_metrics() -> dict:
    from .metrics import metrics_snapshot

    return metrics_snapshot()


@app.get("/api/missions")
def api_missions(limit: int = 40, mission_id: str | None = None, session_id: str | None = None) -> dict:
    return {"items": db.list_mission_steps(limit=limit, mission_id=mission_id, session_id=session_id)}


@app.get("/api/turns/recent")
def api_turns_recent(limit: int = 20) -> dict:
    """Last N chat/confirm turns for capability-test review (also mirrored to work/LAST_TURNS.md)."""
    from .turn_log import log_paths, recent_turns

    return {"items": recent_turns(limit=limit), "paths": log_paths()}


@app.get("/api/turns/open")
def api_turns_open(session_id: str = "default") -> dict:
    from .config import settings
    from . import db
    from .turns import list_open_turns, turn_row_to_api

    if not settings.turn_ledger_enabled:
        return {"enabled": False, "turns": []}

    items: list[dict] = []
    for row in list_open_turns(session_id):
        api_row = turn_row_to_api(row)
        pid = row.get("pending_action_id")
        if pid:
            pending = db.get_pending(str(pid))
            if pending:
                api_row["pending_action"] = pending
                api_row["pending_status"] = pending.get("status") or "pending"
        items.append(api_row)
    return {"enabled": True, "turns": items}


@app.get("/api/turns/{turn_id}/events")
async def api_turn_events(turn_id: str, request: Request) -> StreamingResponse:
    from .turns import get_turn
    from .turns.events import parse_last_event_id, stream_turn_events

    if not get_turn(turn_id):
        raise HTTPException(status_code=404, detail="turn not found")

    last_id = parse_last_event_id(request.headers.get("Last-Event-ID"))

    async def _body():
        async for chunk in stream_turn_events(turn_id, last_id):
            yield chunk

    return StreamingResponse(
        _body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/turns/{turn_id}")
def api_turn_get(turn_id: str) -> dict:
    from .turns import get_turn, turn_row_to_api

    row = get_turn(turn_id)
    if not row:
        raise HTTPException(status_code=404, detail="turn not found")
    return turn_row_to_api(row)


@app.get("/api/google/status")
def api_google_status() -> dict:
    return google_auth.status()


@app.get("/api/google/auth")
def api_google_auth() -> RedirectResponse:
    try:
        return RedirectResponse(google_auth.auth_url())
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/google/callback")
def api_google_callback(code: str = "", state: str = "") -> RedirectResponse:
    try:
        google_auth.finish_auth(code, state)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        kick_mail_bulk(days=100, force=True)
    except Exception:
        pass
    return RedirectResponse(f"{settings.hud_url}/?gmail=1")


class MailSyncRequest(BaseModel):
    days: int = 100
    force: bool = False
    inline: bool = False


@app.post("/api/mail/sync")
def api_mail_sync(payload: MailSyncRequest | None = None) -> dict:
    """Start background bulk Gmail sync (100d inbox default) or run inline on desk."""
    body = payload or MailSyncRequest()
    if body.inline:
        from .mail_sync import sync_bulk_inline

        return sync_bulk_inline(days=body.days, force=body.force)
    return kick_mail_bulk(days=body.days, force=body.force)


@app.get("/api/mail/sync")
def api_mail_sync_status() -> dict:
    return mail_sync_state()


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
async def api_chat(payload: ChatRequest, request: Request) -> dict:
    if settings.turn_ledger_enabled:
        from .turns.accept import accept_chat_turn
        from .turns.worker import schedule_turn

        message = payload.message.strip()
        idempotency_key = (request.headers.get("Idempotency-Key") or "").strip() or uuid.uuid4().hex
        row, is_new = accept_chat_turn(
            session_id=payload.session_id,
            message=message,
            idempotency_key=idempotency_key,
        )
        if is_new:
            schedule_turn(row["id"])
        return {"turn_id": row["id"], "state": row["state"]}

    from .semantic_router import classify_intent, handle_ui_command, stamp_route, try_obvious_casual

    t0 = time.perf_counter()
    message = payload.message.strip()
    try:
        from .live_log import record as live_record

        live_record(
            source="api",
            kind="chat_in",
            session_id=payload.session_id,
            fields={"message": message},
        )
    except Exception:
        pass
    classification = try_obvious_casual(message) or await classify_intent(message)

    if classification.intent == "ui_command":
        result = handle_ui_command(message, payload.session_id, classification)
    else:
        result = run_agent(message, payload.session_id, route=classification)
        result = stamp_route(result, classification)

    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    remember_hud(payload.session_id, data)
    try:
        from .turn_log import record_turn

        record_turn(session_id=payload.session_id, user=message, response=data, source="chat")
    except Exception:
        pass
    try:
        from .live_log import chat_out_fields, record as live_record

        live_record(
            source="api",
            kind="chat_out",
            session_id=payload.session_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            fields=chat_out_fields(data),
        )
    except Exception:
        pass
    speak = str(data.get("speak") or "").strip()
    if speak:
        try:
            from .voicebox import prefetch_tts

            prefetch_tts(speak)
        except Exception:
            pass
    return data


@app.post("/api/confirm")
def api_confirm(payload: ConfirmRequest, request: Request) -> dict:
    t0 = time.perf_counter()
    idempotency_key = (request.headers.get("Idempotency-Key") or "").strip()
    if idempotency_key:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM confirm_idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if row:
            return json.loads(row["response_json"])

    result = resolve_pending(payload.action_id, payload.approved, payload.session_id)
    data = result.model_dump()
    if idempotency_key:
        with db.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO confirm_idempotency
                (idempotency_key, action_id, approved, response_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    payload.action_id,
                    1 if payload.approved else 0,
                    json.dumps(data),
                    db.utc_now(),
                ),
            )
            row = conn.execute(
                "SELECT response_json FROM confirm_idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if row:
            data = json.loads(row["response_json"])
    remember_hud(payload.session_id, data)
    try:
        from .turn_log import record_turn

        decision = "Authorize" if payload.approved else "Reject"
        record_turn(
            session_id=payload.session_id,
            user=f"[{decision}] action_id={payload.action_id}",
            response=data,
            source="confirm",
        )
    except Exception:
        pass
    try:
        from .live_log import chat_out_fields, record as live_record

        live_record(
            source="api",
            kind="confirm",
            session_id=payload.session_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            fields={
                "decision": "Authorize" if payload.approved else "Reject",
                "action_id": payload.action_id,
                "speak": str(data.get("speak") or "").strip(),
                "pending": chat_out_fields(data).get("pending"),
            },
        )
    except Exception:
        pass
    speak = str(data.get("speak") or "").strip()
    if speak:
        try:
            from .voicebox import prefetch_tts

            prefetch_tts(speak)
        except Exception:
            pass
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


@app.get("/api/suggested-tasks")
def api_suggested_tasks(refresh: bool = False, session_id: str = "default") -> dict:
    from .office_day import list_tasks, refresh_suggested_tasks

    weather = None
    if refresh:
        payload = refresh_suggested_tasks(session_id)
        weather = payload.get("weather")
        return {"items": payload.get("tasks") or list_tasks(), "weather": weather}
    return {"items": list_tasks(), "weather": weather}


@app.post("/api/suggested-tasks/{task_id}/status")
def api_suggested_task_status(task_id: str, status: str = "dismissed") -> dict:
    from .office_day import set_task_status

    row = set_task_status(task_id, status)
    if not row:
        raise HTTPException(404, "Task not found")
    return row


@app.post("/api/hermes/warm")
def api_hermes_warm(session_id: str = "default", force: bool = False) -> dict:
    from .hermes.bridge import warm_hermes

    return warm_hermes(session_id, force=force)


@app.get("/api/hermes/warm")
def api_hermes_warm_status(session_id: str = "default") -> dict:
    from .hermes.bridge import hermes_warm_status

    return hermes_warm_status(session_id)


@app.post("/api/office/refresh")
def api_office_refresh(session_id: str = "default") -> dict:
    from .office_day import refresh_suggested_tasks

    try:
        from .hermes.bridge import warm_hermes

        warm_hermes(session_id)
    except Exception:
        pass
    return refresh_suggested_tasks(session_id)


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
def api_artifact_download(artifact_id: str) -> FileResponse:
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
def api_drawing_download(filename: str) -> FileResponse:
    try:
        path = safe_drawing_path(filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.exists():
        raise HTTPException(404, "Drawing not found")
    suffix = path.suffix.lower()
    media = "application/pdf" if suffix == ".pdf" else None
    return FileResponse(path, media_type=media)


class VisionBenchAnalyse(BaseModel):
    file_sha256: str


class VisionConsentPost(BaseModel):
    customer_id: str
    allow: bool
    nda: bool = False
    attested_by: str


@app.get("/api/masterdata/vision-consent")
def api_masterdata_vision_consent_get(customer_id: str | None = None) -> dict:
    from .vision.gate import vision_consent_get_payload

    return vision_consent_get_payload(customer_id)


@app.post("/api/masterdata/vision-consent")
def api_masterdata_vision_consent_post(payload: VisionConsentPost) -> dict:
    if not settings.masterdata_enabled:
        return {"enabled": False, "ok": False}
    from .vision.gate import attest_customer_vision

    out = attest_customer_vision(
        payload.customer_id,
        allow=payload.allow,
        nda=payload.nda,
        attested_by=payload.attested_by,
    )
    out["enabled"] = True
    return out


@app.get("/api/vision/bench")
def api_vision_bench() -> dict:
    from .vision.gate import vision_bench_get_payload

    return vision_bench_get_payload()


@app.post("/api/vision/bench/analyse")
def api_vision_bench_analyse(payload: VisionBenchAnalyse) -> dict:
    if not settings.vision_bench_enabled:
        return {"enabled": False, "ok": False}
    from .vision.gate import bench_analyse_drawing

    digest = (payload.file_sha256 or "").strip()
    if not digest:
        raise HTTPException(400, "file_sha256 required")
    out = bench_analyse_drawing(digest)
    out["enabled"] = True
    return out


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
def api_conversations(desk: bool = False) -> dict:
    from . import conversations as convs

    items = convs.list_desk() if desk else convs.list_public()
    return {"items": items, "ambient_session": convs.ambient_session()}


@app.post("/api/conversations")
def api_conversation_create(payload: ConversationCreate) -> dict:
    from . import conversations as convs

    return convs.create(payload.category, payload.title, payload.focus)


@app.post("/api/conversations/discussion")
def api_conversation_discussion(payload: DiscussionCreate) -> dict:
    from . import conversations as convs

    return convs.start_discussion(payload.title, payload.focus)


@app.post("/api/conversations/workflow")
def api_conversation_workflow(payload: WorkflowCreate) -> dict:
    from . import conversations as convs

    return convs.start_or_resume_workflow(
        title=payload.title,
        focus=payload.focus,
        resume_key=payload.resume_key,
    )


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
def api_canvas_file(file_id: str) -> FileResponse:
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
