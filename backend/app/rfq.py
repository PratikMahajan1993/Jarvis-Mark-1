"""Inbound drawing-RFQ reasoning, Shall I hold/deadline, CNC on request.

Auto-RFQ never drafts G-code. Tony must ask before ``cnc_suggest.suggest_program``.
Visible dimensions only — unreadable numbers are named, never invented.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import db
from . import jobs
from .config import settings
from .familiarity import first_name, get_set, remember_artifact

FIXTURE_GROUNDING = (
    "Title block: Input pinion blank. Material 18CrNiMo7-6. "
    "Front view and side view on the sheet. "
    "OD Ø50 mm is visible. Overall length 80 mm is visible. "
    "Bore diameter is unreadable. "
    "The OD tolerance is missing on the sheet. "
    "Notes: soft-jaw hold on first-op OD. Face both ends, finish-turn OD, "
    "drill and bore through."
)

_SIMILAR_KEYS = ("id", "part_name", "material", "machine", "cycle_min", "geometry_notes")
_UNREADABLE = re.compile(
    r"\b(unreadable|illegible|cannot read|can't read|not readable|could not read|"
    r"missing(?:\s+on\s+the\s+sheet)?|not visible|illegible)\b",
    re.I,
)
_MATERIAL = re.compile(
    r"\b(18CrNiMo7-6|EN36C|EN36|EN24|EN8|EN19|20MnCr5|16MnCr5|Al\s*6061|aluminium|aluminum|"
    r"mild steel|MS|SS304|SS316|C45|42CrMo4)\b",
    re.I,
)
_MATERIAL_LABEL = re.compile(r"\bmaterial\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9./\s-]{1,40})", re.I)
_OD = re.compile(
    r"\b(?:od|o\.d\.|outer\s+dia(?:meter)?|stock\s+od)\b[^.]{0,40}?"
    r"(?:ø|Ø)?\s*(\d+(?:\.\d+)?)\s*(mm|in(?:ch(?:es)?)?)?",
    re.I,
)
_OD_MARK = re.compile(r"(?:ø|Ø)\s*(\d+(?:\.\d+)?)\s*(mm|in(?:ch(?:es)?)?)?", re.I)
_LENGTH = re.compile(
    r"\b(?:overall\s+length|oal|stock\s+length|finished\s+length|length)\b[^.]{0,40}?"
    r"(\d+(?:\.\d+)?)\s*(mm|in(?:ch(?:es)?)?)?",
    re.I,
)
_BORE = re.compile(
    r"\b(?:bore(?:\s+dia(?:meter)?)?|inner\s+dia(?:meter)?|\bid\b|\bi\.d\.)\b[^.]{0,40}?"
    r"(?:ø|Ø)?\s*(\d+(?:\.\d+)?)\s*(mm|in(?:ch(?:es)?)?)?",
    re.I,
)
_RFQ_USER = re.compile(
    r"\brfq\b|request for quot|treat this as (?:an?\s+)?rfq"
    r"|(?:\bquote\b|\bquotation\b).{0,40}\bdrawing\b"
    r"|\bdrawing\b.{0,40}(?:\bquote\b|\bquotation\b|\brfq\b)",
    re.I,
)
_DRAWING_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".dwg", ".dxf", ".step", ".stp")


def to_public(row: jobs.Rfq) -> dict[str, Any]:
    extract = dict(row.get("extract") or {})
    if extract.get("title"):
        extract["title"] = _clean_part_title(str(extract.get("title") or ""))
    catch = str(extract.get("catch") or "").strip()
    similar: list[dict[str, Any]] = []
    for job_id in row.get("similar_job_ids") or []:
        job = jobs.get_job(str(job_id))
        if not job:
            continue
        similar.append({key: job.get(key) for key in _SIMILAR_KEYS})
    return {
        "id": row.get("id") or "",
        "status": row.get("status") or "",
        "mail_id": row.get("mail_id") or "",
        "conversation_id": row.get("conversation_id") or "",
        "extract": extract,
        "similar_jobs": similar,
        "pending_reply": row.get("pending_reply") or "",
        "deadline_iso": row.get("deadline_iso") or "",
        "catch": catch,
        "updated_at": row.get("updated_at") or "",
    }


def list_public(*, include_dismissed: bool = False) -> list[dict[str, Any]]:
    items = []
    for row in jobs.list_rfqs():
        if not include_dismissed and row.get("status") == "dismissed":
            continue
        items.append(to_public(row))
    return items


def get_public(rfq_id: str) -> dict[str, Any] | None:
    row = jobs.get_rfq(rfq_id)
    return to_public(row) if row else None


def glance_critical() -> dict[str, Any] | None:
    """One RFQ chip while Shall I hold/deadline is waiting. Do not spam intake or declined rows."""
    for row in jobs.list_rfqs():
        if row.get("status") != "pending":
            continue
        public = to_public(row)
        catch = public.get("catch") or "Drawing RFQ is waiting."
        title = _title_from_extract(public.get("extract") or {}) or "Drawing RFQ"
        return {
            "kind": "rfq",
            "title": title,
            "detail": catch[:220],
            "tone": "amber",
            "sourceId": public["id"],
        }
    return None


def attachment_is_drawing(item: dict[str, Any] | None) -> bool:
    att = item or {}
    if att.get("vision") or att.get("cad") or att.get("readable"):
        return True
    name = str(att.get("filename") or att.get("local_name") or "").lower()
    mime = str(att.get("mime") or "").lower()
    if any(name.endswith(ext) for ext in _DRAWING_EXT):
        return True
    if mime == "application/pdf" or mime.startswith("image/"):
        return True
    return False


def mail_looks_like_rfq(mail: dict[str, Any] | None, message: str = "") -> bool:
    if _RFQ_USER.search(message or ""):
        return True
    blob = f"{(mail or {}).get('subject') or ''} {(mail or {}).get('body') or ''}"
    if _RFQ_USER.search(blob):
        return True
    for item in (mail or {}).get("attachments") or []:
        if attachment_is_drawing(item):
            return True
    return False


def detect_inbound_drawings() -> list[jobs.Rfq]:
    """Silent tick: intake rows for new drawing mail. Does not reason or draft CNC."""
    from .connectors import email as email_conn

    created: list[jobs.Rfq] = []
    try:
        rows = email_conn.search_emails(limit=20)
    except Exception:
        return created
    known = {row.get("mail_id") for row in jobs.list_rfqs() if row.get("mail_id")}
    for mail in rows:
        mail_id = str(mail.get("id") or "")
        if not mail_id or mail_id in known:
            continue
        if not mail_looks_like_rfq(mail):
            continue
        if not any(attachment_is_drawing(item) for item in mail.get("attachments") or []):
            continue
        created.append(jobs.create_rfq(mail_id=mail_id, status="intake"))
        known.add(mail_id)
    return created


def intake(
    *,
    mail_id: str = "",
    conversation_id: str = "",
    message: str = "",
    session_id: str = "default",
) -> dict[str, Any]:
    """Resolve a drawing conversation, reason the RFQ, queue Shall I hold + deadline.

    Never calls ``cnc_suggest``.
    """
    from . import conversations as convs
    from .connectors import email as email_conn
    from .familiarity import remember_rfq

    mail = email_conn.get_email(mail_id) if mail_id else None
    user_says = bool(_RFQ_USER.search(message or ""))
    conv: dict[str, Any] | None = None
    if conversation_id:
        conv = convs.public_row(db.get_conversation(conversation_id) or {}) if db.get_conversation(conversation_id) else None
        if not conv or not conv.get("id"):
            conv = None
    if conv is None:
        conv = _resolve_drawing_conversation(session_id, message)
    if conv is None and mail and mail_looks_like_rfq(mail, message):
        conv = _spawn_from_mail(session_id, mail)
    if conv is None and user_says:
        conv = _resolve_drawing_conversation(session_id, message)
    if conv is None:
        speak = "I need the drawing in focus to treat this as an RFQ."
        return {"rfq": None, "conversation": None, "speak": speak}

    cid = str(conv.get("id") or conversation_id)
    result = reason_rfq(
        cid,
        mail_id=mail_id or str((mail or {}).get("id") or ""),
        message=message,
        session_id=session_id or str(conv.get("session_id") or "default"),
        from_name=_from_name(message, mail),
    )
    remember_rfq(session_id or str(conv.get("session_id") or "default"), result["rfq"]["id"], cid)
    updated = convs.public_row(db.get_conversation(cid) or {}) if db.get_conversation(cid) else conv
    return {
        "rfq": result["rfq"],
        "conversation": updated,
        "speak": result["speak"],
    }


def reason_rfq(
    conversation_id: str,
    *,
    mail_id: str = "",
    message: str = "",
    session_id: str = "default",
    from_name: str = "",
    rfq_id: str | None = None,
) -> dict[str, Any]:
    """Read drawing grounding + job library. Persist reasoned then pending.

    Returns speak (the catch), public RFQ, and queued pending ids.
    """
    row = db.get_conversation(conversation_id)
    if not row:
        raise ValueError("Conversation not found")
    focus = dict(row.get("focus") or {})
    grounding = str(focus.get("grounding") or "").strip()
    session = session_id or str(row.get("session_id") or "default")
    parsed = _extract_from_grounding(grounding)
    gemini_bit = _gemini_extract(grounding) if grounding else None
    if gemini_bit:
        parsed = _merge_visible(parsed, gemini_bit, grounding)
    similar = jobs.search_similar(str(parsed.get("material") or ""), str(parsed.get("geometry_notes") or ""))
    catch = _build_catch(parsed, similar, grounding)
    parsed["catch"] = catch
    deadline = suggested_deadline()
    who = from_name or parsed.get("from") or _from_name(message, None) or "there"
    parsed["from"] = who
    reply = _holding_reply(who, catch, deadline, similar, parsed)
    existing = _rfq_for_conversation(conversation_id, mail_id)
    if existing and not rfq_id:
        rfq_id = existing["id"]
        record = jobs.update_rfq(
            rfq_id,
            mail_id=mail_id or existing.get("mail_id") or "",
            conversation_id=conversation_id,
            status="reasoned",
            extract=parsed,
            similar_job_ids=[job["id"] for job in similar],
            pending_reply=reply,
            deadline_iso=deadline,
        )
    else:
        record = jobs.create_rfq(
            mail_id=mail_id,
            conversation_id=conversation_id,
            status="reasoned",
            extract=parsed,
            similar_job_ids=[job["id"] for job in similar],
            pending_reply=reply,
            deadline_iso=deadline,
            rfq_id=rfq_id,
        )
    assert record is not None
    pending_ids = _queue_hold(session, record, reply, deadline, who)
    updated = jobs.update_rfq(record["id"], status="pending") or record
    public = to_public(updated)
    focus["rfq_id"] = updated["id"]
    focus["extract"] = parsed
    focus["catch"] = catch
    focus["similar_jobs"] = public["similar_jobs"]
    db.update_conversation(conversation_id, focus=focus, status="ready")
    from .familiarity import remember_rfq

    remember_rfq(session, updated["id"], conversation_id)
    speak = catch
    return {
        "speak": speak,
        "rfq": public,
        "extract": parsed,
        "similar_jobs": public["similar_jobs"],
        "pending_reply": reply,
        "deadline_iso": deadline,
        "pending_ids": pending_ids,
    }


def request_program(
    *,
    session_id: str = "default",
    conversation_id: str = "",
    extract: dict[str, Any] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Tony asked for a from-scratch CNC draft. Never used on auto-RFQ."""
    from .cnc_suggest import suggest_program
    from .familiarity import remember_cnc

    payload_extract, job, rfq_row = _extract_for_cnc(session_id, conversation_id, extract)
    dest: Path | None = None
    if write:
        dest = _draft_nc_path(rfq_row.get("id") if rfq_row else "", session_id)
    result = suggest_program(payload_extract, job=job, write_path=dest)
    if not result.get("ok"):
        speak = str(result.get("strategy") or "I will not invent geometry for a CNC draft.")
        scene = {
            "title": "No CNC draft",
            "subtitle": "Missing trusted sizes",
            "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}],
        }
        return {
            "ok": False,
            "speak": speak,
            "scene": scene,
            "result": result,
            "pending": None,
        }
    path = str(result.get("path") or "")
    remember_cnc(session_id, path, rfq_row.get("id") if rfq_row else "")
    if path:
        art = db.add_artifact(uuid.uuid4().hex[:12], "cnc-draft", Path(path).name, path)
        remember_artifact(session_id, art, Path(path).stem)
    pending = db.add_pending(
        f"cnc-promote-{uuid.uuid4().hex[:8]}",
        session_id,
        "cnc_promote",
        "Keep this CNC draft",
        "Copy it as draft-accepted. Not proven, not sent to a machine.",
        {
            "path": path,
            "rfq_id": (rfq_row or {}).get("id") or "",
            "job_id": (job or {}).get("id") or "",
            "nc": result.get("nc") or "",
        },
    )
    strategy = str(result.get("strategy") or "")
    speak = (
        f"Draft CNC program is on disk as {Path(path).name}. "
        "It is not proven and I will not send it to a machine. Shall I keep it as an accepted draft?"
    )
    scene = {
        "title": "CNC draft",
        "subtitle": Path(path).name if path else "Draft",
        "widgets": [
            {"type": "markdown", "title": "Strategy", "text": strategy},
            {"type": "quote", "text": "Shall I keep this draft? It is not proven.", "cite": "Jarvis"},
        ],
    }
    return {
        "ok": True,
        "speak": speak,
        "scene": scene,
        "result": result,
        "pending": pending,
        "path": path,
    }


