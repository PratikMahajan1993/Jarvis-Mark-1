from __future__ import annotations

import imaplib
import uuid
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from typing import Any

from ..config import settings
from ..db import connect, utc_now, upsert_email


def seed_mailbox() -> None:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM emails").fetchone()["n"]
        if count:
            return
        now = datetime.now(timezone.utc)
        samples = [
            {
                "id": "mail-client-proposal",
                "sender": "Priya Shah <priya@northline.example>",
                "to_addr": "you@jarvis.local",
                "subject": "Re: Q3 proposal - need your redlines by 4pm",
                "body": (
                    "Thanks for the draft. Two items before we circulate:\n"
                    "1) Confirm the 12-week rollout and the on-site week.\n"
                    "2) Please send the revised pricing sheet as Excel.\n\n"
                    "Can you reply today before the 4pm review?"
                ),
                "unread": 1,
                "created_at": (now - timedelta(hours=2)).isoformat(),
                "folder": "INBOX",
            },
            {
                "id": "mail-standup",
                "sender": "Amit Rao <amit@team.example>",
                "to_addr": "you@jarvis.local",
                "subject": "Standup notes and blockers",
                "body": (
                    "Yesterday: closed the invoice export.\n"
                    "Today: prepare the client review deck.\n"
                    "Blocker: waiting on legal language for the MSA."
                ),
                "unread": 1,
                "created_at": (now - timedelta(hours=5)).isoformat(),
                "folder": "INBOX",
            },
            {
                "id": "mail-invoice",
                "sender": "Billing <billing@vertex-labs.example>",
                "to_addr": "you@jarvis.local",
                "subject": "Invoice VL-1842 due Friday",
                "body": "Invoice VL-1842 for INR 84,500 is due this Friday. Reply if you need a GST split.",
                "unread": 1,
                "created_at": (now - timedelta(days=1)).isoformat(),
                "folder": "INBOX",
            },
            {
                "id": "mail-ashutosh",
                "sender": "Ashutosh Mehta <ashutosh@northline.example>",
                "to_addr": "you@jarvis.local",
                "subject": "Re: Q3 proposal — your note",
                "body": (
                    "Price is fine on our side.\n"
                    "Please send the MSA redlines by Thursday.\n"
                    "Can you confirm the on-site week?\n"
                ),
                "unread": 1,
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "folder": "INBOX",
            },
            {
                "id": "mail-sent-ack",
                "sender": "you@jarvis.local",
                "to_addr": "legal@northline.example",
                "subject": "MSA redlines received",
                "body": "Acknowledging receipt. We will return comments after the afternoon review.",
                "unread": 0,
                "created_at": (now - timedelta(days=2)).isoformat(),
                "folder": "SENT",
            },
        ]
        conn.executemany(
            """
            INSERT INTO emails (id, sender, to_addr, subject, body, unread, created_at, folder)
            VALUES (:id, :sender, :to_addr, :subject, :body, :unread, :created_at, :folder)
            """,
            samples,
        )


def _decode(value: str | bytes | None) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        try:
            return str(make_header(decode_header(value.decode("utf-8", errors="replace"))))
        except Exception:
            return value.decode("utf-8", errors="replace")
    return str(value)


