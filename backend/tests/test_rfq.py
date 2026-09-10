from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

settings.data_dir = Path(tempfile.mkdtemp(prefix="jarvis-rfq-"))
settings.exports_dir = Path(tempfile.mkdtemp(prefix="jarvis-rfq-ex-"))
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.gemini_api_key = ""

from app import db
from app import jobs
from app import rfq
from app.agent import resolve_pending
from app.conversations import create as create_conversation
from app.intent import classify, planned_tools
from app.rfq import FIXTURE_GROUNDING


RFQ_PUBLIC_KEYS = (
    "id",
    "status",
    "mail_id",
    "conversation_id",
    "extract",
    "similar_jobs",
    "pending_reply",
    "deadline_iso",
    "catch",
    "updated_at",
)
SIMILAR_KEYS = ("id", "part_name", "material", "machine", "cycle_min", "geometry_notes")


def _clear() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM rfqs")
        conn.execute("DELETE FROM pending_actions")
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM artifacts")
    jobs.seed_demo_job()


def _drawing(grounding: str = FIXTURE_GROUNDING, title: str = "Pinion") -> dict:
    _clear()
    return create_conversation(
        "drawing",
        title,
        {
            "filename": "ace-pinion-blank.pdf",
            "grounding": grounding,
            "saw_drawing": True,
        },
        status="ready",
    )


def _nc_files() -> list[Path]:
    return list(settings.exports_dir.rglob("*.nc"))


def test_intake_reason_does_not_call_cnc():
    row = _drawing()
    import app.cnc_suggest as cnc_mod

    called: list[object] = []
    original = cnc_mod.suggest_program

    def boom(*_args, **_kwargs):
        called.append(1)
        raise AssertionError("auto-RFQ must not draft CNC")

    cnc_mod.suggest_program = boom  # type: ignore[method-assign]
    try:
        result = rfq.intake(
            conversation_id=row["id"],
            message="treat this as an RFQ from Deepak",
            session_id="default",
        )
        assert called == []
        assert result["rfq"]
        assert result["speak"]
        assert _nc_files() == []
        assert (result["rfq"].get("extract") or {}).get("nc") in (None, "", [])
    finally:
        cnc_mod.suggest_program = original  # type: ignore[method-assign]


def test_similar_job_hits_ace_seed():
    row = _drawing()
    result = rfq.reason_rfq(row["id"], message="treat this as an RFQ from Deepak", session_id="default")
    extract = result["rfq"]["extract"]
    assert extract.get("material") == "18CrNiMo7-6"
    hits = result["rfq"]["similar_jobs"]
    assert hits
    assert any(item["id"] == jobs.DEMO_JOB_ID for item in hits)
    assert hits[0]["material"] == "18CrNiMo7-6"


def test_unreadable_dim_is_named_not_invented():
    row = _drawing()
    result = rfq.reason_rfq(row["id"], session_id="default")
    catch = (result["speak"] or result["rfq"]["catch"] or "").lower()
    assert "unreadable" in catch or "will not invent" in catch or "missing" in catch
    extract = result["rfq"]["extract"]
    assert extract.get("bore") in (None, "")
    assert "20" not in catch
    assert "25" not in catch
    assert "Ø12" not in (result["speak"] or "")
    assert extract.get("od") == 50 or extract.get("diameter") == 50
    assert extract.get("length") == 80


def test_pending_hold_and_deadline_no_does_not_send():
    row = _drawing()
    result = rfq.reason_rfq(row["id"], message="treat this as an RFQ from Deepak", session_id="default")
    assert result["rfq"]["status"] == "pending"
    pending = db.list_pending("default")
    kinds = {item["kind"] for item in pending}
    assert "email_send" in kinds
    assert "calendar_create" in kinds
    hold = next(item for item in pending if item["kind"] == "email_send")
    sent: list[object] = []
    created: list[object] = []

    import app.connectors.email as email_mod
    import app.connectors.calendar as cal_mod

    orig_send = email_mod.send_email
    orig_create = cal_mod.create_event

    def no_send(*_args, **_kwargs):
        sent.append(1)
        return {"id": "should-not"}

    def no_cal(*_args, **_kwargs):
        created.append(1)
        return {"id": "should-not"}

    email_mod.send_email = no_send  # type: ignore[method-assign]
    cal_mod.create_event = no_cal  # type: ignore[method-assign]
    try:
        response = resolve_pending(hold["id"], False, "default")
        assert sent == []
        assert "cancel" in response.speak.lower() or "left" in response.speak.lower() or "alright" in response.speak.lower()
        still = db.get_pending(hold["id"])
        assert still and still["status"] == "rejected"
        cal = next(item for item in db.list_pending("default") if item["kind"] == "calendar_create")
        resolve_pending(cal["id"], False, "default")
        assert created == []
        idle = jobs.get_rfq(result["rfq"]["id"])
        assert idle and idle["status"] == "reasoned"
        assert rfq.glance_critical() is None
    finally:
        email_mod.send_email = orig_send  # type: ignore[method-assign]
        cal_mod.create_event = orig_create  # type: ignore[method-assign]


