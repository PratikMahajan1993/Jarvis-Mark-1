"""Quotation build: vision → sheet → PDF → verify → HITL email (foundation Phase 3)."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import db
from .config import settings
from .hermes.hitl import request_human_approval
from .memory.ingest import ingest_drawing_summary
from .tools import documents

_PLAYBOOK_ROOT = Path(__file__).resolve().parent / "hermes" / "playbooks" / "quote"
PLAYBOOK_NOTES_PATH = _PLAYBOOK_ROOT / "notes.md"
CLIENT_NAMES_PATH = _PLAYBOOK_ROOT / "files" / "client-names.md"
MHR_DEMO_PATH = _PLAYBOOK_ROOT / "files" / "mhr-demo.md"
MHR_ATTEST_PATH = _PLAYBOOK_ROOT / "files" / "mhr-demo-attestation.md"

_RM_ROW_RE = re.compile(r"raw\s*material|\brm\b|material\s*supply|material\s*purchase", re.I)


def pdf_file_sha256(path: str | Path) -> str | None:
    """SHA-256 hex digest of PDF file bytes, or None if not a readable file."""
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def quote_refuse_if_pdf_drift(
    session_id: str,
    pdf_path: str,
    verify_result: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a blocked verify-shaped result when PDF bytes differ from last verify binding."""
    expected = _latest_memory(session_id, "last_quote_pdf_sha256")
    if not expected:
        return None
    current = pdf_file_sha256(pdf_path) if pdf_path else None
    if current == expected:
        return None
    got = current or "missing"
    checks = list(verify_result.get("checks") or [])
    checks.append(
        _check(
            "pdf_sha256",
            False,
            f"PDF changed since verify (bound {expected[:16]}…, now {got[:16] if got != 'missing' else got})",
            "last_quote_pdf_path",
        )
    )
    return _finalize_verify(checks)


def _latest_memory(session_id: str, key: str) -> str:
    for mem in db.list_memories(session_id, limit=50):
        if mem.get("key") == key:
            return str(mem.get("value") or "")
    return ""


