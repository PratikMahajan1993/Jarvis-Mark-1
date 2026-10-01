from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-desk-"))
    prev = (settings.data_dir, settings.exports_dir, settings.canvas_dir)
    settings.data_dir = tmp / "data"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir = tmp / "exports"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.canvas_dir = tmp / "data" / "canvas"
    settings.canvas_dir.mkdir(parents=True, exist_ok=True)
    from app import db

    db.init_db()
    yield
    settings.data_dir, settings.exports_dir, settings.canvas_dir = prev


from app import db
from app.shop_desk import (
    customer_status_text,
    program_validity_refusal,
    release_inspection,
    review_staff_mail,
    send_drawing_to_person,
    set_order_status,
    write_setup_chart,
)
from app.vision.gate import dispatch_drawing_vision


def test_program_validity_is_refused():
    assert program_validity_refusal("is the old program valid for rev C")
    assert program_validity_refusal("hello") is None


def test_staff_mail_holds_a_price_and_allows_a_question():
    held = review_staff_mail("Please confirm the price is Rs 400.")
    assert held["held"] is True
    assert held["ping_owner"] is True
    allowed = review_staff_mail("Which revision is on the print?")
    assert allowed["ok"] is True
    assert allowed["held"] is False


def test_owner_sets_status_and_customer_hears_only_that():
    missing = customer_status_text("JOB-1")
    assert missing["say"] == "I'll ask the shop."
    assert missing["ping_owner"] is True
    denied = set_order_status(job_ref="JOB-1", status="Ready", delivery_date="2026-10-02", role="staff")
    assert denied["ok"] is False
    ok = set_order_status(
        job_ref="JOB-1",
        status="Halted",
        delivery_date="2026-10-02",
        halted_reason="Waiting on material",
        role="owner",
    )
    assert ok["ok"] is True
    heard = customer_status_text("JOB-1")
    assert heard["say"] == "Halted. Waiting on material"
    assert "price" not in heard


def test_inspector_release_does_not_change_status():
    set_order_status(job_ref="JOB-2", status="In process", delivery_date="2026-10-03", role="owner")
    staff = release_inspection(
        role="staff",
        job_ref="JOB-2",
        measurements={"od_mm": "20.00"},
        disposition="accept",
    )
    assert staff["ok"] is False
    assert staff["ping_owner"] is True
    released = release_inspection(
        role="quality_inspector",
        job_ref="JOB-2",
        measurements={"od_mm": "20.00"},
        disposition="accept",
    )
    assert released["ok"] is True
    assert released["status_unchanged"] is True
    assert customer_status_text("JOB-2")["status"] == "In process"
    priced = release_inspection(
        role="quality_inspector",
        job_ref="JOB-2",
        measurements={"price": "100"},
        disposition="accept",
    )
    assert priced["ok"] is False


def test_drawing_email_requires_owner_and_active_component():
    cid = f"cust_{uuid.uuid4().hex[:8]}"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, gstin, currency, status) VALUES (?, ?, NULL, 'INR', 'active')",
            (cid, "Desk Customer"),
        )
        conn.execute(
            """
            INSERT INTO products (
              id, product_number, name, customer_id, uom, status, effective_from
            ) VALUES (?, ?, ?, ?, 'pcs', 'active', '2026-01-01')
            """,
            (f"prod_{uuid.uuid4().hex[:8]}", "PN-1", "Pin", cid),
        )
    sent: list[str] = []
    refused = send_drawing_to_person(
        role="owner",
        product_number="PN-1",
        to_email="ravi@shop.example",
        channel="whatsapp",
    )
    assert refused["ok"] is False
    ok = send_drawing_to_person(
        role="owner",
        product_number="PN-1",
        to_email="ravi@shop.example",
        channel="email",
        send_fn=lambda addr, _subject, _body: sent.append(addr),
    )
    assert ok["ok"] is True
    assert sent == ["ravi@shop.example"]
    group = send_drawing_to_person(
        role="owner",
        product_number="PN-1",
        to_email="supervisors@group",
        channel="email",
    )
    assert group["ok"] is False


def test_setup_chart_is_not_a_program(tmp_path: Path):
    nc = tmp_path / "job.nc"
    nc.write_text("(NOT PROVEN ON THE MACHINE)\nG21\n", encoding="utf-8")
    chart = Path(write_setup_chart(str(nc), notes="Soft jaws, stop on the left."))
    text = chart.read_text(encoding="utf-8")
    assert "not transmitted" in text
    assert "Soft jaws" in text


def test_cloud_vision_stays_down_when_the_line_is_down(monkeypatch, tmp_path: Path):
    drawing = tmp_path / "part.pdf"
    drawing.write_bytes(b"%PDF-1.1\n")
    monkeypatch.setattr("app.vision.gate.cloud_line_is_down", lambda: True)
    called = {"n": 0}

    def _provider():
        called["n"] += 1
        return {"content": "10 mm", "provider": "test"}

    result = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_provider)
    assert result["ok"] is False
    assert "line is down" in result["error"]
    assert called["n"] == 0
