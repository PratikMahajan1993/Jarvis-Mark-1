from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.memory.embeddings import DIM
from app.memory.ingest_queue import (
    IngestPriority,
    IngestQueue,
    IngestTask,
    nightly_ingest,
)
from app.memory.store import latency_budget, search, upsert


def setup_module(_module=None):
    db.init_db()


def test_priority_lane_runs_high_before_low():
    seen: list[str] = []

    async def _handler(payload: dict) -> None:
        seen.append(str(payload["tag"]))

    async def _run() -> None:
        queue = IngestQueue(max_workers=1, backoff=lambda _retries: 0)
        queue.register_handler("drawing", _handler)
        await queue.enqueue(
            IngestTask(kind="drawing", payload={"tag": "low"}, priority=IngestPriority.LOW)
        )
        await queue.enqueue(
            IngestTask(kind="drawing", payload={"tag": "high"}, priority=IngestPriority.HIGH)
        )
        await queue.start()
        for _ in range(50):
            if len(seen) >= 2:
                break
            await asyncio.sleep(0.02)
        await queue.stop()

    asyncio.run(_run())
    assert seen[0] == "high"
    assert seen[1] == "low"


def test_retry_then_success_with_backoff():
    calls = {"n": 0}

    async def _flaky(_payload: dict) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")

    async def _run() -> None:
        queue = IngestQueue(max_workers=1, backoff=lambda _retries: 0)
        queue.register_handler("production", _flaky)
        await queue.enqueue(IngestTask(kind="production", payload={}, max_retries=3))
        await queue.start()
        for _ in range(50):
            if queue.completed:
                break
            await asyncio.sleep(0.02)
        await queue.stop()

    asyncio.run(_run())
    assert calls["n"] == 3
    assert calls["n"] > 1


def test_search_does_not_wait_on_ingest(monkeypatch):
    monkeypatch.setattr("app.memory.store._get_lance", lambda: None)
    monkeypatch.setattr("app.memory.store._lance_tried", True)
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow(_payload: dict) -> None:
        started.set()
        await release.wait()

    async def _run() -> None:
        queue = IngestQueue(max_workers=1, backoff=lambda _retries: 0)
        queue.register_handler("drawing", _slow)
        await queue.start()
        await queue.enqueue(IngestTask(kind="drawing", payload={"name": "slow"}, priority=IngestPriority.HIGH))
        await asyncio.wait_for(started.wait(), timeout=2)
        began = time.perf_counter()
        search("phase2 ingest must not block search", namespace="profile", limit=1)
        elapsed = time.perf_counter() - began
        release.set()
        await queue.stop()
        assert elapsed < 0.5
        assert queue.depth() >= 0

    asyncio.run(_run())


def test_nightly_enqueues_low_priority_work():
    async def _run() -> None:
        from app.memory.ingest_queue import ingest_queue

        if ingest_queue.running:
            await ingest_queue.stop()
        body = await nightly_ingest()
        assert body["ok"] is True
        assert body["queue_depth"] >= 3

    asyncio.run(_run())


def test_latency_budget_warns(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING):
        with latency_budget("sql_lookup", 0):
            time.sleep(0.01)
    assert "exceeded budget" in caplog.text


def test_embed_metadata_labelled_and_mixed_dims_rejected(caplog: pytest.LogCaptureFixture):
    key_a = "phase2-embed-a"
    key_b = "phase2-embed-b"
    with db.connect() as conn:
        conn.execute("DELETE FROM memory_docs WHERE key IN (?, ?)", (key_a, key_b))
    saved = upsert(namespace="jobs", key=key_a, text="hash labelled bracket drawing EN8")
    assert saved["embed_provider"] == "hash"
    assert saved["embed_model_id"]
    assert saved["embed_dim"] == DIM
    with pytest.raises(ValueError, match="mixed embedding dimensions"):
        upsert(
            namespace="jobs",
            key=key_a,
            text="hash labelled bracket drawing EN8",
            embed_meta={"model_id": "hash-v1", "provider": "hash", "dim": 16},
        )
    upsert(namespace="jobs", key=key_b, text="second hash vector for mixed dim check")
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE memory_docs
            SET embed_dim = 16, embed_provider = 'onnx', embed_model_id = 'other-model'
            WHERE key = ?
            """,
            (key_b,),
        )
    caplog.set_level(logging.ERROR, logger="app.memory.store")
    hits = search("bracket drawing EN8", namespace="jobs", limit=5)
    assert "mixed embedding dimensions" in caplog.text
    assert all((hit.get("meta") or {}).get("embed_provider") == "hash" for hit in hits)
    with db.connect() as conn:
        conn.execute("DELETE FROM memory_docs WHERE key IN (?, ?)", (key_a, key_b))
