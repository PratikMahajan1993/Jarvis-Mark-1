from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.memory import ingest as memory_ingest
from app.quote import analyze_drawing_vision
from app.vision.gate import (
    dispatch_drawing_vision,
    file_sha256,
    get_analysis_state,
    on_mail_drawing_saved,
)
from app.vision.ledger import apply_override_claim, current_cycle_start


def setup_module(_module=None):
    db.init_db()


@pytest.fixture(autouse=True)
def _isolated_vision_ledger():
    with db.connect() as conn:
        from app.vision.schema import ensure_vision_schema

        ensure_vision_schema(conn)
        conn.execute("DELETE FROM vision_quota_usage")
        conn.execute("DELETE FROM disclosure_log")
        conn.execute("DELETE FROM drawing_analysis_state")
    for session in ("v1-mail", "v1-cap", "v1-fail", "default"):
        for row in db.list_pending(session):
            db.set_pending_status(row["id"], "rejected")
    yield


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


def test_mail_ingest_needs_vision_zero_provider_calls(tmp_path, monkeypatch):
    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("provider")
        raise AssertionError("provider must not run")

    monkeypatch.setattr("app.gemini_client.chat_multimodal", _boom)
    drawing = _write_bytes(tmp_path / "cust-drawing.bin", b"mail-ingest-1")

    on_mail_drawing_saved(drawing)
    digest = file_sha256(drawing)
    assert get_analysis_state(digest) == "needs_vision"
    assert calls == []

    result = analyze_drawing_vision(str(drawing), session_id="v1-mail")
    assert not result.get("ok")
    assert result.get("analysis_state") == "needs_vision"
    assert calls == []


def test_sixth_distinct_owner_spend_queues_hitl_no_provider(tmp_path, monkeypatch):
    calls: list[str] = []

    def _provider(*_a, **_k):
        calls.append("hit")
        return {"content": "dims", "provider": "stub"}

    cycle = current_cycle_start()
    paths = []
    for i in range(6):
        p = _write_bytes(tmp_path / f"doc-{i}.bin", f"pdf-bytes-{i}".encode())
        paths.append(p)

    for p in paths[:5]:
        out = dispatch_drawing_vision(
            p,
            owner_spend=True,
            session_id="v1-cap",
            provider_call=_provider,
        )
        assert out.get("ok"), out

    assert len(calls) == 5
    assert _quota_count(cycle) == 5

    sixth = dispatch_drawing_vision(
        paths[5],
        owner_spend=True,
        session_id="v1-cap",
        provider_call=_provider,
    )
    assert not sixth.get("ok")
    assert sixth.get("pending")
    assert sixth["pending"].get("kind") == "vision_quota_override"
    assert len(calls) == 5

    pending = db.list_pending("v1-cap")
    assert any(p.get("kind") == "vision_quota_override" for p in pending)


def test_concurrent_last_free_unit_one_success(tmp_path):
    cycle = current_cycle_start()
    for i in range(4):
        p = _write_bytes(tmp_path / f"seed-{i}.bin", f"seed-{i}".encode())
        with db.connect() as conn:
            from app.vision.schema import ensure_vision_schema

            ensure_vision_schema(conn)
            conn.execute(
                """
                INSERT INTO vision_quota_usage (
                  id, cycle_start, file_sha256, customer_id, spent_by, arrival,
                  pages, state, turn_id, override_action_id, created_at
                ) VALUES (?, ?, ?, NULL, 'owner_bench', 'test', 1, 'dispatched', NULL, NULL, ?)
                """,
                (f"seed{i}", cycle, file_sha256(p), db.utc_now()),
            )

    a = _write_bytes(tmp_path / "race-a.bin", b"race-a")
    b = _write_bytes(tmp_path / "race-b.bin", b"race-b")
    results: list[dict] = []

    def _run(path: Path):
        out = dispatch_drawing_vision(
            path,
            owner_spend=True,
            provider_call=lambda: {"content": "ok", "provider": "stub"},
        )
        results.append(out)

    t1 = threading.Thread(target=_run, args=(a,))
    t2 = threading.Thread(target=_run, args=(b,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    ok_count = sum(1 for r in results if r.get("ok"))
    cap_count = sum(1 for r in results if r.get("pending") or r.get("error") == "Vision quota exhausted for this cycle.")
    assert ok_count == 1
    assert cap_count == 1
    assert _quota_count(cycle) == 5


def test_second_owner_spend_same_sha_no_new_unit(tmp_path):
    cycle = current_cycle_start()
    drawing = _write_bytes(tmp_path / "repeat.bin", b"same-drawing")
    digest = file_sha256(drawing)
    n_calls = {"n": 0}

    def _provider():
        n_calls["n"] += 1
        return {"content": "first", "provider": "stub"}

    first = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_provider)
    assert first.get("ok")
    assert _quota_count(cycle) == 1

    second = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_provider)
    assert second.get("ok")
    assert second.get("reused_unit") is True
    assert _quota_count(cycle) == 1
    assert n_calls["n"] == 2


