from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-qrev-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.masterdata.quotes import (  # noqa: E402
    load_revision_facts,
    machining_rate_for_revision,
    revision_id_from_session,
)
from app.quote import build_quote, quote_to_pdf, verify_quote  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _build(
    session: str,
    *,
    part: str,
    rate: str,
    customer: str = "Revision Test Co",
) -> str:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    build_quote(
        session_id=session,
        part_name=part,
        material="EN8",
        customer=customer,
        scope="with_material",
        rm_price="4200",
        machine="Demo CNC vertical mill",
        machining_rate=rate,
        line_items=[
            {
                "item": part,
                "material": "EN8",
                "qty": 1,
                "unit_price": rate,
                "notes": "test",
            }
        ],
    )
    quote_to_pdf(session_id=session, part_name=part)
    return revision_id_from_session(session)


def test_two_builds_keep_both_revisions(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    session = "s4-two-builds"
    rev_a = _build(session, part="Part-A", rate="900")
    rev_b = _build(session, part="Part-B", rate="1200")
    assert rev_a and rev_b and rev_a != rev_b
    with db.connect() as conn:
        n_revisions = conn.execute("SELECT COUNT(*) AS n FROM quote_revisions").fetchone()["n"]
        lines_a = conn.execute(
            "SELECT COUNT(*) AS n FROM quote_lines WHERE quote_revision_id = ?",
            (rev_a,),
        ).fetchone()["n"]
        lines_b = conn.execute(
            "SELECT COUNT(*) AS n FROM quote_lines WHERE quote_revision_id = ?",
            (rev_b,),
        ).fetchone()["n"]
        facts_a = load_revision_facts(conn, rev_a)
        facts_b = load_revision_facts(conn, rev_b)
    assert n_revisions >= 2
    assert lines_a >= 1 and lines_b >= 1
    assert facts_a and facts_b
    assert facts_a["machining_rate"] == "900"
    assert facts_b["machining_rate"] == "1200"


def test_fifty_memory_writes_do_not_change_first_revision_rate(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    session = "s4-memory-flood"
    rev_first = _build(session, part="Stable-Part", rate="777")
    _build(session, part="Later-Part", rate="999")
    for i in range(50):
        db.add_memory(session, f"filler_{i}", f"noise-{i}")
    assert machining_rate_for_revision(rev_first) == "777"
    with db.connect() as conn:
        facts = load_revision_facts(conn, rev_first)
    assert facts is not None
    assert facts["machining_rate"] == "777"


def test_verify_uses_latest_revision_not_memory_collision(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    session = "s4-verify-latest"
    _build(session, part="First", rate="500")
    _build(session, part="Second", rate="1500")
    db.add_memory(session, "last_quote_machining_rate", "1")
    latest = revision_id_from_session(session)
    assert machining_rate_for_revision(latest) == "1500"
    result = verify_quote(session_id=session, stage="draft")
    checks = {c["id"]: c for c in result["checks"]}
    assert checks["rows_exist"]["pass"] is True
    assert checks.get("mhr_demo_floor") is not None
    assert " rate 1 " not in checks["mhr_demo_floor"]["evidence"]
