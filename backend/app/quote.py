"""Quotation build: vision → sheet → PDF → HITL email (foundation Phase 3)."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from . import db
from .config import settings
from .hermes.hitl import request_human_approval
from .memory.ingest import ingest_drawing_summary
from .tools import documents


def analyze_drawing_vision(path: str, *, prompt: str = "") -> dict[str, Any]:
    """Send drawing bytes to Gemini vision for dimensional notes."""
    from . import gemini_client

    file_path = Path(path)
    if not file_path.is_file():
        return {"ok": False, "error": f"Drawing not found: {path}"}
    raw = file_path.read_bytes()
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    if mime == "application/pdf":
        # Prefer image pages when possible; still send PDF bytes as inline data
        pass
    b64 = base64.b64encode(raw).decode("ascii")
    media = [{"inline_data": {"mime_type": mime, "data": b64}}]
    ask = prompt or (
        "You are helping a machining firm quote a part. "
        "List visible dimensions, material if shown, title block, and call out unreadable values. "
        "Do not invent numbers. Reply in concise bullet points."
    )
    try:
        result = gemini_client.chat_multimodal(
            [],
            ask,
            media,
            system="Precision machining quotation assistant. Never invent dimensions.",
            model=settings.gemini_drawing_model or settings.gemini_model,
            timeout=180,
        )
        text = str(result.get("content") or "")
        ingest_drawing_summary(file_path.name, text[:2000], meta={"path": str(file_path)})
        return {"ok": True, "summary": text, "path": str(file_path), "name": file_path.name}
    except Exception as exc:
        # Offline / no key: deterministic stub from filename for dry-run
        stub = (
            f"Vision unavailable ({exc}). "
            f"File {file_path.name} queued for manual dimensional review."
        )
        ingest_drawing_summary(file_path.name, stub, meta={"path": str(file_path), "stub": True})
        return {"ok": False, "error": str(exc), "summary": stub, "path": str(file_path), "name": file_path.name}


def build_quote(
    *,
    session_id: str,
    part_name: str,
    material: str = "",
    vision_summary: str = "",
    line_items: list[dict[str, Any]] | None = None,
    customer: str = "",
) -> dict[str, Any]:
    """Create a local quotation spreadsheet artifact (live Sheet bind can follow)."""
    items = line_items or [
        {
            "item": part_name or "Component",
            "material": material or "TBD",
            "qty": 1,
            "unit_price": "",
            "notes": (vision_summary or "")[:240],
        }
    ]
    columns = ["Item", "Material", "Qty", "Unit price", "Notes"]
    rows = [
        [
            str(it.get("item") or ""),
            str(it.get("material") or ""),
            it.get("qty") if it.get("qty") is not None else 1,
            it.get("unit_price") if it.get("unit_price") is not None else "",
            str(it.get("notes") or ""),
        ]
        for it in items
    ]
    title = f"Quote — {part_name or 'Component'}"
    artifact = documents.create_spreadsheet(title, columns, rows)
    db.add_memory(session_id, "last_quote", artifact["id"])
    db.add_memory(session_id, "last_quote_name", artifact["name"])
    # Best-effort Google Sheet mirror when shop sheets connector works
    sheet_ref = ""
    try:
        from .connectors import sheets as sheets_conn

        if hasattr(sheets_conn, "create_spreadsheet"):
            created = sheets_conn.create_spreadsheet(title)  # type: ignore[attr-defined]
            sheet_ref = str((created or {}).get("url") or (created or {}).get("id") or "")
    except Exception:
        sheet_ref = ""
    payload = {
        "artifact": artifact,
        "columns": columns,
        "rows": rows,
        "customer": customer,
        "part_name": part_name,
        "material": material,
        "vision_summary": vision_summary,
        "sheet_ref": sheet_ref,
    }
    return {"ok": True, **payload}


def quote_to_pdf(*, session_id: str, part_name: str = "", rows: list[list[Any]] | None = None) -> dict[str, Any]:
    body_lines = [f"Quotation: {part_name or 'Component'}", ""]
    for row in rows or []:
        body_lines.append(" | ".join(str(c) for c in row))
    body = "\n".join(body_lines) or "Quotation"
    artifact = documents.create_pdf(f"Quote PDF — {part_name or 'Component'}", body)
    db.add_memory(session_id, "last_quote_pdf", artifact["id"])
    return {"ok": True, "artifact": artifact}


def queue_quote_send(
    *,
    session_id: str,
    to: str,
    subject: str,
    body: str,
    pdf_path: str,
) -> dict[str, Any]:
    pending = request_human_approval(
        session_id=session_id,
        kind="quote_send",
        title=f"Send quote: {subject}",
        summary=f"To {to} with PDF attachment",
        payload={
            "to": to,
            "subject": subject,
            "body": body,
            "attachment_paths": [pdf_path] if pdf_path else [],
        },
        tool_name="quote_send",
    )
    return {"ok": True, "pending": pending}
