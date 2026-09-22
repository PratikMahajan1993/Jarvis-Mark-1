"""Vision dispatch gate — deny-all unless owner_spend."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Callable

from .. import db
from ..config import settings
from ..hermes.hitl import request_human_approval
from .ledger import (
    VISION_CAP,
    claim_unit,
    current_cycle_start,
    mark_dispatched,
    release_claim,
    vision_page_threshold,
    write_disclosure,
)
from .schema import ensure_vision_schema

ProviderFn = Callable[[], dict[str, Any]]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def page_count(path: Path) -> int:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return max(1, len(reader.pages))
        except Exception:
            return 1
    return 1


def local_sheet_index(path: Path) -> dict[str, Any]:
    """Local-only sheet index for multi-page packs (no cloud)."""
    pages = page_count(path)
    sheets: list[dict[str, Any]] = []
    unresolved = False
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            for idx, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                label = ""
                if text:
                    first = " ".join(text.split())[:80]
                    label = first
                else:
                    unresolved = True
                sheets.append({"page": idx, "label": label or "(no local text)"})
        except Exception:
            unresolved = True
    else:
        unresolved = True
    if not sheets:
        sheets = [{"page": n, "label": "(index unresolved)"} for n in range(1, pages + 1)]
        unresolved = True
    return {
        "page_count": pages,
        "sheets": sheets,
        "index_unresolved": unresolved,
    }


def set_analysis_state(
    file_hash: str,
    state: str,
    *,
    display_name: str | None = None,
    path: str | None = None,
) -> None:
    with db.connect() as conn:
        ensure_vision_schema(conn)
        conn.execute(
            """
            INSERT INTO drawing_analysis_state (
              file_sha256, analysis_state, updated_at, display_name, path
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_sha256) DO UPDATE SET
              analysis_state = excluded.analysis_state,
              updated_at = excluded.updated_at,
              display_name = COALESCE(excluded.display_name, drawing_analysis_state.display_name),
              path = COALESCE(excluded.path, drawing_analysis_state.path)
            """,
            (file_hash, state, db.utc_now(), display_name, path),
        )


def get_analysis_state(file_hash: str) -> str | None:
    with db.connect() as conn:
        ensure_vision_schema(conn)
        row = conn.execute(
            "SELECT analysis_state FROM drawing_analysis_state WHERE file_sha256 = ?",
            (file_hash,),
        ).fetchone()
        return str(row["analysis_state"]) if row else None


def list_needs_vision_bench_items() -> list[dict[str, Any]]:
    with db.connect() as conn:
        ensure_vision_schema(conn)
        rows = conn.execute(
            """
            SELECT file_sha256, display_name, path
            FROM drawing_analysis_state
            WHERE analysis_state = 'needs_vision'
            ORDER BY updated_at ASC
            """
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        digest = str(row["file_sha256"])
        name = row["display_name"]
        display = str(name).strip() if name else digest[:12]
        item: dict[str, Any] = {"file_sha256": digest, "display_name": display}
        if row["path"]:
            item["path"] = str(row["path"])
        items.append(item)
    return items


def bench_analyse_drawing(file_sha256: str) -> dict[str, Any]:
    """Owner bench spend path — resolves queued row and dispatches vision."""
    with db.connect() as conn:
        ensure_vision_schema(conn)
        row = conn.execute(
            """
            SELECT analysis_state, path
            FROM drawing_analysis_state
            WHERE file_sha256 = ?
            """,
            (file_sha256,),
        ).fetchone()
    if not row:
        return {"ok": False, "enabled": True, "error": "Drawing not queued for vision."}
    path_val = row["path"]
    if not path_val:
        return {"ok": False, "enabled": True, "error": "Queued drawing has no path."}
    return dispatch_drawing_vision(
        str(path_val),
        owner_spend=True,
        spent_by="owner_bench",
        arrival="mail",
    )


def vision_bench_get_payload() -> dict[str, Any]:
    from .ledger import current_cycle_used, next_cycle_reset_at

    if not settings.vision_bench_enabled:
        return {"enabled": False, "items": [], "used": 0, "total": VISION_CAP, "reset_at": ""}
    return {
        "enabled": True,
        "items": list_needs_vision_bench_items(),
        "used": current_cycle_used(),
        "total": VISION_CAP,
        "reset_at": next_cycle_reset_at(),
    }


def on_mail_drawing_saved(path: str | Path, *, customer_id: str | None = None) -> dict[str, Any]:
    """Mail ingest: local only, never spends a vision unit."""
    file_path = Path(path)
    if not file_path.is_file():
        return {"ok": False, "error": f"Drawing not found: {path}"}
    digest = file_sha256(file_path)
    set_analysis_state(
        digest,
        "needs_vision",
        display_name=file_path.name,
        path=str(file_path.resolve()),
    )
    return {
        "ok": True,
        "file_sha256": digest,
        "analysis_state": "needs_vision",
        "customer_id": customer_id,
    }


def _customer_vision_consent_error(customer_id: str | None) -> str | None:
    """Gate 1 — deny unless attested customer_terms row allows cloud vision."""
    if not customer_id or not str(customer_id).strip():
        return (
            "Cloud vision requires a known customer. "
            "Attest vision consent for this customer in master data."
        )
    cid = str(customer_id).strip()
    with db.connect() as conn:
        cust = conn.execute("SELECT id FROM customers WHERE id = ?", (cid,)).fetchone()
        if not cust:
            return (
                "Customer is unknown or unresolved. "
                "Attest vision consent for this customer in master data before cloud vision."
            )
        row = conn.execute(
            """
            SELECT allow_cloud_vision, nda, vision_consent_by
            FROM customer_terms
            WHERE customer_id = ?
            """,
            (cid,),
        ).fetchone()
        if not row:
            return (
                "No vision consent on file for this customer. "
                "Attest allow_cloud_vision and NDA status for this customer."
            )
        if int(row["nda"]):
            return (
                "This customer has an NDA on file. "
                "Cloud vision is not permitted and cannot be overridden by quota spend."
            )
        if not int(row["allow_cloud_vision"]):
            return (
                "Cloud vision is not allowed for this customer. "
                "Set allow_cloud_vision via owner attestation in master data."
            )
        consent_by = row["vision_consent_by"]
        if not consent_by or not str(consent_by).strip():
            return (
                "Vision consent is not attested. "
                "Owner attestation (vision_consent_by) is required before cloud vision."
            )
    return None


def attest_customer_vision(
    customer_id: str,
    *,
    allow: bool,
    nda: bool,
    attested_by: str,
) -> dict[str, Any]:
    """Only writer for customer_terms vision consent fields."""
    cid = (customer_id or "").strip()
    who = (attested_by or "").strip()
    if not cid:
        return {"ok": False, "error": "customer_id required"}
    if not who:
        return {"ok": False, "error": "attested_by required"}
    now = db.utc_now()
    allow_i = 1 if allow else 0
    nda_i = 1 if nda else 0
    with db.connect() as conn:
        cust = conn.execute("SELECT id FROM customers WHERE id = ?", (cid,)).fetchone()
        if not cust:
            return {"ok": False, "error": f"Unknown customer id: {cid}"}
        existing = conn.execute(
            "SELECT customer_id FROM customer_terms WHERE customer_id = ?",
            (cid,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE customer_terms
                SET allow_cloud_vision = ?,
                    nda = ?,
                    vision_consent_by = ?,
                    vision_consent_at = ?
                WHERE customer_id = ?
                """,
                (allow_i, nda_i, who, now, cid),
            )
        else:
            conn.execute(
                """
                INSERT INTO customer_terms (
                  customer_id, default_scope, nda, allow_cloud_vision,
                  vision_consent_by, vision_consent_at
                ) VALUES (?, 'ask', ?, ?, ?, ?)
                """,
                (cid, nda_i, allow_i, who, now),
            )
    return {
        "ok": True,
        "customer_id": cid,
        "allow_cloud_vision": bool(allow),
        "nda": bool(nda),
        "vision_consent_by": who,
        "vision_consent_at": now,
    }