def promote_cnc_draft(payload: dict[str, Any], session_id: str, approved: bool) -> dict[str, Any]:
    src = Path(str(payload.get("path") or ""))
    if not approved:
        return {
            "speak": "Left the draft.",
            "detail": "Left the CNC draft on disk.",
            "path": str(src) if src else "",
        }
    if not src.is_file():
        return {
            "speak": "The draft file is gone.",
            "detail": "CNC draft missing.",
            "path": "",
        }
    dest = src.with_name(f"{src.stem}-accepted{src.suffix}")
    if dest.resolve() == src.resolve():
        dest = src.with_name(f"{src.stem}-accepted.nc")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    art = db.add_artifact(uuid.uuid4().hex[:12], "cnc-draft", dest.name, str(dest))
    remember_artifact(session_id, art, dest.stem)
    rfq_id = str(payload.get("rfq_id") or "")
    if rfq_id:
        row = jobs.get_rfq(rfq_id)
        if row:
            extract = dict(row.get("extract") or {})
            extract["cnc_accepted_path"] = str(dest)
            jobs.update_rfq(rfq_id, extract=extract)
    speak = (
        f"Draft accepted on disk as {dest.name}. "
        "It is not proven on the machine and I did not email it."
    )
    return {"speak": speak, "detail": speak, "path": str(dest), "artifact": art}