def _is_tbd(value: str) -> bool:
    text = (value or "").strip().lower()
    return not text or text in {"tbd", "n/a", "na", "unknown", "?"}


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or _is_tbd(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def analyze_drawing_vision(
    path: str,
    *,
    prompt: str = "",
    session_id: str = "",
    owner_spend: bool = False,
    customer_id: str | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """Cloud vision for dimensional notes — gated; default deny (owner_spend=False)."""
    from .vision.gate import dispatch_drawing_vision

    out = dispatch_drawing_vision(
        path,
        owner_spend=owner_spend,
        prompt=prompt,
        session_id=session_id,
        turn_id=turn_id,
        customer_id=customer_id,
        arrival="owner_bench",
        spent_by="owner_bench",
    )
    if out.get("ok") and out.get("summary"):
        file_path = Path(path)
        ingest_drawing_summary(
            file_path.name,
            str(out["summary"])[:2000],
            meta={"path": str(file_path)},
        )
    if session_id:
        file_path = Path(path)
        if file_path.is_file():
            db.add_memory(session_id, "last_quote_drawing", file_path.name)
            db.add_memory(session_id, "last_quote_drawing_path", str(file_path))
    return out


def _parse_mhr_demo_mins() -> dict[str, float]:
    path = MHR_DEMO_PATH
    if not path.is_file():
        return {}
    mins: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        head = parts[0].lower()
        if head in {"machine type", "---", "machine type (demo)"} or head.startswith("-"):
            continue
        rate = _parse_numeric(parts[1])
        if rate is not None:
            mins[parts[0].strip().lower()] = rate
    return mins


def _parse_mhr_attestation() -> dict[str, tuple[str, str]]:
    """Owner sign-off for the markdown MHR fallback. Empty means not attested."""
    path = MHR_ATTEST_PATH
    if not path.is_file():
        return {}
    signed: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            continue
        head = parts[0].lower()
        if not head or head in {"machine type", "---"} or set(head) <= {"-"}:
            continue
        signed[parts[0].strip().lower()] = (parts[1].strip(), parts[2].strip())
    return signed


def _row_item_text(row: list[Any]) -> str:
    return str(row[0]) if row else ""


def _is_rm_row(row: list[Any]) -> bool:
    return bool(_RM_ROW_RE.search(_row_item_text(row)))


def _rm_price_from_rows(rows: list[list[Any]]) -> float | None:
    for row in rows:
        if not _is_rm_row(row):
            continue
        if len(row) > 3:
            price = _parse_numeric(row[3])
            if price is not None and price > 0:
                return price
    return None


def get_customer_scope_default(customer_id: str = "", customer_name: str = "") -> str | None:
    """Customer labour/material default. ``ask``, a missing row, or master data off → None."""
    if not settings.masterdata_enabled:
        return None
    cid = (customer_id or "").strip()
    name = (customer_name or "").strip()
    with db.connect() as conn:
        if not cid and name:
            row = conn.execute(
                "SELECT customer_id FROM customer_aliases WHERE alias = ? COLLATE NOCASE LIMIT 1",
                (name,),
            ).fetchone()
            if row:
                cid = str(row["customer_id"])
            else:
                row = conn.execute(
                    "SELECT id FROM customers WHERE name = ? COLLATE NOCASE LIMIT 1",
                    (name,),
                ).fetchone()
                if row:
                    cid = str(row["id"])
        if not cid:
            return None
        terms = conn.execute(
            "SELECT default_scope FROM customer_terms WHERE customer_id = ?",
            (cid,),
        ).fetchone()
    if not terms:
        return None
    scope = str(terms["default_scope"] or "").strip().lower()
    if scope in {"labour", "with_material"}:
        return scope
    return None


def resolve_quote_scope(
    session_id: str,
    *,
    customer: str = "",
    scope: str = "",
    remember: bool = False,
) -> dict[str, Any]:
    """Explicit scope wins, then this order's saved choice, then the customer default."""
    chosen = (scope or "").strip().lower()
    if chosen in {"labour", "with_material"}:
        if remember and session_id:
            db.add_memory(session_id, "last_quote_scope", chosen)
        return {"ok": True, "scope": chosen, "source": "override"}
    remembered = _latest_memory(session_id, "last_quote_scope").strip().lower() if session_id else ""
    if remembered in {"labour", "with_material"}:
        return {"ok": True, "scope": remembered, "source": "order"}
    name = (customer or "").strip() or (_latest_memory(session_id, "last_quote_customer") if session_id else "")
    default = get_customer_scope_default(customer_name=name)
    if default:
        if remember and session_id:
            db.add_memory(session_id, "last_quote_scope", default)
        return {"ok": True, "scope": default, "source": "customer"}
    return {"ok": False, "need": "scope", "message": "Labour-only or with material?"}


def build_quote(
    *,
    session_id: str,
    part_name: str,
    material: str = "",
    vision_summary: str = "",
    line_items: list[dict[str, Any]] | None = None,
    customer: str = "",
    scope: str = "",
    rm_source: str = "",
    rm_source_note: str = "",
    rm_price: Any = "",
    machine: str = "",
    machining_rate: Any = "",
) -> dict[str, Any]:
    """Create a local quotation spreadsheet artifact (live Sheet bind can follow)."""
    resolved = resolve_quote_scope(session_id, customer=customer, scope=scope, remember=True)
    if not resolved.get("ok"):
        return resolved
    scope = str(resolved["scope"])
    from .quote_ops import operation_line_items

    from_ops = operation_line_items(session_id, machining_rate=machining_rate)
    items = line_items or from_ops or [
        {
            "item": part_name or "Component",
            "material": material or "TBD",
            "qty": 1,
            "unit_price": "",
            "notes": (vision_summary or "")[:240],
        }
    ]
    rate_num = _parse_numeric(machining_rate)
    if rate_num is not None:
        for it in items:
            if it.get("outsource"):
                continue
            if _parse_numeric(it.get("unit_price")) is None:
                it["unit_price"] = rate_num
    rm_num = _parse_numeric(rm_price)
    scope_norm = scope
    if rm_num is not None and rm_num > 0 and scope_norm == "with_material":
        has_rm_row = any(_RM_ROW_RE.search(str(it.get("item") or "")) for it in items)
        if not has_rm_row:
            items.append(
                {
                    "item": "Raw material",
                    "material": material or "TBD",
                    "qty": 1,
                    "unit_price": rm_num,
                    "notes": "Material supply",
                }
            )
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
    if settings.masterdata_enabled:
        from .masterdata.quotes import persist_built_quote

        eff_scope = scope
        eff_rm_source = rm_source
        eff_rm_source_note = rm_source_note
        eff_rm_price = rm_price
        eff_machine = machine
        eff_machining_rate = machining_rate
        if not (eff_scope or "").strip():
            eff_scope = _latest_memory(session_id, "last_quote_scope")
        if not (eff_rm_source or "").strip():
            eff_rm_source = _latest_memory(session_id, "last_quote_rm_source")
        if not (eff_rm_source_note or "").strip():
            eff_rm_source_note = _latest_memory(session_id, "last_quote_rm_source_note")
        if eff_rm_price is None or not str(eff_rm_price).strip():
            eff_rm_price = _latest_memory(session_id, "last_quote_rm_price")
        if not (eff_machine or "").strip():
            eff_machine = _latest_memory(session_id, "last_quote_machine")
        if eff_machining_rate is None or not str(eff_machining_rate).strip():
            eff_machining_rate = _latest_memory(session_id, "last_quote_machining_rate")
        if not (customer or "").strip():
            customer = _latest_memory(session_id, "last_quote_customer")

        with db.connect() as conn:
            revision_id = persist_built_quote(
                conn,
                session_id=session_id,
                artifact_id=artifact["id"],
                rows=rows,
                customer=customer,
                part_name=part_name or "Component",
                material=material or str(items[0].get("material") or ""),
                scope=eff_scope,
                rm_source=eff_rm_source,
                rm_source_note=eff_rm_source_note,
                rm_price=eff_rm_price,
                machine=eff_machine,
                machining_rate=eff_machining_rate,
            )
        db.add_memory(session_id, "last_quote_revision_id", revision_id)
    else:
        db.add_memory(session_id, "last_quote", artifact["id"])
        db.add_memory(session_id, "last_quote_name", artifact["name"])
        db.add_memory(session_id, "last_quote_rows", json.dumps(rows))
        db.add_memory(session_id, "last_quote_columns", json.dumps(columns))
        db.add_memory(session_id, "last_quote_material", material or str(items[0].get("material") or ""))
        db.add_memory(session_id, "last_quote_customer", customer)
        db.add_memory(session_id, "last_quote_part_name", part_name or "Component")
        if (scope or "").strip():
            db.add_memory(session_id, "last_quote_scope", scope.strip().lower())
        if (rm_source or "").strip():
            db.add_memory(session_id, "last_quote_rm_source", rm_source.strip().lower())
        if (rm_source_note or "").strip():
            db.add_memory(session_id, "last_quote_rm_source_note", rm_source_note.strip())
        if rm_price is not None and str(rm_price).strip():
            db.add_memory(session_id, "last_quote_rm_price", str(rm_price).strip())
        if (machine or "").strip():
            db.add_memory(session_id, "last_quote_machine", machine.strip())
        if machining_rate is not None and str(machining_rate).strip():
            db.add_memory(session_id, "last_quote_machining_rate", str(machining_rate).strip())
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
        "scope": scope,
        "scope_source": resolved.get("source") or "",
    }
    return {"ok": True, **payload}


def _load_quote_rows(session_id: str) -> list[list[Any]]:
    if settings.masterdata_enabled:
        from .masterdata.quotes import load_session_revision_facts

        facts = load_session_revision_facts(session_id)
        if facts and facts.get("rows"):
            return list(facts["rows"])
    raw = _latest_memory(session_id, "last_quote_rows")
    if raw:
        try:
            rows = json.loads(raw)
            if isinstance(rows, list):
                return rows
        except json.JSONDecodeError:
            pass
    return []


def quote_to_pdf(*, session_id: str, part_name: str = "", rows: list[list[Any]] | None = None) -> dict[str, Any]:
    """Formal quotation PDF. Sections follow the shop-quote template. No invented address or terms."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    effective_rows = rows if rows is not None else _load_quote_rows(session_id)
    part = part_name or "Component"
    customer = ""
    if not part_name or True:
        if settings.masterdata_enabled:
            from .masterdata.quotes import load_session_revision_facts

            facts = load_session_revision_facts(session_id)
            if facts and facts.get("part_name") and not part_name:
                part = str(facts["part_name"])
            if facts and facts.get("customer"):
                customer = str(facts["customer"])
        if part == "Component":
            part = _latest_memory(session_id, "last_quote_part_name") or "Component"
        if not customer:
            customer = _latest_memory(session_id, "last_quote_customer")
    scope = _latest_memory(session_id, "last_quote_scope")
    material = _latest_memory(session_id, "last_quote_material")
    rm_note = _latest_memory(session_id, "last_quote_rm_source_note")
    delivery = _latest_memory(session_id, "last_quote_delivery_days")
    drawing = _latest_memory(session_id, "last_quote_drawing")
    issued = _quote_calendar_today().isoformat()
    styles = getSampleStyleSheet()
    total_style = ParagraphStyle("QuoteTotal", parent=styles["Title"], fontSize=16, leading=20, textColor=colors.HexColor("#0B1F33"))
    story: list[Any] = [
        Paragraph("QUOTATION", styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(f"Date: {issued}", styles["BodyText"]),
        Paragraph(f"Customer: {customer or '—'}", styles["BodyText"]),
        Paragraph(f"Part: {part}", styles["BodyText"]),
    ]
    if drawing:
        story.append(Paragraph(f"Drawing: {drawing}", styles["BodyText"]))
    story.append(Spacer(1, 4 * mm))
    scope_line = "Labour-only" if scope == "labour" else "With material" if scope == "with_material" else ""
    if scope_line:
        story.append(Paragraph(f"Scope: {scope_line}", styles["BodyText"]))
    if material:
        rm_line = f"Material: {material}"
        if rm_note:
            rm_line += f" — {rm_note}"
        story.append(Paragraph(rm_line, styles["BodyText"]))
    story.append(Spacer(1, 4 * mm))
    table_data = [["Item", "Material", "Qty", "Unit price", "Line total"]]
    grand = 0.0
    any_price = False
    for row in effective_rows:
        cells = [str(cell) for cell in row]
        while len(cells) < 4:
            cells.append("")
        qty = _parse_numeric(cells[2]) or 0
        unit = _parse_numeric(cells[3])
        line_total = ""
        if unit is not None and qty:
            amount = qty * unit
            grand += amount
            any_price = True
            line_total = f"INR {amount:,.2f}"
        table_data.append([cells[0], cells[1], cells[2], cells[3], line_total])
    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF5")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#8AA0B4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    if any_price:
        story.append(Paragraph(f"<b>Total Quoted Cost: INR {grand:,.2f}</b>", total_style))
    else:
        story.append(Paragraph("Total Quoted Cost: —", styles["BodyText"]))
    if delivery and not _is_tbd(delivery):
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"Delivery: {delivery} days", styles["BodyText"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Authorized signatory", styles["BodyText"]))
    name = f"Quote PDF — {part}-{uuid.uuid4().hex[:6]}.pdf"
    path = db.safe_export_path(name)
    SimpleDocTemplate(str(path), pagesize=A4, title=f"Quotation — {part}").build(story)
    artifact = db.add_artifact(uuid.uuid4().hex[:12], "pdf", name, str(path))
    db.add_memory(session_id, "last_quote_pdf", artifact["id"])
    db.add_memory(session_id, "last_quote_pdf_path", artifact["path"])
    return {"ok": True, "artifact": artifact, "total_inr": grand if any_price else None}


def _check(
    label: str,
    passed: bool,
    evidence: str,
    source: str,
    *,
    severity: str = "BLOCKER",
) -> dict[str, Any]:
    return {
        "id": label,
        "pass": passed,
        "evidence": evidence,
        "source": source,
        "severity": severity,
    }


def _normalize_stage(stage: str) -> str:
    norm = (stage or "draft").strip().lower()
    return norm if norm == "send" else "draft"


def _delivery_empty(session_id: str) -> bool:
    raw = _latest_memory(session_id, "last_quote_delivery_days").strip()
    return _is_tbd(raw)


def _rm_basis_applies(scope: str, rm_present: bool) -> bool:
    return rm_present or scope == "with_material"


_RM_BASIS_MAX_AGE_DAYS = 30
_RM_BASIS_WARN_AGE_DAYS = 25


def _quote_calendar_today() -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(settings.tz)).date()


def _parse_rm_basis_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _rm_basis_age_days(basis_date_raw: str) -> int | None:
    basis = _parse_rm_basis_date(basis_date_raw)
    if basis is None:
        return None
    return (_quote_calendar_today() - basis).days


def _rm_basis_date_check(
    basis_date: str,
    *,
    stage_norm: str,
) -> dict[str, Any]:
    age = _rm_basis_age_days(basis_date)
    if age is None:
        return _check(
            "rm_basis_date",
            False,
            f"Raw-material basis date is not a valid date ({basis_date[:40]})",
            "last_quote_rm_basis_date",
        )
    if age <= 24:
        return _check(
            "rm_basis_date",
            True,
            basis_date[:40],
            "last_quote_rm_basis_date",
        )
    if age <= _RM_BASIS_MAX_AGE_DAYS:
        return _check(
            "rm_basis_date",
            False,
            f"RM basis {age} day(s) old (dated {basis_date[:10]})",
            "last_quote_rm_basis_date",
            severity="WARN",
        )
    severity = "BLOCKER" if stage_norm == "send" else "WARN"
    return _check(
        "rm_basis_date",
        False,
        f"RM basis {age} day(s) old — max {_RM_BASIS_MAX_AGE_DAYS} (dated {basis_date[:10]})",
        "last_quote_rm_basis_date",
        severity=severity,
    )


def _finalize_verify(checks: list[dict[str, Any]]) -> dict[str, Any]:
    blocker_failures = [
        c for c in checks if not c["pass"] and c.get("severity", "BLOCKER") == "BLOCKER"
    ]
    warn_failures = [c for c in checks if not c["pass"] and c.get("severity") == "WARN"]
    stop = bool(blocker_failures)
    verdict = "block" if stop else "pass"
    failed_count = len(blocker_failures)
    checklist_items = [
        {
            "label": c["id"],
            "pass": c["pass"],
            "evidence": c["evidence"],
            "severity": c.get("severity", "BLOCKER"),
        }
        for c in checks
    ]
    scene = {
        "title": "Quote proof",
        "widgets": [
            {
                "type": "checklist",
                "title": "Quote proof",
                "items": checklist_items,
            }
        ],
    }
    return {
        "ok": True,
        "passed": failed_count == 0,
        "failed_count": failed_count,
        "warn_count": len(warn_failures),
        "stop": stop,
        "verdict": verdict,
        "checks": checks,
        "scene": scene,
    }


def _masterdata_customer_spelling_known(conn: sqlite3.Connection, customer: str) -> bool:
    """Owner-confirmed names/aliases only — not auto-provisioned quote_build rows."""
    norm = (customer or "").strip()
    if not norm:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM customer_aliases
        WHERE alias = ? COLLATE NOCASE AND COALESCE(source, '') != 'quote_build'
        LIMIT 1
        """,
        (norm,),
    ).fetchone()
    if row:
        return True
    row = conn.execute(
        """
        SELECT 1 FROM customers c
        WHERE c.name = ? COLLATE NOCASE
          AND EXISTS (
            SELECT 1 FROM customer_aliases a
            WHERE a.customer_id = c.id AND COALESCE(a.source, '') != 'quote_build'
          )
        LIMIT 1
        """,
        (norm,),
    ).fetchone()
    return row is not None


