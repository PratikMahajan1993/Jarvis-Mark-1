from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.knowledge.cards import card_primary_id
from app.knowledge.identity import (
    format_revision_change_summary,
    resolve_drawing_identity,
    text_fingerprint,
)
from app.masterdata import routings
from app.vision.gate import dispatch_drawing_vision, file_sha256
from app.vision.schema import ensure_vision_schema


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _clean_tables():
    with db.connect() as conn:
        ensure_vision_schema(conn)
        conn.execute("DELETE FROM vision_quota_usage")
        conn.execute("DELETE FROM disclosure_log")
        conn.execute("DELETE FROM drawing_analysis_state")
        conn.execute("DELETE FROM entity_facts")
        conn.execute("DELETE FROM entity_cards")
        conn.execute("DELETE FROM routing_operations")
        conn.execute("DELETE FROM routings")
        conn.execute("DELETE FROM part_revisions")
        conn.execute("DELETE FROM components")
        conn.execute("DELETE FROM customers")
    prev = settings.knowledge_cards_enabled
    settings.knowledge_cards_enabled = True
    yield
    settings.knowledge_cards_enabled = prev


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _seed_customer_component(*, suffix: str) -> tuple[str, str]:
    cust_id = f"cust_id_{suffix}"
    comp_id = f"comp_id_{suffix}"
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, gstin, currency, status)
            VALUES (?, ?, NULL, 'INR', 'active')
            """,
            (cust_id, f"Identity Co {suffix}"),
        )
        routings.create_component(
            conn,
            component_id=comp_id,
            customer_id=cust_id,
            name="Bracket",
            customer_part_no=f"P-{suffix}",
        )
    return cust_id, comp_id


def _seed_part_revision(
    conn,
    *,
    revision_id: str,
    component_id: str,
    revision: str,
    drawing_no: str,
    drawing_sha256: str = "",
    fingerprint_text: str | None = None,
) -> None:
    fp_hash = text_fingerprint(fingerprint_text) if fingerprint_text else ""
    routings.create_part_revision(
        conn,
        revision_id=revision_id,
        component_id=component_id,
        revision=revision,
        drawing_no=drawing_no,
        drawing_sha256=drawing_sha256,
        drawing_artifact_id=fp_hash,
    )


def _seed_card_with_confirmed(revision_id: str, facts: dict[str, str]) -> None:
    card_id = card_primary_id("part_revision", revision_id)
    now = db.utc_now()
    with db.connect() as conn:
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
                (f"fact-{revision_id}-{idx}", card_id, field, value, now),
            )


def test_resolve_exact_sha256():
    digest = "a" * 64
    cust_id, comp_id = _seed_customer_component(suffix="exact")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-exact",
            component_id=comp_id,
            revision="A",
            drawing_no="DWG-100",
            drawing_sha256=digest,
        )
    out = resolve_drawing_identity(drawing_sha256=digest)
    assert out.kind == "exact"
    assert out.part_revision_id == "rev-exact"


def test_resolve_propose_same_fingerprint_different_sha():
    fp_text = "Title  BR-001  Rev A  Material En1A"
    fp_hash = text_fingerprint(fp_text)
    _, comp_id = _seed_customer_component(suffix="prop")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-propose",
            component_id=comp_id,
            revision="A",
            drawing_no="DWG-200",
            drawing_sha256="b" * 64,
            fingerprint_text=fp_text,
        )
    out = resolve_drawing_identity(
        drawing_sha256="c" * 64,
        fingerprint_text=fp_text,
    )
    assert out.kind == "propose"
    assert out.matched_part_revision_id == "rev-propose"
    assert fp_hash == text_fingerprint("  TITLE   br-001   rev a   material en1a  ")


def test_resolve_revision_change_lists_confirmed_diffs():
    cust_id, comp_id = _seed_customer_component(suffix="revchg")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-b",
            component_id=comp_id,
            revision="B",
            drawing_no="DWG-300",
            drawing_sha256="d" * 64,
        )
        _seed_part_revision(
            conn,
            revision_id="rev-c",
            component_id=comp_id,
            revision="C",
            drawing_no="DWG-300",
            drawing_sha256="e" * 64,
        )
    _seed_card_with_confirmed("rev-b", {"od_mm": "50", "material": "En1A", "scope": "labour only"})
    _seed_card_with_confirmed("rev-c", {"od_mm": "52", "material": "En1A", "case_depth": "0.8"})

    out = resolve_drawing_identity(
        drawing_sha256="f" * 64,
        customer_id=cust_id,
        drawing_no="DWG-300",
        revision="C",
    )
    assert out.kind == "revision_change"
    assert out.prior_part_revision_id == "rev-b"
    assert set(out.changed_fields) == {"od_mm", "scope", "case_depth"}
    summary = format_revision_change_summary(out)
    assert "od_mm" in summary
    assert "scope" in summary
    assert "case_depth" in summary


def test_dispatch_exact_hit_zero_provider_calls(tmp_path):
    body = b"known-drawing-bytes-k2"
    drawing = _write_bytes(tmp_path / "known.bin", body)
    digest = file_sha256(drawing)
    _, comp_id = _seed_customer_component(suffix="gate")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-gate",
            component_id=comp_id,
            revision="A",
            drawing_no="DWG-400",
            drawing_sha256=digest,
        )
    _seed_card_with_confirmed("rev-gate", {"material": "En1A"})

    calls: list[str] = []

    def _provider():
        calls.append("vision")
        return {"content": "should not run", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        provider_call=_provider,
    )
    assert calls == []
    assert out.get("ok") is True
    assert out.get("identity_kind") == "exact"
    assert out.get("recalled") is True
    assert "En1A" in str(out.get("summary") or "")


def test_dispatch_propose_zero_provider_calls(tmp_path):
    fp_text = "Bracket drawing title block tokens"
    drawing = _write_bytes(tmp_path / "rescan.bin", b"rescan-other-bytes")
    _, comp_id = _seed_customer_component(suffix="gateprop")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-rescan",
            component_id=comp_id,
            revision="A",
            drawing_no="DWG-500",
            drawing_sha256="f" * 64,
            fingerprint_text=fp_text,
        )

    calls: list[str] = []

    def _provider():
        calls.append("vision")
        return {"content": "nope", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        provider_call=_provider,
        fingerprint_text=fp_text,
    )
    assert calls == []
    assert out.get("identity_kind") == "propose"
    assert out.get("proposed_part_revision_id") == "rev-rescan"


def test_dispatch_revision_change_zero_provider_calls(tmp_path):
    cust_id, comp_id = _seed_customer_component(suffix="gate rev")
    drawing = _write_bytes(tmp_path / "rev-c.bin", b"rev-c-bytes")
    digest = file_sha256(drawing)
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-gate-b",
            component_id=comp_id,
            revision="B",
            drawing_no="DWG-600",
            drawing_sha256="1" * 64,
        )
        _seed_part_revision(
            conn,
            revision_id="rev-gate-c",
            component_id=comp_id,
            revision="C",
            drawing_no="DWG-600",
            drawing_sha256="2" * 64,
        )
    _seed_card_with_confirmed("rev-gate-b", {"od_mm": "40"})
    _seed_card_with_confirmed("rev-gate-c", {"od_mm": "41", "material": "En1A"})

    calls: list[str] = []

    def _provider():
        calls.append("vision")
        return {"content": "nope", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        provider_call=_provider,
        customer_id=cust_id,
        drawing_no="DWG-600",
        revision="C",
    )
    assert calls == []
    assert out.get("identity_kind") == "revision_change"
    assert "od_mm" in str(out.get("change_summary") or "")
    assert "material" in str(out.get("change_summary") or "")


def test_flag_off_skips_identity_lookup(tmp_path, monkeypatch):
    settings.knowledge_cards_enabled = False
    body = b"flag-off-known"
    drawing = _write_bytes(tmp_path / "flagoff.bin", body)
    digest = file_sha256(drawing)
    _, comp_id = _seed_customer_component(suffix="flagoff")
    with db.connect() as conn:
        _seed_part_revision(
            conn,
            revision_id="rev-flagoff",
            component_id=comp_id,
            revision="A",
            drawing_no="DWG-700",
            drawing_sha256=digest,
        )

    calls: list[str] = []

    def _provider():
        calls.append("vision")
        return {"content": "ran", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        provider_call=_provider,
    )
    assert out.get("ok") is True
    assert calls == ["vision"]
    assert out.get("identity_kind") is None
