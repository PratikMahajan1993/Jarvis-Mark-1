"""Raw-material quote request, receive, and labelled estimate."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-rmq-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app.quote import record_rm_quote, request_rm_quote, verify_quote
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def test_request_queues_and_does_not_send():
    result = request_rm_quote(
        "rmq-session",
        material="EN8",
        supplier="Acme Metals",
        supplier_email="quotes@acme.example",
    )
    assert result["ok"] is True
    assert result["sent"] is False
    assert result["queued"] is True
    assert result["pending"]["kind"] == "email_send"
    assert result["requests"][0]["status"] == "requested"
    assert result["requests"][0]["quoted_price_minor"] is None


def test_record_received_then_estimate_rules():
    session = "rmq-record"
    request_rm_quote(session, material="EN8", supplier="Acme Metals", supplier_email="q@acme.example")
    missing = record_rm_quote(session, price_inr="", quote_date="2026-09-20")
    assert missing["ok"] is False
    assert missing["need"] == "rm_price"

    bare_estimate = record_rm_quote(session, price_inr="80", quote_date="2026-09-20", is_estimate=True, notes="guess")
    assert bare_estimate["ok"] is False
    assert bare_estimate["need"] == "rm_basis"

    recorded = record_rm_quote(session, price_inr="84.5", quote_date="2026-09-20", notes="quote #123")
    assert recorded["ok"] is True
    assert recorded["quoted_price_minor"] == 8450
    assert recorded["is_estimate"] is False
    mems = {row["key"]: row["value"] for row in db.list_memories(session)}
    assert mems["last_quote_rm_source"] == "supplier"
    assert mems["last_quote_rm_price"] == "84.5"
    assert mems["last_quote_rm_basis_date"] == "2026-09-20"


def test_estimate_only_blocks_until_labelled():
    session = "rmq-estimate"
    record_rm_quote(
        session,
        material="EN8",
        supplier="Desk",
        price_inr="10",
        quote_date="2026-09-01",
        is_estimate=True,
        notes="market trend September",
    )
    db.add_memory(session, "last_quote_drawing", "fixture.pdf")
    db.add_memory(session, "last_quote_scope", "with_material")
    db.add_memory(session, "last_quote_delivery_days", "7")
    result = verify_quote(session_id=session)
    track = next(check for check in result["checks"] if check["id"] == "rm_quote_track")
    assert track["pass"] is True

    session_bad = "rmq-estimate-bad"
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO rm_quote_requests (
              id, session_id, material, supplier, supplier_email, status,
              quoted_price_minor, currency, quote_date, received_at, notes, is_estimate,
              source_kind, source_ref, pending_id, created_at
            ) VALUES ('bad-1', ?, 'EN8', 'Desk', '', 'received', 1000, 'INR', '2026-09-01', '2026-09-01T00:00:00Z', 'guess', 1, 'estimate', 'guess', '', '2026-09-01T00:00:00Z')
            """,
            (session_bad,),
        )
    bad = verify_quote(session_id=session_bad)
    track_bad = next(check for check in bad["checks"] if check["id"] == "rm_quote_track")
    assert track_bad["pass"] is False


def test_two_open_requests_ask():
    session = "rmq-two"
    request_rm_quote(session, material="EN8", supplier="A", supplier_email="a@example.com")
    request_rm_quote(session, material="MS", supplier="B", supplier_email="b@example.com")
    result = record_rm_quote(session, price_inr="10", quote_date="2026-09-20")
    assert result["ok"] is False
    assert result["need"] == "rm_request"
    assert len(result["candidates"]) == 2


def test_tool_refuses_without_email():
    result = execute_tool(
        "quote_request_rm_quote",
        {"material": "EN8", "supplier": "Acme", "supplier_email": ""},
        "rmq-tool",
    )
    assert result["ok"] is False
    assert result["data"]["need"] == "rm_request"