def _reference_client_names() -> list[str]:
    path = CLIENT_NAMES_PATH
    if not path.is_file():
        return []
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("-"):
            raw = raw.lstrip("- ").strip()
        if raw:
            names.append(raw)
    return names


def verify_quote(*, session_id: str, stage: str = "draft", to: str = "", subject: str = "") -> dict[str, Any]:
    """Deterministic quote proof — any BLOCKER failure sets stop."""
    stage_norm = _normalize_stage(stage)
    checks: list[dict[str, Any]] = []

    revision_facts: dict[str, Any] | None = None
    if settings.masterdata_enabled:
        from .masterdata.quotes import load_session_revision_facts

        revision_facts = load_session_revision_facts(session_id)

    def _fact(key: str) -> str:
        if revision_facts is not None and key in revision_facts:
            val = revision_facts.get(key)
            if val is None:
                return ""
            if key == "delivery_days" and isinstance(val, int):
                return str(val)
            return str(val)
        return _latest_memory(session_id, key)

    # 1. Line items / rows exist
    artifact_id = (
        str(revision_facts.get("artifact_id") or "")
        if revision_facts
        else _latest_memory(session_id, "last_quote")
    )
    rows_raw = (
        str(revision_facts.get("rows_raw") or "")
        if revision_facts
        else _latest_memory(session_id, "last_quote_rows")
    )
    rows: list[list[Any]] = []
    if revision_facts and revision_facts.get("rows"):
        rows = list(revision_facts["rows"])
    elif rows_raw:
        try:
            parsed = json.loads(rows_raw)
            if isinstance(parsed, list):
                rows = parsed
        except json.JSONDecodeError:
            rows = []
    rows_ok = bool(rows) and artifact_id
    if rows_ok:
        checks.append(_check("rows_exist", True, f"{len(rows)} row(s) in artifact {artifact_id}", "last_quote_rows"))
    else:
        checks.append(_check("rows_exist", False, "No quote rows or artifact id in session memory", "last_quote"))

    # 2. Unit prices — positive numeric required (zero/negative/absent ⇒ BLOCKER)
    price_failures: list[str] = []
    line_extended = 0.0
    qty_rate_failures: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if len(row) < 4:
            price_failures.append(f"row {idx}: missing price column")
            continue
        unit = row[3]
        qty = _parse_numeric(row[2] if len(row) > 2 else 1) or 1.0
        price = _parse_numeric(unit)
        if price is None:
            price_failures.append(f"absent unit_price row {idx}")
        elif price <= 0:
            price_failures.append(f"non-positive unit_price row {idx} ({price})")
        else:
            line_extended += qty * price
        if price is not None and price > 0 and len(row) >= 6:
            stated_total = _parse_numeric(row[4])
            if stated_total is not None:
                expected = qty * price
                if abs(stated_total - expected) > 0.009:
                    qty_rate_failures.append(
                        f"row {idx}: qty×rate {expected:g} ≠ line total {stated_total:g}"
                    )
    if rows and not price_failures:
        checks.append(
            _check(
                "unit_prices",
                True,
                f"All {len(rows)} row(s) have positive unit prices",
                "last_quote_rows",
            )
        )
    elif rows:
        checks.append(
            _check("unit_prices", False, "; ".join(price_failures[:5]), "last_quote_rows")
        )
    elif not rows_ok:
        checks.append(_check("unit_prices", False, "Skipped — no rows", "last_quote_rows"))

    if rows:
        if line_extended <= 0:
            checks.append(
                _check(
                    "quote_total",
                    False,
                    f"Quote total {line_extended:g} must be > 0",
                    "last_quote_rows",
                )
            )
        else:
            checks.append(
                _check(
                    "quote_total",
                    True,
                    f"Quote total {line_extended:g}",
                    "last_quote_rows",
                )
            )
        if qty_rate_failures:
            checks.append(
                _check(
                    "qty_rate_mismatch",
                    False,
                    "; ".join(qty_rate_failures[:5]),
                    "last_quote_rows",
                )
            )
        else:
            checks.append(
                _check(
                    "qty_rate_mismatch",
                    True,
                    "Line totals match qty × unit price where stated",
                    "last_quote_rows",
                )
            )

    # 3. Material grade present
    material = _fact("last_quote_material") if not revision_facts else _fact("material")
    if not material and rows:
        for row in rows:
            if len(row) > 1 and not _is_tbd(str(row[1])):
                material = str(row[1])
                break
    mat_ok = not _is_tbd(material)
    if mat_ok:
        checks.append(_check("material", True, material, "last_quote_material"))
    else:
        checks.append(_check("material", False, f"Material empty or TBD ({material or 'missing'})", "last_quote_material"))

    # 4. Drawing filename recorded
    drawing = _latest_memory(session_id, "last_quote_drawing")
    if drawing.strip():
        checks.append(_check("drawing", True, drawing, "last_quote_drawing"))
    else:
        checks.append(_check("drawing", False, "No drawing filename in session memory", "last_quote_drawing"))

    # 5. PDF artifact exists under exports
    pdf_id = _latest_memory(session_id, "last_quote_pdf")
    pdf_path = _latest_memory(session_id, "last_quote_pdf_path")
    art = db.get_artifact(pdf_id) if pdf_id else None
    if art:
        pdf_path = art.get("path") or pdf_path
    pdf_file = Path(pdf_path) if pdf_path else None
    exports_root = settings.exports_dir.resolve()
    pdf_ok = bool(pdf_file and pdf_file.is_file())
    if pdf_ok:
        try:
            pdf_ok = pdf_file.resolve().is_relative_to(exports_root)  # type: ignore[attr-defined]
        except AttributeError:
            pdf_ok = str(pdf_file.resolve()).startswith(str(exports_root))
    if pdf_ok:
        checks.append(_check("pdf", True, str(pdf_file), "last_quote_pdf"))
    else:
        checks.append(
            _check(
                "pdf",
                False,
                f"PDF missing or outside exports ({pdf_path or 'no path'})",
                "last_quote_pdf",
            )
        )

    # 6. Send not claimed sent — pending quote_send or not queued
    pending_rows = [p for p in db.list_pending(session_id) if p.get("kind") == "quote_send"]
    if pending_rows:
        pid = pending_rows[0]["id"]
        checks.append(
            _check("send_hitl", True, f"quote_send pending Authorize ({pid})", "pending_actions")
        )
    else:
        checks.append(_check("send_hitl", True, "not queued — must not claim emailed", "pending_actions"))

    # 7. Customer spelling — master data or client-names.md
    customer = _fact("last_quote_customer") if not revision_facts else _fact("customer")
    if settings.masterdata_enabled:
        from .masterdata import sync_client_names_if_enabled

        if not customer.strip():
            checks.append(_check("customer_spelling", False, "Customer name empty", "last_quote_customer"))
        else:
            with db.connect() as conn:
                sync_client_names_if_enabled(conn)
                known = _masterdata_customer_spelling_known(conn, customer)
            if known:
                checks.append(
                    _check(
                        "customer_spelling",
                        True,
                        f"'{customer}' matches master data",
                        "customer_aliases",
                    )
                )
            else:
                checks.append(
                    _check(
                        "customer_spelling",
                        False,
                        f"'{customer}' not in customer_aliases",
                        "customer_aliases",
                    )
                )
    else:
        ref_names = _reference_client_names()
        if not ref_names:
            checks.append(_check("customer_spelling", True, "no reference names", "client-names.md"))
        elif not customer.strip():
            checks.append(_check("customer_spelling", False, "Customer name empty", "last_quote_customer"))
        else:
            norm = customer.strip().lower()
            match = any(norm == n.lower() or norm in n.lower() or n.lower() in norm for n in ref_names)
            if match:
                checks.append(
                    _check("customer_spelling", True, f"'{customer}' matches reference list", "client-names.md")
                )
            else:
                checks.append(
                    _check(
                        "customer_spelling",
                        False,
                        f"'{customer}' not in client-names.md",
                        "client-names.md",
                    )
                )

    scope = (
        _fact("scope").strip().lower()
        if revision_facts
        else _latest_memory(session_id, "last_quote_scope").strip().lower()
    )
    rm_mem = _parse_numeric(
        _fact("rm_price") if revision_facts else _latest_memory(session_id, "last_quote_rm_price")
    )
    rm_row_price = _rm_price_from_rows(rows)
    rm_present = (rm_mem is not None and rm_mem > 0) or rm_row_price is not None

    if scope == "labour":
        if rm_present:
            detail = []
            if rm_mem is not None and rm_mem > 0:
                detail.append(f"memory rm_price={rm_mem}")
            if rm_row_price is not None:
                detail.append(f"row rm_price={rm_row_price}")
            checks.append(
                _check(
                    "scope_labour_no_rm",
                    False,
                    "Labour-only scope must not include raw-material cost (" + ", ".join(detail) + ")",
                    "last_quote_scope",
                )
            )
        else:
            checks.append(
                _check("scope_labour_no_rm", True, "Labour-only — no RM cost recorded", "last_quote_scope")
            )

    if scope == "with_material":
        if rm_present:
            checks.append(
                _check(
                    "scope_with_material_rm",
                    True,
                    f"RM cost present ({rm_mem if rm_mem else rm_row_price})",
                    "last_quote_rm_price",
                )
            )
        else:
            checks.append(
                _check(
                    "scope_with_material_rm",
                    False,
                    "With-material scope requires RM price (memory or RM line item)",
                    "last_quote_rm_price",
                )
            )

    if _rm_basis_applies(scope, rm_present):
        basis_date = _latest_memory(session_id, "last_quote_rm_basis_date").strip()
        if basis_date and not _is_tbd(basis_date):
            checks.append(_rm_basis_date_check(basis_date, stage_norm=stage_norm))
        else:
            checks.append(
                _check(
                    "rm_basis_date",
                    False,
                    "Raw-material price basis requires a dated evidence (supplier quote, invoice, or estimate)",
                    "last_quote_rm_basis_date",
                )
            )

    rm_source = (
        _fact("rm_source").strip().lower()
        if revision_facts
        else _latest_memory(session_id, "last_quote_rm_source").strip().lower()
    )
    if rm_source == "estimate":
        note = (
            _fact("rm_source_note").strip()
            if revision_facts
            else _latest_memory(session_id, "last_quote_rm_source_note").strip()
        )
        if note:
            checks.append(
                _check("rm_estimate_source", True, note[:120], "last_quote_rm_source_note")
            )
        else:
            checks.append(
                _check(
                    "rm_estimate_source",
                    False,
                    "RM estimate requires non-empty source note (historical / market)",
                    "last_quote_rm_source_note",
                )
            )

    for track in _rm_quote_track_checks(session_id):
        checks.append(track)
    from .quote_ops import outsource_checks

    checks.extend(outsource_checks(session_id))

    machine = (
        _fact("machine").strip()
        if revision_facts
        else _latest_memory(session_id, "last_quote_machine").strip()
    )
    mhr_rate = _parse_numeric(
        _fact("machining_rate")
        if revision_facts
        else _latest_memory(session_id, "last_quote_machining_rate")
    )
    if machine or mhr_rate is not None:
        if not machine:
            checks.append(
                _check(
                    "mhr_machine",
                    False,
                    "Machining rate recorded but machine type is missing",
                    "last_quote_machine",
                )
            )
        elif mhr_rate is None:
            checks.append(
                _check(
                    "mhr_rate",
                    False,
                    f"Machine {machine!r} recorded but machining rate is missing",
                    "last_quote_machining_rate",
                )
            )
        else:
            if settings.masterdata_enabled:
                from datetime import datetime
                from zoneinfo import ZoneInfo

                from .masterdata.mhr_lookup import (
                    machine_hour_rate_as_of,
                    mhr_rate_is_sendable_as_of,
                    sync_mhr_demo_if_enabled,
                )

                as_of = datetime.now(ZoneInfo(settings.tz)).date().isoformat()
                with db.connect() as conn:
                    sync_mhr_demo_if_enabled(conn)
                    rate_row = machine_hour_rate_as_of(conn, machine_type=machine, as_of=as_of)
                    floor = (
                        rate_row["min_mhr_minor"] / 100.0 if rate_row is not None else None
                    )
                mhr_source = "machine_hour_rates"
                if floor is None:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            f"Machine {machine!r} has no effective MHR floor as of {as_of}",
                            mhr_source,
                        )
                    )
                elif not mhr_rate_is_sendable_as_of(rate_row):
                    seed_note = ""
                    if rate_row and rate_row["shipped_seed_value_minor"] is not None:
                        if rate_row["min_mhr_minor"] == rate_row["shipped_seed_value_minor"]:
                            seed_note = " (still the shipped demo seed value)"
                    if rate_row and not rate_row["attested_by"]:
                        msg = (
                            f"{machine} MHR floor {floor} as of {as_of} is not owner-attested"
                            f"{seed_note}"
                        )
                    else:
                        msg = (
                            f"{machine} MHR floor {floor} as of {as_of} cannot price a send"
                            f"{seed_note}"
                        )
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            msg,
                            mhr_source,
                        )
                    )
                elif mhr_rate >= floor:
                    att_date = (rate_row["attested_at"] or "")[:10] if rate_row else ""
                    att_note = f", attested {att_date}" if att_date else ""
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            True,
                            f"{machine} rate {mhr_rate} ≥ floor {floor} (as of {as_of}{att_note})",
                            mhr_source,
                        )
                    )
                else:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            f"{machine} rate {mhr_rate} below floor {floor} (as of {as_of})",
                            mhr_source,
                        )
                    )
            else:
                demo_mins = _parse_mhr_demo_mins()
                attestation = _parse_mhr_attestation()
                floor = demo_mins.get(machine.lower())
                signed_by, signed_on = attestation.get(machine.lower(), ("", ""))
                if floor is None:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            f"Machine {machine!r} is not listed in mhr-demo.md",
                            "mhr-demo.md",
                        )
                    )
                elif not signed_by or not signed_on:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            f"{machine} MHR floor {floor} is not owner-attested (mhr-demo-attestation.md)",
                            "mhr-demo-attestation.md",
                        )
                    )
                elif mhr_rate >= floor:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            True,
                            f"{machine} rate {mhr_rate} ≥ demo minimum {floor}, attested {signed_on} by {signed_by}",
                            "mhr-demo-attestation.md",
                        )
                    )
                else:
                    checks.append(
                        _check(
                            "mhr_demo_floor",
                            False,
                            f"{machine} rate {mhr_rate} below demo minimum {floor}",
                            "mhr-demo.md",
                        )
                    )

    delivery_missing = _delivery_empty(session_id)
    if revision_facts and revision_facts.get("delivery_days") is not None:
        delivery_missing = False
    if delivery_missing:
        delivery_sev = "BLOCKER" if stage_norm == "send" else "WARN"
        checks.append(
            _check(
                "delivery_days",
                False,
                "Delivery time not entered — owner must type it (never computed)",
                "last_quote_delivery_days",
                severity=delivery_sev,
            )
        )
    else:
        if revision_facts and revision_facts.get("delivery_days") is not None:
            delivery_val = str(revision_facts["delivery_days"])
        else:
            delivery_val = _latest_memory(session_id, "last_quote_delivery_days").strip()
        checks.append(
            _check(
                "delivery_days",
                True,
                delivery_val[:80],
                "last_quote_delivery_days",
            )
        )

    digest_now = pdf_file_sha256(pdf_file) if pdf_ok and pdf_file else ""
    if (to or "").strip() and digest_now:
        duplicate = duplicate_delivery_warning(to, subject, digest_now)
        if duplicate:
            checks.append(
                _check(
                    "duplicate_delivery",
                    False,
                    duplicate,
                    "external_effects",
                    severity="WARN",
                )
            )
        else:
            checks.append(
                _check(
                    "duplicate_delivery",
                    True,
                    "No identical delivery in the last 30 days",
                    "external_effects",
                    severity="WARN",
                )
            )

    result = _finalize_verify(checks)
    if pdf_ok and pdf_file:
        digest = pdf_file_sha256(pdf_file)
        if digest:
            result["pdf_sha256"] = digest
            if stage_norm != "send":
                db.add_memory(session_id, "last_quote_pdf_sha256", digest)
    return result


