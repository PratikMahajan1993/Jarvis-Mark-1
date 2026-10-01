from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


@pytest.fixture(scope="module", autouse=True)
def _isolated_cells_db():
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-cells-"))
    prev_data = settings.data_dir
    prev_exports = settings.exports_dir
    prev_canvas = settings.canvas_dir
    settings.data_dir = tmp / "data"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir = tmp / "exports"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.canvas_dir = tmp / "data" / "canvas"
    settings.canvas_dir.mkdir(parents=True, exist_ok=True)
    from app import db

    db.init_db()
    yield
    settings.data_dir = prev_data
    settings.exports_dir = prev_exports
    settings.canvas_dir = prev_canvas


from app import db
from app.quote import (
    build_quote,
    confirm_drawing_cell,
    init_drawing_cells,
    quote_to_pdf,
    store_send_gate_override,
    tag_drawing_cell_assumption,
    verify_quote,
)
from app.tools.registry import execute_tool
import app.quote as quote_mod

EXACT_CUSTOMER = "Deepak Industries Private Limited"
WRONG_CUSTOMER_NAME = "Deepak Industries Pvt Ltd"


def _ensure_exact_customer() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM customers WHERE name = ? LIMIT 1",
            (EXACT_CUSTOMER,),
        ).fetchone()
        if row:
            cid = str(row["id"])
        else:
            cid = f"cust_{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO customers (id, name, gstin, currency, status)
                VALUES (?, ?, NULL, 'INR', 'active')
                """,
                (cid, EXACT_CUSTOMER),
            )


def _build_with_material(session: str, *, customer: str = "Quote Cells Bench Co") -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer=customer,
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": "Bracket",
                "material": "EN8",
                "qty": 2,
                "unit_price": 1500,
                "notes": "From drawing",
            }
        ],
    )


def _confirm_hard_cells(session: str) -> None:
    init_drawing_cells(session)
    confirm_drawing_cell(session, "revision", "Rev B")
    confirm_drawing_cell(session, "quantity", "2")
    confirm_drawing_cell(session, "material", "EN8, as rolled")


def test_send_blocks_when_drawing_cells_never_initialized():
    session = "cells-null-hard-block"
    _build_with_material(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = verify_quote(session_id=session, stage="send")
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "drawing_cell_revision" in failed
    assert "drawing_cell_quantity" in failed
    assert "drawing_cell_material" in failed
    assert result["stop"] is True


def test_hard_cells_block_send_when_not_confirmed():
    session = "cells-hard-block"
    _build_with_material(session)
    init_drawing_cells(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = verify_quote(session_id=session, stage="send")
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "drawing_cell_revision" in failed
    assert "drawing_cell_quantity" in failed
    assert "drawing_cell_material" in failed
    assert result["stop"] is True


def test_hard_cells_pass_after_confirm():
    session = "cells-hard-ok"
    _build_with_material(session)
    _confirm_hard_cells(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    by_id = {c["id"]: c for c in verify_quote(session_id=session, stage="send")["checks"]}
    assert by_id["drawing_cell_revision"]["pass"] is True
    assert by_id["drawing_cell_quantity"]["pass"] is True
    assert by_id["drawing_cell_material"]["pass"] is True


def test_assumption_blocks_send_without_exact_customer_name():
    session = "cells-assumption-block"
    _ensure_exact_customer()
    _build_with_material(session)
    _confirm_hard_cells(session)
    tag_drawing_cell_assumption(session, "heat_treat", "HRC 58-62")
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["assumption_send_gate"]["pass"] is False
    assert result["stop"] is True


def test_assumption_send_after_exact_customer_name():
    session = "cells-assumption-ok"
    _ensure_exact_customer()
    _build_with_material(session)
    _confirm_hard_cells(session)
    tag_drawing_cell_assumption(session, "heat_treat", "HRC 58-62")
    quote_to_pdf(session_id=session, part_name="Bracket")
    store_send_gate_override(session, customer_exact_name=WRONG_CUSTOMER_NAME)
    blocked = verify_quote(session_id=session, stage="send")
    blocked_by_id = {c["id"]: c for c in blocked["checks"]}
    assert blocked_by_id["assumption_send_gate"]["pass"] is False
    store_send_gate_override(session, customer_exact_name=EXACT_CUSTOMER)
    ok = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in ok["checks"]}
    assert by_id["assumption_send_gate"]["pass"] is True
    assert by_id["pdf_assumptions_disclosed"]["pass"] is True


def test_stale_material_blocks_without_name_and_age(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 4))
    session = "cells-stale-rm-block"
    _ensure_exact_customer()
    _build_with_material(session)
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-30")
    _confirm_hard_cells(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is False
    assert by_id["rm_basis_date"]["severity"] == "BLOCKER"
    assert result["stop"] is True


def test_stale_material_send_after_exact_name_and_age(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 4))
    session = "cells-stale-rm-ok"
    _ensure_exact_customer()
    _build_with_material(session)
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-30")
    _confirm_hard_cells(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    store_send_gate_override(
        session,
        customer_exact_name=EXACT_CUSTOMER,
        rm_basis_age_ack="33",
    )
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is True
    assert by_id["rm_basis_date"]["source"] == "quote_revisions.send_gate_overrides_json"


def test_quote_send_refuses_when_hard_cells_block():
    session = "cells-send-refuse"
    _build_with_material(session)
    init_drawing_cells(session)
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = execute_tool(
        "quote_send",
        {"to": "buyer@example.com", "subject": "Quote Bracket"},
        session,
    )
    assert result.get("ok") is False
    assert not db.list_pending(session)
