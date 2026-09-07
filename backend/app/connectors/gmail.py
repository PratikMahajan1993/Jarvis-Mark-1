from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any

from . import google_auth
from ..db import utc_now


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


def _walk_text(payload: dict[str, Any], plain: list[str], html: list[str]) -> None:
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
        _walk_text(part, plain, html)


def _body_from_payload(payload: dict[str, Any]) -> str:
    from ..tables import html_to_text

    plain: list[str] = []
    html: list[str] = []
    _walk_text(payload, plain, html)
    html_text = html[0] if html else ""
    if html_text and "<table" in html_text.lower():
        return html_to_text(html_text)
    if plain:
        return plain[0]
    if html_text:
        return html_to_text(html_text)
    return _decode_part(payload)


def _normalize(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    labels = message.get("labelIds") or []
    folder = "SENT" if "SENT" in labels else "INBOX"
    return {
        "id": f"gmail-{message.get('id')}",
        "gmail_id": message.get("id") or "",
        "thread_id": message.get("threadId") or "",
        "sender": _header(headers, "From"),
        "to_addr": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "body": _body_from_payload(payload)[:4000],
        "unread": 1 if "UNREAD" in labels else 0,
        "created_at": utc_now(),
        "folder": folder,
    }


def unread_estimate() -> int:
    listed = (
        _service()
        .users()
        .messages()
        .list(userId="me", q="is:unread", maxResults=1)
        .execute()
    )
    return int(listed.get("resultSizeEstimate") or 0)


def list_messages(query: str = "", unread_only: bool = False, limit: int = 8) -> list[dict[str, Any]]:
    service = _service()
    q_parts = []
    if unread_only:
        q_parts.append("is:unread")
    if query:
        q_parts.append(query)
    listed = (
        service.users()
        .messages()
        .list(userId="me", q=" ".join(q_parts), maxResults=limit)
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


def send_message(
    to_addr: str,
    subject: str,
    body: str,
    thread_id: str = "",
    in_reply_to: str = "",
) -> dict[str, Any]:
    from ..config import settings

    mime = MIMEText(body or "", "plain", "utf-8")
    mime["To"] = to_addr
    mime["From"] = settings.google_account
    mime["Subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to
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
