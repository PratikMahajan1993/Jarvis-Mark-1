from __future__ import annotations

import asyncio
import json
import threading

from fastapi.testclient import TestClient

from app.core import features as f
from app.main import app


def test_register_and_publish():
    f.register_feature(f.Feature(id="t"))
    assert any(x.id == "t" for x in f.features())
    f.publish("x", {"a": 1})


def test_get_api_features_includes_weather():
    client = TestClient(app)
    resp = client.get("/api/features")
    assert resp.status_code == 200
    body = resp.json()
    assert "features" in body
    ids = {row["id"] for row in body["features"]}
    assert "weather" in ids
    weather = next(row for row in body["features"] if row["id"] == "weather")
    assert "intents" in weather
    assert "approval_kinds" in weather
    assert "topics" in weather


def test_events_sse_publish_and_subscriber_cleanup():
    """Publish is received by GET /api/events SSE; closing the stream drops the subscriber."""

    async def _run() -> None:
        f._subscribers.clear()
        # GET /api/events handler
        resp = await f.events(topics="feat-sse")
        agen = resp.body_iterator

        open_chunk = await agen.__anext__()
        assert open_chunk.strip().startswith(": open")
        assert len(f._subscribers) == 1

        # Off-loop publish (sync FastAPI threadpool path → call_soon_threadsafe)
        threading.Thread(
            target=lambda: f.publish("feat-sse", {"ok": True}),
            daemon=True,
        ).start()

        chunk = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
        assert "event: feat-sse" in chunk
        data_line = next(ln for ln in chunk.splitlines() if ln.startswith("data:"))
        assert json.loads(data_line.split(":", 1)[1].strip()) == {"ok": True}
        assert len(f._subscribers) == 1

        await agen.aclose()
        assert len(f._subscribers) == 0

    asyncio.run(_run())


def test_publish_threadsafe_still_works_with_loaded_features():
    """Regression: publish must not raise after load_features and remains thread-safe."""
    f.publish("platform-smoke", {"n": 1})
    assert any(x.id == "weather" for x in f.features())
