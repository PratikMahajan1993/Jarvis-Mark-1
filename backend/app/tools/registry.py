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
from ..familiarity import get_set, note_tool, speak_for_tool
from . import documents


def _briefing_payload() -> dict[str, Any]:
    from ..briefing import build_briefing

    return build_briefing()


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


def _drive_file_line(session_id: str, link: str = "", title: str = "") -> str:
    if link:
        return link
    if title:
        return title
    drive = (get_set(session_id).get("drive") or {})
    return (drive.get("link") or drive.get("title") or "").strip()


def _ok(
    data: Any,
    scene: dict[str, Any] | None = None,
    pending: dict[str, Any] | None = None,
    speak: str | None = None,
) -> dict[str, Any]:
    return {"ok": True, "data": data, "scene": scene, "pending": pending, "speak": speak}


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
    return _ok(payload, scene=payload["scene"])


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
    **_: Any,
) -> dict[str, Any]:
    prefs = db.get_preferences()
    if prefs.get("sign_off") and prefs["sign_off"] not in body:
        body = f"{body.rstrip()}\n\n{prefs['sign_off']}"
    draft = email_conn.create_draft(to, subject, body)
    if in_reply_to:
        email_conn.mark_read(in_reply_to)
        db.add_memory(session_id, "last_email", in_reply_to)
    db.add_memory(session_id, "last_draft", draft["id"])
    scene = {
        "title": "Draft ready",
        "subtitle": subject,
        "widgets": [
            {"type": "kpi", "label": "To", "value": to},
            {"type": "markdown", "title": "Draft", "text": f"**{subject}**\n\n{body}"},
            {"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"},
        ],
    }
    pending = db.add_pending(
        f"send-{draft['id']}",
        session_id,
        "email_send",
        f"Send: {subject}",
        f"To {to}",
        {"to": to, "subject": subject, "body": body, "source_id": in_reply_to},
    )
    return _ok(draft, scene=scene, pending=pending)


def _send_email(
    session_id: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    **_: Any,
) -> dict[str, Any]:
    pending = db.add_pending(
        f"send-{db.utc_now()}",
        session_id,
        "email_send",
        f"Send: {subject}",
        f"To {to}",
        {"to": to, "subject": subject, "body": body, "source_id": in_reply_to},
    )
    return _ok({"queued": True}, pending=pending)


def _list_calendar(session_id: str, days: int = 2, **_: Any) -> dict[str, Any]:
    events = calendar_conn.list_events(days=days)
    scene = {
        "title": "Schedule",
        "subtitle": f"Next {days} day(s)",
        "widgets": [
            {"type": "kpi", "label": "Events", "value": len(events)},
            {
                "type": "timeline",
                "title": "Upcoming",
                "items": [
                    {
                        "time": event["start_at"][11:16] if len(event["start_at"]) > 16 else event["start_at"],
                        "title": event["title"],
                        "detail": event.get("location") or event.get("notes") or "",
                    }
                    for event in events
                ],
            },
        ],
    }
    return _ok(events, scene=scene)