def suggested_deadline(*, days: int = 3) -> str:
    tz = _tz()
    moment = datetime.now(tz) + timedelta(days=max(1, days))
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    moment = moment.replace(hour=17, minute=0, second=0, microsecond=0)
    return moment.isoformat()


def _tz() -> ZoneInfo:
    prefs = db.get_preferences()
    try:
        return ZoneInfo(prefs.get("timezone") or settings.tz or "Asia/Kolkata")
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def _clean_part_title(text: str) -> str:
    """Keep the part name. Drop title-block boilerplate (scale, sheet, material)."""
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = re.split(r"\s+[—–-]\s+TITLE BLOCK\b", raw, maxsplit=1, flags=re.I)[0]
    raw = re.split(r",\s*(?:Scale|Sheet|Material)\b", raw, maxsplit=1, flags=re.I)[0]
    raw = re.sub(r"\btitle block\b[:\s]*", "", raw, flags=re.I)
    return raw.strip(" —–-,:.")[:60]


def _title_from_extract(extract: dict[str, Any]) -> str:
    for key in ("title", "part_name", "drawing", "drawing_no"):
        text = _clean_part_title(str(extract.get(key) or ""))
        if text:
            return text
    material = str(extract.get("material") or "").strip()
    if material:
        return f"{material} RFQ"
    return ""


