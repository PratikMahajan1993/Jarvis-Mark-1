from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.hermes.bridge import ensure_playbooks_installed
from app.quote import (
    PLAYBOOK_NOTES_PATH,
    append_playbook_note,
    build_quote,
    quote_to_pdf,
    verify_quote,
)
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def _seed_good_quote(session: str) -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
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
    quote_to_pdf(session_id=session, part_name="Bracket")
    db.add_memory(session, "last_quote_delivery_days", "14")


def test_quote_verify_fails_on_empty_session():
    session = "verify-empty"
    result = verify_quote(session_id=session)
    data = result
    assert data["ok"] is True
    assert data["passed"] is False
    assert data["failed_count"] >= 3
    assert data["stop"] is True
    failed_ids = {c["id"] for c in data["checks"] if not c["pass"]}
    assert "material" in failed_ids
    assert "pdf" in failed_ids
    assert "unit_prices" in failed_ids or "rows_exist" in failed_ids
    widget = (data.get("scene") or {}).get("widgets") or [{}]
    assert widget[0].get("type") == "checklist"


def test_quote_verify_passes_fixture():
    session = "verify-good"
    _seed_good_quote(session)
    result = verify_quote(session_id=session)
    assert result["ok"] is True
    assert result["passed"] is True
    assert result["failed_count"] == 0
    assert result["stop"] is False
    assert all(c["pass"] for c in result["checks"])


def test_quote_verify_stop_on_any_blocker():
    session = "verify-stop"
    db.add_memory(session, "last_quote_drawing", "only-drawing.pdf")
    result = verify_quote(session_id=session)
    assert result["failed_count"] >= 1
    assert result["verdict"] == "block"
    assert result["stop"] is True


def test_quote_send_queues_hitl_when_verify_passes():
    session = "send-good"
    _seed_good_quote(session)
    result = execute_tool(
        "quote_send",
        {"to": "deepak@example.com", "subject": "Quote Bracket", "body": "Please review."},
        session,
    )
    assert result.get("ok") is True
    pending = result.get("pending") or {}
    assert pending.get("kind") == "quote_send"
    assert pending.get("tool_name") == "quote_send"
    payload = pending.get("payload") or {}
    assert payload.get("verify")
    assert result.get("data", {}).get("sent") is False
    db.set_pending_status(pending["id"], "rejected")


def test_quote_send_refuses_when_stop_true():
    session = "send-refuse"
    result = execute_tool(
        "quote_send",
        {"to": "nobody@example.com", "subject": "Bad quote"},
        session,
    )
    assert result.get("ok") is False
    assert "proof" in (result.get("error") or "").lower()
    assert not db.list_pending(session)


def test_playbook_note_appends(tmp_path, monkeypatch):
    notes = tmp_path / "notes.md"
    notes.write_text("# Quote playbook notes\n\nCorrections newest first.\n\n", encoding="utf-8")
    monkeypatch.setattr("app.quote.PLAYBOOK_NOTES_PATH", notes)
    out = append_playbook_note(
        what_went_wrong="wrong material default",
        layer="toolbox",
        change="ask owner before EN8",
    )
    assert out["ok"] is True
    text = notes.read_text(encoding="utf-8")
    assert "wrong material default" in text
    assert "[toolbox]" in text


def test_ensure_playbooks_installed_copies_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "hermes_home", str(tmp_path / "hermes"))
    ok = ensure_playbooks_installed()
    assert ok is True
    dest = tmp_path / "hermes" / "skills" / "shop" / "quote" / "SKILL.md"
    assert dest.is_file()
    content = dest.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name:" in content.split("---", 2)[1]


def test_skill_md_has_yaml_and_triggers():
    skill = ROOT / "app" / "hermes" / "playbooks" / "quote" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---")
    front = text.split("---", 2)[1]
    assert "name:" in front
    assert "description:" in front
    body = text.split("---", 2)[2]
    for phrase in (
        "I want to create a new quote for XYZ drawing",
        "start quote workflow for XYZ",
        "work on the RFQ",
        "quote this drawing",
        "make a quotation for Deepak",
        "quote this RFQ",
    ):
        assert phrase in body or phrase in front


def test_verify_fails_labour_scope_with_rm_price():
    session = "verify-labour-rm"
    _seed_good_quote(session)
    build_quote(session_id=session, part_name="Bracket", material="EN8", scope="labour", rm_price=4200)
    result = verify_quote(session_id=session)
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "scope_labour_no_rm" in failed
    assert result["passed"] is False


