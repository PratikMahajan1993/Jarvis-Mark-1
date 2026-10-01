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
def _isolated_margin_db():
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-margin-"))
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
from app.masterdata.quotes import revision_id_from_session
from app.quote import build_quote, verify_quote
from app.quote_margin import (
    compute_margin_hint,
    mark_quote_revision_won,
    set_revision_margin_context,
)

_BREAKDOWN_25 = {
    "machining_minor": 500_000,
    "material_minor": 200_000,
    "outsource_minor": 50_000,
    "tooling_minor": 0,
}
_BREAKDOWN_30 = {
    "machining_minor": 400_000,
    "material_minor": 200_000,
    "outsource_minor": 50_000,
    "tooling_minor": 50_000,
}


def _build_session(session: str) -> str:
    db.add_memory(session, "last_quote_drawing", "margin-fixture.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    build_quote(
        session_id=session,
        part_name="Spindle",
        material="EN8",
        customer="Margin Test Co",
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": "Spindle",
                "material": "EN8",
                "qty": 1,
                "unit_price": 10000,
                "notes": "fixture",
            }
        ],
    )
    rid = revision_id_from_session(session)
    assert rid
    return rid


def _apply_context(rid: str, *, sell_minor: int, breakdown: dict[str, int]) -> None:
    set_revision_margin_context(
        rid,
        primary_process="turning",
        tolerance_class="tight",
        cost_breakdown=breakdown,
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE quote_revisions SET total_minor = ? WHERE id = ?",
            (sell_minor, rid),
        )


def _seed_won(tag: str, sell_minor: int, breakdown: dict[str, int]) -> None:
    rid = _build_session(f"won-{tag}")
    _apply_context(rid, sell_minor=sell_minor, breakdown=breakdown)
    mark_quote_revision_won(rid)


def test_fewer_than_three_matching_won_jobs_is_silent():
    session = "margin-silent"
    rid = _build_session(session)
    _apply_context(rid, sell_minor=1_000_000, breakdown=_BREAKDOWN_30)
    _seed_won("a", 1_000_000, _BREAKDOWN_25)
    _seed_won("b", 1_000_000, _BREAKDOWN_25)
    hint = compute_margin_hint(session, route="owner")
    assert hint.get("silent") is True
    assert "hint_text" not in hint


def test_three_won_jobs_yield_hint_without_changing_sell_price():
    session = "margin-hint"
    rid = _build_session(session)
    _apply_context(rid, sell_minor=1_000_000, breakdown=_BREAKDOWN_30)
    _seed_won("1", 1_000_000, _BREAKDOWN_25)
    _seed_won("2", 1_000_000, _BREAKDOWN_25)
    _seed_won("3", 1_000_000, _BREAKDOWN_25)

    with db.connect() as conn:
        before = int(
            conn.execute("SELECT total_minor FROM quote_revisions WHERE id = ?", (rid,)).fetchone()[
                "total_minor"
            ]
        )

    hint = compute_margin_hint(session, route="owner")
    assert hint.get("silent") is False
    assert hint.get("hint_text")
    assert "lower" in hint["hint_text"].lower()

    verify = verify_quote(session_id=session, stage="draft")
    assert verify.get("margin_hint") == hint["hint_text"]

    with db.connect() as conn:
        after = int(
            conn.execute("SELECT total_minor FROM quote_revisions WHERE id = ?", (rid,)).fetchone()[
                "total_minor"
            ]
        )
    assert after == before == 1_000_000


def test_staff_route_is_silent():
    session = "margin-staff"
    rid = _build_session(session)
    _apply_context(rid, sell_minor=1_000_000, breakdown=_BREAKDOWN_30)
    for i in range(3):
        _seed_won(f"s{i}", 1_000_000, _BREAKDOWN_25)
    hint = compute_margin_hint(session, route="staff")
    assert hint.get("silent") is True
    assert "hint_text" not in hint