def _from_name(message: str, mail: dict[str, Any] | None) -> str:
    if mail:
        name = first_name(str(mail.get("sender") or ""))
        if name:
            return name
    match = re.search(r"\bfrom\s+([A-Za-z][A-Za-z'-]+)\b", message or "", re.I)
    if match:
        return match.group(1)
    return ""


def _resolve_drawing_conversation(session_id: str, message: str) -> dict[str, Any] | None:
    from . import conversations as convs

    if session_id:
        row = db.get_conversation_by_session(session_id)
        if row and row.get("category") == "drawing":
            return convs.public_row(row)
    latest = convs.latest_drawing()
    if latest:
        return latest
    named = convs.match_named(message or "")
    if named and named.get("category") == "drawing":
        return named
    return _conversation_from_saved_drawing()


def _conversation_from_saved_drawing() -> dict[str, Any] | None:
    from . import conversations as convs

    for art in db.list_artifacts(20):
        name = str(art.get("name") or "")
        path = str(art.get("path") or "")
        kind = str(art.get("kind") or "")
        if kind not in {"drawing", "pdf", "cnc-draft"} and not any(name.lower().endswith(ext) for ext in _DRAWING_EXT):
            continue
        if kind == "cnc-draft":
            continue
        if not path or not Path(path).is_file():
            continue
        return convs.spawn_drawing(
            {
                "filename": name,
                "local_name": Path(path).name,
                "local_path": path,
                "mime": "application/pdf" if name.lower().endswith(".pdf") else "",
            }
        )
    return None