_DRAWING_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
    ".dwg",
    ".dxf",
    ".step",
    ".stp",
}
_DRAWING_ASK = "Which drawing — inbox attachment, file on desk, or photo?"


def _drawing_filename(name: str) -> bool:
    return Path(name or "").suffix.lower() in _DRAWING_SUFFIXES


def _hint_matches(part_hint: str, filename: str) -> bool:
    hint = (part_hint or "").strip().lower()
    if len(hint) < 2:
        return False
    name = Path(filename or "").name.lower()
    if not name:
        return False
    return hint in name or hint in Path(name).stem


def _existing_file(raw: str) -> Path | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        path = Path(text).resolve()
    except OSError:
        return None
    return path if path.is_file() else None


def _resolve_provided_path(drawing_path: str) -> Path | None:
    raw = (drawing_path or "").strip()
    if not raw:
        return None
    direct = _existing_file(raw)
    if direct:
        return direct
    given = Path(raw)
    if given.is_absolute():
        return None
    exports = settings.exports_dir.resolve()
    for candidate in (exports / raw, exports / "drawings" / given.name):
        found = _existing_file(str(candidate))
        if found:
            return found
    return None


def _candidate(path: str, filename: str, source: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"path": path, "filename": filename, "source": source}
    row.update(extra)
    return row


