from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .. import db
from ..connectors import calendar as calendar_conn
from ..connectors import drive as drive_conn
from ..connectors import email as email_conn
from ..connectors import search as search_conn
from ..config import settings
from ..familiarity import get_set, note_tool, speak_calendar, speak_for_tool
from ..hermes.hitl import request_human_approval
from . import documents


def _queue_pending(
    session_id: str,
    kind: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    *,
    action_id: str | None = None,
    tool_name: str = "",
) -> dict[str, Any]:
    return request_human_approval(
        session_id=session_id,
        kind=kind,
        title=title,
        summary=summary,
        payload=payload,
        action_id=action_id,
        tool_name=tool_name,
    )


def _briefing_payload() -> dict[str, Any]:
    from ..briefing import gather_briefing_facts

    return gather_briefing_facts()


DEFAULT_GEMINI_REPLY = "Short facts. If there are numbers, include a small table."


def gemini_body(file_line: str, steps: str, reply_format: str = "") -> str:
    numbered = steps.strip()
    if numbered and not re.match(r"^\s*\d+[).]", numbered):
        lines = [line.strip(" -") for line in re.split(r"[\n;]+", numbered) if line.strip()]
        numbered = "\n".join(f"{index}) {line}" for index, line in enumerate(lines, start=1)) or "1) Follow the spoken ask."
    return (
        f"File:\n{file_line.strip() or 'None — compose from the instructions below.'}\n\n"
        f"Do this:\n{numbered}\n\n"
        f"Reply like this:\n{(reply_format or DEFAULT_GEMINI_REPLY).strip()}"
    )


def _open_path(path: str) -> bool:
    target = Path(path) if path else None
    if not target or not target.is_file():
        return False
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except OSError:
        return False


def _local_file(session_id: str, artifact_id: str = "", inbox_id: str = "") -> tuple[str, str]:
    if artifact_id:
        item = db.get_artifact(artifact_id)
        if item and item.get("path"):
            return item["path"], item.get("name") or ""
    if inbox_id:
        item = db.get_inbox_file(inbox_id)
        if item and item.get("path"):
            return item["path"], item.get("name") or ""
    artifact = get_set(session_id).get("artifact") or {}
    if artifact.get("id"):
        item = db.get_artifact(str(artifact["id"]))
        if item and item.get("path"):
            return item["path"], item.get("name") or artifact.get("title") or ""
    files = db.list_inbox_files(1)
    if files and files[0].get("path"):
        return files[0]["path"], files[0].get("name") or ""
    return "", ""


def _guess_file_title(steps: str, given: str = "") -> str:
    if str(given or "").strip():
        return str(given).strip()
    text = steps or ""
    match = re.search(
        r"\b(?:the\s+)?([A-Za-z][A-Za-z'-]+)\s+(?:spread\s*)?sheet\b"
        r"|\b(?:the\s+)?([A-Za-z][A-Za-z'-]+)\s+(?:pdf|xlsx|file|workbook|quotation|quote)\b",
        text,
        re.I,
    )
    if match:
        word = (match.group(1) or match.group(2) or "").strip()
        if word.lower() not in {"this", "that", "the", "a", "an", "my", "our"}:
            return word
    return ""


def _ensure_drive_file(session_id: str, link: str = "", title: str = "") -> tuple[str, str]:
    """Return (drive_url_or_empty, error_speak). Uploads a local file when needed."""
    from ..familiarity import remember_drive

    if str(link or "").startswith("http"):
        return str(link).strip(), ""
    drive = get_set(session_id).get("drive") or {}
    if str(drive.get("link") or "").startswith("http"):
        return str(drive["link"]).strip(), ""
    query = (title or drive.get("title") or drive.get("name") or "").strip()
    if not query:
        artifact = get_set(session_id).get("artifact") or {}
        query = str(artifact.get("title") or artifact.get("name") or "").strip()
    path, name = _local_file(session_id)
    if not query and not path:
        return "", ""
    if not drive_conn.live():
        return "", "Drive is not connected."
    if query:
        try:
            rows = drive_conn.find_by_title(query)
        except Exception:
            rows = []
        if rows and rows[0].get("link") and len({row.get("name") for row in rows}) == 1:
            remember_drive(session_id, rows[0])
            return str(rows[0]["link"]), ""
        if len(rows) > 1 and not path:
            return "", "Two files could match. Say the exact title."
    if not path:
        return "", ""
    try:
        uploaded = drive_conn.upload_file(path, name or query)
    except Exception:
        return "", "Drive did not take the file."
    remember_drive(session_id, uploaded)
    return str(uploaded.get("link") or ""), ""


def _ok(
    data: Any,
    scene: dict[str, Any] | None = None,
    pending: dict[str, Any] | None = None,
    speak: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    mail_id: str | None = None,
    critical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "data": data, "scene": scene, "pending": pending, "speak": speak}
    if attachments is not None:
        out["attachments"] = attachments
    if mail_id:
        out["mail_id"] = mail_id
    if critical is not None:
        out["critical"] = critical
    return out


HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {}


def execute_tool(name: str, args: dict[str, Any], session_id: str) -> dict[str, Any]:
    from ..metrics import new_mission_id, record_mission_step

    mission_id = new_mission_id()
    handler = HANDLERS.get(name)
    if not handler:
        db.add_audit(session_id, name, f"Unknown tool {name}", "error")
        record_mission_step(
            session_id=session_id,
            mission_id=mission_id,
            step=0,
            role="tool",
            detail=f"unknown:{name}",
            status="error",
        )
        if name.startswith("quote_"):
            unknown_result = {"ok": False, "error": f"Unknown tool: {name}"}
            try:
                from ..quote_run_log import record as quote_record

                quote_record(
                    kind="tool",
                    session_id=session_id,
                    fields={"name": name, "args": args, "result": unknown_result},
                )
            except Exception:
                pass
            return unknown_result
        return {"ok": False, "error": f"Unknown tool: {name}"}
    try:
        record_mission_step(
            session_id=session_id,
            mission_id=mission_id,
            step=0,
            role="tool",
            detail=f"{name} {str(args)[:400]}",
            status="ok",
        )
        result = handler(session_id=session_id, **args)
        db.add_audit(session_id, name, str(result.get("data", result))[:400], "ok")
        note_tool(session_id, name, result)
        if not result.get("speak"):
            result["speak"] = speak_for_tool(name, result, session_id)
        record_mission_step(
            session_id=session_id,
            mission_id=mission_id,
            step=1,
            role="result",
            detail=str(result.get("data", result))[:800],
            status="ok" if result.get("ok", True) else "error",
        )
        if name.startswith("quote_"):
            try:
                from ..quote_run_log import record as quote_record

                quote_record(
                    kind="tool",
                    session_id=session_id,
                    fields={"name": name, "args": args, "result": result},
                )
            except Exception:
                pass
        return result
    except TypeError as exc:
        db.add_audit(session_id, name, str(exc), "error")
        record_mission_step(
            session_id=session_id,
            mission_id=mission_id,
            step=1,
            role="result",
            detail=str(exc)[:800],
            status="error",
        )
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        db.add_audit(session_id, name, str(exc), "error")
        record_mission_step(
            session_id=session_id,
            mission_id=mission_id,
            step=1,
            role="result",
            detail=str(exc)[:800],
            status="error",
        )
        return {"ok": False, "error": str(exc)}