def _spawn_from_mail(session_id: str, mail: dict[str, Any]) -> dict[str, Any] | None:
    from . import conversations as convs
    from .mail_attachments import save_attachments

    drawings = [item for item in (mail.get("attachments") or []) if attachment_is_drawing(item)]
    saved: list[dict[str, Any]] = []
    ids = [str(item.get("attachment_id") or "") for item in drawings if item.get("attachment_id")]
    if ids:
        try:
            result = save_attachments(
                session_id,
                email_id=str(mail.get("id") or ""),
                attachment_ids=ids,
            )
            saved = list(result.get("attachments") or [])
        except Exception:
            saved = drawings
    else:
        saved = drawings
    focus = None
    for item in saved:
        path = str(item.get("local_path") or "")
        name = str(item.get("local_name") or item.get("filename") or "")
        if path or name:
            focus = {
                "filename": name or Path(path).name,
                "local_name": name or Path(path).name,
                "local_path": path,
                "mime": item.get("mime") or "",
                "drive_link": item.get("drive_link") or "",
            }
            break
    if not focus:
        return None
    local_path = str(focus.get("local_path") or "")
    if local_path:
        from .vision.gate import on_mail_drawing_saved

        on_mail_drawing_saved(local_path)
    return convs.spawn_drawing(focus)


def _rfq_for_conversation(conversation_id: str, mail_id: str = "") -> jobs.Rfq | None:
    rows = jobs.list_rfqs()
    for row in rows:
        if conversation_id and row.get("conversation_id") == conversation_id:
            return row
    if mail_id:
        for row in rows:
            if row.get("mail_id") == mail_id:
                return row
    return None


def _rfq_gate_pendings(session_id: str, rfq_id: str) -> list[dict[str, Any]]:
    ident = str(rfq_id or "")
    if not ident:
        return []
    out: list[dict[str, Any]] = []
    for item in db.list_pending(session_id):
        if item.get("kind") not in {"email_send", "calendar_create"}:
            continue
        payload = item.get("payload") or {}
        if str(payload.get("rfq_id") or "") == ident:
            out.append(item)
    return out


def supersede_hold_pendings(session_id: str, rfq_id: str) -> None:
    """Drop stacked Shall I gates from a prior reason of the same RFQ."""
    for item in _rfq_gate_pendings(session_id, rfq_id):
        db.set_pending_status(item["id"], "rejected")


def mark_rfq_idle_if_gates_cleared(session_id: str, rfq_id: str) -> None:
    """After the last hold/deadline is declined, stop treating the RFQ as waiting."""
    ident = str(rfq_id or "")
    if not ident or _rfq_gate_pendings(session_id, ident):
        return
    row = jobs.get_rfq(ident)
    if row and row.get("status") == "pending":
        jobs.update_rfq(ident, status="reasoned")


