from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


@pytest.fixture(scope="module", autouse=True)
def _isolated_assumption_mail_db():
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-asmp-"))
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
    tag_drawing_cell_assumption,
    verify_quote,
)
from app.quote_assumption_mail import handle_customer_assumption_reply


def _seed_assumption(session: str) -> None:
    db.add_memory(session, "last_quote_drawing", "assumption-mail.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer="Assumption Mail Co",
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": "Bracket",
                "material": "EN8",
                "qty": 2,
                "unit_price": 1500,
                "notes": "fixture",
            }
        ],
    )
    init_drawing_cells(session)
    confirm_drawing_cell(session, "revision", "Rev A")
    confirm_drawing_cell(session, "quantity", "2")
    confirm_drawing_cell(session, "material", "EN8")
    tag_drawing_cell_assumption(session, "heat_treat", "HRC 58-62")


def test_accepting_email_clears_assumption():
    session = "asmp-accept"
    _seed_assumption(session)
    out = handle_customer_assumption_reply(
        session,
        "heat_treat",
        "We accept the heat treat assumption at HRC 58-62.",
        channel="email",
    )
    assert out["classification"] == "accept"
    assert out["cells"]["heat_treat"]["state"] == "confirmed"
    assert out["cells"]["heat_treat"]["value"] == "HRC 58-62"


def test_changing_email_leaves_cell_unconfirmed():
    session = "asmp-change"
    _seed_assumption(session)
    out = handle_customer_assumption_reply(
        session,
        "heat_treat",
        "Please change to HRC 60-64 instead.",
        channel="email",
    )
    assert out["classification"] == "change"
    assert out["cells"]["heat_treat"]["state"] == "proposed"
    assert "60-64" in out["cells"]["heat_treat"]["value"]
    send = verify_quote(session_id=session, stage="send")
    by_id = {c["id"]: c for c in send["checks"]}
    assert by_id.get("drawing_cell_heat_treat", {}).get("pass") is False
    assert send["stop"] is True


def test_unreadable_email_keeps_assumption_tag():
    session = "asmp-unclear"
    _seed_assumption(session)
    out = handle_customer_assumption_reply(
        session,
        "heat_treat",
        "???",
        channel="email",
    )
    assert out["classification"] == "unclear"
    assert out["cells"]["heat_treat"]["state"] == "assumption"
    mems = {m["key"]: m["value"] for m in db.list_memories(session, limit=20)}
    assert "assumption_reply_unread_heat_treat" in mems


def test_whatsapp_does_not_clear_tag():
    session = "asmp-wa"
    _seed_assumption(session)
    out = handle_customer_assumption_reply(
        session,
        "heat_treat",
        "We accept HRC 58-62",
        channel="whatsapp",
    )
    assert out.get("ignored") is True
    init_cells = init_drawing_cells(session)["cells"]
    assert init_cells["heat_treat"]["state"] == "assumption"