def _remember_drawing(session_id: str, path: Path) -> None:
    if not session_id:
        return
    db.add_memory(session_id, "last_quote_drawing", path.name)
    db.add_memory(session_id, "last_quote_drawing_path", str(path))


def _found(session_id: str, path: Path, source: str) -> dict[str, Any]:
    resolved = path.resolve()
    _remember_drawing(session_id, resolved)
    return {
        "ok": True,
        "path": str(resolved),
        "filename": resolved.name,
        "source": source,
    }


def _ask(candidates: list[dict[str, Any]], message: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "need": "path",
        "candidates": candidates,
        "message": message or _DRAWING_ASK,
    }


def _focus_drawing_rows(session_id: str) -> list[dict[str, Any]]:
    """Drawings the desk is showing. The tool session's own sheet comes first."""
    own = db.get_conversation_by_session(session_id) if session_id else None
    ordered: list[dict[str, Any]] = []
    if own and own.get("category") == "drawing" and own.get("status") != "archived":
        ordered.append(own)
    own_id = str(own.get("id") or "") if own else ""
    for row in db.list_conversations():
        if row.get("category") != "drawing" or row.get("status") == "archived":
            continue
        if row.get("minimized"):
            continue
        if str(row.get("id") or "") == own_id:
            continue
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        if focus.get("viewing") is False:
            continue
        ordered.append(row)
    return ordered