def _queue_hold(
    session_id: str,
    record: jobs.Rfq,
    reply: str,
    deadline: str,
    who: str,
) -> list[str]:
    from .connectors import email as email_conn

    supersede_hold_pendings(session_id, str(record.get("id") or ""))
    to_addr = _reply_address(session_id, record.get("mail_id") or "", who)
    subject = _reply_subject(record)
    mail = email_conn.get_email(record.get("mail_id") or "") if record.get("mail_id") else None
    source_id = str((mail or {}).get("id") or record.get("mail_id") or "")
    thread_id = str((mail or {}).get("thread_id") or "")
    hold = db.add_pending(
        f"rfq-hold-{record['id']}-{uuid.uuid4().hex[:6]}",
        session_id,
        "email_send",
        f"Send holding reply: {subject}",
        f"To {to_addr}",
        {
            "to": to_addr,
            "subject": subject,
            "body": reply,
            "source_id": source_id,
            "thread_id": thread_id,
            "rfq_id": record["id"],
            "attachment_paths": [],
        },
    )
    end_at = _deadline_end(deadline)
    cal = db.add_pending(
        f"rfq-cal-{record['id']}-{uuid.uuid4().hex[:6]}",
        session_id,
        "calendar_create",
        f"Add quote deadline: {_title_from_extract(record.get('extract') or {}) or 'RFQ'}",
        deadline,
        {
            "title": f"Quote deadline — {_title_from_extract(record.get('extract') or {}) or 'drawing RFQ'}",
            "start_at": deadline,
            "end_at": end_at,
            "location": "",
            "notes": "Suggested quote deadline from Jarvis RFQ reasoner. Confirm before it is saved.",
            "rfq_id": record["id"],
        },
    )
    return [hold["id"], cal["id"]]


def _reply_address(session_id: str, mail_id: str, who: str) -> str:
    from .connectors import email as email_conn

    if mail_id:
        mail = email_conn.get_email(mail_id)
        if mail and mail.get("sender"):
            return str(mail["sender"])
    if who:
        rows = email_conn.search_emails(query=f"from:{who}", limit=1)
        if rows and rows[0].get("sender"):
            return str(rows[0]["sender"])
    data = get_set(session_id)
    person = data.get("person") or {}
    if who and str(person.get("first") or "").lower() == who.lower():
        return str(person.get("email") or person.get("sender") or who)
    if who:
        return f"{who} <{who.lower()}@customer.example>"
    return "customer@example.com"


def _reply_subject(record: jobs.Rfq) -> str:
    from .connectors import email as email_conn

    mail = email_conn.get_email(record.get("mail_id") or "") if record.get("mail_id") else None
    subject = str((mail or {}).get("subject") or "").strip()
    if subject:
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        return subject
    title = _title_from_extract(record.get("extract") or {}) or "drawing RFQ"
    return f"Re: {title} — holding"


def _deadline_end(start_iso: str) -> str:
    try:
        start = datetime.fromisoformat(start_iso)
    except ValueError:
        start = datetime.now(_tz()) + timedelta(days=3)
    return (start + timedelta(minutes=30)).isoformat()


def _holding_reply(
    who: str,
    catch: str,
    deadline: str,
    similar: list[jobs.Job],
    extract: dict[str, Any],
) -> str:
    prefs = db.get_preferences()
    name = who or "there"
    try:
        stamp = datetime.fromisoformat(deadline).strftime("%a %d %b %Y %H:%M %Z")
    except ValueError:
        stamp = deadline
    lines = [
        f"Hi {name},",
        "",
        "Thank you for the drawing. I have the sheet in focus.",
        catch,
    ]
    if similar:
        job = similar[0]
        lines.append(
            f"Closest job on file: {job.get('part_name') or job.get('id')} "
            f"in {job.get('material') or 'the same material'}."
        )
    else:
        lines.append("I do not have a similar job in the library yet, but I still have the sheet.")
    lines.append(
        f"Holding a quote until the unreadable items are confirmed. "
        f"Suggested deadline (Asia/Kolkata, a suggestion only): {stamp}."
    )
    lines.append("")
    lines.append("I will not invent missing sizes.")
    sign = str(prefs.get("sign_off") or "").strip()
    if sign:
        lines.append("")
        lines.append(sign)
    return "\n".join(lines)


def _build_catch(extract: dict[str, Any], similar: list[jobs.Job], grounding: str) -> str:
    unread = [str(item) for item in (extract.get("unreadable") or []) if item]
    bits: list[str] = []
    if not (grounding or "").strip():
        bits.append("I could not see the sheet clearly, so I will not invent geometry.")
    if unread:
        listed = ", ".join(unread[:3])
        bits.append(f"{listed} — I will not invent a number.")
    if extract.get("material"):
        bits.append(f"Material reads {extract['material']}.")
    if similar:
        job = similar[0]
        notes = str(job.get("geometry_notes") or "")
        hold = "soft-jaw" if "soft-jaw" in notes.lower() or "soft jaw" in notes.lower() else "the recorded holding"
        bits.append(
            f"Similar to {job.get('part_name') or 'a library job'} "
            f"({hold}; {job.get('machine') or 'turning'})."
        )
    else:
        bits.append("No similar job in the library.")
    od = extract.get("od") or extract.get("diameter")
    length = extract.get("length")
    visible = []
    if od is not None:
        visible.append(f"OD {od}")
    if length is not None:
        visible.append(f"length {length}")
    if visible:
        bits.append("Visible sizes: " + " and ".join(visible) + ".")
    if not bits:
        bits.append("The drawing is in focus; I will only use visible sizes.")
    return " ".join(bits)


