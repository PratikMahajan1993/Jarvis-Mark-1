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


def reindex_recent_mail(limit: int = 20) -> dict[str, Any]:
    rows = email_conn.search_emails(query="", limit=limit) if hasattr(email_conn, "search_emails") else []
    if not rows:
        try:
            rows = email_conn.list_emails(limit=limit)  # type: ignore[attr-defined]
        except Exception:
            rows = []
    count = 0
    for row in rows or []:
        mail_id = str(row.get("id") or "")
        mail = row
        # Prefer full local/Gmail body when the list row is a stub.
        if mail_id and not str(row.get("body") or "").strip():
            try:
                full = email_conn.get_email(mail_id)
                if full:
                    mail = full
            except Exception:
                pass
        subject = str(mail.get("subject") or "")
        sender = str(mail.get("sender") or "")
        body = str(mail.get("body") or "")[:4000]
        atts = mail.get("attachments") or []
        att_line = ""
        if isinstance(atts, list) and atts:
            names = ", ".join(str(a.get("filename") or "file") for a in atts[:5] if isinstance(a, dict))
            if names:
                att_line = f"\nAttachments: {names}"
        text = f"Email from {sender}\nSubject: {subject}\n{body}{att_line}".strip()
        ingest_text(
            text,
            namespace="corpus",
            key=f"mail:{mail_id or abs(hash(text)) % 10_000_000}",
            meta={"kind": "mail", "mail_id": mail_id, "subject": subject},
        )
        count += 1
    return {"ok": True, "indexed": count}