def _row_drawing_file(row: dict[str, Any]) -> Path | None:
    from .conversations import _local_path

    focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
    return _local_path(focus)


def _unique_files(items: list[tuple[Path, dict[str, Any]]]) -> list[tuple[Path, dict[str, Any]]]:
    seen: set[str] = set()
    out: list[tuple[Path, dict[str, Any]]] = []
    for path, meta in items:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((path.resolve(), meta))
    return out


def _named_disk_hits(part_hint: str) -> list[tuple[Path, dict[str, Any]]]:
    hint = (part_hint or "").strip()
    if len(hint) < 2:
        return []
    found: list[tuple[Path, dict[str, Any]]] = []
    exports = settings.exports_dir.resolve()
    if exports.is_dir():
        for path in exports.rglob("*"):
            if path.is_file() and _drawing_filename(path.name) and _hint_matches(hint, path.name):
                found.append((path, _candidate(str(path.resolve()), path.name, "named_search")))
    for row in db.list_inbox_files(40):
        name = str(row.get("name") or "")
        raw = str(row.get("path") or "")
        if not _hint_matches(hint, name) or not _drawing_filename(name):
            continue
        path = _existing_file(raw)
        if path:
            found.append((path, _candidate(str(path), path.name, "inbox_file")))
    for row in db.list_conversations():
        if row.get("category") != "drawing" or row.get("status") == "archived":
            continue
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        label = str(focus.get("filename") or focus.get("local_name") or row.get("title") or "")
        if not _hint_matches(hint, label):
            continue
        path = _row_drawing_file(row)
        if path and _drawing_filename(path.name):
            found.append((path, _candidate(str(path), path.name, "named_search")))
    return _unique_files(found)


def _mail_drawing_hits(session_id: str, part_hint: str) -> list[dict[str, Any]]:
    """Drawing attachments on the open mail, or filename matches when a hint is set."""
    from .connectors import email as email_conn
    from .mail_attachments import get_mail_context
    from .rfq import attachment_is_drawing

    hint = (part_hint or "").strip()
    mails: list[dict[str, Any]] = []
    ctx = get_mail_context(session_id) if session_id else {}
    open_id = str(ctx.get("email_id") or "")
    if hint:
        try:
            mails = list(email_conn.search_emails(query="", limit=30))
        except Exception:
            mails = []
    elif open_id:
        opened = email_conn.get_email(open_id)
        if opened:
            mails.append(opened)
    if open_id and hint and all(str(mail.get("id") or "") != open_id for mail in mails):
        opened = email_conn.get_email(open_id)
        if opened:
            mails.append(opened)
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mail in mails:
        mail_id = str(mail.get("id") or "")
        for att in mail.get("attachments") or []:
            if not isinstance(att, dict) or not attachment_is_drawing(att):
                continue
            filename = str(att.get("filename") or att.get("local_name") or "")
            if hint and not _hint_matches(hint, filename):
                continue
            att_id = str(att.get("attachment_id") or "")
            key = f"{mail_id}:{att_id or filename.lower()}"
            if key in seen:
                continue
            seen.add(key)
            local = _existing_file(str(att.get("local_path") or ""))
            hits.append(
                _candidate(
                    str(local) if local else "",
                    filename or (local.name if local else "drawing"),
                    "mail_attachment",
                    mail_id=mail_id,
                    attachment_id=att_id,
                    on_disk=bool(local),
                )
            )
    return hits


def _save_one_mail_drawing(session_id: str, hit: dict[str, Any]) -> Path | None:
    from .mail_attachments import save_attachments

    mail_id = str(hit.get("mail_id") or "")
    att_id = str(hit.get("attachment_id") or "")
    filename = str(hit.get("filename") or "")
    if not mail_id or not session_id:
        return None
    ids = [att_id] if att_id else None
    names = [filename] if filename and not att_id else None
    try:
        result = save_attachments(
            session_id,
            email_id=mail_id,
            attachment_ids=ids,
            filenames=names,
            local=True,
            drive=False,
        )
    except Exception:
        return None
    for item in result.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        if filename and str(item.get("filename") or "").lower() != filename.lower():
            if att_id and str(item.get("attachment_id") or "") != att_id:
                continue
        path = _existing_file(str(item.get("local_path") or ""))
        if path:
            return path
    return None


