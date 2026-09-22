from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.vision.gate import (
    attest_customer_vision,
    dispatch_drawing_vision,
    file_sha256,
    get_analysis_state,
)
from app.vision.ledger import current_cycle_start


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _clean_vision_and_terms():
    with db.connect() as conn:
        from app.vision.schema import ensure_vision_schema

        ensure_vision_schema(conn)
        conn.execute("DELETE FROM vision_quota_usage")
        conn.execute("DELETE FROM disclosure_log")
        conn.execute("DELETE FROM drawing_analysis_state")
        conn.execute("DELETE FROM quote_actuals")
        conn.execute("DELETE FROM quote_lines")
        conn.execute("DELETE FROM quote_proofs")
        conn.execute("DELETE FROM quote_events")
        conn.execute("DELETE FROM quote_revisions")
        conn.execute("DELETE FROM quotes")
        conn.execute("DELETE FROM routing_operations")
        conn.execute("DELETE FROM routings")
        conn.execute("DELETE FROM part_revisions")
        conn.execute("DELETE FROM components")
        conn.execute("DELETE FROM customer_terms")
        conn.execute("DELETE FROM customer_aliases")
        conn.execute("DELETE FROM customers")
    yield


def _insert_customer(customer_id: str, name: str | None = None) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, gstin, currency, status)
            VALUES (?, ?, NULL, 'INR', 'active')
            """,
            (customer_id, name or customer_id),
        )


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _quota_count(cycle: str) -> int:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM vision_quota_usage
            WHERE cycle_start = ? AND state IN ('claimed', 'dispatched', 'override')
            """,
            (cycle,),
        ).fetchone()
        return int(row["n"] if row else 0)


def test_unknown_customer_denies_no_spend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    drawing = _write_bytes(tmp_path / "unk.bin", b"unknown-customer")
    digest = file_sha256(drawing)
    calls: list[str] = []

    def _provider():
        calls.append("hit")
        return {"content": "x", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        customer_id=None,
        provider_call=_provider,
    )
    assert not out.get("ok")
    assert out.get("analysis_state") == "needs_vision"
    assert "attest" in (out.get("error") or "").lower()
    assert get_analysis_state(digest) == "needs_vision"
    assert calls == []
    assert _quota_count(current_cycle_start()) == 0


def test_nda_customer_denies_even_with_allow_and_owner_spend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    _insert_customer("cust_nda")
    attest_customer_vision(
        "cust_nda",
        allow=True,
        nda=True,
        attested_by="owner@test",
    )
    drawing = _write_bytes(tmp_path / "nda.bin", b"nda-blocked")
    calls: list[str] = []

    def _provider():
        calls.append("hit")
        return {"content": "x", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        customer_id="cust_nda",
        provider_call=_provider,
    )
    assert not out.get("ok")
    assert "nda" in (out.get("error") or "").lower()
    assert calls == []
    assert _quota_count(current_cycle_start()) == 0


def test_attested_allow_nda_clear_reaches_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    _insert_customer("cust_ok")
    attest_customer_vision(
        "cust_ok",
        allow=True,
        nda=False,
        attested_by="owner@test",
    )
    drawing = _write_bytes(tmp_path / "ok.bin", b"consented")
    cycle = current_cycle_start()
    calls: list[str] = []

    def _provider():
        calls.append("hit")
        return {"content": "dims ok", "provider": "stub"}

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        customer_id="cust_ok",
        provider_call=_provider,
    )
    assert out.get("ok"), out
    assert calls == ["hit"]
    assert _quota_count(cycle) == 1
    assert get_analysis_state(file_sha256(drawing)) == "vision_done"


def test_attest_refuses_empty_attested_by():
    _insert_customer("cust_empty")
    out = attest_customer_vision("cust_empty", allow=True, nda=False, attested_by="  ")
    assert not out.get("ok")


def test_masterdata_off_skips_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    drawing = _write_bytes(tmp_path / "legacy.bin", b"no-consent-row")
    cycle = current_cycle_start()

    out = dispatch_drawing_vision(
        drawing,
        owner_spend=True,
        customer_id=None,
        provider_call=lambda: {"content": "ok", "provider": "stub"},
    )
    assert out.get("ok"), out
    assert _quota_count(cycle) == 1
