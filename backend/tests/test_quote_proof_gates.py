from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.quote import build_quote, quote_to_pdf, verify_quote


def setup_module(_module=None):
    db.init_db()


def _minimal_send_ready(session: str, *, unit_price: float | str = 1500) -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer="Deepak",
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": "Bracket",
                "material": "EN8",
                "qty": 2,
                "unit_price": unit_price,
                "notes": "From drawing",
            }
        ],
    )
    quote_to_pdf(session_id=session, part_name="Bracket")


def test_zero_unit_price_blocks():
    session = "pg1-zero-price"
    _minimal_send_ready(session, unit_price=0)
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    assert result["stop"] is True
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "unit_prices" in failed


def test_machine_without_rate_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "pg1-machine-no-rate"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_machine", "Demo CNC vertical mill")
    db.add_memory(session, "last_quote_machining_rate", "")
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "mhr_rate" in failed


def test_rate_without_machine_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "pg1-rate-no-machine"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_machine", "")
    db.add_memory(session, "last_quote_machining_rate", "900")
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "mhr_machine" in failed


def test_machine_not_in_demo_table_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "pg1-unknown-machine"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_machine", "Mystery five-axis")
    db.add_memory(session, "last_quote_machining_rate", "1200")
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "mhr_demo_floor" in failed


def test_undated_rm_basis_blocks():
    session = "pg1-undated-rm"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_rm_basis_date", "")
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "rm_basis_date" in failed


def test_dated_rm_basis_stale_blocks_send():
    session = "pg1-old-dated-rm"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_rm_basis_date", "2020-01-01")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is False
    assert by_id["rm_basis_date"]["severity"] == "BLOCKER"
    assert result["stop"] is True


def test_missing_delivery_warns_draft_blocks_send(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "pg1-delivery-stage"
    _minimal_send_ready(session)
    db.add_memory(session, "last_quote_delivery_days", "")
    draft = verify_quote(session_id=session, stage="draft")
    send = verify_quote(session_id=session, stage="send")
    d_draft = {c["id"]: c for c in draft["checks"]}["delivery_days"]
    d_send = {c["id"]: c for c in send["checks"]}["delivery_days"]
    assert d_draft["severity"] == "WARN"
    assert draft["stop"] is False
    assert draft["verdict"] == "pass"
    assert d_send["severity"] == "BLOCKER"
    assert send["stop"] is True
    assert send["verdict"] == "block"


def test_qty_rate_mismatch_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "pg1-qty-rate"
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "7")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-02-01")
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer="Deepak",
        scope="labour",
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
    rows = db.list_memories(session)
    raw_rows = next(m["value"] for m in rows if m["key"] == "last_quote_rows")
    import json

    parsed = json.loads(raw_rows)
    parsed[0] = ["Bracket", "EN8", 2, 1500, 5000, "From drawing"]
    db.add_memory(session, "last_quote_rows", json.dumps(parsed))
    quote_to_pdf(session_id=session, part_name="Bracket")
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "block"
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "qty_rate_mismatch" in failed
