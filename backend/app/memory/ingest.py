"""Corpus ingest hooks for local RAG."""

from __future__ import annotations

from typing import Any

from ..connectors import email as email_conn
from .store import upsert


def ingest_text(
    text: str,
    *,
    namespace: str = "corpus",
    key: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = (text or "").strip()
    if not body:
        return {"ok": False, "error": "empty"}
    doc = upsert(namespace=namespace, key=key or f"doc-{abs(hash(body)) % 10_000_000}", text=body, meta=meta)
    return {"ok": True, **doc}


def ingest_drawing_summary(
    drawing_name: str,
    summary: str,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = (drawing_name or "drawing").strip()
    return ingest_text(
        f"Drawing {name}: {summary}",
        namespace="corpus",
        key=f"drawing:{name}",
        meta={"kind": "drawing", **(meta or {})},
    )


def _mail_corpus_text(mail: dict) -> str:
    subject = str(mail.get("subject") or "")
    sender = str(mail.get("sender") or "")
    body = str(mail.get("body") or "")[:4000]
    atts = mail.get("attachments") or []
    att_line = ""
    if isinstance(atts, list) and atts:
        names = ", ".join(str(a.get("filename") or "file") for a in atts[:5] if isinstance(a, dict))
        if names:
            att_line = f"\nAttachments: {names}"
    return f"Email from {sender}\nSubject: {subject}\n{body}{att_line}".strip()


def _index_mail_row(mail: dict[str, Any]) -> None:
    mail_id = str(mail.get("id") or "")
    text = _mail_corpus_text(mail)
    if not text:
        return
    ingest_text(
        text,
        namespace="corpus",
        key=f"mail:{mail_id or abs(hash(text)) % 10_000_000}",
        meta={"kind": "mail", "mail_id": mail_id, "subject": str(mail.get("subject") or "")},
    )


def reindex_mail_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = 0
    for row in rows or []:
        _index_mail_row(row)
        count += 1
    return {"ok": True, "indexed": count}


def reindex_recent_mail(limit: int = 20) -> dict[str, Any]:
    from ..db import list_gmail_emails_local

    rows = list_gmail_emails_local(limit=limit)
    if not rows:
        rows = email_conn.search_emails(query="", limit=limit) if hasattr(email_conn, "search_emails") else []
    count = 0
    for row in rows or []:
        mail_id = str(row.get("id") or "")
        mail = row
        if mail_id and not str(row.get("body") or "").strip():
            try:
                full = email_conn.get_email(mail_id)
                if full:
                    mail = full
            except Exception:
                pass
        _index_mail_row(mail)
        count += 1
    return {"ok": True, "indexed": count}


def reindex_all_mail_in_db(*, batch_size: int = 50, limit: int | None = None) -> dict[str, Any]:
    """Walk gmail-* rows in SQLite and index into corpus (deduped by mail:{id})."""
    from ..db import list_gmail_emails_local

    offset = 0
    total = 0
    while True:
        if limit is not None and total >= limit:
            break
        take = batch_size if limit is None else min(batch_size, limit - total)
        rows = list_gmail_emails_local(limit=take, offset=offset)
        if not rows:
            break
        reindex_mail_rows(rows)
        total += len(rows)
        offset += len(rows)
        if len(rows) < take:
            break
    return {"ok": True, "indexed": total}