def test_provider_exception_no_quota_no_corpus(tmp_path, monkeypatch):
    drawing = _write_bytes(tmp_path / "fail.bin", b"fail-bytes")
    cycle = current_cycle_start()

    ingest_mock = MagicMock()
    monkeypatch.setattr(memory_ingest, "ingest_drawing_summary", ingest_mock)

    def _fail():
        raise RuntimeError("cloud down")

    out = dispatch_drawing_vision(drawing, owner_spend=True, provider_call=_fail)
    assert not out.get("ok")
    assert _quota_count(cycle) == 0
    ingest_mock.assert_not_called()

    out2 = analyze_drawing_vision(str(drawing), owner_spend=True, session_id="v1-fail")
    assert not out2.get("ok")
    ingest_mock.assert_not_called()


def test_six_page_pack_sheet_index_no_provider(tmp_path):
    from pypdf import PdfWriter

    pdf_path = tmp_path / "pack.pdf"
    writer = PdfWriter()
    for i in range(6):
        writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as fh:
        writer.write(fh)

    calls: list[str] = []

    def _provider():
        calls.append("nope")
        return {"content": "x", "provider": "stub"}

    out = dispatch_drawing_vision(pdf_path, owner_spend=True, provider_call=_provider)
    assert not out.get("ok")
    assert out.get("page_count") == 6
    assert out.get("sheet_index")
    assert out["sheet_index"]["page_count"] == 6
    assert len(out["sheet_index"]["sheets"]) == 6
    assert calls == []


def test_override_claim_allows_one_document_at_cap(tmp_path):
    cycle = current_cycle_start()
    for i in range(5):
        p = _write_bytes(tmp_path / f"full-{i}.bin", f"full-{i}".encode())
        with db.connect() as conn:
            from app.vision.schema import ensure_vision_schema

            ensure_vision_schema(conn)
            conn.execute(
                """
                INSERT INTO vision_quota_usage (
                  id, cycle_start, file_sha256, customer_id, spent_by, arrival,
                  pages, state, turn_id, override_action_id, created_at
                ) VALUES (?, ?, ?, NULL, 'owner_bench', 'test', 1, 'dispatched', NULL, NULL, ?)
                """,
                (f"full{i}", cycle, file_sha256(p), db.utc_now()),
            )

    extra = _write_bytes(tmp_path / "override-me.bin", b"override-doc")
    digest = file_sha256(extra)
    with db.connect() as conn:
        claim = apply_override_claim(
            conn,
            cycle_start=cycle,
            file_sha256=digest,
            customer_id="cust-1",
            arrival="owner_bench",
            pages=1,
            override_action_id="hitl-override-1",
        )
    assert claim.get("ok")

    out = dispatch_drawing_vision(
        extra,
        owner_spend=True,
        provider_call=lambda: {"content": "override ok", "provider": "stub"},
    )
    assert out.get("ok")
    assert _quota_count(cycle) == 6
