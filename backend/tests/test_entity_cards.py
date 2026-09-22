from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.knowledge.cards import card_primary_id, read_card, what_do_you_know
from app.main import app


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _knowledge_cards_reset():
    with db.connect() as conn:
        conn.execute("DELETE FROM entity_facts")
        conn.execute("DELETE FROM entity_cards")
    prev = settings.knowledge_cards_enabled
    settings.knowledge_cards_enabled = False
    yield
    settings.knowledge_cards_enabled = prev


def _seed_card(
    *,
    entity_type: str = "part_revision",
    entity_id: str = "rev-test-1",
    open_questions: list[str] | None = None,
) -> str:
    card_id = card_primary_id(entity_type, entity_id)
    oq = "[]" if open_questions is None else __import__("json").dumps(open_questions)
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO entity_cards (
              id, entity_type, entity_id, summary, fact_count, confirmed_count,
              open_questions, updated_at
            ) VALUES (?, ?, ?, '', 0, 0, ?, ?)
            """,
            (card_id, entity_type, entity_id, oq, now),
        )
    return card_id


def _insert_fact(
    card_id: str,
    fact_id: str,
    *,
    field: str,
    value: str,
    state: str = "candidate",
    source_kind: str = "vision_suggestion",
) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO entity_facts (
              id, card_id, field, value, unit, source_kind, source_ref,
              confidence, state, created_at
            ) VALUES (?, ?, ?, ?, '', ?, '', 0, ?, ?)
            """,
            (fact_id, card_id, field, value, source_kind, state, db.utc_now()),
        )


def test_read_card_confirmed_in_facts_candidate_separate():
    settings.knowledge_cards_enabled = True
    card_id = _seed_card()
    _insert_fact(
        card_id,
        "fact-confirmed-1",
        field="material",
        value="En1A",
        state="confirmed",
        source_kind="owner_confirmed",
    )
    _insert_fact(
        card_id,
        "fact-candidate-1",
        field="od_mm",
        value="25",
        state="candidate",
        source_kind="vision_suggestion",
    )

    payload = read_card("part_revision", "rev-test-1")
    assert payload["found"] is True
    fact_ids = {f["id"] for f in payload["facts"]}
    cand_ids = {f["id"] for f in payload["candidates"]}
    assert "fact-confirmed-1" in fact_ids
    assert "fact-candidate-1" not in fact_ids
    assert "fact-candidate-1" in cand_ids


def test_what_do_you_know_quotes_only_owner_confirmed():
    settings.knowledge_cards_enabled = True
    card_id = _seed_card(open_questions=["case depth spec"])
    _insert_fact(
        card_id,
        "fact-owner-1",
        field="material",
        value="En1A",
        state="confirmed",
        source_kind="owner_confirmed",
    )
    _insert_fact(
        card_id,
        "fact-title-1",
        field="qty",
        value="25",
        state="confirmed",
        source_kind="title_block",
    )
    _insert_fact(
        card_id,
        "fact-cand-1",
        field="bore_h7_mm",
        value="25",
        state="candidate",
        source_kind="vision_suggestion",
    )

    text = what_do_you_know("part_revision", "rev-test-1")
    assert "fact-owner-1" in text
    assert "En1A" in text
    assert "fact-title-1" not in text
    assert "qty:" not in text
    assert "fact-cand-1" not in text
    assert "case depth spec" in text


def test_what_do_you_know_missing_card_asks():
    text = what_do_you_know("part_revision", "does-not-exist")
    assert "do not have a knowledge card" in text.lower()
    assert "En1A" not in text
    assert "6061" not in text


def test_api_flag_off():
    settings.knowledge_cards_enabled = False
    _seed_card()
    with TestClient(app) as client:
        r = client.get(
            "/api/knowledge/card",
            params={"entity_type": "part_revision", "entity_id": "rev-test-1"},
        )
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "found": False, "facts": []}


def test_api_flag_on_returns_read_card():
    settings.knowledge_cards_enabled = True
    card_id = _seed_card()
    _insert_fact(
        card_id,
        "fact-api-1",
        field="scope",
        value="labour only",
        state="confirmed",
        source_kind="owner_confirmed",
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/knowledge/card",
            params={"entity_type": "part_revision", "entity_id": "rev-test-1"},
        )
    body = r.json()
    assert body["enabled"] is True
    assert body["found"] is True
    assert {f["id"] for f in body["facts"]} == {"fact-api-1"}
