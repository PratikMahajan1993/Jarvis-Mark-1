"""Quotation build: vision → sheet → PDF → verify → HITL email (foundation Phase 3)."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
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

_RM_ROW_RE = re.compile(r"raw\s*material|\brm\b|material\s*supply|material\s*purchase", re.I)


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


def analyze_drawing_vision(path: str, *, prompt: str = "", session_id: str = "") -> dict[str, Any]:
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
        out = {"ok": True, "summary": text, "path": str(file_path), "name": file_path.name}
    except Exception as exc:
        # Offline / no key: deterministic stub from filename for dry-run
        stub = (
            f"Vision unavailable ({exc}). "
            f"File {file_path.name} queued for manual dimensional review."
        )
        ingest_drawing_summary(file_path.name, stub, meta={"path": str(file_path), "stub": True})
        out = {"ok": False, "error": str(exc), "summary": stub, "path": str(file_path), "name": file_path.name}
    if session_id:
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
    }
    return {"ok": True, **payload}


def _load_quote_rows(session_id: str) -> list[list[Any]]:
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
    effective_rows = rows if rows is not None else _load_quote_rows(session_id)
    part = part_name or _latest_memory(session_id, "last_quote_part_name") or "Component"
    body_lines = [f"Quotation: {part}", ""]
    for row in effective_rows:
        body_lines.append(" | ".join(str(c) for c in row))
    body = "\n".join(body_lines) or "Quotation"
    artifact = documents.create_pdf(f"Quote PDF — {part}", body)
    db.add_memory(session_id, "last_quote_pdf", artifact["id"])
    db.add_memory(session_id, "last_quote_pdf_path", artifact["path"])
    return {"ok": True, "artifact": artifact}


def _check(label: str, passed: bool, evidence: str, source: str) -> dict[str, Any]:
    return {"id": label, "pass": passed, "evidence": evidence, "source": source}


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


def verify_quote(*, session_id: str) -> dict[str, Any]:
    """Deterministic quote proof — no Gemini. Returns checklist + stop when >2 fails."""
    checks: list[dict[str, Any]] = []
    failed = 0

    # 1. Line items / rows exist
    artifact_id = _latest_memory(session_id, "last_quote")
    rows_raw = _latest_memory(session_id, "last_quote_rows")
    rows: list[list[Any]] = []
    if rows_raw:
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
        failed += 1
        checks.append(_check("rows_exist", False, "No quote rows or artifact id in session memory", "last_quote"))

    # 2. Numeric unit prices (fail on empty/TBD)
    price_failures: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if len(row) < 4:
            price_failures.append(f"row {idx}: missing price column")
            continue
        unit = row[3]
        qty = _parse_numeric(row[2] if len(row) > 2 else 1) or 1.0
        price = _parse_numeric(unit)
        if price is None:
            price_failures.append(f"empty unit_price row {idx}")
        elif qty > 0 and price >= 0:
            # sanity: numeric present
            pass
    if rows and not price_failures:
        checks.append(_check("unit_prices", True, f"All {len(rows)} row(s) have numeric unit prices", "last_quote_rows"))
    elif rows:
        failed += 1
        checks.append(
            _check("unit_prices", False, "; ".join(price_failures[:5]), "last_quote_rows")
        )
    elif not rows_ok:
        checks.append(_check("unit_prices", False, "Skipped — no rows", "last_quote_rows"))

    # 3. Material grade present
    material = _latest_memory(session_id, "last_quote_material")
    if not material and rows:
        for row in rows:
            if len(row) > 1 and not _is_tbd(str(row[1])):
                material = str(row[1])
                break
    mat_ok = not _is_tbd(material)
    if mat_ok:
        checks.append(_check("material", True, material, "last_quote_material"))
    else:
        failed += 1
        checks.append(_check("material", False, f"Material empty or TBD ({material or 'missing'})", "last_quote_material"))

    # 4. Drawing filename recorded
    drawing = _latest_memory(session_id, "last_quote_drawing")
    if drawing.strip():
        checks.append(_check("drawing", True, drawing, "last_quote_drawing"))
    else:
        failed += 1
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
        failed += 1
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

    # 7. Customer spelling vs client-names.md
    customer = _latest_memory(session_id, "last_quote_customer")
    ref_names = _reference_client_names()
    if not ref_names:
        checks.append(_check("customer_spelling", True, "no reference names", "client-names.md"))
    elif not customer.strip():
        failed += 1
        checks.append(_check("customer_spelling", False, "Customer name empty", "last_quote_customer"))
    else:
        norm = customer.strip().lower()
        match = any(norm == n.lower() or norm in n.lower() or n.lower() in norm for n in ref_names)
        if match:
            checks.append(_check("customer_spelling", True, f"'{customer}' matches reference list", "client-names.md"))
        else:
            failed += 1
            checks.append(
                _check(
                    "customer_spelling",
                    False,
                    f"'{customer}' not in client-names.md",
                    "client-names.md",
                )
            )

    scope = _latest_memory(session_id, "last_quote_scope").strip().lower()
    rm_mem = _parse_numeric(_latest_memory(session_id, "last_quote_rm_price"))
    rm_row_price = _rm_price_from_rows(rows)
    rm_present = (rm_mem is not None and rm_mem > 0) or rm_row_price is not None

    if scope == "labour":
        if rm_present:
            failed += 1
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
            failed += 1
            checks.append(
                _check(
                    "scope_with_material_rm",
                    False,
                    "With-material scope requires RM price (memory or RM line item)",
                    "last_quote_rm_price",
                )
            )

    rm_source = _latest_memory(session_id, "last_quote_rm_source").strip().lower()
    if rm_source == "estimate":
        note = _latest_memory(session_id, "last_quote_rm_source_note").strip()
        if note:
            checks.append(
                _check("rm_estimate_source", True, note[:120], "last_quote_rm_source_note")
            )
        else:
            failed += 1
            checks.append(
                _check(
                    "rm_estimate_source",
                    False,
                    "RM estimate requires non-empty source note (historical / market)",
                    "last_quote_rm_source_note",
                )
            )

    machine = _latest_memory(session_id, "last_quote_machine").strip()
    mhr_rate = _parse_numeric(_latest_memory(session_id, "last_quote_machining_rate"))
    if machine and mhr_rate is not None:
        demo_mins = _parse_mhr_demo_mins()
        floor = demo_mins.get(machine.lower())
        if floor is not None:
            if mhr_rate >= floor:
                checks.append(
                    _check(
                        "mhr_demo_floor",
                        True,
                        f"{machine} rate {mhr_rate} ≥ demo minimum {floor}",
                        "mhr-demo.md",
                    )
                )
            else:
                failed += 1
                checks.append(
                    _check(
                        "mhr_demo_floor",
                        False,
                        f"{machine} rate {mhr_rate} below demo minimum {floor}",
                        "mhr-demo.md",
                    )
                )

    stop = failed > 2
    checklist_items = [{"label": c["id"], "pass": c["pass"], "evidence": c["evidence"]} for c in checks]
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
        "passed": failed == 0,
        "failed_count": failed,
        "stop": stop,
        "checks": checks,
        "scene": scene,
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


def queue_quote_send(
    *,
    session_id: str,
    to: str,
    subject: str,
    body: str,
    pdf_path: str,
    verify_snapshot: dict[str, Any] | None = None,
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
            "verify": verify_snapshot or {},
        },
        tool_name="quote_send",
    )
    return {"ok": True, "pending": pending, "queued": True, "sent": False}
