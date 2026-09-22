from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.quote import build_quote, pdf_file_sha256, quote_to_pdf, verify_quote
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def _minimal_send_ready(session: str) -> Path:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-09-13")
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
                "unit_price": 1500,
                "notes": "From drawing",
            }
        ],
    )
    quote_to_pdf(session_id=session, part_name="Bracket")
    pdf_path = db.list_memories(session, limit=50)
    path_str = ""
    for mem in pdf_path:
        if mem.get("key") == "last_quote_pdf_path":
            path_str = str(mem.get("value") or "")
            break
    assert path_str
    return Path(path_str)


def test_verify_records_pdf_sha256():
    session = "q3-verify-hash"
    _minimal_send_ready(session)
    result = verify_quote(session_id=session, stage="send")
    assert result["verdict"] == "pass"
    assert result.get("pdf_sha256")
    assert len(result["pdf_sha256"]) == 64


def test_mutated_pdf_blocks_send():
    session = "q3-drift-block"
    pdf_file = _minimal_send_ready(session)
    verify = verify_quote(session_id=session, stage="draft")
    assert verify["verdict"] == "pass"
    bound = verify["pdf_sha256"]

    data = pdf_file.read_bytes()
    pdf_file.write_bytes(data[:-1] + bytes([data[-1] ^ 0x01]))

    send = execute_tool(
        "quote_send",
        {"to": "deepak@example.com", "subject": "Quote Bracket", "body": "Please review."},
        session,
    )
    assert send.get("ok") is False
    assert "pdf" in (send.get("error") or "").lower()
    data_out = send.get("data") or {}
    assert data_out.get("verdict") == "block"
    assert data_out.get("stop") is True
    failed = {c["id"] for c in data_out.get("checks", []) if not c["pass"]}
    assert "pdf_sha256" in failed
    assert not db.list_pending(session)
    assert pdf_file_sha256(pdf_file) != bound


def test_queue_payload_carries_pdf_sha256():
    session = "q3-payload-hash"
    _minimal_send_ready(session)
    send = execute_tool(
        "quote_send",
        {"to": "deepak@example.com", "subject": "Quote Bracket", "body": "Please review."},
        session,
    )
    assert send.get("ok") is True
    pending = send.get("pending") or {}
    payload = pending.get("payload") or {}
    verify = payload.get("verify") or {}
    assert payload.get("pdf_sha256") == verify.get("pdf_sha256")
    db.set_pending_status(pending["id"], "rejected")
