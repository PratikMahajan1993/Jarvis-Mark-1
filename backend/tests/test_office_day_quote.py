from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.browser_evidence import record_evidence
from app.office_day import list_tasks, refresh_suggested_tasks, upsert_task
from app.quote import build_quote, quote_to_pdf, queue_quote_send
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def test_quote_build_and_pdf():
    built = build_quote(
        session_id="quote-test",
        part_name="Input pinion",
        material="18CrNiMo7-6",
        vision_summary="OD 50mm visible; bore unreadable",
    )
    assert built["ok"]
    assert built["artifact"]["path"]
    pdf = quote_to_pdf(session_id="quote-test", part_name="Input pinion", rows=built["rows"])
    assert pdf["ok"]
    queued = queue_quote_send(
        session_id="quote-test",
        to="deepak@example.com",
        subject="Quotation — Input pinion",
        body="Please find quote attached.",
        pdf_path=pdf["artifact"]["path"],
    )
    assert queued["pending"]["kind"] == "quote_send"
    assert queued["pending"]["irreversibility"] == 5
    db.set_pending_status(queued["pending"]["id"], "rejected")


def test_suggested_tasks_refresh():
    upsert_task(
        task_id="rfq-fixture-1",
        kind="rfq",
        title="KOSO drawings RFQ",
        detail="14 drawings — quote in 15 days",
        actions=[{"id": "engineering", "label": "Start review"}],
        source_id="fixture",
    )
    rows = list_tasks()
    assert any(t["id"] == "rfq-fixture-1" for t in rows)
    payload = refresh_suggested_tasks("office-test")
    assert payload["ok"]
    assert "weather" in payload


def test_browser_evidence_and_tool():
    ev = record_evidence(session_id="bev", url="https://example.com", title="Example", notes="stretch task")
    assert ev["ok"]
    result = execute_tool(
        "browser_queue_action",
        {"title": "Open example", "summary": "Navigate example.com", "url": "https://example.com"},
        "bev",
    )
    assert result.get("ok")
    pending = result.get("pending") or {}
    assert pending.get("kind") == "browser_action"
    db.set_pending_status(pending["id"], "rejected")
