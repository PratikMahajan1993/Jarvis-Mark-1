from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.knowledge.cards import card_primary_id, read_card
from app.knowledge.confirm import (
    confirm_fact,
    expire_candidates,
    list_quotable_fact_ids,
    reject_fact,
)
from app.main import app


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _knowledge_cards_reset():
    with db.connect() as conn:
        conn.execute("DELETE FROM entity_facts")
        conn.execute("DELETE FROM entity_cards")
    prev = settings.knowledge_cards_enabled
    settings.knowledge_cards_enabled = True
    yield
    settings.knowledge_cards_enabled = prev


def _seed_card(entity_id: str = "rev-k3a-1") -> str:
    card_id = card_primary_id("part_revision", entity_id)
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO entity_cards (
              id, entity_type, entity_id, summary, fact_count, confirmed_count,
              open_questions, updated_at
            ) VALUES (?, 'part_revision', ?, '', 0, 0, '[]', ?)
            """,
            (card_id, entity_id, now),
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
    expires_at: str | None = None,
) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO entity_facts (
              id, card_id, field, value, unit, source_kind, source_ref,
              confidence, state, expires_at, created_at
            ) VALUES (?, ?, ?, ?, '', ?, '', 0, ?, ?, ?)
            """,
            (
                fact_id,
                card_id,
                field,
                value,
                source_kind,
                state,
                expires_at,
                db.utc_now(),
            ),
        )


def _fact_state(fact_id: str) -> str:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT state, confirmed_by, confirmed_from, source_kind FROM entity_facts WHERE id = ?",
            (fact_id,),
        ).fetchone()
    assert row is not None
    return str(row["state"])


def test_material_wrong_value_stays_candidate():
    card_id = _seed_card()
    _insert_fact(card_id, "fact-mat-1", field="material", value="En1A")

    out = confirm_fact("fact-mat-1", "owner", "6061")
    assert out["ok"] is False
    assert out["state"] == "candidate"
    assert _fact_state("fact-mat-1") == "candidate"

    with db.connect() as conn:
        row = conn.execute(
            "SELECT confirmed_by FROM entity_facts WHERE id = 'fact-mat-1'"
        ).fetchone()
    assert row["confirmed_by"] is None


def test_material_correct_value_confirms():
    card_id = _seed_card()
    _insert_fact(card_id, "fact-mat-2", field="material", value="En1A")

    out = confirm_fact("fact-mat-2", "owner", "En1A")
    assert out["ok"] is True
    assert out["state"] == "confirmed"
    assert out["confirmed_by"] == "owner"
    assert out["confirmed_from"] == "vision_suggestion"
    assert out["source_kind"] == "vision_suggestion"

    with db.connect() as conn:
        row = conn.execute(
            "SELECT state, confirmed_by, confirmed_from, source_kind FROM entity_facts WHERE id = 'fact-mat-2'"
        ).fetchone()
    assert row["state"] == "confirmed"
    assert row["confirmed_by"] == "owner"
    assert row["confirmed_from"] == "vision_suggestion"
    assert row["source_kind"] == "vision_suggestion"
    assert list_quotable_fact_ids(card_id) == ["fact-mat-2"]


def test_low_value_field_confirms_without_value_repeat():
    card_id = _seed_card()
    _insert_fact(card_id, "fact-note-1", field="finish", value="black oxide")

    out = confirm_fact("fact-note-1", "owner", "")
    assert out["ok"] is True
    assert _fact_state("fact-note-1") == "confirmed"


def test_expire_candidates_rejects_past_ttl():
    card_id = _seed_card()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _insert_fact(
        card_id,
        "fact-exp-1",
        field="od_mm",
        value="25",
        expires_at=yesterday,
    )
    now = db.utc_now()
    n = expire_candidates(now)
    assert n == 1
    assert _fact_state("fact-exp-1") == "rejected"
    assert list_quotable_fact_ids(card_id) == []

    payload = read_card("part_revision", "rev-k3a-1")
    assert "fact-exp-1" not in {c["id"] for c in payload["candidates"]}


def test_confirmed_fact_not_expired_by_expire_candidates():
    card_id = _seed_card()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _insert_fact(
        card_id,
        "fact-old-conf",
        field="material",
        value="En1A",
        state="confirmed",
        source_kind="owner_confirmed",
        expires_at=yesterday,
    )
    expire_candidates(db.utc_now())
    assert _fact_state("fact-old-conf") == "confirmed"
    assert list_quotable_fact_ids(card_id) == ["fact-old-conf"]


def test_api_confirm_flag_off_does_not_write():
    settings.knowledge_cards_enabled = False
    card_id = _seed_card(entity_id="rev-flag-off")
    _insert_fact(card_id, "fact-flag-1", field="material", value="En1A")

    with TestClient(app) as client:
        r = client.post(
            "/api/knowledge/facts/fact-flag-1/confirm",
            json={"confirmed_by": "owner", "value": "En1A"},
        )
    assert r.status_code == 200
    assert r.json() == {"enabled": False}
    assert _fact_state("fact-flag-1") == "candidate"


def test_api_confirm_empty_confirmed_by_refused():
    card_id = _seed_card(entity_id="rev-empty-by")
    _insert_fact(card_id, "fact-empty-by", field="finish", value="passivate")

    with TestClient(app) as client:
        r = client.post(
            "/api/knowledge/facts/fact-empty-by/confirm",
            json={"confirmed_by": "  ", "value": ""},
        )
    assert r.status_code == 400
    assert _fact_state("fact-empty-by") == "candidate"


def test_reject_fact_and_api():
    card_id = _seed_card(entity_id="rev-reject")
    _insert_fact(card_id, "fact-rej-1", field="qty", value="10")
    _insert_fact(card_id, "fact-rej-2", field="scope", value="labour only")

    out = reject_fact("fact-rej-1")
    assert out["ok"] is True
    assert out["state"] == "rejected"

    with TestClient(app) as client:
        r = client.post("/api/knowledge/facts/fact-rej-2/reject")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["ok"] is True
    assert _fact_state("fact-rej-2") == "rejected"