def _create_calendar_event(
    session_id: str,
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
    notes: str = "",
    **_: Any,
) -> dict[str, Any]:
    pending = db.add_pending(
        f"cal-{title[:12]}-{db.utc_now()}",
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
    )
    scene = {
        "title": "Event draft",
        "subtitle": title,
        "widgets": [
            {"type": "kpi", "label": "Starts", "value": start_at[11:16] if len(start_at) > 16 else start_at},
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
        pending = db.add_pending(
            f"gem-{item['id']}",
            session_id,
            "handoff_gemini",
            "Send this file to Gemini",
            item["name"],
            {"inbox_id": item["id"], "steps": "Extract the useful facts from this file.", "reply_format": DEFAULT_GEMINI_REPLY},
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
    hits = search_conn.search_web(query)
    db.add_memory(session_id, "last_research", query)
    citations = "\n".join(f"- [{hit['title']}]({hit['url']}) — {hit['snippet']}" for hit in hits)
    scene = {
        "title": "Research",
        "subtitle": query,
        "widgets": [
            {"type": "kpi", "label": "Sources", "value": len(hits)},
            {"type": "markdown", "title": "Cited briefing", "text": citations or "No sources found."},
        ],
    }
    return _ok(hits, scene=scene)


def _read_email(session_id: str, email_id: str = "", query: str = "", **_: Any) -> dict[str, Any]:
    mail = email_conn.get_email(email_id) if email_id else None
    if not mail and query:
        rows = email_conn.search_emails(query=query, limit=1)
        mail = rows[0] if rows else None
    if not mail:
        scene = {
            "title": "No mail",
            "widgets": [{"type": "markdown", "text": "I do not have that message."}],
        }
        return _ok({"empty": True}, scene=scene, speak="I do not have that mail.")
    name = (mail["sender"] or "").split("<")[0].strip()
    scene = {
        "title": name.split()[0] if name else "Mail",
        "subtitle": mail["subject"],
        "widgets": [
            {"type": "kpi", "label": "From", "value": name},
            {"type": "markdown", "title": mail["subject"], "text": mail["body"]},
        ],
    }
    return _ok(mail, scene=scene)


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
    path = ""
    title = ""
    if artifact_id:
        item = db.get_artifact(artifact_id)
        if item:
            path, title = item.get("path") or "", item.get("name") or ""
    if not path and inbox_id:
        item = db.get_inbox_file(inbox_id)
        if item:
            path, title = item.get("path") or "", item.get("name") or ""
    if not path:
        artifact = (get_set(session_id).get("artifact") or {})
        if artifact.get("id"):
            item = db.get_artifact(str(artifact["id"]))
            if item:
                path, title = item.get("path") or "", item.get("name") or ""
    if not path:
        files = db.list_inbox_files(1)
        if files and files[0].get("path"):
            path, title = files[0]["path"], files[0]["name"]
    if not path:
        scene = {"title": "Nothing to upload", "widgets": [{"type": "quote", "text": "Make a file or drop one first.", "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak="I do not have a file to put on Drive.")
    uploaded = drive_conn.upload_file(path, title)
    scene = {
        "title": uploaded.get("title") or "Drive",
        "subtitle": uploaded.get("link") or "",
        "widgets": [
            {"type": "kpi", "label": "Drive", "value": uploaded.get("name") or title},
            {"type": "markdown", "text": uploaded.get("link") or ""},
        ],
    }
    return _ok(uploaded, scene=scene)


def _drive_find(session_id: str, title: str = "", **_: Any) -> dict[str, Any]:
    if not drive_conn.live():
        return _ok({"empty": True}, scene={"title": "Drive is not connected", "widgets": []}, speak="Drive is not connected.")
    query = title or (get_set(session_id).get("drive") or {}).get("title") or ""
    rows = drive_conn.find_by_title(query) if query else []
    if not rows:
        return _ok({"empty": True}, scene={"title": "Not on Drive", "widgets": []}, speak="I could not find that on Drive.")
    if len(rows) > 1 and query:
        names = ", ".join(row["name"] for row in rows[:3])
        return _ok(
            {"matches": rows},
            scene={"title": "Say which file", "widgets": [{"type": "quote", "text": names, "cite": "Drive"}]},
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
    file_line = _drive_file_line(session_id, file_link, file_title)
    if not file_line:
        artifact = get_set(session_id).get("artifact") or {}
        file_line = str(artifact.get("title") or artifact.get("name") or "").strip()
    needs_file = bool(re.search(r"\b(pdf|image|scan|sheet|xlsx|file|drive|photo|picture)\b", (steps or "").lower()))
    if needs_file and not file_line:
        speak = "I need a Drive link or the exact file title first."
        scene = {"title": "Say that again", "widgets": [{"type": "quote", "text": speak, "cite": "Jarvis"}]}
        return _ok({"empty": True}, scene=scene, speak=speak)
    body = gemini_body(file_line, steps or "Follow the spoken ask.", reply_format)
    to_addr = settings.gemini_task_to or settings.google_account
    subject = "Task for Gemini"
    pending = db.add_pending(
        f"gem-task-{db.utc_now()}",
        session_id,
        "email_send",
        "Send: Task for Gemini",
        f"To {to_addr}",
        {"to": to_addr, "subject": subject, "body": body, "source_id": "", "watch": True},
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


HANDLERS.update(
    {
        "get_briefing": _get_briefing,
        "search_emails": _search_emails,
        "draft_email": _draft_email,
        "send_email": _send_email,
        "list_calendar": _list_calendar,
        "create_calendar_event": _create_calendar_event,
        "create_spreadsheet": _create_spreadsheet,
        "create_document": _create_document,
        "create_pdf": _create_pdf,
        "review_inbox": _review_inbox,
        "research": _research,
        "read_email": _read_email,
        "show_artifact": _show_artifact,
        "drive_upload": _drive_upload,
        "drive_find": _drive_find,
        "task_for_gemini": _task_for_gemini,
        "open_artifact": _open_artifact,
        "remember": _remember,
        "update_preferences": _update_preferences,
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
            "name": "list_calendar",
            "description": "List upcoming calendar events.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "How many days ahead"}},
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
            "description": "Search the web and return cited sources.",
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
]