def _extract_from_grounding(grounding: str) -> dict[str, Any]:
    text = grounding or ""
    out: dict[str, Any] = {
        "material": "",
        "od": None,
        "length": None,
        "bore": None,
        "units": "mm",
        "unreadable": [],
        "geometry_notes": "",
        "title": "",
    }
    if not text.strip():
        out["unreadable"] = ["sheet not seen"]
        return out
    mat = _MATERIAL.search(text)
    if mat:
        out["material"] = mat.group(1).replace(" ", "") if " " not in mat.group(1).strip()[:3] else mat.group(0).strip()
        if re.search(r"18crnimo7-6", mat.group(0), re.I):
            out["material"] = "18CrNiMo7-6"
        elif re.search(r"\ben8\b", mat.group(0), re.I):
            out["material"] = "EN8"
    else:
        labeled = _MATERIAL_LABEL.search(text)
        if labeled:
            out["material"] = labeled.group(1).strip().rstrip(".")
    title = re.search(r"title block:\s*([^.]{3,80})", text, re.I)
    if title:
        out["title"] = _clean_part_title(title.group(1))
    notes: list[str] = []
    if re.search(r"soft-?jaw", text, re.I):
        notes.append("soft-jaw hold")
    if re.search(r"\bface\b", text, re.I):
        notes.append("face")
    if re.search(r"\bbore\b", text, re.I):
        notes.append("bore")
    if re.search(r"\bod\b|outer dia", text, re.I):
        notes.append("OD")
    out["geometry_notes"] = " ".join(notes)
    unread: list[str] = []
    for sent in _sentences(text):
        flagged = bool(_UNREADABLE.search(sent))
        low = sent.lower()
        if flagged:
            if re.search(r"\bbore\b|\bid\b", low):
                unread.append("bore diameter")
            if re.search(r"toleranc", low):
                unread.append("OD tolerance")
            if re.search(r"\blength\b|\boal\b", low) and "visible" not in low:
                unread.append("length")
            if re.search(r"\b(?:od|o\.d\.|outer\s+dia)", low) and "toleranc" not in low and "visible" not in low:
                if "unreadable" in low or "illegible" in low:
                    unread.append("OD")
            continue
        od_hit = _OD.search(sent) or (_OD_MARK.search(sent) if re.search(r"\bod\b|outer", low) else None)
        if od_hit and out["od"] is None:
            out["od"] = _as_float(od_hit.group(1))
            if len(od_hit.groups()) > 1 and od_hit.group(2) and od_hit.group(2).lower().startswith("in"):
                out["units"] = "inch"
        len_hit = _LENGTH.search(sent)
        if len_hit and out["length"] is None:
            out["length"] = _as_float(len_hit.group(1))
        bore_hit = _BORE.search(sent)
        if bore_hit and out["bore"] is None:
            out["bore"] = _as_float(bore_hit.group(1))
    # Deduplicate unreadable labels while preserving order.
    seen: set[str] = set()
    clean: list[str] = []
    for item in unread:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(item)
    if re.search(r"toleranc", text, re.I) and _UNREADABLE.search(text) and "OD tolerance" not in clean:
        if re.search(r"toleranc.{0,40}(missing|unreadable)| (missing|unreadable).{0,40}toleranc", text, re.I):
            clean.append("OD tolerance")
    if re.search(r"bore.{0,40}unreadable|unreadable.{0,20}bore", text, re.I) and "bore diameter" not in clean:
        clean.append("bore diameter")
    out["unreadable"] = clean
    if "bore diameter" in {item.lower() for item in clean}:
        out["bore"] = None
    if "OD" in clean:
        out["od"] = None
    return out


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _gemini_extract(grounding: str) -> dict[str, Any] | None:
    if not (settings.gemini_api_key or "").strip():
        return None
    if not (grounding or "").strip():
        return None
    prompt = (
        "Engineering drawing grounding follows. Return JSON only with keys: "
        "catch (string), material (string), od (number or null), length (number or null), "
        "bore (number or null), unreadable (string array), geometry_notes (string), "
        "title (string), units (mm or inch). "
        "Use only numbers that appear in the grounding. If a size is unreadable or a "
        "tolerance is missing, list it in unreadable and set that size to null. Never invent."
    )
    try:
        from .gemini_client import chat

        response = chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": grounding[:2000]},
            ],
            format_json=True,
            timeout=45,
            options={"temperature": 0.1, "num_predict": 400},
        )
    except Exception:
        return None
    blob = str(response.get("content") or "").strip()
    data = _parse_json(blob)
    if not data:
        return None
    return data


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


