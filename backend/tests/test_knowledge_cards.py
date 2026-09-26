from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.knowledge.cards import card_primary_id, read_card, record_vision_candidates
from app.knowledge.confirm import confirm_drawing_fact, list_quotable_fact_ids


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _clean():
    with db.connect() as conn:
        conn.execute("DELETE FROM entity_facts")
        conn.execute("DELETE FROM entity_cards")
    prev = settings.knowledge_cards_enabled
    settings.knowledge_cards_enabled = True
    yield
    settings.knowledge_cards_enabled = prev


def test_vision_summary_lands_as_candidate():
    out = record_vision_candidates(
        "part_revision",
        "rev-vision-1",
        "Material: EN8\nQty: 50\nScope: with_material\n",
        source_ref="sha-vision",
    )
    assert out["inserted"] == 3
    card = read_card("part_revision", "rev-vision-1")
    assert card["facts"] == []
    fields = {row["field"]: row for row in card["candidates"]}
    assert fields["material"]["value"] == "EN8"
    assert fields["material"]["source_kind"] == "vision_suggestion"
    assert list_quotable_fact_ids(card_primary_id("part_revision", "rev-vision-1")) == []


def test_error_text_is_not_a_candidate():
    out = record_vision_candidates("part_revision", "rev-err", "Error: cloud down")
    assert out["inserted"] == 0
    assert read_card("part_revision", "rev-err")["found"] is False


def test_high_value_confirm_requires_value_then_becomes_quotable():
    record_vision_candidates("part_revision", "rev-confirm", "Material: EN8\n")
    missing = confirm_drawing_fact(entity_id="rev-confirm", field="material", value="")
    assert missing["ok"] is False
    assert missing["error"] == "value_required"

    wrong = confirm_drawing_fact(entity_id="rev-confirm", field="material", value="6061")
    assert wrong["ok"] is True
    assert wrong["source_kind"] == "owner_confirmed"
    assert wrong["value"] == "6061"

    card = read_card("part_revision", "rev-confirm")
    assert card["candidates"] == []
    assert card["facts"][0]["value"] == "6061"
    assert card["facts"][0]["source_kind"] == "owner_confirmed"
    assert list_quotable_fact_ids(card_primary_id("part_revision", "rev-confirm")) == [
        card["facts"][0]["id"]
    ]


def test_matching_candidate_confirms_in_place():
    record_vision_candidates("part_revision", "rev-match", "Material: EN8\n")
    out = confirm_drawing_fact(entity_id="rev-match", field="material", value="EN8")
    assert out["ok"] is True
    assert out["state"] == "confirmed"
    assert out["source_kind"] == "owner_confirmed"
    card = read_card("part_revision", "rev-match")
    assert len(card["facts"]) == 1
    assert card["facts"][0]["value"] == "EN8"