def vision_consent_get_payload(customer_id: str | None = None) -> dict[str, Any]:
    if not settings.masterdata_enabled:
        return {"enabled": False}
    out: dict[str, Any] = {"enabled": True}
    cid = (customer_id or "").strip()
    if not cid:
        return out
    out["customer_id"] = cid
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT allow_cloud_vision, nda, vision_consent_by, vision_consent_at
            FROM customer_terms
            WHERE customer_id = ?
            """,
            (cid,),
        ).fetchone()
    if not row:
        out["allow_cloud_vision"] = False
        out["nda"] = False
        out["vision_consent_by"] = ""
        out["vision_consent_at"] = ""
        out["attested"] = False
        return out
    out["allow_cloud_vision"] = bool(int(row["allow_cloud_vision"]))
    out["nda"] = bool(int(row["nda"]))
    out["vision_consent_by"] = str(row["vision_consent_by"] or "")
    out["vision_consent_at"] = str(row["vision_consent_at"] or "")
    out["attested"] = bool(out["vision_consent_by"])
    return out


def _queue_cap_override(
    *,
    session_id: str,
    path: Path,
    file_hash: str,
    customer_id: str | None,
    cycle_start: str,
    used: int,
) -> dict[str, Any]:
    title = f"Vision quota — {path.name}"
    summary = (
        f"Drawing {path.name} would use vision unit {used + 1}/{5} this cycle "
        f"(cycle from {cycle_start}). Authorize one override for this document only."
    )
    pending = request_human_approval(
        session_id=session_id or "default",
        kind="vision_quota_override",
        title=title,
        summary=summary,
        payload={
            "file_sha256": file_hash,
            "filename": path.name,
            "path": str(path),
            "customer_id": customer_id,
            "cycle_start": cycle_start,
            "used": used,
            "cap": 5,
        },
        tool_name="vision_quota_override",
    )
    return pending


def dispatch_drawing_vision(
    path: str | Path,
    *,
    owner_spend: bool = False,
    prompt: str = "",
    session_id: str = "",
    turn_id: str | None = None,
    customer_id: str | None = None,
    arrival: str = "mail",
    spent_by: str = "owner_bench",
    provider_call: ProviderFn | None = None,
) -> dict[str, Any]:
    """
    Gate cloud vision. Default deny: no owner_spend ⇒ needs_vision only.
    provider_call must perform the cloud request when invoked; stub in tests.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return {"ok": False, "error": f"Drawing not found: {path}"}

    digest = file_sha256(file_path)
    pages = page_count(file_path)
    cycle = current_cycle_start()

    if not owner_spend:
        set_analysis_state(digest, "needs_vision")
        return {
            "ok": False,
            "analysis_state": "needs_vision",
            "path": str(file_path),
            "name": file_path.name,
            "file_sha256": digest,
            "error": "Cloud vision requires owner_spend.",
        }

    threshold = vision_page_threshold()
    if pages > threshold:
        index = local_sheet_index(file_path)
        set_analysis_state(digest, "needs_vision")
        return {
            "ok": False,
            "analysis_state": "needs_vision",
            "path": str(file_path),
            "name": file_path.name,
            "file_sha256": digest,
            "page_count": pages,
            "sheet_index": index,
            "error": f"Pack has {pages} sheets (threshold {threshold}). Review the sheet index before spending a unit.",
        }

    if settings.masterdata_enabled and owner_spend:
        consent_err = _customer_vision_consent_error(customer_id)
        if consent_err:
            set_analysis_state(
                digest,
                "needs_vision",
                display_name=file_path.name,
                path=str(file_path.resolve()),
            )
            return {
                "ok": False,
                "analysis_state": "needs_vision",
                "path": str(file_path),
                "name": file_path.name,
                "file_sha256": digest,
                "customer_id": customer_id,
                "error": consent_err,
            }

    claim_id: str | None = None
    reused = False
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ensure_vision_schema(conn)
        claim = claim_unit(
            conn,
            cycle_start=cycle,
            file_sha256=digest,
            customer_id=customer_id,
            spent_by=spent_by,
            arrival=arrival,
            pages=pages,
            turn_id=turn_id,
        )
        if not claim.get("ok"):
            reason = claim.get("reason")
            if reason == "cap":
                used = conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM vision_quota_usage
                    WHERE cycle_start = ? AND state IN ('claimed', 'dispatched', 'override')
                    """,
                    (cycle,),
                ).fetchone()
                used_n = int(used["n"] if used else 5)
                conn.commit()
                pending = _queue_cap_override(
                    session_id=session_id,
                    path=file_path,
                    file_hash=digest,
                    customer_id=customer_id,
                    cycle_start=cycle,
                    used=used_n,
                )
                set_analysis_state(digest, "needs_vision")
                return {
                    "ok": False,
                    "analysis_state": "needs_vision",
                    "path": str(file_path),
                    "name": file_path.name,
                    "file_sha256": digest,
                    "pending": pending,
                    "quota": {"used": used_n, "cap": 5},
                    "error": "Vision quota exhausted for this cycle.",
                }
            conn.commit()
            set_analysis_state(digest, "needs_vision")
            return {
                "ok": False,
                "analysis_state": "needs_vision",
                "path": str(file_path),
                "name": file_path.name,
                "file_sha256": digest,
                "error": "Could not claim vision unit.",
            }
        claim_id = str(claim["claim_id"])
        reused = bool(claim.get("reused"))
        conn.commit()

    if provider_call is None:
        from .. import gemini_client

        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        raw = file_path.read_bytes()
        import base64

        b64 = base64.b64encode(raw).decode("ascii")
        media = [{"inline_data": {"mime_type": mime, "data": b64}}]
        ask = prompt or (
            "You are helping a machining firm quote a part. "
            "List visible dimensions, material if shown, title block, and call out unreadable values. "
            "Do not invent numbers. Reply in concise bullet points."
        )
        model = settings.gemini_drawing_model or settings.gemini_model

        def _default_provider() -> dict[str, Any]:
            result = gemini_client.chat_multimodal(
                [],
                ask,
                media,
                system="Precision machining quotation assistant. Never invent dimensions.",
                model=model,
                timeout=180,
            )
            return {"content": str(result.get("content") or ""), "provider": model}

        provider_call = _default_provider

    try:
        result = provider_call()
        text = str(result.get("content") or "")
        provider_name = str(result.get("provider") or settings.gemini_drawing_model or "gemini")
        nbytes = file_path.stat().st_size
        with db.connect() as conn:
            write_disclosure(
                conn,
                file_sha256=digest,
                customer_id=customer_id,
                provider=provider_name,
                purpose="drawing_quote_analysis",
                nbytes=nbytes,
                turn_id=turn_id,
                cycle_start=cycle,
                authorized_by=spent_by,
            )
            if claim_id and not reused:
                mark_dispatched(conn, claim_id)
            elif claim_id:
                mark_dispatched(conn, claim_id)
        set_analysis_state(digest, "vision_done")
        return {
            "ok": True,
            "summary": text,
            "path": str(file_path),
            "name": file_path.name,
            "file_sha256": digest,
            "analysis_state": "vision_done",
            "reused_unit": reused,
        }
    except Exception as exc:
        if claim_id:
            with db.connect() as conn:
                release_claim(conn, claim_id)
        set_analysis_state(digest, "needs_vision")
        return {
            "ok": False,
            "error": str(exc),
            "path": str(file_path),
            "name": file_path.name,
            "file_sha256": digest,
            "analysis_state": "needs_vision",
        }
