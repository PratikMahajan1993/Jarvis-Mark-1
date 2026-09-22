from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.main import app
from app.vision.gate import file_sha256, on_mail_drawing_saved
from app.vision.ledger import current_cycle_start, current_cycle_used


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _isolated_vision_bench():
    with db.connect() as conn:
        from app.vision.schema import ensure_vision_schema

        ensure_vision_schema(conn)
        conn.execute("DELETE FROM vision_quota_usage")
        conn.execute("DELETE FROM disclosure_log")
        conn.execute("DELETE FROM drawing_analysis_state")
    prev = settings.vision_bench_enabled
    settings.vision_bench_enabled = False
    yield
    settings.vision_bench_enabled = prev


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


def test_bench_get_disabled_no_spend(monkeypatch):
    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("dispatch")
        raise AssertionError("dispatch must not run on GET")

    monkeypatch.setattr("app.vision.gate.dispatch_drawing_vision", _boom)
    settings.vision_bench_enabled = False
    with TestClient(app) as client:
        r = client.get("/api/vision/bench")
    assert r.status_code == 200
    body = r.json()
    assert body == {"enabled": False, "items": [], "used": 0, "total": 5, "reset_at": ""}
    assert calls == []


def test_bench_get_lists_queue_and_counter(tmp_path):
    settings.vision_bench_enabled = True
    drawing = _write_bytes(tmp_path / "wait.pdf", b"bench-queue-1")
    on_mail_drawing_saved(drawing)
    digest = file_sha256(drawing)
    cycle = current_cycle_start()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO vision_quota_usage (
              id, cycle_start, file_sha256, customer_id, spent_by, arrival,
              pages, state, turn_id, override_action_id, created_at
            ) VALUES ('u1', ?, ?, NULL, 'owner_bench', 'mail', 1, 'dispatched', NULL, NULL, ?)
            """,
            (cycle, digest, db.utc_now()),
        )

    with TestClient(app) as client:
        r = client.get("/api/vision/bench")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["used"] == 1
    assert body["total"] == 5
    assert body["reset_at"]
    assert len(body["items"]) == 1
    assert body["items"][0]["file_sha256"] == digest
    assert body["items"][0]["display_name"] == "wait.pdf"


def test_bench_analyse_disabled_no_spend(tmp_path, monkeypatch):
    drawing = _write_bytes(tmp_path / "x.bin", b"x")
    digest = file_sha256(drawing)
    on_mail_drawing_saved(drawing)
    settings.vision_bench_enabled = False

    def _boom(*_a, **_k):
        raise AssertionError("must not dispatch when disabled")

    monkeypatch.setattr("app.vision.gate.dispatch_drawing_vision", _boom)
    with TestClient(app) as client:
        r = client.post("/api/vision/bench/analyse", json={"file_sha256": digest})
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "ok": False}
    assert _quota_count(current_cycle_start()) == 0


def test_bench_analyse_spends_via_owner_bench(tmp_path, monkeypatch):
    settings.vision_bench_enabled = True
    drawing = _write_bytes(tmp_path / "spend-me.bin", b"vision-spend")
    on_mail_drawing_saved(drawing)
    digest = file_sha256(drawing)
    seen: dict = {}

    def _fake_dispatch(path, **kwargs):
        seen.update(kwargs)
        return {"ok": True, "file_sha256": digest, "analysis_state": "vision_done"}

    monkeypatch.setattr("app.vision.gate.dispatch_drawing_vision", _fake_dispatch)

    with TestClient(app) as client:
        r = client.post(
            "/api/vision/bench/analyse",
            json={"file_sha256": digest},
        )
    assert r.status_code == 200
    body = r.json()
    assert body.get("enabled") is True
    assert body.get("ok") is True
    assert seen.get("owner_spend") is True
    assert seen.get("spent_by") == "owner_bench"


def test_bench_analyse_over_page_threshold_no_spend(tmp_path, monkeypatch):
    settings.vision_bench_enabled = True
    pdf_path = tmp_path / "big.pdf"
    _write_bytes(pdf_path, b"%PDF-1.4\n")
    monkeypatch.setattr("app.vision.gate.page_count", lambda _p: 10)
    on_mail_drawing_saved(pdf_path)
    digest = file_sha256(pdf_path)

    def _boom():
        raise AssertionError("provider must not run")

    monkeypatch.setattr("app.gemini_client.chat_multimodal", lambda *_a, **_k: _boom())

    with TestClient(app) as client:
        r = client.post("/api/vision/bench/analyse", json={"file_sha256": digest})
    assert r.status_code == 200
    body = r.json()
    assert not body.get("ok")
    assert "sheet index" in (body.get("error") or "").lower()
    assert _quota_count(current_cycle_start()) == 0


def test_bench_analyse_missing_file_no_spend(tmp_path):
    settings.vision_bench_enabled = True
    drawing = _write_bytes(tmp_path / "gone.bin", b"gone")
    on_mail_drawing_saved(drawing)
    digest = file_sha256(drawing)
    drawing.unlink()

    with TestClient(app) as client:
        r = client.post("/api/vision/bench/analyse", json={"file_sha256": digest})
    assert r.status_code == 200
    body = r.json()
    assert not body.get("ok")
    assert _quota_count(current_cycle_start()) == 0


def test_bench_analyse_uses_provider_stub(tmp_path, monkeypatch):
    settings.vision_bench_enabled = True
    drawing = _write_bytes(tmp_path / "prov.bin", b"prov")
    on_mail_drawing_saved(drawing)
    digest = file_sha256(drawing)

    monkeypatch.setattr(
        "app.gemini_client.chat_multimodal",
        MagicMock(return_value={"content": "dims", "provider": "gemini-stub"}),
    )

    with TestClient(app) as client:
        r = client.post("/api/vision/bench/analyse", json={"file_sha256": digest})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert current_cycle_used() == 1
