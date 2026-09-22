"""Persist built quotes into quote_revisions + quote_lines when masterdata is on."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from typing import Any

from .. import db
from ..config import settings

_RM_ROW_RE = re.compile(r"raw\s*material|\brm\b|material\s*supply|material\s*purchase", re.I)


def _customer_id_for_name(name: str) -> str:
    digest = hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"cust_{digest}"


def _is_rm_description(text: str) -> bool:
    return bool(_RM_ROW_RE.search(text or ""))


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def get_or_create_customer(conn: sqlite3.Connection, customer_name: str) -> str:
    """Return customers.id; insert a row when the name is new (no invented pricing)."""
    norm = (customer_name or "").strip()
    if not norm:
        cid = f"cust_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO customers (id, name, gstin, currency, status)
            VALUES (?, ?, NULL, 'INR', 'active')
            """,
            (cid, "Unknown customer"),
        )
        return cid
    row = conn.execute(
        """
        SELECT customer_id FROM customer_aliases WHERE alias = ? COLLATE NOCASE LIMIT 1
        """,
        (norm,),
    ).fetchone()
    if row:
        return str(row["customer_id"])
    row = conn.execute(
        """
        SELECT id FROM customers WHERE name = ? COLLATE NOCASE LIMIT 1
        """,
        (norm,),
    ).fetchone()
    if row:
        return str(row["id"])
    cid = _customer_id_for_name(norm)
    conn.execute(
        """
        INSERT OR IGNORE INTO customers (id, name, gstin, currency, status)
        VALUES (?, ?, NULL, 'INR', 'active')
        """,
        (cid, norm),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO customer_aliases (customer_id, alias, source)
        VALUES (?, ?, 'quote_build')
        """,
        (cid, norm),
    )
    return cid


def _machine_id_for_type(conn: sqlite3.Connection, machine: str) -> str | None:
    norm = (machine or "").strip()
    if not norm:
        return None
    row = conn.execute(
        """
        SELECT id FROM machines
        WHERE machine_type = ? COLLATE NOCASE OR name = ? COLLATE NOCASE
        LIMIT 1
        """,
        (norm, norm),
    ).fetchone()
    return str(row["id"]) if row else None


def _delivery_days_from_session(session_id: str) -> int | None:
    for mem in db.list_memories(session_id, limit=50):
        if mem.get("key") != "last_quote_delivery_days":
            continue
        raw = str(mem.get("value") or "").strip()
        if not raw:
            return None
        try:
            days = int(float(raw))
        except ValueError:
            return None
        return days if days > 0 else None
    return None


def persist_built_quote(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    artifact_id: str,
    rows: list[list[Any]],
    customer: str,
    part_name: str,
    material: str,
    scope: str,
    rm_source: str = "",
    rm_source_note: str = "",
    rm_price: Any = "",
    machine: str = "",
    machining_rate: Any = "",
) -> str:
    """Insert quotes + quote_revisions + quote_lines; return quote_revisions.id."""
    customer_id = get_or_create_customer(conn, customer)
    quote_id = f"q_{uuid.uuid4().hex[:12]}"
    revision_id = f"qrev_{uuid.uuid4().hex[:12]}"
    scope_norm = (scope or "").strip().lower()
    if scope_norm not in {"labour", "with_material"}:
        scope_norm = "labour"
    delivery_days = _delivery_days_from_session(session_id)
    meta = {
        "part_name": part_name or "Component",
        "material": material or "",
        "rm_source": (rm_source or "").strip().lower(),
        "rm_source_note": (rm_source_note or "").strip(),
        "rm_price": str(rm_price).strip() if rm_price is not None and str(rm_price).strip() else "",
        "machine": (machine or "").strip(),
        "machining_rate": str(machining_rate).strip()
        if machining_rate is not None and str(machining_rate).strip()
        else "",
        "spreadsheet_artifact_id": artifact_id,
    }
    conn.execute(
        """
        INSERT INTO quotes (id, customer_id, rfq_ref, mail_id, conversation_id, status)
        VALUES (?, ?, NULL, NULL, ?, 'open')
        """,
        (quote_id, customer_id, session_id),
    )
    qty_total = 0
    total_minor = 0
    line_rows: list[tuple[Any, ...]] = []
    machine_id = _machine_id_for_type(conn, machine)
    for seq, row in enumerate(rows, start=1):
        desc = str(row[0]) if row else ""
        mat = str(row[1]) if len(row) > 1 else material
        qty = _parse_numeric(row[2] if len(row) > 2 else 1) or 1.0
        unit = _parse_numeric(row[3] if len(row) > 3 else None)
        rate_minor = int(round((unit or 0) * 100))
        amount_minor = int(round(qty * (unit or 0) * 100))
        if _is_rm_description(desc):
            kind = "material"
        elif machine_id and not _is_rm_description(desc):
            kind = "machining"
        else:
            kind = "other"
        line_id = f"ql_{uuid.uuid4().hex[:12]}"
        line_machine = machine_id if kind == "machining" else None
        line_rows.append(
            (
                line_id,
                revision_id,
                seq,
                kind,
                desc or part_name or "Line",
                qty,
                "pc",
                rate_minor,
                amount_minor,
                line_machine,
                None,
                "owner_input",
                artifact_id,
                0,
                "",
            )
        )
        qty_total += int(qty) if qty == int(qty) else max(1, int(qty))
        total_minor += amount_minor
    if qty_total <= 0:
        qty_total = 1
    conn.execute(
        """
        INSERT INTO quote_revisions (
          id, quote_id, revision, part_revision_id, routing_id,
          scope, scope_source, qty, currency, total_minor, margin_pct,
          delivery_days, delivery_entered_by, delivery_entered_at,
          notes, frozen, pdf_artifact_id, pdf_sha256
        ) VALUES (
          ?, ?, 1, NULL, NULL,
          ?, 'owner_input', ?, 'INR', ?, NULL,
          ?, NULL, NULL,
          ?, 0, NULL, NULL
        )
        """,
        (
            revision_id,
            quote_id,
            scope_norm,
            qty_total,
            total_minor,
            delivery_days,
            json.dumps(meta),
        ),
    )
    conn.executemany(
        """
        INSERT INTO quote_lines (
          id, quote_revision_id, seq, kind, description,
          qty, qty_unit, rate_minor, amount_minor,
          machine_id, time_min, rate_source_kind, rate_source_id,
          is_estimate, estimate_basis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        line_rows,
    )
    return revision_id


def revision_id_from_session(session_id: str) -> str:
    for mem in db.list_memories(session_id, limit=50):
        if mem.get("key") == "last_quote_revision_id":
            return str(mem.get("value") or "").strip()
    return ""


def rows_from_lines(lines: list[sqlite3.Row]) -> list[list[Any]]:
    out: list[list[Any]] = []
    for ln in lines:
        rate = ln["rate_minor"] / 100.0
        out.append(
            [
                ln["description"],
                "",
                ln["qty"],
                rate if rate > 0 else "",
                "",
            ]
        )
    return out


def load_revision_facts(conn: sqlite3.Connection, revision_id: str) -> dict[str, Any] | None:
    """Facts verify_quote needs when masterdata is on."""
    rev = conn.execute(
        """
        SELECT qr.*, c.name AS customer_name
        FROM quote_revisions qr
        JOIN quotes q ON q.id = qr.quote_id
        JOIN customers c ON c.id = q.customer_id
        WHERE qr.id = ?
        """,
        (revision_id,),
    ).fetchone()
    if not rev:
        return None
    lines = conn.execute(
        """
        SELECT * FROM quote_lines
        WHERE quote_revision_id = ?
        ORDER BY seq
        """,
        (revision_id,),
    ).fetchall()
    meta: dict[str, Any] = {}
    if rev["notes"]:
        try:
            parsed = json.loads(rev["notes"])
            if isinstance(parsed, dict):
                meta = parsed
        except json.JSONDecodeError:
            meta = {}
    rows = rows_from_lines(lines)
    for row in rows:
        if len(row) > 1 and not str(row[1]).strip() and meta.get("material"):
            row[1] = meta["material"]
    return {
        "revision_id": revision_id,
        "artifact_id": meta.get("spreadsheet_artifact_id") or "",
        "rows": rows,
        "rows_raw": json.dumps(rows),
        "customer": rev["customer_name"] or "",
        "scope": (rev["scope"] or "").strip().lower(),
        "material": meta.get("material") or "",
        "part_name": meta.get("part_name") or "Component",
        "rm_source": meta.get("rm_source") or "",
        "rm_source_note": meta.get("rm_source_note") or "",
        "rm_price": meta.get("rm_price") or "",
        "machine": meta.get("machine") or "",
        "machining_rate": meta.get("machining_rate") or "",
        "delivery_days": rev["delivery_days"],
    }


def load_session_revision_facts(session_id: str) -> dict[str, Any] | None:
    if not settings.masterdata_enabled:
        return None
    rid = revision_id_from_session(session_id)
    if not rid:
        return None
    with db.connect() as conn:
        return load_revision_facts(conn, rid)


def machining_rate_for_revision(revision_id: str) -> str:
    with db.connect() as conn:
        facts = load_revision_facts(conn, revision_id)
    if not facts:
        return ""
    return str(facts.get("machining_rate") or "")
