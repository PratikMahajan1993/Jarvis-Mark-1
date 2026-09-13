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
    handler = HANDLERS.get(name)
    if not handler:
        db.add_audit(session_id, name, f"Unknown tool {name}", "error")
        return {"ok": False, "error": f"Unknown tool: {name}"}
    try:
        result = handler(session_id=session_id, **args)
        db.add_audit(session_id, name, str(result.get("data", result))[:400], "ok")
        note_tool(session_id, name, result)
        if not result.get("speak"):
            result["speak"] = speak_for_tool(name, result, session_id)
        return result
    except TypeError as exc:
        db.add_audit(session_id, name, str(exc), "error")
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        db.add_audit(session_id, name, str(exc), "error")
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
    return _ok({"key": key, "value": value})


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
        "update_preferences": _update_preferences,
        "reason_rfq": _reason_rfq,
        "cnc_suggest": _cnc_suggest,
        "bind_shop_sheet": _bind_shop_sheet,
        "ensure_shop_sheet": _ensure_shop_sheet,
        "read_shop_sheet": _read_shop_sheet,
        "update_shop_sheet": _update_shop_sheet,
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
]