def _get_briefing(session_id: str, **_: Any) -> dict[str, Any]:
    payload = _briefing_payload()
    return _ok(payload, scene=None, speak=None)


def _search_emails(session_id: str, query: str = "", unread_only: bool = False, **_: Any) -> dict[str, Any]:
    rows = email_conn.search_emails(query=query, unread_only=unread_only)
    scene = {
        "title": "Inbox",
        "subtitle": query or "Recent mail",
        "widgets": [
            {
                "type": "kpi",
                "label": "Matches",
                "value": len(rows),
                "hint": "Unread only" if unread_only else "Inbox search",
            },
            {
                "type": "table",
                "title": "Messages",
                "columns": ["From", "Subject", "When"],
                "rows": [[row["sender"], row["subject"], row["created_at"][:16]] for row in rows],
            },
        ],
    }
    return _ok(rows, scene=scene)


def _draft_email(
    session_id: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    attachment_paths: list[str] | None = None,
    **_: Any,
) -> dict[str, Any]:
    prefs = db.get_preferences()
    if prefs.get("sign_off") and prefs["sign_off"] not in body:
        body = f"{body.rstrip()}\n\n{prefs['sign_off']}"
    draft = email_conn.create_draft(to, subject, body)
    source = email_conn.get_email(in_reply_to) if in_reply_to else None
    thread_id = (source.get("thread_id") if source else "") or ""
    if in_reply_to:
        email_conn.mark_read(in_reply_to)
        db.add_memory(session_id, "last_email", in_reply_to)
    db.add_memory(session_id, "last_draft", draft["id"])
    widgets: list[dict[str, Any]] = [
        {"type": "kpi", "label": "To", "value": to},
        {"type": "markdown", "title": "Draft", "text": f"**{subject}**\n\n{body}"},
    ]
    paths = [path for path in (attachment_paths or []) if path]
    if paths:
        widgets.append({"type": "markdown", "title": "Attachments", "text": ", ".join(Path(path).name for path in paths)})
    widgets.append({"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"})
    scene = {
        "title": "Draft ready",
        "subtitle": subject,
        "widgets": widgets,
    }
    pending = _queue_pending(
        session_id,
        "email_send",
        f"Send: {subject}",
        f"To {to}",
        {
            "to": to,
            "subject": subject,
            "body": body,
            "source_id": in_reply_to,
            "thread_id": thread_id,
            "attachment_paths": paths,
        },
        action_id=f"send-{draft['id']}",
        tool_name="draft_email",
    )
    return _ok(draft, scene=scene, pending=pending)


def _forward_email(
    session_id: str,
    to: str,
    email_id: str = "",
    query: str = "",
    note: str = "",
    body: str = "",
    **_: Any,
) -> dict[str, Any]:
    mail = email_conn.get_email(email_id) if email_id else None
    if not mail and query:
        rows = email_conn.search_emails(query=query, limit=1)
        mail = rows[0] if rows else None
    if not mail:
        scene = {
            "title": "No mail",
            "widgets": [{"type": "markdown", "text": "I do not have that message to forward."}],
        }
        return _ok({"empty": True}, scene=scene, speak="I do not have that mail.")
    forward_note = note or body
    subject = mail.get("subject") or ""
    if not subject.lower().startswith("fwd:"):
        subject = f"Fwd: {subject}".strip()
    pending = _queue_pending(
        session_id,
        "email_forward",
        f"Forward: {subject}",
        f"To {to}",
        {
            "to": to,
            "source_id": mail.get("id") or "",
            "subject": subject,
            "note": forward_note,
        },
        action_id=f"fwd-{mail.get('id')}-{db.utc_now()}",
        tool_name="forward_email",
    )
    scene = {
        "title": "Forward ready",
        "subtitle": subject,
        "widgets": [
            {"type": "kpi", "label": "To", "value": to},
            {"type": "markdown", "title": "Note", "text": forward_note or "(no note)"},
            {"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"},
        ],
    }
    return _ok({"to": to, "source_id": mail.get("id"), "subject": subject}, scene=scene, pending=pending)


def _send_email(
    session_id: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    **_: Any,
) -> dict[str, Any]:
    pending = _queue_pending(
        session_id,
        "email_send",
        f"Send: {subject}",
        f"To {to}",
        {"to": to, "subject": subject, "body": body, "source_id": in_reply_to},
        action_id=f"send-{db.utc_now()}",
        tool_name="send_email",
    )
    return _ok({"queued": True}, pending=pending)


def _list_calendar(session_id: str, days: int = 7, span: str = "", **_: Any) -> dict[str, Any]:
    events = calendar_conn.list_events(days=days, span=span)
    next_up = calendar_conn.upcoming(days=days, span=span)
    note = calendar_conn.calendar_note(empty=not events)
    widgets: list[dict[str, Any]] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for event in events:
        bucket = calendar_conn.day_bucket(event.get("start_at") or "") or "Upcoming"
        if bucket not in buckets:
            buckets[bucket] = []
            order.append(bucket)
        buckets[bucket].append(
            {
                "time": calendar_conn.when_label(event.get("start_at") or ""),
                "title": event.get("title") or "(No title)",
                "detail": event.get("location") or event.get("notes") or "",
            }
        )
    titles = {"today": "Today", "tomorrow": "Tomorrow"}
    for bucket in order:
        heading = titles.get(bucket)
        if not heading:
            first = next((event for event in events if calendar_conn.day_bucket(event.get("start_at") or "") == bucket), None)
            heading = calendar_conn.day_heading((first or {}).get("start_at") or "") if first else bucket
        widgets.append(
            {
                "type": "timeline",
                "title": heading,
                "items": buckets[bucket],
            }
        )
    if note:
        widgets.append({"type": "markdown", "text": note})
    if span == "today":
        subtitle = "Today"
    elif span == "tomorrow":
        subtitle = "Tomorrow"
    else:
        subtitle = "This week"
    scene = {
        "title": "Schedule",
        "subtitle": subtitle,
        "widgets": widgets,
    }
    speak_note = ""
    if not events and note:
        if "Reconnect Google" in note or "not connected" in note.lower():
            speak_note = "Calendar is not connected. Reconnect Google in preferences."
        elif "primary calendar" in note.lower():
            speak_note = "Primary calendar is empty. Allow all calendars in preferences if the day lives elsewhere."
    speak = speak_calendar(events, upcoming=next_up, span=span, note=speak_note)
    return _ok(events, scene=scene, speak=speak)


