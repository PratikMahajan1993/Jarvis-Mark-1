from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Any

from . import google_auth
from ..db import utc_now

_BODY_CAP = 12000
_ATTACH_MAX = 8 * 1024 * 1024
_CAD_EXT = {".dwg", ".dxf", ".step", ".stp", ".iges", ".igs", ".sat", ".ipt", ".iam"}


def live() -> bool:
    return google_auth.connected()


def _service():
    return google_auth.google_service("gmail", "v1")


def _header(headers: list[dict[str, str]], name: str) -> str:
    for item in headers:
        if (item.get("name") or "").lower() == name.lower():
            return item.get("value") or ""
    return ""


def _decode_part(part: dict[str, Any]) -> str:
    data = (part.get("body") or {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "==")
    return raw.decode("utf-8", errors="replace")


def _attachment_meta(part: dict[str, Any]) -> dict[str, Any] | None:
    body = part.get("body") or {}
    attachment_id = body.get("attachmentId")
    if not attachment_id:
        return None
    mime = (part.get("mimeType") or "").lower()
    filename = (part.get("filename") or "").strip()
    if not filename and mime.startswith("text/"):
        return None
    name = filename or f"attachment.{mime.split('/')[-1] if '/' in mime else 'bin'}"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    cad = ext in _CAD_EXT
    image = mime.startswith("image/")
    pdf = mime == "application/pdf" or name.lower().endswith(".pdf")
    readable = image or pdf
    return {
        "filename": name,
        "mime": mime or "application/octet-stream",
        "attachment_id": attachment_id,
        "size": int(body.get("size") or 0),
        "readable": readable,
        "cad": cad,
        "vision": readable and not cad,
    }


def _walk_parts(payload: dict[str, Any], plain: list[str], html: list[str], attachments: list[dict[str, Any]]) -> None:
    meta = _attachment_meta(payload)
    if meta:
        attachments.append(meta)
        return
    mime = (payload.get("mimeType") or "").lower()
    if mime.startswith("text/plain"):
        text = _decode_part(payload)
        if text.strip():
            plain.append(text)
        return
    if mime.startswith("text/html"):
        text = _decode_part(payload)
        if text.strip():
            html.append(text)
        return
    for part in payload.get("parts") or []:
        _walk_parts(part, plain, html, attachments)


def _body_from_payload(payload: dict[str, Any]) -> str:
    from ..tables import html_to_text

    plain: list[str] = []
    html: list[str] = []
    attachments: list[dict[str, Any]] = []
    _walk_parts(payload, plain, html, attachments)
    html_text = html[0] if html else ""
    if html_text and "<table" in html_text.lower():
        return html_to_text(html_text)
    if plain:
        return plain[0]
    if html_text:
        return html_to_text(html_text)
    return _decode_part(payload)


def _attachments_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    plain: list[str] = []
    html: list[str] = []
    attachments: list[dict[str, Any]] = []
    _walk_parts(payload, plain, html, attachments)
    return attachments


def _created_at(message: dict[str, Any], headers: list[dict[str, str]]) -> str:
    internal = message.get("internalDate")
    if internal:
        try:
            stamp = datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc)
            return stamp.isoformat()
        except (TypeError, ValueError):
            pass
    date_hdr = _header(headers, "Date")
    if date_hdr:
        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(date_hdr).isoformat()
        except Exception:
            pass
    return utc_now()


def _normalize(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    labels = message.get("labelIds") or []
    folder = "SENT" if "SENT" in labels else "INBOX"
    message_id = _header(headers, "Message-ID") or _header(headers, "Message-Id")
    return {
        "id": f"gmail-{message.get('id')}",
        "gmail_id": message.get("id") or "",
        "thread_id": message.get("threadId") or "",
        "message_id": message_id,
        "references": _header(headers, "References"),
        "sender": _header(headers, "From"),
        "to_addr": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "body": _body_from_payload(payload)[:_BODY_CAP],
        "attachments": _attachments_from_payload(payload),
        "labels": list(labels),
        "unread": 1 if "UNREAD" in labels else 0,
        "created_at": _created_at(message, headers),
        "folder": folder,
    }


def download_attachment(gmail_id: str, attachment_id: str) -> bytes:
    service = _service()
    raw = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=gmail_id, id=attachment_id)
        .execute()
    )
    data = raw.get("data") or ""
    return base64.urlsafe_b64decode(data + "==")


