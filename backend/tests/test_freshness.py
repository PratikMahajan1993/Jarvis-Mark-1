from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.knowledge.cards import card_primary_id, is_stale, record_vision_candidates
from app.quote import verify_quote


def setup_module(_module=None):
    db.init_db()


def _checks(session_id: str) -> dict[str, dict]:
    result = verify_quote(session_id=session_id)
    return {row["id"]: row for row in result["checks"]}


def test_staleness_thresholds():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    fresh = {"updated_at": (now - timedelta(days=1)).isoformat()}
    old = {"updated_at": (now - timedelta(days=31)).isoformat()}
    assert is_stale(fresh, "drawing_card", now=now) is False
    assert is_stale(old, "drawing_card", now=now) is True
    recent_machine = {"updated_at": (now - timedelta(minutes=20)).isoformat()}
    hour_old = {"updated_at": (now - timedelta(hours=2)).isoformat()}
    assert is_stale(recent_machine, "machine_status", now=now) is False
    assert is_stale(hour_old, "machine_status", now=now) is True
    assert is_stale({}, "drawing_card", now=now) is True


def test_stale_card_and_unconfirmed_fact_block_verify():
    prev = settings.knowledge_cards_enabled
    settings.knowledge_cards_enabled = True
    revision_id = "rev-stale-1"
    card_id = card_primary_id("part_revision", revision_id)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    try:
        with db.connect() as conn:
            conn.execute("DELETE FROM entity_facts WHERE card_id = ?", (card_id,))
            conn.execute("DELETE FROM entity_cards WHERE id = ?", (card_id,))
            conn.execute(
                """
                INSERT INTO entity_cards (
                  id, entity_type, entity_id, summary, fact_count, confirmed_count,
                  open_questions, updated_at
                ) VALUES (?, 'part_revision', ?, '', 0, 0, '[]', ?)
                """,
                (card_id, revision_id, old),
            )
        record_vision_candidates("part_revision", revision_id, "Material: EN8\n")
        with db.connect() as conn:
            conn.execute("UPDATE entity_cards SET updated_at = ? WHERE id = ?", (old, card_id))
        db.add_memory("phase2-stale", "last_part_revision_id", revision_id)
        checks = _checks("phase2-stale")
        assert checks["drawing_card_fresh"]["pass"] is False
        assert checks["drawing_card_fresh"]["severity"] == "BLOCKER"
        assert checks["unconfirmed_drawing_fact"]["pass"] is False
        assert "unconfirmed drawing fact" in checks["unconfirmed_drawing_fact"]["evidence"]
        assert verify_quote(session_id="phase2-stale")["stop"] is True
    finally:
        settings.knowledge_cards_enabled = prev
