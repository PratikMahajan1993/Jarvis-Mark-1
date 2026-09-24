from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.quote import build_quote, quote_to_pdf, verify_quote
import app.quote as quote_mod


def setup_module(_module=None):
    db.init_db()


def _minimal_send_ready(session: str, *, basis_date: str) -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", basis_date)
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


def test_rm_basis_31_days_old_blocks_send(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 2))
    session = "q5b-rm-31-send"
    _minimal_send_ready(session, basis_date="2026-01-30")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is False
    assert by_id["rm_basis_date"]["severity"] == "BLOCKER"
    assert result["stop"] is True
    assert result["verdict"] == "block"


def test_rm_basis_29_then_31_re_evaluated_at_send(monkeypatch):
    session = "q5b-rm-29-then-31"
    _minimal_send_ready(session, basis_date="2026-02-01")
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 2))
    day29 = verify_quote(session_id=session, stage="send")
    rm29 = {c["id"]: c for c in day29["checks"]}["rm_basis_date"]
    assert rm29["pass"] is False
    assert rm29["severity"] == "WARN"
    assert day29["stop"] is False

    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 4))
    day31 = verify_quote(session_id=session, stage="send")
    rm31 = {c["id"]: c for c in day31["checks"]}["rm_basis_date"]
    assert rm31["pass"] is False
    assert rm31["severity"] == "BLOCKER"
    assert day31["stop"] is True


def test_rm_basis_25_days_warns(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 2, 25))
    session = "q5b-rm-25-warn"
    _minimal_send_ready(session, basis_date="2026-01-31")
    send = verify_quote(session_id=session, stage="send")
    draft = verify_quote(session_id=session, stage="draft")
    for result in (send, draft):
        rm = {c["id"]: c for c in result["checks"]}["rm_basis_date"]
        assert rm["pass"] is False
        assert rm["severity"] == "WARN"
    assert send["stop"] is False
    assert draft["stop"] is False


def test_rm_basis_over_30_warns_draft_blocks_send(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 5))
    session = "q5b-rm-draft-warn-send-block"
    _minimal_send_ready(session, basis_date="2026-01-30")
    draft = verify_quote(session_id=session, stage="draft")
    send = verify_quote(session_id=session, stage="send")
    d_rm = {c["id"]: c for c in draft["checks"]}["rm_basis_date"]
    s_rm = {c["id"]: c for c in send["checks"]}["rm_basis_date"]
    assert d_rm["severity"] == "WARN"
    assert draft["stop"] is False
    assert s_rm["severity"] == "BLOCKER"
    assert send["stop"] is True


def test_malformed_rm_basis_date_fails_closed(monkeypatch):
    """LOGIC-4b: a present but unparseable basis date is a BLOCKER, same as empty."""
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 5))
    session = "q5b-rm-malformed"
    _minimal_send_ready(session, basis_date="not-a-date")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is False
    assert by_id["rm_basis_date"]["severity"] == "BLOCKER"
    assert result["stop"] is True


def test_undated_rm_basis_still_blocker(monkeypatch):
    monkeypatch.setattr(quote_mod, "_quote_calendar_today", lambda: date(2026, 3, 5))
    session = "q5b-rm-undated"
    _minimal_send_ready(session, basis_date="")
    result = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["rm_basis_date"]["pass"] is False
    assert by_id["rm_basis_date"]["severity"] == "BLOCKER"
    assert "evidence" in by_id["rm_basis_date"]
    assert "today" not in by_id["rm_basis_date"]["evidence"].lower()