def find_drawing_for_quote(
    session_id: str,
    part_hint: str = "",
    drawing_path: str = "",
) -> dict[str, Any]:
    """Resolve one drawing file. Stop at the first clear hit. Several matches ask.

    Order: provided path → Engineering focus → named search → save one mail
    attachment → ask. Never picks the newest file when more than one matches.
    """
    provided = (drawing_path or "").strip()
    if provided:
        path = _resolve_provided_path(provided)
        if path is None:
            return _ask([], f"That path is not a file on disk: {provided}")
        return _found(session_id, path, "provided_path")

    focus_hits: list[tuple[Path, dict[str, Any]]] = []
    own = db.get_conversation_by_session(session_id) if session_id else None
    own_id = str(own.get("id") or "") if own else ""
    for row in _focus_drawing_rows(session_id):
        path = _row_drawing_file(row)
        if not path:
            continue
        focus = row.get("focus") if isinstance(row.get("focus"), dict) else {}
        label = str(focus.get("filename") or focus.get("local_name") or path.name)
        focus_hits.append((path, _candidate(str(path), label, "focus")))
        if own_id and str(row.get("id") or "") == own_id:
            return _found(session_id, path, "focus")
    focus_hits = _unique_files(focus_hits)
    if len(focus_hits) == 1:
        return _found(session_id, focus_hits[0][0], "focus")
    if len(focus_hits) > 1:
        hint = (part_hint or "").strip()
        named = [(path, meta) for path, meta in focus_hits if hint and _hint_matches(hint, meta["filename"])]
        if len(named) == 1:
            return _found(session_id, named[0][0], "focus")
        if named:
            return _ask([meta for _path, meta in named], "Several drawings are on the desk. Which one?")
        if not hint:
            return _ask(
                [meta for _path, meta in focus_hits],
                "Several drawings are on the desk. Which one?",
            )

    disk_hits = _named_disk_hits(part_hint)
    mail_hits = _mail_drawing_hits(session_id, part_hint)
    mail_on_disk = [
        (_existing_file(str(hit.get("path") or "")), hit)
        for hit in mail_hits
        if hit.get("on_disk") and _existing_file(str(hit.get("path") or ""))
    ]
    combined = _unique_files(disk_hits + [(path, hit) for path, hit in mail_on_disk if path])
    if len(combined) == 1:
        return _found(session_id, combined[0][0], "named_search")
    if len(combined) > 1:
        return _ask([meta for _path, meta in combined], "Several drawings match. Which one?")

    unsaved = [hit for hit in mail_hits if not hit.get("on_disk")]
    if len(unsaved) == 1:
        saved = _save_one_mail_drawing(session_id, unsaved[0])
        if saved:
            return _found(session_id, saved, "mail_attachment")
        return _ask(unsaved, "The mail drawing is not on disk yet, and I could not save it.")
    if len(unsaved) > 1:
        return _ask(unsaved, "Several mail drawings match. Which attachment should I save?")

    if len(focus_hits) > 1:
        return _ask(
            [meta for _path, meta in focus_hits],
            "Several drawings are on the desk. Which one?",
        )
    return _ask([])


_ESTIMATE_BASIS_RE = re.compile(r"historical|market", re.I)


