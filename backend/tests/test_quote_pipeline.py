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
def _isolated_pipeline_db():
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-pipe-"))
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
from app.quote import build_quote
from app.quote_pipeline import (
    activate_live_quote,
    begin_quote_detour,
    park_live_quote,
    read_quote_pipeline_state,
    resume_parked_quote,
    write_quote_pipeline_state,
)
from app.tools.registry import execute_tool
from app.masterdata.quotes import revision_id_from_session


def _build(session: str, tag: str) -> str:
    db.add_memory(session, "last_quote_drawing", f"{tag}-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    build_quote(
        session_id=session,
        part_name=f"Part-{tag}",
        material="EN8",
        customer="Pipeline Test Co",
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": f"Part-{tag}",
                "material": "EN8",
                "qty": 2,
                "unit_price": 1500,
                "notes": "pipeline test",
            }
        ],
    )
    rid = revision_id_from_session(session)
    assert rid
    return rid


def test_second_quote_cannot_go_live_while_one_is_live():
    session = "pipe-second-live"
    rev_a = _build(session, "A")
    assert write_quote_pipeline_state(session, rev_a, "live").get("ok")
    rev_b = _build(session, "B")
    assert read_quote_pipeline_state(session, rev_b)["state"] == "on_desk"
    assert write_quote_pipeline_state(session, rev_b, "handoff_ready").get("ok")
    blocked = activate_live_quote(session, rev_b)
    assert blocked.get("ok") is False
    assert "live" in (blocked.get("error") or "").lower()
    assert read_quote_pipeline_state(session, rev_a)["state"] == "live"
    assert read_quote_pipeline_state(session, rev_b)["state"] == "handoff_ready"


def test_park_then_resume():
    session = "pipe-park-resume"
    rev = _build(session, "P")
    assert write_quote_pipeline_state(session, rev, "handoff_ready").get("ok")
    assert activate_live_quote(session, rev).get("ok")
    assert park_live_quote(session, rev).get("ok")
    assert read_quote_pipeline_state(session, rev)["state"] == "parked"
    assert resume_parked_quote(session, rev).get("ok")
    assert read_quote_pipeline_state(session, rev)["state"] == "live"


def test_quote_send_while_detour_does_not_queue():
    session = "pipe-detour-send"
    rev = _build(session, "D")
    assert write_quote_pipeline_state(session, rev, "live").get("ok")
    assert begin_quote_detour(session, rev).get("ok")
    assert read_quote_pipeline_state(session, rev)["state"] == "detour"
    result = execute_tool(
        "quote_send",
        {"to": "buyer@example.com", "subject": "Quote", "body": "See attached"},
        session,
    )
    assert result.get("ok") is False
    assert "detour" in (result.get("error") or "").lower()
    assert not db.list_pending(session)