def _create_calendar_event(
    session_id: str,
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
    notes: str = "",
    **_: Any,
) -> dict[str, Any]:
    pending = _queue_pending(
        session_id,
        "calendar_create",
        f"Add event: {title}",
        f"{start_at} → {end_at}",
        {
            "title": title,
            "start_at": start_at,
            "end_at": end_at,
            "location": location,
            "notes": notes,
        },
        action_id=f"cal-{title[:12]}-{db.utc_now()}",
        tool_name="create_calendar_event",
    )
    scene = {
        "title": "Event draft",
        "subtitle": title,
        "widgets": [
            {"type": "kpi", "label": "Starts", "value": calendar_conn.clock(start_at)},
            {"type": "markdown", "text": f"**{title}**\n\n{location}\n\n{notes}"},
        ],
    }
    return _ok({"queued": True}, scene=scene, pending=pending)


def _create_spreadsheet(
    session_id: str,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    chart: bool = False,
    **_: Any,
) -> dict[str, Any]:
    artifact = documents.create_spreadsheet(title, columns, rows, chart=chart)
    db.add_memory(session_id, "last_spreadsheet", artifact["name"])
    scene = {
        "title": title or "Spreadsheet",
        "subtitle": artifact["name"],
        "widgets": [
            {"type": "kpi", "label": "Rows", "value": len(rows)},
            {"type": "table", "columns": columns, "rows": rows[:12]},
            {"type": "markdown", "text": f"Saved as **{artifact['name']}** in the artifact tray."},
        ],
    }
    return _ok(artifact, scene=scene)


def _create_document(
    session_id: str,
    title: str,
    body: str,
    bullets: list[str] | None = None,
    **_: Any,
) -> dict[str, Any]:
    artifact = documents.create_document(title, body, bullets)
    db.add_memory(session_id, "last_document", artifact["name"])
    scene = {
        "title": title,
        "subtitle": "Word document",
        "widgets": [{"type": "markdown", "title": title, "text": body}],
    }
    return _ok(artifact, scene=scene)


def _create_pdf(session_id: str, title: str, body: str, **_: Any) -> dict[str, Any]:
    artifact = documents.create_pdf(title, body)
    db.add_memory(session_id, "last_pdf", artifact["name"])
    scene = {
        "title": title,
        "subtitle": "PDF brief",
        "widgets": [{"type": "markdown", "title": title, "text": body}],
    }
    return _ok(artifact, scene=scene)


def _review_inbox(session_id: str, name: str = "", **_: Any) -> dict[str, Any]:
    files = db.list_inbox_files(8)
    item = None
    if name:
        item = next((row for row in files if name.lower() in row["name"].lower()), None)
    item = item or (files[0] if files else None)
    if not item:
        scene = {
            "title": "Nothing dropped",
            "widgets": [{"type": "markdown", "text": "There is no file in the inbox yet."}],
        }
        return _ok({"empty": True}, scene=scene)
    text = (item.get("text") or "").strip()
    db.add_memory(session_id, "last_file", item["name"])
    if len(text) < 40:
        speak = "I cannot read that here. Shall I send it to Gemini?"
        pending = _queue_pending(
            session_id,
            "handoff_gemini",
            "Send this file to Gemini",
            item["name"],
            {"inbox_id": item["id"], "steps": "Extract the useful facts from this file.", "reply_format": DEFAULT_GEMINI_REPLY},
            action_id=f"gem-{item['id']}",
            tool_name="review_inbox",
        )
        scene = {
            "title": item["name"],
            "subtitle": "No readable text",
            "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}],
        }
        return _ok({"name": item["name"], "readable": False}, scene=scene, pending=pending, speak=speak)
    excerpt = text[:2500]
    db.add_memory(session_id, "last_file_excerpt", excerpt[:400])
    scene = {
        "title": item["name"],
        "subtitle": "Extracted text",
        "widgets": [
            {"type": "kpi", "label": "Characters", "value": len(text)},
            {"type": "markdown", "title": "What I can read", "text": excerpt},
        ],
    }
    return _ok({"name": item["name"], "readable": True, "chars": len(text)}, scene=scene)


def _research(session_id: str, query: str, **_: Any) -> dict[str, Any]:
    brief = search_conn.brief_research(query)
    topic = brief.get("query") or query
    db.add_memory(session_id, "last_research", topic)
    hits = brief.get("hits") or []
    speak = f"I opened {len(hits)} pages on {topic}." if hits else "I found nothing useful."
    scene = {
        "title": (topic[:1].upper() + topic[1:]) if topic else "Research",
        "subtitle": None,
        "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}],
    }
    return _ok(brief, scene=scene, speak=speak)


def _read_email(session_id: str, email_id: str = "", query: str = "", last: bool = False, **_: Any) -> dict[str, Any]:
    from ..mail_attachments import build_mail_scene, merge_attachment_status, remember_mail_context

    mail = email_conn.get_email(email_id) if email_id else None
    if not mail and query:
        hint = query.strip()
        rows: list[dict[str, Any]] = []
        if hint.lower().startswith("from:"):
            rows = email_conn.search_emails(query=hint, limit=5)
        elif re.fullmatch(r"[A-Za-z][A-Za-z'-]+", hint):
            rows = email_conn.search_emails(query=f"from:{hint}", limit=5) or email_conn.search_emails(query=hint, limit=5)
        else:
            rows = email_conn.search_emails(query=hint, limit=5)
        lowered = hint.lower().replace("from:", "").strip()
        for row in rows:
            sender = (row.get("sender") or "").lower()
            if lowered and lowered in sender:
                mail = row
                break
        if not mail and rows:
            mail = rows[0]
    if not mail and last and not (query or "").strip():
        rows = email_conn.search_emails(limit=1)
        mail = rows[0] if rows else None
    if not mail:
        scene = {
            "title": "No mail",
            "widgets": [{"type": "markdown", "text": "I do not have that message."}],
        }
        who = (query or "").replace("from:", "").strip()
        speak = f"I do not have mail from {who}." if who and " " not in who else "I do not have that mail."
        return _ok({"empty": True}, scene=scene, speak=speak)
    attachments = merge_attachment_status(session_id, mail)
    remember_mail_context(session_id, mail, attachments)
    payload = {
        **mail,
        "attachments": attachments,
    }
    scene = build_mail_scene(mail, attachments)
    return _ok(payload, scene=scene, mail_id=mail.get("id"), attachments=attachments)


