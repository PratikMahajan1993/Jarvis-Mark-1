from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from . import db
from .compose import reply_draft
from .config import settings
from .connectors import drive as drive_conn
from .connectors import email as email_conn
from .connectors import gmail as gmail_conn
from .familiarity import first_name, get_set, remember_artifact, remember_drive, remember_person, save_set


def _drawings_dir() -> Path:
    target = (settings.exports_dir / "drawings").resolve()
    target.mkdir(parents=True, exist_ok=True)
    exports = settings.exports_dir.resolve()
    if exports not in target.parents and target != exports:
        raise ValueError("Drawings folder must stay inside exports")
    return target


def safe_drawing_path(filename: str) -> Path:
    clean = Path(filename).name
    if not clean or clean in {".", ".."}:
        raise ValueError("Invalid file name")
    target = (_drawings_dir() / clean).resolve()
    drawings = _drawings_dir()
    exports = settings.exports_dir.resolve()
    if drawings not in target.parents and target != drawings and exports not in target.parents:
        raise ValueError("Exports must stay inside the workspace folder")
    return target


def empty_mail_context() -> dict[str, Any]:
    return {"email_id": "", "gmail_id": "", "subject": "", "sender": "", "attachments": []}


def get_mail_context(session_id: str) -> dict[str, Any]:
    data = get_set(session_id)
    ctx = data.get("mail_attachments") or empty_mail_context()
    if not isinstance(ctx.get("attachments"), list):
        ctx["attachments"] = []
    return ctx


def remember_mail_context(session_id: str, mail: dict[str, Any], attachments: list[dict[str, Any]]) -> None:
    data = get_set(session_id)
    data["mail_attachments"] = {
        "email_id": mail.get("id") or "",
        "gmail_id": mail.get("gmail_id") or "",
        "subject": mail.get("subject") or "",
        "sender": mail.get("sender") or "",
        "attachments": attachments,
    }
    if mail.get("id"):
        data["thread"] = {"id": mail["id"], "subject": mail.get("subject") or "", "sender": mail.get("sender") or ""}
    save_set(session_id, data)


def merge_attachment_status(session_id: str, mail: dict[str, Any]) -> list[dict[str, Any]]:
    ctx = get_mail_context(session_id)
    saved_map: dict[str, dict[str, Any]] = {}
    if ctx.get("email_id") == mail.get("id"):
        for item in ctx.get("attachments") or []:
            fname = str(item.get("filename") or "").lower()
            if fname:
                saved_map[fname] = item

    result: list[dict[str, Any]] = []
    for raw in mail.get("attachments") or []:
        att_id = raw.get("attachment_id") or ""
        filename = raw.get("filename") or "file"
        saved = saved_map.get(filename.lower()) or {}
        local_path = str(saved.get("local_path") or "")
        drive_link = str(saved.get("drive_link") or "")
        artifact_id = str(saved.get("artifact_id") or "")
        if local_path and drive_link:
            status = "both"
        elif local_path:
            status = "local"
        elif drive_link:
            status = "drive"
        else:
            status = "gmail"
        result.append(
            {
                "attachment_id": att_id,
                "filename": filename,
                "mime": raw.get("mime") or "",
                "size": int(raw.get("size") or 0),
                "readable": bool(raw.get("readable")),
                "cad": bool(raw.get("cad")),
                "status": status,
                "local_path": local_path or None,
                "local_name": Path(local_path).name if local_path else None,
                "drive_link": drive_link or None,
                "artifact_id": artifact_id or None,
            }
        )
    return result


def attachment_widget(email_id: str, attachments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "attachments",
        "title": "Attachments",
        "email_id": email_id,
        "items": attachments,
    }