def test_verify_fails_mhr_below_demo_minimum(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "verify-mhr-floor"
    _seed_good_quote(session)
    db.add_memory(session, "last_quote_machine", "Demo CNC vertical mill")
    db.add_memory(session, "last_quote_machining_rate", "400")
    result = verify_quote(session_id=session)
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "mhr_demo_floor" in failed


def test_verify_fails_rm_estimate_without_source_note(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    session = "verify-rm-estimate"
    _seed_good_quote(session)
    db.add_memory(session, "last_quote_rm_source", "estimate")
    result = verify_quote(session_id=session)
    failed = {c["id"] for c in result["checks"] if not c["pass"]}
    assert "rm_estimate_source" in failed


def test_verify_delivery_warns_at_draft_not_stop():
    session = "verify-no-delivery"
    _seed_good_quote(session)
    db.add_memory(session, "last_quote_delivery_days", "")
    result = verify_quote(session_id=session, stage="draft")
    by_id = {c["id"]: c for c in result["checks"]}
    assert "delivery_days" in by_id
    assert by_id["delivery_days"]["pass"] is False
    assert by_id["delivery_days"]["severity"] == "WARN"
    assert result["verdict"] == "pass"
    assert result["stop"] is False
    assert result["passed"] is True


def test_quote_build_machining_rate_fills_empty_unit_price():
    session = "quote-build-mhr-unit-price"
    result = execute_tool(
        "quote_build",
        {
            "part_name": "Bracket",
            "material": "EN8",
            "customer": "Deepak",
            "scope": "labour",
            "machining_rate": "900",
            "line_items": [
                {
                    "item": "Bracket",
                    "material": "EN8",
                    "qty": 2,
                    "unit_price": "",
                    "notes": "From drawing",
                }
            ],
        },
        session,
    )
    assert result.get("ok") is True
    rows = (result.get("data") or {}).get("rows") or []
    assert rows and _parse_row_price(rows[0]) == 900.0

    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    quote_to_pdf(session_id=session, part_name="Bracket")
    verify = verify_quote(session_id=session)
    by_id = {c["id"]: c for c in verify["checks"]}
    assert by_id["unit_prices"]["pass"] is True


def _parse_row_price(row: list) -> float:
    from app.quote import _parse_numeric

    return _parse_numeric(row[3]) or 0.0


def test_quote_build_tool_round_trips_scope_and_mhr_into_verify():
    session = "quote-build-tool-roundtrip"
    result = execute_tool(
        "quote_build",
        {
            "part_name": "Bracket",
            "material": "EN8",
            "customer": "Deepak",
            "scope": "labour",
            "rm_source": "supplier",
            "rm_source_note": "Acme Metals quote #123",
            "machine": "Demo CNC vertical mill",
            "machining_rate": "900",
            "line_items": [
                {
                    "item": "Bracket",
                    "material": "EN8",
                    "qty": 2,
                    "unit_price": 1500,
                    "notes": "From drawing",
                }
            ],
        },
        session,
    )
    assert result.get("ok") is True
    mems = {m["key"]: m["value"] for m in db.list_memories(session)}
    assert mems.get("last_quote_scope") == "labour"
    assert mems.get("last_quote_rm_source") == "supplier"
    assert mems.get("last_quote_rm_source_note") == "Acme Metals quote #123"
    assert mems.get("last_quote_machine") == "Demo CNC vertical mill"
    assert mems.get("last_quote_machining_rate") == "900"

    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    quote_to_pdf(session_id=session, part_name="Bracket")
    verify = verify_quote(session_id=session)
    by_id = {c["id"]: c for c in verify["checks"]}
    assert by_id["scope_labour_no_rm"]["pass"] is True
    assert by_id["mhr_demo_floor"]["pass"] is False
    assert "not owner-attested" in by_id["mhr_demo_floor"]["evidence"]
    assert by_id["unit_prices"]["pass"] is True


def test_quote_build_tool_with_material_rm_price_passes_verify():
    session = "quote-build-with-material-rm"
    result = execute_tool(
        "quote_build",
        {
            "part_name": "Bracket",
            "material": "EN8",
            "customer": "Deepak",
            "scope": "with_material",
            "rm_price": "4200",
            "line_items": [
                {
                    "item": "Bracket",
                    "material": "EN8",
                    "qty": 2,
                    "unit_price": 1500,
                    "notes": "From drawing",
                }
            ],
        },
        session,
    )
    assert result.get("ok") is True
    mems = {m["key"]: m["value"] for m in db.list_memories(session)}
    assert mems.get("last_quote_scope") == "with_material"
    assert mems.get("last_quote_rm_price") == "4200"

    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-09-13")
    quote_to_pdf(session_id=session, part_name="Bracket")
    verify = verify_quote(session_id=session)
    by_id = {c["id"]: c for c in verify["checks"]}
    assert by_id["scope_with_material_rm"]["pass"] is True
    assert by_id["rm_basis_date"]["pass"] is True