def _save_mail_attachments(
    session_id: str,
    email_id: str = "",
    attachment_ids: list[str] | None = None,
    filenames: list[str] | None = None,
    query: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..mail_attachments import save_attachments

    result = save_attachments(
        session_id,
        email_id=email_id,
        attachment_ids=attachment_ids or None,
        filenames=filenames or None,
        query=query,
    )
    if not result.get("ok"):
        return _ok(result.get("data") or {"empty": True}, scene=result.get("scene"), speak=result.get("speak"))
    return _ok(
        result.get("data"),
        scene=result.get("scene"),
        speak=result.get("speak"),
        mail_id=result.get("mail_id"),
        attachments=result.get("attachments"),
    )


def _reply_with_attachments(
    session_id: str,
    email_id: str = "",
    attachment_ids: list[str] | None = None,
    filenames: list[str] | None = None,
    query: str = "",
    body: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..mail_attachments import draft_reply_with_attachments

    result = draft_reply_with_attachments(
        session_id,
        email_id=email_id,
        attachment_ids=attachment_ids or None,
        filenames=filenames or None,
        query=query,
        body=body,
    )
    if not result.get("ok"):
        return _ok(result.get("data") or {"empty": True}, scene=result.get("scene"), speak=result.get("speak"))
    return _ok(
        result.get("data"),
        scene=result.get("scene"),
        pending=result.get("pending"),
        speak=result.get("speak"),
        mail_id=result.get("mail_id"),
        attachments=result.get("attachments"),
    )


def _show_artifact(session_id: str, artifact_id: str = "", **_: Any) -> dict[str, Any]:
    item = db.get_artifact(artifact_id) if artifact_id else None
    if not item:
        scene = {
            "title": "Nothing to open",
            "widgets": [{"type": "markdown", "text": "I do not have a spreadsheet from this session yet."}],
        }
        return _ok({"empty": True}, scene=scene, speak="I do not have that spreadsheet yet.")
    title = item.get("name") or "Spreadsheet"
    opened = _open_path(item.get("path") or "")
    scene = {
        "title": title.split(".")[0],
        "subtitle": item["name"],
        "widgets": [
            {"type": "kpi", "label": "File", "value": item["kind"].upper()},
            {"type": "markdown", "text": f"**{item['name']}** is still in the tray."},
        ],
    }
    return _ok({**item, "title": title.split(".")[0], "opened": opened}, scene=scene)


def _drive_upload(session_id: str, artifact_id: str = "", inbox_id: str = "", **_: Any) -> dict[str, Any]:
    if not drive_conn.live():
        scene = {"title": "Drive is not connected", "widgets": [{"type": "quote", "text": "Connect Gmail in preferences first.", "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak="Drive is not connected.")
    path, title = _local_file(session_id, artifact_id, inbox_id)
    if not path:
        scene = {"title": "Nothing to upload", "widgets": [{"type": "quote", "text": "Make a file or drop one first.", "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak="I do not have a file to put on Drive.")
    existing = []
    if title:
        try:
            existing = drive_conn.find_by_title(title)
        except Exception:
            existing = []
    match = next((row for row in existing if (row.get("link") or "").startswith("http")), None)
    uploaded = match or drive_conn.upload_file(path, title)
    reused = bool(match)
    scene = {
        "title": uploaded.get("title") or "Drive",
        "subtitle": uploaded.get("link") or "",
        "widgets": [
            {"type": "kpi", "label": "Drive", "value": uploaded.get("name") or title},
            {"type": "markdown", "text": uploaded.get("link") or ""},
        ],
    }
    return _ok(uploaded, scene=scene, speak=f"The {uploaded.get('title') or title} is already on Drive." if reused else None)


def _drive_find(session_id: str, title: str = "", **_: Any) -> dict[str, Any]:
    if not drive_conn.live():
        return _ok({"empty": True}, scene={"title": "Drive is not connected", "widgets": []}, speak="Drive is not connected.")
    query = title or (get_set(session_id).get("drive") or {}).get("title") or ""
    rows = drive_conn.find_by_title(query) if query else []
    if not rows:
        return _ok({"empty": True}, scene={"title": "Not on Drive", "widgets": []}, speak="I could not find that on Drive.")
    unique = {str(row.get("name") or "") for row in rows}
    if len(rows) > 1 and query and len(unique) > 1:
        listed = ", ".join(row["name"] for row in rows[:3])
        return _ok(
            {"matches": rows},
            scene={"title": "Say which file", "widgets": [{"type": "quote", "text": listed, "cite": "Drive"}]},
            speak="Two files could match. Say the exact title.",
        )
    found = rows[0]
    scene = {
        "title": found.get("title") or found.get("name") or "Drive",
        "subtitle": found.get("link") or "",
        "widgets": [{"type": "markdown", "text": found.get("link") or found.get("name") or ""}],
    }
    return _ok(found, scene=scene)


def _task_for_gemini(
    session_id: str,
    steps: str = "",
    reply_format: str = "",
    file_link: str = "",
    file_title: str = "",
    **_: Any,
) -> dict[str, Any]:
    file_line, error = _ensure_drive_file(session_id, file_link, _guess_file_title(steps, file_title))
    if error:
        scene = {"title": "Say that again", "widgets": [{"type": "quote", "text": error, "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak=error)
    needs_file = bool(re.search(r"\b(pdf|image|scan|sheet|xlsx|file|drive|photo|picture|spreadsheet)\b", (steps or "").lower()))
    if not file_line:
        artifact = get_set(session_id).get("artifact") or {}
        file_line = str(artifact.get("title") or artifact.get("name") or "").strip()
    if needs_file and not str(file_line).startswith("http"):
        speak = "I need that file on Drive first. Make it, drop it, or say the exact title."
        scene = {"title": "Say that again", "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak=speak)
    body = gemini_body(file_line, steps or "Follow the spoken ask.", reply_format)
    to_addr = settings.gemini_task_to or settings.google_account
    subject = "Task for Gemini"
    pending = _queue_pending(
        session_id,
        "email_send",
        "Send: Task for Gemini",
        f"To {to_addr}",
        {"to": to_addr, "subject": subject, "body": body, "source_id": "", "watch": True},
        action_id=f"gem-task-{db.utc_now()}",
        tool_name="task_for_gemini",
    )
    scene = {
        "title": "Task for Gemini",
        "subtitle": "Shall I send it?",
        "widgets": [{"type": "markdown", "title": "Envelope", "text": body}],
    }
    return _ok({"to": to_addr, "subject": subject, "body": body}, scene=scene, pending=pending)


def _open_artifact(session_id: str, artifact_id: str = "", **_: Any) -> dict[str, Any]:
    item = db.get_artifact(artifact_id) if artifact_id else None
    if not item:
        artifact = get_set(session_id).get("artifact") or {}
        if artifact.get("id"):
            item = db.get_artifact(str(artifact["id"]))
    if not item:
        return _ok({"empty": True}, scene={"title": "Nothing to open", "widgets": []}, speak="I do not have that file yet.")
    opened = _open_path(item.get("path") or "")
    scene = {
        "title": item.get("name") or "File",
        "widgets": [{"type": "markdown", "text": "Opened on your machine." if opened else "I could not open that file."}],
    }
    return _ok({**item, "opened": opened}, scene=scene)


def _remember(session_id: str, key: str, value: str, **_: Any) -> dict[str, Any]:
    db.add_memory(session_id, key, value)
    from ..memory.mirror import mirror_fact

    mirror_fact(f"{key}: {value}", namespace="profile", key=f"pref:{key}", meta={"session_id": session_id})
    return _ok({"key": key, "value": value})


def _memory_search(session_id: str, query: str, namespace: str = "", limit: int = 8, **_: Any) -> dict[str, Any]:
    from ..memory import search

    hits = search(query, namespace=namespace or None, limit=limit)
    scene = {
        "title": "Local memory",
        "subtitle": query[:80],
        "widgets": [
            {
                "type": "markdown",
                "text": "\n\n".join(
                    f"**{h['namespace']}/{h['key']}** ({h['score']})\n{h['text'][:400]}" for h in hits
                )
                or "No matches.",
            }
        ],
    }
    return _ok({"hits": hits}, scene=scene)


def _memory_upsert(
    session_id: str,
    text: str,
    namespace: str = "corpus",
    key: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..memory import upsert

    doc = upsert(namespace=namespace, key=key, text=text, meta={"session_id": session_id})
    return _ok(doc)


def _memory_forget(
    session_id: str,
    namespace: str = "",
    key: str = "",
    doc_id: str = "",
    wipe_namespace: bool = False,
    **_: Any,
) -> dict[str, Any]:
    from ..memory import forget

    if wipe_namespace and namespace:
        pending = _queue_pending(
            session_id,
            "memory_wipe",
            f"Wipe memory namespace: {namespace}",
            f"Deletes all local memory docs in `{namespace}`.",
            {"namespace": namespace, "wipe_namespace": True},
            tool_name="memory_forget",
        )
        return _ok({"queued": True}, pending=pending, speak="Authorize to wipe that memory namespace.")
    result = forget(namespace=namespace or None, key=key or None, doc_id=doc_id or None, wipe_namespace=False)
    return _ok(result)


def _memory_summary(session_id: str, **_: Any) -> dict[str, Any]:
    from ..memory import get_summary

    summary = get_summary()
    lines = [f"- {row['namespace']}/{row['key']}: {row['text'][:160]}" for row in summary.get("recent") or []]
    scene = {
        "title": "What I know (local)",
        "subtitle": summary.get("engine") or "memory",
        "widgets": [{"type": "markdown", "text": "\n".join(lines) or "Nothing stored yet."}],
    }
    return _ok(summary, scene=scene)


def _memory_reindex_mail(session_id: str, limit: int = 20, full: bool = False, **_: Any) -> dict[str, Any]:
    from ..memory.ingest import reindex_all_mail_in_db, reindex_recent_mail

    if full:
        return _ok(reindex_all_mail_in_db(batch_size=50))
    return _ok(reindex_recent_mail(limit=limit))


def _sync_mailbox(session_id: str, days: int = 100, force: bool = False, **_: Any) -> dict[str, Any]:
    from ..mail_sync import kick_bulk

    result = kick_bulk(days=days, force=force)
    started = result.get("started")
    speak = "Mailbox sync is running in the background." if started else "Mailbox sync is already up to date or running."
    return _ok(result, speak=speak)


def _update_preferences(session_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        "display_name",
        "assistant_name",
        "persona",
        "verbosity",
        "timezone",
        "job_context",
        "sign_off",
        "voice_enabled",
        "email_enabled",
        "calendar_enabled",
        "files_enabled",
        "research_enabled",
        "hud_density",
    }
    patch = {key: value for key, value in fields.items() if key in allowed and value is not None}
    prefs = db.update_preferences(patch)
    return _ok(prefs)


def _reason_rfq(
    session_id: str,
    conversation_id: str = "",
    mail_id: str = "",
    message: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..rfq import glance_critical, intake

    result = intake(
        mail_id=mail_id,
        conversation_id=conversation_id,
        message=message,
        session_id=session_id,
    )
    speak = str(result.get("speak") or "The drawing RFQ is on the board.")
    rfq = result.get("rfq") or {}
    pending_items = db.list_pending(session_id)
    hold = next((item for item in pending_items if item.get("kind") == "email_send"), None)
    scene = {
        "title": "Drawing RFQ",
        "subtitle": (rfq.get("catch") or "Reasoned")[:80],
        "widgets": [
            {"type": "quote", "text": speak, "cite": "Jarvis"},
            {"type": "markdown", "title": "Holding reply", "text": rfq.get("pending_reply") or ""},
        ],
    }
    return _ok(
        result,
        scene=scene,
        pending=hold,
        speak=speak,
        critical=glance_critical(),
    )


def _cnc_suggest(
    session_id: str,
    conversation_id: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..rfq import request_program

    result = request_program(session_id=session_id, conversation_id=conversation_id)
    return _ok(
        result.get("result") or result,
        scene=result.get("scene"),
        pending=result.get("pending"),
        speak=result.get("speak"),
    )


def _shop_result(result: dict[str, Any]) -> dict[str, Any]:
    return _ok(
        result.get("data") if "data" in result else result,
        scene=result.get("scene"),
        pending=result.get("pending"),
        speak=result.get("speak"),
    )


def _bind_shop_sheet(session_id: str, query: str = "", sheet_name: str = "", **_: Any) -> dict[str, Any]:
    from ..shop_log import bind

    return _shop_result(bind(query, sheet_name=sheet_name, session_id=session_id))


def _ensure_shop_sheet(session_id: str, title: str = "", **_: Any) -> dict[str, Any]:
    from ..shop_log import ensure

    return _shop_result(ensure(title=title, session_id=session_id))


def _read_shop_sheet(session_id: str, sheet_name: str = "", **_: Any) -> dict[str, Any]:
    from ..shop_log import read_sheet

    return _shop_result(read_sheet(sheet_name=sheet_name, session_id=session_id))


def _update_shop_sheet(
    session_id: str,
    message: str = "",
    updates: list[dict[str, Any]] | None = None,
    sheet_name: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..shop_log import queue_write

    return _shop_result(
        queue_write(session_id, message=message, updates=updates, sheet_name=sheet_name)
    )


def _quote_analyze_drawing(session_id: str, path: str = "", prompt: str = "", **_: Any) -> dict[str, Any]:
    from ..quote import analyze_drawing_vision

    result = analyze_drawing_vision(path, prompt=prompt, session_id=session_id)
    scene = {
        "title": "Drawing vision",
        "subtitle": result.get("name") or path,
        "widgets": [{"type": "markdown", "text": result.get("summary") or result.get("error") or ""}],
    }
    return _ok(result, scene=scene, speak=(result.get("summary") or "")[:280])


def _quote_build(
    session_id: str,
    part_name: str = "Component",
    material: str = "",
    vision_summary: str = "",
    customer: str = "",
    line_items: list[dict[str, Any]] | None = None,
    scope: str = "",
    rm_source: str = "",
    rm_source_note: str = "",
    rm_price: Any = "",
    machine: str = "",
    machining_rate: Any = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import build_quote

    result = build_quote(
        session_id=session_id,
        part_name=part_name,
        material=material,
        vision_summary=vision_summary,
        line_items=line_items,
        customer=customer,
        scope=scope,
        rm_source=rm_source,
        rm_source_note=rm_source_note,
        rm_price=rm_price,
        machine=machine,
        machining_rate=machining_rate,
    )
    if not result.get("ok"):
        speak = str(result.get("message") or "Labour-only or with material?")
        out = _ok(result, speak=speak)
        out["ok"] = False
        return out
    artifact = result.get("artifact") or {}
    scene = {
        "title": "Quotation sheet",
        "subtitle": artifact.get("name") or part_name,
        "widgets": [
            {"type": "table", "columns": result.get("columns") or [], "rows": (result.get("rows") or [])[:12]},
            {"type": "markdown", "text": f"Saved as **{artifact.get('name') or 'quote'}**. Edit locally or ask for changes."},
        ],
    }
    return _ok(result, scene=scene)


def _quote_pdf(session_id: str, part_name: str = "", **_: Any) -> dict[str, Any]:
    from ..quote import quote_to_pdf

    result = quote_to_pdf(session_id=session_id, part_name=part_name)
    return _ok(result)


def _quote_verify(session_id: str, **_: Any) -> dict[str, Any]:
    from ..quote import verify_quote

    result = verify_quote(session_id=session_id)
    scene = result.get("scene") or {}
    speak = "Quote proof passed." if result.get("passed") else f"{result.get('failed_count', 0)} check(s) failed."
    if result.get("stop"):
        speak = f"Quote proof stopped: {result.get('failed_count')} failures — fix before send."
    return _ok(result, scene=scene, speak=speak)


def _quote_playbook_note(
    session_id: str,
    what_went_wrong: str = "",
    layer: str = "process",
    change: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import append_playbook_note

    result = append_playbook_note(
        what_went_wrong=what_went_wrong,
        layer=layer,
        change=change,
    )
    return _ok(result)


def _quote_find_drawing(
    session_id: str,
    part_hint: str = "",
    drawing_path: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import find_drawing_for_quote

    result = find_drawing_for_quote(
        session_id=session_id,
        part_hint=part_hint,
        drawing_path=drawing_path,
    )
    if result.get("ok"):
        speak = f"Drawing is {result.get('filename') or 'on disk'}."
    else:
        speak = str(result.get("message") or "Which drawing — inbox attachment, file on desk, or photo?")
    out = _ok(result, speak=speak)
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_request_rm_quote(
    session_id: str,
    material: str = "",
    supplier: str = "",
    supplier_email: str = "",
    customer: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import request_rm_quote

    result = request_rm_quote(
        session_id,
        material=material,
        supplier=supplier,
        supplier_email=supplier_email,
        customer=customer,
    )
    if result.get("ok"):
        speak = f"Raw-material request queued for {supplier or 'the supplier'}. It is not sent."
    else:
        speak = str(result.get("message") or "Need a supplier email before requesting a quote.")
    out = _ok(result, speak=speak, pending=result.get("pending"))
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_record_rm_quote(
    session_id: str,
    price_inr: Any = "",
    is_estimate: bool = False,
    notes: str = "",
    quote_date: str = "",
    request_id: str = "",
    material: str = "",
    supplier: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import record_rm_quote

    result = record_rm_quote(
        session_id,
        price_inr=price_inr,
        is_estimate=bool(is_estimate),
        notes=notes,
        quote_date=quote_date,
        request_id=request_id,
        material=material,
        supplier=supplier,
    )
    if result.get("ok"):
        speak = "Raw-material quote recorded."
    else:
        speak = str(result.get("message") or "Need the quoted price.")
    out = _ok(result, speak=speak)
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_add_operation(session_id: str, **kwargs: Any) -> dict[str, Any]:
    from ..quote_ops import add_quote_operation

    result = add_quote_operation(session_id, **kwargs)
    out = _ok(result, speak="Operation added." if result.get("ok") else str(result.get("message") or "Need an operation."))
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_update_operation(session_id: str, operation_id: str = "", **kwargs: Any) -> dict[str, Any]:
    from ..quote_ops import update_quote_operation

    result = update_quote_operation(session_id, operation_id, **kwargs)
    out = _ok(result, speak="Operation updated." if result.get("ok") else str(result.get("message") or "Could not update."))
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_delete_operation(session_id: str, operation_id: str = "", **_: Any) -> dict[str, Any]:
    from ..quote_ops import delete_quote_operation

    result = delete_quote_operation(session_id, operation_id)
    return _ok(result, speak="Operation removed.")


def _quote_reorder_operations(session_id: str, ordered_ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
    from ..quote_ops import reorder_quote_operations

    result = reorder_quote_operations(session_id, list(ordered_ids or []))
    out = _ok(result, speak="Operations reordered." if result.get("ok") else str(result.get("message") or "Could not reorder."))
    out["ok"] = bool(result.get("ok"))
    return out


def _mhr_list_rates(session_id: str, **_: Any) -> dict[str, Any]:
    from ..quote_ops import list_mhr_rates

    return _ok(list_mhr_rates(), speak="Machine-hour rates.")


def _mhr_attest_rate(
    session_id: str,
    rate_id: str = "",
    machine_type: str = "",
    attested_by: str = "",
    floor_inr: Any = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote_ops import attest_mhr_rate

    result = attest_mhr_rate(
        rate_id=rate_id,
        machine_type=machine_type,
        attested_by=attested_by,
        floor_inr=floor_inr,
    )
    out = _ok(result, speak="Rate attested." if result.get("ok") else str(result.get("message") or "Could not attest."))
    out["ok"] = bool(result.get("ok"))
    return out


def _quote_send(
    session_id: str,
    to: str,
    subject: str = "",
    body: str = "",
    pdf_path: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..quote import queue_quote_send, quote_refuse_if_pdf_drift, verify_quote

    verify_result = verify_quote(session_id=session_id, stage="send", to=to, subject=subject)
    if verify_result.get("stop"):
        return {
            "ok": False,
            "error": "Quote proof blocked — fix BLOCKER failures before send.",
            "data": verify_result,
            "scene": verify_result.get("scene"),
            "speak": "Quote proof blocked — fix blockers before queuing send.",
        }

    if not pdf_path:
        pdf_id = ""
        for mem in db.list_memories(session_id):
            if mem.get("key") == "last_quote_pdf":
                pdf_id = str(mem.get("value") or "")
        art = db.get_artifact(pdf_id) if pdf_id else None
        if art:
            pdf_path = art.get("path") or ""
    drift = quote_refuse_if_pdf_drift(session_id, pdf_path, verify_result)
    if drift:
        return {
            "ok": False,
            "error": "Quote proof blocked — PDF changed since verify.",
            "data": drift,
            "scene": drift.get("scene"),
            "speak": "Quote proof blocked — the PDF no longer matches the verified file.",
        }
    subj = subject or "Quotation"
    body_text = body or "Please find the quotation attached."
    result = queue_quote_send(
        session_id=session_id,
        to=to,
        subject=subj,
        body=body_text,
        pdf_path=pdf_path,
        verify_snapshot=verify_result,
    )
    pending = result.get("pending")
    fail_n = int(verify_result.get("failed_count") or 0)
    warn = f" ({fail_n} proof warning(s))" if fail_n else ""
    scene = {
        "title": "Quote ready to send",
        "subtitle": subj,
        "widgets": [{"type": "markdown", "text": f"To **{to}**{warn}\n\n{body_text}"}],
    }
    return _ok(result, scene=scene, pending=pending, speak="Authorize to send the quote PDF.")


def _office_refresh_tasks(session_id: str, **_: Any) -> dict[str, Any]:
    from ..office_day import refresh_suggested_tasks

    result = refresh_suggested_tasks(session_id)
    return _ok(result)


def _office_list_tasks(session_id: str, **_: Any) -> dict[str, Any]:
    from ..office_day import list_tasks

    return _ok({"tasks": list_tasks()})


def _get_weather(session_id: str, city: str = "Pune", **_: Any) -> dict[str, Any]:
    from ..office_day import fetch_weather

    weather = fetch_weather(city=city)
    return _ok(weather, speak=weather.get("speak") or "")


def _browser_record_evidence(
    session_id: str,
    url: str,
    title: str = "",
    notes: str = "",
    screenshot_b64: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..browser_evidence import record_evidence

    result = record_evidence(
        session_id=session_id,
        url=url,
        title=title,
        notes=notes,
        screenshot_b64=screenshot_b64,
    )
    return _ok(result)


def _browser_queue_action(
    session_id: str,
    title: str,
    summary: str,
    url: str,
    evidence_id: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ..browser_evidence import queue_browser_action

    result = queue_browser_action(
        session_id=session_id,
        title=title,
        summary=summary,
        url=url,
        evidence_id=evidence_id,
    )
    return _ok(result, pending=result.get("pending"))


HANDLERS.update(
    {
        "get_briefing": _get_briefing,
        "search_emails": _search_emails,
        "draft_email": _draft_email,
        "send_email": _send_email,
        "forward_email": _forward_email,
        "list_calendar": _list_calendar,
        "create_calendar_event": _create_calendar_event,
        "create_spreadsheet": _create_spreadsheet,
        "create_document": _create_document,
        "create_pdf": _create_pdf,
        "review_inbox": _review_inbox,
        "research": _research,
        "read_email": _read_email,
        "save_mail_attachments": _save_mail_attachments,
        "reply_with_attachments": _reply_with_attachments,
        "show_artifact": _show_artifact,
        "drive_upload": _drive_upload,
        "drive_find": _drive_find,
        "task_for_gemini": _task_for_gemini,
        "open_artifact": _open_artifact,
        "remember": _remember,
        "memory_search": _memory_search,
        "memory_upsert": _memory_upsert,
        "memory_forget": _memory_forget,
        "memory_summary": _memory_summary,
        "memory_reindex_mail": _memory_reindex_mail,
        "sync_mailbox": _sync_mailbox,
        "update_preferences": _update_preferences,
        "reason_rfq": _reason_rfq,
        "cnc_suggest": _cnc_suggest,
        "bind_shop_sheet": _bind_shop_sheet,
        "ensure_shop_sheet": _ensure_shop_sheet,
        "read_shop_sheet": _read_shop_sheet,
        "update_shop_sheet": _update_shop_sheet,
        "quote_analyze_drawing": _quote_analyze_drawing,
        "quote_build": _quote_build,
        "quote_pdf": _quote_pdf,
        "quote_verify": _quote_verify,
        "quote_playbook_note": _quote_playbook_note,
        "quote_find_drawing": _quote_find_drawing,
        "quote_request_rm_quote": _quote_request_rm_quote,
        "quote_record_rm_quote": _quote_record_rm_quote,
        "quote_add_operation": _quote_add_operation,
        "quote_update_operation": _quote_update_operation,
        "quote_delete_operation": _quote_delete_operation,
        "quote_reorder_operations": _quote_reorder_operations,
        "mhr_list_rates": _mhr_list_rates,
        "mhr_attest_rate": _mhr_attest_rate,
        "quote_send": _quote_send,
        "office_refresh_tasks": _office_refresh_tasks,
        "office_list_tasks": _office_list_tasks,
        "get_weather": _get_weather,
        "browser_record_evidence": _browser_record_evidence,
        "browser_queue_action": _browser_queue_action,
    }
)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_briefing",
            "description": "Get today's work briefing: unread mail, calendar, and open follow-ups.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search the inbox. Use for unread mail, a sender, or a subject.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "unread_only": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Draft an email. Sending still requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "in_reply_to": {"type": "string", "description": "Optional email id being answered"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Queue an email send. Never sends immediately; user must confirm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "in_reply_to": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forward_email",
            "description": "Forward a message to someone. Never sends immediately; user must confirm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "email_id": {"type": "string"},
                    "query": {"type": "string"},
                    "note": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar",
            "description": "List upcoming calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days ahead"},
                    "span": {"type": "string", "description": "today, tomorrow, or empty for the next couple of days"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Draft a calendar event. User must confirm before it is saved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_at": {"type": "string", "description": "ISO datetime"},
                    "end_at": {"type": "string", "description": "ISO datetime"},
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "start_at", "end_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_spreadsheet",
            "description": "Create an Excel workbook in the exports tray.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "rows": {"type": "array", "items": {"type": "array"}},
                    "chart": {"type": "boolean"},
                },
                "required": ["title", "columns", "rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_document",
            "description": "Create a Word document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pdf",
            "description": "Create a PDF brief.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_inbox",
            "description": "Read the latest dropped file and show extracted text. Use after a PDF, Word, or spreadsheet is uploaded.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Optional file name to review"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read one mail and put the body on the board. Speak a short summary, not the full letter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string"},
                    "query": {"type": "string"},
                    "last": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_mail_attachments",
            "description": "Save selected Gmail attachments locally under exports and upload to Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string"},
                    "attachment_ids": {"type": "array", "items": {"type": "string"}},
                    "filenames": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string", "description": "Natural language file hint, e.g. piston PDF"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_with_attachments",
            "description": "Draft a reply with saved mail attachments. Sending still requires confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string"},
                    "attachment_ids": {"type": "array", "items": {"type": "string"}},
                    "filenames": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string"},
                    "body": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_artifact",
            "description": "Show an existing spreadsheet or file from this session. Do not create a new one.",
            "parameters": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research",
            "description": "Search the public web and read the pages. Use for prices, news, facts, or anything that needs the internet. Pass the topic as query, e.g. aluminium prices in India.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drive_upload",
            "description": "Upload the last local file to Google Drive and remember the link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "inbox_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drive_find",
            "description": "Find a Google Drive file by exact or close title.",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_for_gemini",
            "description": "Draft a Task for Gemini email with File, Do this, and Reply like this. Needs confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {"type": "string"},
                    "reply_format": {"type": "string"},
                    "file_link": {"type": "string"},
                    "file_title": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_artifact",
            "description": "Open a local spreadsheet, Word file, or PDF on this machine.",
            "parameters": {
                "type": "object",
                "properties": {"artifact_id": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a short fact for this session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search local dual-write memory / RAG corpus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "namespace": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_upsert",
            "description": "Upsert a durable local memory document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "namespace": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_forget",
            "description": "Forget a local memory doc. Broad namespace wipe queues HITL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "key": {"type": "string"},
                    "doc_id": {"type": "string"},
                    "wipe_namespace": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_summary",
            "description": "Summarize what Jarvis knows in the local memory store.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_reindex_mail",
            "description": "Reindex recent mail into the local RAG corpus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "full": {"type": "boolean", "description": "Reindex all gmail-* rows in SQLite."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_mailbox",
            "description": "Background bulk Gmail sync (default last 100 days) into local SQLite with spam filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer"},
                    "force": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_preferences",
            "description": "Update Jarvis preferences such as name, persona, or skill toggles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string"},
                    "assistant_name": {"type": "string"},
                    "persona": {"type": "string"},
                    "verbosity": {"type": "string"},
                    "timezone": {"type": "string"},
                    "job_context": {"type": "string"},
                    "sign_off": {"type": "string"},
                    "voice_enabled": {"type": "boolean"},
                    "email_enabled": {"type": "boolean"},
                    "calendar_enabled": {"type": "boolean"},
                    "files_enabled": {"type": "boolean"},
                    "research_enabled": {"type": "boolean"},
                    "hud_density": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reason_rfq",
            "description": "Reason an inbound drawing RFQ: visible sizes only, similar jobs, holding reply. Never drafts CNC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                    "mail_id": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cnc_suggest",
            "description": "Draft a from-scratch CNC turning program from the open drawing extract. Never send to a machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bind_shop_sheet",
            "description": "Bind Tony's live shop log Google Sheet by URL or workbook name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "sheet_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_shop_sheet",
            "description": "Create the default Jarvis shop log spreadsheet if none is bound. Do not invent OEE numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_shop_sheet",
            "description": "Read the bound shop log Sheet and report real OEE only. Never invent a number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_shop_sheet",
            "description": "Queue a shop-log cell write behind Shall I. Do not claim it was saved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "updates": {"type": "array"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_build",
            "description": "Build a local quotation spreadsheet. Optional scope, RM source, machine, and MHR must come from the owner or tools — never invented.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_name": {"type": "string"},
                    "material": {"type": "string"},
                    "vision_summary": {"type": "string"},
                    "customer": {"type": "string"},
                    "scope": {
                        "type": "string",
                        "description": "labour or with_material — owner-confirmed only",
                    },
                    "rm_source": {"type": "string"},
                    "rm_source_note": {"type": "string"},
                    "rm_price": {
                        "type": "string",
                        "description": "Owner- or tool-confirmed raw material price — never invented",
                    },
                    "machine": {"type": "string"},
                    "machining_rate": {
                        "type": "string",
                        "description": "Must not be below demo minimum in mhr-demo.md when machine is listed there",
                    },
                    "line_items": {"type": "array"},
                },
                "required": ["part_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_verify",
            "description": "Deterministic quote proof checklist before send. Never invent numbers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_playbook_note",
            "description": "Append a dated correction to the quote playbook notes.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "what_went_wrong": {"type": "string"},
                    "layer": {"type": "string", "enum": ["process", "toolbox", "proof"]},
                    "change": {"type": "string"},
                },
                "required": ["what_went_wrong", "change"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_find_drawing",
            "description": "Resolve a drawing path for a quote. Stops at first hit: provided path → focus → named search → mail attachment save → ask.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "part_hint": {"type": "string", "description": "Part name or filename hint for named search"},
                    "drawing_path": {"type": "string", "description": "Absolute or relative path to a drawing file"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_request_rm_quote",
            "description": "Queue a raw-material quote request email for HITL Authorize. Does not send. Records the request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "material": {"type": "string"},
                    "supplier": {"type": "string"},
                    "supplier_email": {"type": "string"},
                    "customer": {"type": "string"},
                },
                "required": ["material", "supplier", "supplier_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_record_rm_quote",
            "description": "Record a received supplier RM quote or a labelled estimate. Never invent the price. Estimate notes must name historical transactions or market trend.",
            "parameters": {
                "type": "object",
                "properties": {
                    "price_inr": {"type": "string"},
                    "is_estimate": {"type": "boolean"},
                    "notes": {"type": "string"},
                    "quote_date": {"type": "string", "description": "ISO date of the quote or estimate basis"},
                    "request_id": {"type": "string"},
                    "material": {"type": "string"},
                    "supplier": {"type": "string"},
                },
                "required": ["price_inr", "quote_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote_send",
            "description": "Queue quote PDF email for HITL Authorize. Does not send. Refuses when proof stop=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "pdf_path": {"type": "string"},
                },
                "required": ["to"],
            },
        },
    },
]