def unread_estimate() -> int:
    listed = (
        _service()
        .users()
        .messages()
        .list(userId="me", q="is:unread", maxResults=1)
        .execute()
    )
    return int(listed.get("resultSizeEstimate") or 0)


def _list_query(query: str = "", unread_only: bool = False) -> str:
    q_parts: list[str] = []
    if unread_only:
        q_parts.append("is:unread")
    if query:
        q_parts.append(query)
    return " ".join(q_parts)


def iter_message_id_pages(
    query: str = "",
    *,
    unread_only: bool = False,
    page_size: int = 50,
    max_pages: int | None = None,
):
    """Yield (gmail_ids, next_page_token) for paginated bulk sync."""
    service = _service()
    q = _list_query(query, unread_only)
    page_token: str | None = None
    pages = 0
    while True:
        kwargs: dict[str, Any] = {"userId": "me", "maxResults": max(1, min(page_size, 500))}
        if q:
            kwargs["q"] = q
        if page_token:
            kwargs["pageToken"] = page_token
        listed = service.users().messages().list(**kwargs).execute()
        ids = [str(item["id"]) for item in listed.get("messages") or [] if item.get("id")]
        next_token = listed.get("nextPageToken") or ""
        yield ids, next_token
        page_token = next_token or None
        pages += 1
        if not page_token or (max_pages is not None and pages >= max_pages):
            break


def list_messages(query: str = "", unread_only: bool = False, limit: int = 8) -> list[dict[str, Any]]:
    service = _service()
    q = _list_query(query, unread_only)
    listed = (
        service.users()
        .messages()
        .list(userId="me", q=q or None, maxResults=limit)
        .execute()
    )
    rows = []
    for item in listed.get("messages") or []:
        raw = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        rows.append(_normalize(raw))
    return rows


def get_message(gmail_id: str) -> dict[str, Any] | None:
    service = _service()
    raw = service.users().messages().get(userId="me", id=gmail_id, format="full").execute()
    return _normalize(raw)


def thread_messages(thread_id: str) -> list[dict[str, Any]]:
    service = _service()
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [_normalize(item) for item in thread.get("messages") or []]