def _rm_rows(session_id: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM rm_quote_requests WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_rm_quote_requests(session_id: str) -> dict[str, Any]:
    return {"ok": True, "requests": _rm_rows(session_id)}


def _rm_quote_track_checks(session_id: str) -> list[dict[str, Any]]:
    received = [row for row in _rm_rows(session_id) if row.get("status") == "received"]
    if not received:
        return []
    priced = [
        row
        for row in received
        if not int(row.get("is_estimate") or 0) and int(row.get("quoted_price_minor") or 0) > 0
    ]
    if priced:
        supplier = str(priced[-1].get("supplier") or "supplier")
        return [_check("rm_quote_track", True, f"Supplier quote from {supplier}", "rm_quote_requests")]
    bad = [
        row
        for row in received
        if not int(row.get("is_estimate") or 0)
        or not str(row.get("notes") or "").strip()
        or not _ESTIMATE_BASIS_RE.search(str(row.get("notes") or ""))
    ]
    if bad:
        return [
            _check(
                "rm_quote_track",
                False,
                "Estimate must be labelled and name historical transactions or market trend",
                "rm_quote_requests",
            )
        ]
    return [_check("rm_quote_track", True, "Estimate labelled from historical or market basis", "rm_quote_requests")]


def request_rm_quote(
    session_id: str,
    *,
    material: str,
    supplier: str,
    supplier_email: str,
    customer: str = "",
) -> dict[str, Any]:
    """Open a raw-material request and queue the supplier email. Does not send."""
    grade = (material or "").strip()
    who = (supplier or "").strip()
    email = (supplier_email or "").strip()
    if not grade or not who or not email or "@" not in email:
        return {
            "ok": False,
            "need": "rm_request",
            "message": "Need material, supplier, and a supplier email before I can request a quote.",
        }
    customer_id = None
    if settings.masterdata_enabled and (customer or "").strip():
        customer_id = None
        with db.connect() as conn:
            row = conn.execute(
                "SELECT customer_id FROM customer_aliases WHERE alias = ? COLLATE NOCASE LIMIT 1",
                (customer.strip(),),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT id AS customer_id FROM customers WHERE name = ? COLLATE NOCASE LIMIT 1",
                    (customer.strip(),),
                ).fetchone()
            if row:
                customer_id = str(row["customer_id"])
    request_id = f"rmq-{uuid.uuid4().hex[:12]}"
    created = db.utc_now()
    body = (
        f"Dear {who},\n\n"
        f"Please quote raw material: {grade}.\n"
        "Reply with price, currency, and the date of the quote.\n\n"
        "Regards"
    )
    pending = request_human_approval(
        session_id=session_id,
        kind="email_send",
        title=f"Request RM quote: {grade}",
        summary=f"To {email}",
        payload={
            "to": email,
            "subject": f"Raw material quote — {grade}",
            "body": body,
            "attachment_paths": [],
            "rm_request_id": request_id,
        },
        tool_name="quote_request_rm_quote",
    )
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO rm_quote_requests (
              id, session_id, customer_id, material, supplier, supplier_email,
              status, currency, notes, is_estimate, source_kind, source_ref, pending_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'requested', 'INR', '', 0, '', '', ?, ?)
            """,
            (request_id, session_id, customer_id, grade, who, email, pending.get("id") or "", created),
        )
    return {
        "ok": True,
        "queued": True,
        "sent": False,
        "request_id": request_id,
        "pending": pending,
        "requests": _rm_rows(session_id),
    }


def _price_minor_inr(price_inr: Any) -> int | None:
    amount = _parse_numeric(price_inr)
    if amount is None or amount <= 0:
        return None
    return int(round(amount * 100))


def record_rm_quote(
    session_id: str,
    *,
    price_inr: Any = "",
    is_estimate: bool = False,
    notes: str = "",
    quote_date: str = "",
    request_id: str = "",
    material: str = "",
    supplier: str = "",
) -> dict[str, Any]:
    """Record a received supplier quote or a labelled estimate. Does not invent a price."""
    note = (notes or "").strip()
    when = (quote_date or "").strip()
    estimate = bool(is_estimate)
    if estimate and (not note or not _ESTIMATE_BASIS_RE.search(note)):
        return {
            "ok": False,
            "need": "rm_basis",
            "message": "An estimate must say whether it comes from historical transactions or market trend.",
        }
    minor = _price_minor_inr(price_inr)
    if minor is None:
        return {"ok": False, "need": "rm_price", "message": "Need the quoted price. I will not guess it."}
    if not when:
        return {"ok": False, "need": "rm_date", "message": "Need the quote date."}
    rows = _rm_rows(session_id)
    target: dict[str, Any] | None = None
    if request_id:
        target = next((row for row in rows if row.get("id") == request_id), None)
        if target is None:
            return {"ok": False, "need": "rm_request", "message": "That raw-material request is not on this quote."}
    else:
        open_rows = [row for row in rows if row.get("status") == "requested"]
        if len(open_rows) == 1:
            target = open_rows[0]
        elif len(open_rows) > 1:
            return {
                "ok": False,
                "need": "rm_request",
                "message": "Several raw-material requests are open. Which one arrived?",
                "candidates": [{"id": row["id"], "material": row["material"], "supplier": row["supplier"]} for row in open_rows],
            }
    received_at = db.utc_now()
    source_kind = "estimate" if estimate else "supplier_quote"
    if target:
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE rm_quote_requests
                SET status = 'received', quoted_price_minor = ?, quote_date = ?, received_at = ?,
                    notes = ?, is_estimate = ?, source_kind = ?, source_ref = ?
                WHERE id = ?
                """,
                (minor, when, received_at, note, 1 if estimate else 0, source_kind, note, target["id"]),
            )
        supplier_name = str(target.get("supplier") or supplier or "")
        grade = str(target.get("material") or material or "")
        request_id = str(target["id"])
    else:
        if not (material or "").strip() or not (supplier or "").strip():
            return {
                "ok": False,
                "need": "rm_request",
                "message": "Need the material and supplier to record a quote that was not requested here.",
            }
        request_id = f"rmq-{uuid.uuid4().hex[:12]}"
        supplier_name = supplier.strip()
        grade = material.strip()
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO rm_quote_requests (
                  id, session_id, customer_id, material, supplier, supplier_email, status,
                  quoted_price_minor, currency, quote_date, received_at, notes, is_estimate,
                  source_kind, source_ref, pending_id, created_at
                ) VALUES (?, ?, NULL, ?, ?, '', 'received', ?, 'INR', ?, ?, ?, ?, ?, ?, '', ?)
                """,
                (
                    request_id,
                    session_id,
                    grade,
                    supplier_name,
                    minor,
                    when,
                    received_at,
                    note,
                    1 if estimate else 0,
                    source_kind,
                    note,
                    received_at,
                ),
            )
    rupees = minor / 100
    db.add_memory(session_id, "last_quote_rm_price", f"{rupees:.2f}".rstrip("0").rstrip("."))
    db.add_memory(session_id, "last_quote_rm_source", "estimate" if estimate else "supplier")
    db.add_memory(session_id, "last_quote_rm_source_note", note or f"{supplier_name} quote")
    db.add_memory(session_id, "last_quote_rm_basis_date", when)
    db.add_memory(session_id, "last_quote_material", grade)
    return {
        "ok": True,
        "request_id": request_id,
        "quoted_price_minor": minor,
        "currency": "INR",
        "is_estimate": estimate,
        "requests": _rm_rows(session_id),
    }


def append_playbook_note(*, what_went_wrong: str, layer: str, change: str) -> dict[str, Any]:
    """Append one dated correction line to playbook notes.md (newest first)."""
    layer_norm = (layer or "process").strip().lower()
    if layer_norm not in {"process", "toolbox", "proof"}:
        layer_norm = "process"
    notes_path = PLAYBOOK_NOTES_PATH
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    header = "# Quote playbook notes\n\nCorrections newest first.\n\n"
    existing = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else header
    if not existing.startswith("#"):
        existing = header + existing
    date = datetime.now().strftime("%Y-%m-%d")
    safe_wrong = re.sub(r"\s+", " ", (what_went_wrong or "").strip())[:240]
    safe_change = re.sub(r"\s+", " ", (change or "").strip())[:240]
    line = f"- **{date}** [{layer_norm}] {safe_wrong} → {safe_change}\n"
    if "Corrections newest first." in existing:
        parts = existing.split("Corrections newest first.\n", 1)
        tail = parts[1] if len(parts) > 1 else "\n"
        body = parts[0] + "Corrections newest first.\n" + line + tail.lstrip("\n")
    else:
        body = header + line + existing.removeprefix(header)
    notes_path.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(notes_path), "line": line.strip()}


def _quote_rows_total(session_id: str) -> float | None:
    total = 0.0
    priced = False
    for row in _load_quote_rows(session_id):
        cells = list(row)
        if len(cells) < 4:
            continue
        qty = _parse_numeric(cells[2]) or 0
        unit = _parse_numeric(cells[3])
        if unit is not None and qty:
            total += qty * unit
            priced = True
    return total if priced else None


def delivery_hash(to: str, subject: str, pdf_sha256: str) -> str:
    raw = f"{(to or '').strip().lower()}{(subject or '').strip()}{pdf_sha256 or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def duplicate_delivery_warning(to: str, subject: str, pdf_sha256: str) -> str:
    """WARN text when the same recipient, subject, and PDF were sent in the last 30 days."""
    digest = delivery_hash(to, subject, pdf_sha256)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT created_at FROM external_effects
            WHERE delivery_hash = ? AND state = 'sent' AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (digest, cutoff),
        ).fetchone()
    if not row:
        return ""
    sent_on = str(row["created_at"] or "")[:10]
    return f"Identical quote sent to {to} on {sent_on}"


def quote_email_body(*, customer: str, part_name: str, total_inr: Any, sign_off: str = "") -> tuple[str, str]:
    part = part_name or "Component"
    total = _parse_numeric(total_inr)
    total_text = f"₹{total:,.2f}" if total is not None else "—"
    subject = f"Quotation — {part}"
    closing = (sign_off or "").strip() or "Jarvis"
    body = (
        f"Dear {customer or 'Customer'},\n\n"
        f"Please find attached our quotation for {part}.\n\n"
        f"Total Quoted Cost: {total_text}\n\n"
        "The detailed breakdown is in the attached PDF. Valid for 30 days.\n\n"
        f"Regards,\n{closing}"
    )
    return subject, body


def queue_quote_send(
    *,
    session_id: str,
    to: str,
    subject: str,
    body: str,
    pdf_path: str,
    verify_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pdf_sha256 = (verify_snapshot or {}).get("pdf_sha256")
    if not pdf_sha256 and pdf_path:
        pdf_sha256 = pdf_file_sha256(pdf_path)
    customer = _latest_memory(session_id, "last_quote_customer")
    part = _latest_memory(session_id, "last_quote_part_name") or "Component"
    if not (subject or "").strip() or not (body or "").strip():
        filled_subject, filled_body = quote_email_body(
            customer=customer,
            part_name=part,
            total_inr=_quote_rows_total(session_id),
        )
        subject = subject.strip() or filled_subject
        body = body.strip() or filled_body
    warning = ""
    digest_key = ""
    if pdf_sha256:
        digest_key = delivery_hash(to, subject, pdf_sha256)
        warning = duplicate_delivery_warning(to, subject, pdf_sha256)
    payload: dict[str, Any] = {
        "to": to,
        "subject": subject,
        "body": body,
        "attachment_paths": [pdf_path] if pdf_path else [],
        "verify": verify_snapshot or {},
        "blast_radius": 5,
        "duplicate_check": True,
    }
    if pdf_sha256:
        payload["pdf_sha256"] = pdf_sha256
    if digest_key:
        payload["delivery_hash"] = digest_key
    if warning:
        payload["duplicate_warning"] = warning
    pending = request_human_approval(
        session_id=session_id,
        kind="quote_send",
        title=f"Send quote: {subject}",
        summary=f"To {to} with PDF attachment",
        payload=payload,
        tool_name="quote_send",
    )
    return {"ok": True, "pending": pending, "queued": True, "sent": False}
