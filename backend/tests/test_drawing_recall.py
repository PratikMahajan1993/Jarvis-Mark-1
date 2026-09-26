from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.knowledge.cards import card_primary_id, recall_drawing_knowledge, record_vision_candidates


def setup_module(_module=None):
    db.init_db()


def _seed(revision_id: str) -> None:
    card_id = card_primary_id("part_revision", revision_id)
    now = db.utc_now()
    facts = {
        "material": "EN8",
        "qty": "50",
        "scope": "with_material",
        "routing": "turning → heat treat → grinding",
        "last_quoted": "2026-08-15 @ ₹12,500",
    }
    with db.connect() as conn:
        conn.execute("DELETE FROM entity_facts WHERE card_id = ?", (card_id,))
        conn.execute("DELETE FROM entity_cards WHERE id = ?", (card_id,))
        conn.execute(
            """
            INSERT INTO entity_cards (
              id, entity_type, entity_id, summary, fact_count, confirmed_count,
              open_questions, updated_at
            ) VALUES (?, 'part_revision', ?, '', ?, ?, '[]', ?)
            """,
            (card_id, revision_id, len(facts), len(facts), now),
        )
        for idx, (field, value) in enumerate(facts.items()):
            conn.execute(
                """
                INSERT INTO entity_facts (
                  id, card_id, field, value, unit, source_kind, source_ref,
                  confidence, state, created_at
                ) VALUES (?, ?, ?, ?, '', 'owner_confirmed', '', 1, 'confirmed', ?)
                """,
                (f"fact-recall-{idx}", card_id, field, value, now),
            )


def test_recall_template_states_confirmed_facts_and_gaps():
    _seed("rev-recall")
    record_vision_candidates(
        "part_revision",
        "rev-recall",
        "Tolerances: OD ±0.02mm\nBore diameter: 12\n",
    )
    out = recall_drawing_knowledge(entity_id="rev-recall")
    text = out["summary"]
    assert "Material: EN8 (confirmed)" in text
    assert "Qty: 50 (confirmed)" in text
    assert "Scope: with_material (confirmed)" in text
    assert "Routing: turning → heat treat → grinding (confirmed)" in text
    assert "Last quoted: 2026-08-15 @ ₹12,500 (confirmed)" in text
    assert "Tolerances: OD ±0.02mm (unconfirmed — gap)" in text
    assert "Gaps:" in text
    assert "bore diameter" in text
    assert "EN8" in text
    assert out["confirmed"]
    assert "bore diameter" in out["gaps"]