def build_mail_scene(mail: dict[str, Any], attachments: list[dict[str, Any]], extra_widgets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from .tables import widgets_from_body

    name = (mail.get("sender") or "").split("<")[0].strip()
    widgets: list[dict[str, Any]] = [
        {"type": "kpi", "label": "From", "value": name},
        *widgets_from_body(mail.get("body") or "", mail.get("subject") or ""),
    ]
    if attachments:
        widgets.append(attachment_widget(mail.get("id") or "", attachments))
    if extra_widgets:
        widgets.extend(extra_widgets)
    return {
        "title": name.split()[0] if name else "Mail",
        "subtitle": mail.get("subject"),
        "widgets": widgets,
    }


def _skip_token(word: str) -> bool:
    return word.lower() in {
        "save",
        "download",
        "attach",
        "reply",
        "drawing",
        "drawings",
        "file",
        "files",
        "this",
        "that",
        "with",
        "the",
        "and",
        "pdf",
        "these",
        "those",
        "selected",
        "mail",
        "email",
    }


def match_attachments(
    message: str,
    attachments: list[dict[str, Any]],
    selected_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    text = (message or "").lower()
    if selected_ids:
        matched = [row for row in attachments if row.get("attachment_id") in selected_ids]
        if matched:
            return matched, None

    if re.search(r"\b(these|those|selected)\b", text):
        return [], "Which attachments? Tick them on the board, or name a file."

    tokens: list[str] = []
    for pattern in (
        r"\b(?:save|download)\s+(?:the\s+)?([A-Za-z0-9._-]+)",
        r"\b([A-Za-z0-9._-]+\.pdf)\b",
        r"\b(DPIS\d+)\b",
        r"\b(RFNW[-_]?\d+)\b",
    ):
        for match in re.finditer(pattern, message, re.I):
            for group in match.groups():
                if group:
                    tokens.append(group)

    if "piston" in text:
        tokens.append("piston")

    if not tokens:
        for word in re.findall(r"[A-Za-z0-9]{4,}", message):
            if not _skip_token(word):
                tokens.append(word)

    if not tokens:
        if len(attachments) == 1:
            return attachments[:1], None
        preview = ", ".join(str(row.get("filename") or "file") for row in attachments[:4])
        return [], f"Which file? {preview}"

    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in attachments:
        fname = (row.get("filename") or "").lower()
        for token in tokens:
            if token.lower() in fname and row.get("attachment_id") not in seen:
                hits.append(row)
                seen.add(str(row.get("attachment_id") or ""))
                break

    if not hits:
        if len(attachments) == 1:
            return attachments[:1], None
        return [], "I could not match that filename. Say which attachment."

    if len(hits) > 1:
        preview = ", ".join(str(row.get("filename") or "file") for row in hits[:4])
        return [], f"Several match — which one? {preview}"
    return hits, None


def _resolve_targets(
    attachments: list[dict[str, Any]],
    attachment_ids: list[str] | None,
    filenames: list[str] | None,
    query: str,
) -> tuple[list[dict[str, Any]], str | None]:
    if filenames:
        names = {name.lower() for name in filenames}
        matched = [row for row in attachments if (row.get("filename") or "").lower() in names]
        return (matched, None) if matched else ([], "No matching attachments.")
    if attachment_ids:
        id_set = set(attachment_ids)
        matched = [row for row in attachments if row.get("attachment_id") in id_set]
        if matched:
            return matched, None
        # Gmail attachment ids can change between fetches — fall back to any single id hint via query.
    if query:
        return match_attachments(query, attachments)
    return [], "Which attachment should I save?"


def save_one(
    session_id: str,
    mail: dict[str, Any],
    attachment: dict[str, Any],
    *,
    local: bool = True,
    drive: bool = True,
) -> dict[str, Any]:
    filename = attachment.get("filename") or "attachment.bin"
    att_id = attachment.get("attachment_id") or ""
    gmail_id = mail.get("gmail_id") or str(mail.get("id") or "").replace("gmail-", "", 1)
    item = dict(attachment)

    if local:
        if not gmail_id or not att_id:
            item["error"] = "Cannot download without Gmail."
        elif item.get("local_path"):
            item["status"] = item.get("status") or "local"
        else:
            try:
                blob = gmail_conn.download_attachment(gmail_id, att_id)
            except Exception as exc:
                item["error"] = str(exc)
                blob = b""
            if blob:
                path = safe_drawing_path(filename)
                path.write_bytes(blob)
                artifact = db.add_artifact(uuid.uuid4().hex[:12], "drawing", filename, str(path))
                remember_artifact(session_id, artifact, Path(filename).stem)
                item["local_path"] = str(path)
                item["local_name"] = path.name
                item["artifact_id"] = artifact["id"]
                item["status"] = "local"

    if drive:
        path = item.get("local_path") or ""
        if not path and local:
            item["drive_note"] = "Save locally first."
        elif not drive_conn.live():
            item["drive_note"] = "Drive is not connected."
        else:
            existing: list[dict[str, Any]] = []
            try:
                existing = drive_conn.find_by_title(filename)
            except Exception:
                existing = []
            match = next(
                (
                    row
                    for row in existing
                    if row.get("name") == filename or filename.lower() in str(row.get("name") or "").lower()
                ),
                None,
            )
            if match:
                uploaded = match
            else:
                try:
                    uploaded = drive_conn.upload_file(path, filename)
                except Exception:
                    item["drive_note"] = "Drive did not take the file."
                    uploaded = None
            if uploaded:
                remember_drive(session_id, uploaded)
                item["drive_link"] = uploaded.get("link") or ""
                item["status"] = "both" if item.get("local_path") else "drive"

    return item


def save_attachments(
    session_id: str,
    email_id: str = "",
    attachment_ids: list[str] | None = None,
    filenames: list[str] | None = None,
    query: str = "",
    *,
    local: bool = True,
    drive: bool = True,
) -> dict[str, Any]:
    mail = email_conn.get_email(email_id) if email_id else None
    if not mail:
        ctx = get_mail_context(session_id)
        mail = email_conn.get_email(ctx.get("email_id") or "")
    if not mail:
        return {"ok": False, "speak": "I do not have that mail open.", "attachments": [], "mail_id": None}

    all_atts = merge_attachment_status(session_id, mail)
    text = (query or "").lower()
    if "drive only" in text or "only drive" in text or "only to drive" in text:
        local, drive = False, True
    elif any(phrase in text for phrase in ("local only", "only local", "only here", "disk only")):
        local, drive = True, False

    targets, err = _resolve_targets(all_atts, attachment_ids, filenames, query)
    if err:
        return {
            "ok": False,
            "speak": err,
            "attachments": all_atts,
            "mail_id": mail.get("id"),
            "mail": mail,
            "scene": build_mail_scene(mail, all_atts),
        }

    updated = {str(row.get("filename") or "").lower(): dict(row) for row in all_atts}
    saved_names: list[str] = []
    drive_disconnected = False

    for att in targets:
        key = str(att.get("filename") or "").lower()
        result = save_one(session_id, mail, att, local=local, drive=drive)
        updated[key] = result
        if result.get("local_path") or result.get("drive_link"):
            saved_names.append(str(result.get("filename") or att.get("filename") or "file"))
        if result.get("drive_note") == "Drive is not connected.":
            drive_disconnected = True

    final_list = list(updated.values())
    remember_mail_context(session_id, mail, final_list)

    if not saved_names:
        speak = "I could not save those attachments."
    elif len(saved_names) == 1:
        label = Path(saved_names[0]).stem
        row = next((item for item in final_list if item.get("filename") == saved_names[0]), {})
        if drive_disconnected and row.get("local_path"):
            speak = f"{label} is on disk. Drive is not connected."
        elif row.get("status") == "both":
            speak = f"{label} is on disk and Drive."
        elif row.get("status") == "drive":
            speak = f"{label} is on Drive."
        else:
            speak = f"{label} is saved."
    else:
        speak = f"Saved {len(saved_names)} files."
        if drive_disconnected:
            speak += " Drive is not connected."

    scene = build_mail_scene(mail, final_list)
    return {
        "ok": True,
        "speak": speak,
        "scene": scene,
        "attachments": final_list,
        "mail_id": mail.get("id"),
        "data": {"saved": saved_names, "attachments": final_list},
    }


def save_marked_drawing(
    session_id: str,
    source_name: str,
    png_bytes: bytes,
) -> dict[str, Any]:
    stem = Path(source_name or "drawing").stem or "drawing"
    base = f"{stem}_marked"
    name = f"{base}.png"
    counter = 1
    while safe_drawing_path(name).exists():
        name = f"{base}_{counter}.png"
        counter += 1
    path = safe_drawing_path(name)
    path.write_bytes(png_bytes)
    artifact = db.add_artifact(uuid.uuid4().hex[:12], "drawing", name, str(path))
    remember_artifact(session_id, artifact, stem)

    drive_link = ""
    drive_disconnected = False
    drive_failed = False
    if drive_conn.live():
        try:
            uploaded = drive_conn.upload_file(str(path), name)
            if uploaded:
                remember_drive(session_id, uploaded)
                drive_link = uploaded.get("link") or ""
            else:
                drive_failed = True
        except Exception:
            drive_failed = True
    else:
        drive_disconnected = True

    label = Path(name).stem
    if drive_link:
        speak = f"{label} is on disk and Drive."
    elif drive_disconnected:
        speak = f"{label} is on disk. Drive is not connected."
    elif drive_failed:
        speak = f"{label} is on disk. Drive did not take the file."
    else:
        speak = f"{label} is saved."

    db.add_audit(session_id, "drawing_marked", f"Saved {name}", "ok")
    return {"ok": True, "speak": speak, "artifact": artifact, "drive_link": drive_link or None}


def draft_reply_with_attachments(
    session_id: str,
    email_id: str = "",
    attachment_ids: list[str] | None = None,
    filenames: list[str] | None = None,
    query: str = "",
    body: str = "",
) -> dict[str, Any]:
    mail = email_conn.get_email(email_id) if email_id else None
    if not mail:
        ctx = get_mail_context(session_id)
        mail = email_conn.get_email(ctx.get("email_id") or "")
    if not mail:
        return {"ok": False, "speak": "I do not have that mail open.", "attachments": [], "mail_id": None}

    all_atts = merge_attachment_status(session_id, mail)
    targets, err = _resolve_targets(all_atts, attachment_ids, filenames, query)
    if err:
        return {
            "ok": False,
            "speak": err,
            "attachments": all_atts,
            "mail_id": mail.get("id"),
            "scene": build_mail_scene(mail, all_atts),
        }

    paths: list[str] = []
    names: list[str] = []
    to_save: list[dict[str, Any]] = []
    for att in targets:
        if att.get("local_path"):
            paths.append(str(att["local_path"]))
            names.append(str(att.get("filename") or Path(att["local_path"]).name))
        else:
            to_save.append(att)

    if to_save:
        saved = save_attachments(
            session_id,
            mail.get("id") or "",
            filenames=[str(row.get("filename") or "") for row in to_save],
            local=True,
            drive=True,
        )
        all_atts = saved.get("attachments") or all_atts
        for att in to_save:
            fname = str(att.get("filename") or "").lower()
            row = next((item for item in all_atts if str(item.get("filename") or "").lower() == fname), None)
            if row and row.get("local_path"):
                paths.append(str(row["local_path"]))
                names.append(str(row.get("filename") or ""))

    if not paths:
        return {
            "ok": False,
            "speak": "I could not attach those files.",
            "attachments": all_atts,
            "mail_id": mail.get("id"),
            "scene": build_mail_scene(mail, all_atts),
        }

    prefs = db.get_preferences()
    draft_body = body or reply_draft(mail)
    if prefs.get("sign_off") and prefs["sign_off"] not in draft_body:
        draft_body = f"{draft_body.rstrip()}\n\n{prefs['sign_off']}"
    subject = mail.get("subject") or ""
    if not str(subject).lower().startswith("re:"):
        subject = f"Re: {subject}".strip()
    to_addr = mail.get("sender") or ""
    thread_id = mail.get("thread_id") or ""
    draft = email_conn.create_draft(to_addr, subject, draft_body)
    email_conn.mark_read(mail.get("id") or "")
    db.add_memory(session_id, "last_email", mail.get("id") or "")
    db.add_memory(session_id, "last_draft", draft["id"])
    remember_person(session_id, to_addr, mail.get("id"), subject)

    attach_line = ", ".join(names[:3])
    if len(names) > 3:
        attach_line += f" and {len(names) - 3} more"
    scene = {
        "title": "Draft ready",
        "subtitle": subject,
        "widgets": [
            {"type": "kpi", "label": "To", "value": first_name(to_addr) or to_addr},
            {"type": "markdown", "title": "Draft", "text": f"**{subject}**\n\n{draft_body}"},
            {"type": "markdown", "title": "Attachments", "text": attach_line},
            {"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"},
        ],
    }
    pending = db.add_pending(
        f"send-{draft['id']}",
        session_id,
        "email_send",
        f"Send: {subject}",
        f"To {to_addr} with {len(paths)} file(s)",
        {
            "to": to_addr,
            "subject": subject,
            "body": draft_body,
            "source_id": mail.get("id") or "",
            "thread_id": thread_id,
            "attachment_paths": paths,
            "attachment_names": names,
        },
    )
    speak = f"Draft for {first_name(to_addr) or 'them'} with {len(paths)} attachment(s) — shall I send it?"
    return {
        "ok": True,
        "speak": speak,
        "scene": scene,
        "attachments": all_atts,
        "mail_id": mail.get("id"),
        "pending": pending,
        "data": draft,
    }