def _rfc_message_id(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.startswith("<") and text.endswith(">"):
        return text
    if "@" in text and not text.startswith("gmail-"):
        return f"<{text.strip('<>')}>"
    return ""


def send_message(
    to_addr: str,
    subject: str,
    body: str,
    thread_id: str = "",
    in_reply_to: str = "",
    references: str = "",
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    from ..config import settings

    paths = [path for path in (attachment_paths or []) if path]
    downloadable: list[tuple[str, str, bytes]] = []
    for path in paths:
        file_path = Path(path)
        if not file_path.is_file():
            continue
        try:
            blob = file_path.read_bytes()
        except OSError:
            continue
        if len(blob) > _ATTACH_MAX:
            continue
        mime = "application/octet-stream"
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            mime = "application/pdf"
        elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            mime = f"image/{suffix.lstrip('.')}"
        downloadable.append((file_path.name, mime, blob))

    if downloadable:
        mime_root = MIMEMultipart()
        mime_root["To"] = to_addr
        mime_root["From"] = settings.google_account
        mime_root["Subject"] = subject
        reply_id = _rfc_message_id(in_reply_to)
        if reply_id:
            mime_root["In-Reply-To"] = reply_id
            refs = (references or "").strip()
            mime_root["References"] = f"{refs} {reply_id}".strip() if refs else reply_id
        mime_root.attach(MIMEText(body or "", "plain", "utf-8"))
        for filename, mime_type, blob in downloadable:
            part = MIMEBase(*((mime_type.split("/", 1) + ["octet-stream"])[:2]))
            part.set_payload(blob)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            mime_root.attach(part)
        raw = base64.urlsafe_b64encode(mime_root.as_bytes()).decode("ascii")
    else:
        mime = MIMEText(body or "", "plain", "utf-8")
        mime["To"] = to_addr
        mime["From"] = settings.google_account
        mime["Subject"] = subject
        reply_id = _rfc_message_id(in_reply_to)
        if reply_id:
            mime["In-Reply-To"] = reply_id
            refs = (references or "").strip()
            mime["References"] = f"{refs} {reply_id}".strip() if refs else reply_id
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    payload: dict[str, Any] = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    sent = _service().users().messages().send(userId="me", body=payload).execute()
    gmail_id = sent.get("id") or ""
    found = get_message(gmail_id) if gmail_id else None
    if found:
        return found
    return {
        "id": f"gmail-{gmail_id}" if gmail_id else "",
        "gmail_id": gmail_id,
        "thread_id": sent.get("threadId") or thread_id,
        "sender": settings.google_account,
        "to_addr": to_addr,
        "subject": subject,
        "body": body,
        "unread": 0,
        "created_at": utc_now(),
        "folder": "SENT",
        "attachments": [],
    }


def forward_message(
    to_addr: str,
    source: dict[str, Any],
    note: str = "",
) -> dict[str, Any]:
    from ..config import settings

    subject = source.get("subject") or ""
    if not subject.lower().startswith("fwd:"):
        subject = f"Fwd: {subject}".strip()
    original_from = source.get("sender") or ""
    original_to = source.get("to_addr") or ""
    original_date = source.get("created_at") or ""
    original_body = source.get("body") or ""
    header_block = (
        f"---------- Forwarded message ---------\n"
        f"From: {original_from}\n"
        f"Date: {original_date}\n"
        f"Subject: {source.get('subject') or ''}\n"
        f"To: {original_to}\n\n"
    )
    body_parts = []
    if note.strip():
        body_parts.append(note.strip())
        body_parts.append("")
    body_parts.append(header_block + original_body)
    body = "\n".join(body_parts)

    attachments = source.get("attachments") or []
    gmail_id = source.get("gmail_id") or ""
    downloadable: list[tuple[str, str, bytes]] = []
    if gmail_id and attachments:
        for item in attachments:
            size = int(item.get("size") or 0)
            if size > _ATTACH_MAX:
                continue
            att_id = item.get("attachment_id") or ""
            if not att_id:
                continue
            try:
                blob = download_attachment(gmail_id, att_id)
            except Exception:
                continue
            if len(blob) > _ATTACH_MAX:
                continue
            downloadable.append((item.get("filename") or "attachment", item.get("mime") or "application/octet-stream", blob))

    if downloadable:
        mime_root = MIMEMultipart()
        mime_root["To"] = to_addr
        mime_root["From"] = settings.google_account
        mime_root["Subject"] = subject
        mime_root.attach(MIMEText(body, "plain", "utf-8"))
        for filename, mime_type, blob in downloadable:
            part = MIMEBase(*((mime_type.split("/", 1) + ["octet-stream"])[:2]))
            part.set_payload(blob)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            mime_root.attach(part)
        raw = base64.urlsafe_b64encode(mime_root.as_bytes()).decode("ascii")
    else:
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"] = to_addr
        mime["From"] = settings.google_account
        mime["Subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")

    payload: dict[str, Any] = {"raw": raw}
    sent = _service().users().messages().send(userId="me", body=payload).execute()
    sent_id = sent.get("id") or ""
    found = get_message(sent_id) if sent_id else None
    if found:
        return found
    return {
        "id": f"gmail-{sent_id}" if sent_id else "",
        "gmail_id": sent_id,
        "thread_id": sent.get("threadId") or "",
        "sender": settings.google_account,
        "to_addr": to_addr,
        "subject": subject,
        "body": body,
        "unread": 0,
        "created_at": utc_now(),
        "folder": "SENT",
        "attachments": [],
    }


def newer_in_thread(thread_id: str, after_id: str = "") -> dict[str, Any] | None:
    rows = thread_messages(thread_id)
    if not rows:
        return None
    if not after_id:
        return rows[-1] if len(rows) > 1 else None
    seen = False
    for row in rows:
        if row.get("gmail_id") == after_id or row.get("id") == after_id:
            seen = True
            continue
        if seen:
            return row
    if len(rows) > 1 and rows[-1].get("gmail_id") != after_id:
        return rows[-1]
    return None