def _imap_search(query: str, unread_only: bool, limit: int) -> list[dict[str, Any]]:
    mail = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    mail.login(settings.imap_user, settings.imap_password)
    mail.select(settings.imap_folder)
    criteria = "(UNSEEN)" if unread_only else "ALL"
    if query:
        safe = query.replace('"', "")
        criteria = f'(OR SUBJECT "{safe}" FROM "{safe}")'
        if unread_only:
            criteria = f"(UNSEEN {criteria})"
    status, data = mail.search(None, criteria)
    if status != "OK":
        mail.logout()
        return []
    ids = data[0].split()[-limit:]
    messages: list[dict[str, Any]] = []
    for msg_id in reversed(ids):
        status, payload = mail.fetch(msg_id, "(RFC822)")
        if status != "OK" or not payload or not payload[0]:
            continue
        raw = payload[0][1]
        parsed = message_from_bytes(raw)
        body = ""
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            payload_bytes = parsed.get_payload(decode=True)
            body = payload_bytes.decode("utf-8", errors="replace") if payload_bytes else ""
        date_raw = parsed.get("Date")
        try:
            created = parsedate_to_datetime(date_raw).isoformat() if date_raw else utc_now()
        except Exception:
            created = utc_now()
        messages.append(
            {
                "id": f"imap-{msg_id.decode()}",
                "sender": _decode(parsed.get("From")),
                "to_addr": _decode(parsed.get("To")),
                "subject": _decode(parsed.get("Subject")),
                "body": body[:4000],
                "unread": 1 if unread_only else 0,
                "created_at": created,
                "folder": settings.imap_folder,
            }
        )
    mail.logout()
    return messages


def search_emails(query: str = "", unread_only: bool = False, limit: int = 8) -> list[dict[str, Any]]:
    from . import gmail as gmail_conn

    if gmail_conn.live():
        try:
            rows = gmail_conn.list_messages(query=query, unread_only=unread_only, limit=limit)
            return [upsert_email(row) for row in rows]
        except Exception:
            pass
    if settings.email_backend == "imap" and settings.imap_host and settings.imap_user:
        return _imap_search(query, unread_only, limit)
    sql = "SELECT * FROM emails WHERE folder = 'INBOX'"
    args: list[Any] = []
    if unread_only:
        sql += " AND unread = 1"
    if query:
        sql += " AND (subject LIKE ? OR sender LIKE ? OR body LIKE ?)"
        like = f"%{query}%"
        args.extend([like, like, like])
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(row) for row in rows]


def get_email(email_id: str) -> dict[str, Any] | None:
    if not email_id:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    if row:
        return dict(row)
    from . import gmail as gmail_conn

    if gmail_conn.live() and str(email_id).startswith("gmail-"):
        try:
            found = gmail_conn.get_message(str(email_id)[6:])
            return upsert_email(found) if found else None
        except Exception:
            return None
    return None


def mark_read(email_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE emails SET unread = 0 WHERE id = ?", (email_id,))


def create_draft(to_addr: str, subject: str, body: str) -> dict[str, Any]:
    email_id = f"draft-{uuid.uuid4().hex[:10]}"
    record = {
        "id": email_id,
        "sender": "you@jarvis.local",
        "to_addr": to_addr,
        "subject": subject,
        "body": body,
        "unread": 0,
        "created_at": utc_now(),
        "folder": "DRAFTS",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO emails (id, sender, to_addr, subject, body, unread, created_at, folder)
            VALUES (:id, :sender, :to_addr, :subject, :body, :unread, :created_at, :folder)
            """,
            record,
        )
    return record


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    source_id: str | None = None,
    thread_id: str = "",
) -> dict[str, Any]:
    from . import gmail as gmail_conn

    source = get_email(source_id) if source_id else None
    reply_thread = thread_id or (source.get("thread_id") if source else "")
    if gmail_conn.live():
        record = gmail_conn.send_message(
            to_addr,
            subject,
            body,
            thread_id=reply_thread or "",
            in_reply_to=source_id or "",
        )
        upsert_email(record)
        if source_id:
            mark_read(source_id)
        return record
    email_id = f"sent-{uuid.uuid4().hex[:10]}"
    record = {
        "id": email_id,
        "sender": settings.google_account or "you@jarvis.local",
        "to_addr": to_addr,
        "subject": subject,
        "body": body,
        "unread": 0,
        "created_at": utc_now(),
        "folder": "SENT",
        "thread_id": reply_thread or email_id,
    }
    upsert_email(record)
    if source_id:
        mark_read(source_id)
    return record


def unread_count() -> int:
    from . import gmail as gmail_conn

    if gmail_conn.live():
        try:
            return gmail_conn.unread_estimate()
        except Exception:
            pass
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM emails WHERE unread = 1 AND folder = 'INBOX'").fetchone()["n"])
