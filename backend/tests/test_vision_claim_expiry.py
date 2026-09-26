"""A claimed vision row older than the provider timeout is released, then claimed again."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.vision.gate import dispatch_drawing_vision, file_sha256
from app.vision.ledger import current_cycle_start
from app.vision.schema import ensure_vision_schema


def setup_module(_module=None) -> None:
    db.init_db()


def _isolate() -> None:
    with db.connect() as conn:
        ensure_vision_schema(conn)
        conn.execute("DELETE FROM vision_quota_usage")
        conn.execute("DELETE FROM disclosure_log")
        conn.execute("DELETE FROM drawing_analysis_state")


def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def _insert_claim(claim_id: str, digest: str, cycle: str, created_at: str) -> None:
    with db.connect() as conn:
        ensure_vision_schema(conn)
        conn.execute(
            """
            INSERT INTO vision_quota_usage (
              id, cycle_start, file_sha256, customer_id, spent_by, arrival,
              pages, state, turn_id, override_action_id, created_at
            ) VALUES (?, ?, ?, NULL, 'owner_bench', 'test', 1, 'claimed', NULL, NULL, ?)
            """,
            (claim_id, cycle, digest, created_at),
        )


def test_stale_claim_is_released_and_provider_runs_once(tmp_path, monkeypatch) -> None:
    _isolate()
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    monkeypatch.setattr(settings, "knowledge_cards_enabled", False)
    drawing = _write(tmp_path / "stale.bin", b"stale-drawing")
    digest = file_sha256(drawing)
    cycle = current_cycle_start()
    old = (datetime.now(timezone.utc) - timedelta(seconds=181)).isoformat()
    _insert_claim("stale-claim", digest, cycle, old)
    calls = {"n": 0}

    def _provider() -> dict[str, str]:
        calls["n"] += 1
        return {"content": "visible note", "provider": "stub"}

    out = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_provider)
    assert out.get("ok"), out
    assert calls["n"] == 1

    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, state FROM vision_quota_usage WHERE file_sha256 = ?",
            (digest,),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] != "stale-claim"
    assert rows[0]["state"] == "dispatched"


def test_fresh_claim_is_not_released(tmp_path, monkeypatch) -> None:
    _isolate()
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    monkeypatch.setattr(settings, "knowledge_cards_enabled", False)
    drawing = _write(tmp_path / "fresh.bin", b"fresh-drawing")
    digest = file_sha256(drawing)
    cycle = current_cycle_start()
    _insert_claim("fresh-claim", digest, cycle, db.utc_now())
    calls = {"n": 0}

    def _provider() -> dict[str, str]:
        calls["n"] += 1
        return {"content": "visible note", "provider": "stub"}

    out = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_provider)
    assert out.get("ok"), out
    assert calls["n"] == 1

    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, state FROM vision_quota_usage WHERE file_sha256 = ?",
            (digest,),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == "fresh-claim"
    assert rows[0]["state"] == "dispatched"