def _merge_visible(base: dict[str, Any], extra: dict[str, Any], grounding: str) -> dict[str, Any]:
    merged = dict(base)
    if extra.get("material") and not merged.get("material"):
        merged["material"] = str(extra["material"]).strip()
    if extra.get("title") and not merged.get("title"):
        merged["title"] = str(extra["title"]).strip()
    if extra.get("geometry_notes"):
        merged["geometry_notes"] = str(extra.get("geometry_notes") or merged.get("geometry_notes") or "")
    if extra.get("units") in {"mm", "inch"}:
        merged["units"] = extra["units"]
    extra_unread = [str(item) for item in (extra.get("unreadable") or []) if item]
    unread = list(merged.get("unreadable") or [])
    for item in extra_unread:
        if item not in unread:
            unread.append(item)
    merged["unreadable"] = unread
    for key in ("od", "length", "bore"):
        candidate = extra.get(key)
        number = _as_float(candidate)
        if number is None:
            continue
        if not _number_in_text(number, grounding):
            continue
        if merged.get(key) is None:
            merged[key] = number
    if extra.get("catch") and not merged.get("catch"):
        merged["catch"] = str(extra["catch"])
    return merged


def _number_in_text(value: float, text: str) -> bool:
    if not text:
        return False
    as_int = str(int(value)) if float(value).is_integer() else ""
    as_raw = str(value)
    compact = re.sub(r"\s+", "", text)
    if as_int and as_int in compact:
        return True
    return as_raw in compact


def _extract_for_cnc(
    session_id: str,
    conversation_id: str,
    extract: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, jobs.Rfq | None]:
    if isinstance(extract, dict) and extract:
        rfq_row = _rfq_for_conversation(conversation_id) if conversation_id else None
        ids = (rfq_row or {}).get("similar_job_ids") or []
        job = jobs.get_job(str(ids[0])) if ids else None
        return extract, job, rfq_row
    row = None
    if conversation_id:
        row = db.get_conversation(conversation_id)
    if not row and session_id:
        row = db.get_conversation_by_session(session_id)
    data = get_set(session_id)
    rfq_id = str((data.get("rfq") or {}).get("id") or "")
    rfq_row = jobs.get_rfq(rfq_id) if rfq_id else None
    if not rfq_row and row:
        rfq_row = _rfq_for_conversation(str(row.get("id") or ""))
    if not rfq_row:
        for item in jobs.list_rfqs():
            if item.get("status") in {"reasoned", "pending"}:
                rfq_row = item
                break
    payload = dict((rfq_row or {}).get("extract") or {})
    if row:
        focus = dict(row.get("focus") or {})
        if focus.get("extract") and isinstance(focus["extract"], dict):
            if not payload.get("od") and not payload.get("length"):
                payload = {**focus["extract"], **payload}
        grounding = str(focus.get("grounding") or "")
        if grounding and not payload.get("od") and not payload.get("length"):
            parsed = _extract_from_grounding(grounding)
            payload = {**parsed, **payload}
    job = None
    ids = (rfq_row or {}).get("similar_job_ids") or []
    if ids:
        job = jobs.get_job(str(ids[0]))
    return payload, job, rfq_row


def _draft_nc_path(rfq_id: str, session_id: str) -> Path:
    folder = (settings.exports_dir / "cnc").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stem = (rfq_id or session_id or "draft").replace("/", "-")[:24] or "draft"
    return folder / f"draft-{stem}.nc"