def test_cnc_on_request_with_dims_queues_promote():
    row = _drawing()
    rfq.reason_rfq(row["id"], session_id="default")
    for leftover in _nc_files():
        leftover.unlink()
    out = rfq.request_program(session_id="default", conversation_id=row["id"])
    assert out["ok"] is True
    assert out["pending"] and out["pending"]["kind"] == "cnc_promote"
    path = Path(out["path"])
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "DRAFT" in text
    assert "Not proven" in text
    assert "G01" in text
    approved = resolve_pending(out["pending"]["id"], True, "default")
    assert "not proven" in approved.speak.lower()
    assert "email" in approved.speak.lower() or "not proven" in approved.speak.lower()
    accepted = list(settings.exports_dir.rglob("*-accepted.nc"))
    assert accepted
    assert path.is_file()


def test_cnc_without_dims_refuses_no_file():
    grounding = (
        "Title block: unknown blank. Material EN8. "
        "Bore diameter is unreadable. No OD or length is visible on the sheet."
    )
    row = _drawing(grounding=grounding, title="Blank")
    rfq.reason_rfq(row["id"], session_id="blank-session")
    for leftover in _nc_files():
        leftover.unlink()
    out = rfq.request_program(session_id="blank-session", conversation_id=row["id"])
    assert out["ok"] is False
    assert out.get("pending") is None
    assert _nc_files() == []
    strategy = str((out.get("result") or {}).get("strategy") or out.get("speak") or "").lower()
    assert "invent" in strategy or "missing" in strategy


def test_intent_rfq_vs_cnc():
    assert classify("what's in this RFQ").kind == "rfq_reason"
    assert classify("treat this as an RFQ from Deepak").kind == "rfq_reason"
    assert classify("quote on this drawing").kind == "rfq_reason"
    assert classify("write a program from scratch").kind == "cnc_suggest"
    assert classify("suggest G-code for this").kind == "cnc_suggest"
    assert classify("CNC program for this").kind == "cnc_suggest"
    assert "cnc_suggest" not in planned_tools("what's in this RFQ")
    assert "cnc_suggest" not in planned_tools("treat this as an RFQ from Deepak")
    assert planned_tools("what's in this RFQ") == ("reason_rfq",)
    assert planned_tools("write a program from scratch") == ("cnc_suggest",)


def test_get_rfqs_shape_and_glance_critical():
    row = _drawing()
    reasoned = rfq.reason_rfq(row["id"], message="treat this as an RFQ from Deepak", session_id="default")
    dismissed = jobs.create_rfq(status="dismissed", mail_id="old-mail")
    items = rfq.list_public()
    ids = [item["id"] for item in items]
    assert reasoned["rfq"]["id"] in ids
    assert dismissed["id"] not in ids
    item = next(row for row in items if row["id"] == reasoned["rfq"]["id"])
    for key in RFQ_PUBLIC_KEYS:
        assert key in item, key
    assert isinstance(item["extract"], dict)
    assert isinstance(item["similar_jobs"], list)
    if item["similar_jobs"]:
        for key in SIMILAR_KEYS:
            assert key in item["similar_jobs"][0], key
    assert item["catch"]
    assert item["deadline_iso"]
    assert item["pending_reply"]
    assert item["status"] == "pending"

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        listed = client.get("/api/rfqs")
        assert listed.status_code == 200
        payload = listed.json()
        assert "items" in payload
        assert payload["items"]
        public = payload["items"][0]
        for key in RFQ_PUBLIC_KEYS:
            assert key in public, key
        one = client.get(f"/api/rfqs/{item['id']}")
        assert one.status_code == 200
        body = one.json()
        for key in RFQ_PUBLIC_KEYS:
            assert key in body, key
        glance = client.get("/api/glance")
        assert glance.status_code == 200
        crit = glance.json().get("critical")
        assert crit
        assert crit["kind"] == "rfq"
        assert crit.get("title")
        assert crit.get("sourceId") == item["id"] or crit.get("sourceId")

    missing = rfq.glance_critical()
    assert missing and missing["kind"] == "rfq"
    assert "TITLE BLOCK" not in (missing.get("title") or "")
    assert missing.get("title") == "Input pinion blank"


def test_title_block_boilerplate_stripped():
    piston = (
        "Title Block: PISTON — TITLE BLOCK, Scale 1:1, Sheet 1 of 1, Material: EN8. "
        "Views: FRONT VIEW showing a circular feature. "
        "Notes: Do not invent dimensions. Bore shown without a readable number."
    )
    parsed = rfq._extract_from_grounding(piston)
    assert parsed.get("title") == "PISTON"
    assert parsed.get("material") == "EN8"
    assert rfq._title_from_extract(parsed) == "PISTON"
    fixture = rfq._extract_from_grounding(FIXTURE_GROUNDING)
    assert fixture.get("title") == "Input pinion blank"


def test_rereason_does_not_stack_shall_i():
    row = _drawing()
    first = rfq.reason_rfq(row["id"], session_id="default")
    second = rfq.reason_rfq(row["id"], session_id="default")
    pending = db.list_pending("default")
    holds = [item for item in pending if item["kind"] == "email_send"]
    cals = [item for item in pending if item["kind"] == "calendar_create"]
    assert len(holds) == 1
    assert len(cals) == 1
    old_hold = db.get_pending(first["pending_ids"][0])
    assert old_hold and old_hold["status"] == "rejected"
    assert second["rfq"]["id"] == first["rfq"]["id"]
    assert second["rfq"]["status"] == "pending"


def test_reason_writes_catch_onto_drawing_focus():
    row = _drawing()
    rfq.reason_rfq(row["id"], session_id="default")
    conv = db.get_conversation(row["id"])
    assert conv
    focus = conv.get("focus") or {}
    assert str(focus.get("catch") or "").strip()
    assert isinstance(focus.get("similar_jobs"), list)
