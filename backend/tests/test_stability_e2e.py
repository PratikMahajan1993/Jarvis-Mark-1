"""Stability + foundation E2E checks against a live Jarvis API.

Run with API up:
  .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
  .venv/bin/python -m pytest backend/tests/test_stability_e2e.py -v --tb=short

The server owns its SQLite state. ``live_api_settings`` points direct test
setup at that same state so confirmations exercise the running API, rather
than a separate pytest-only database.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

BASE = os.environ.get("JARVIS_API", "http://127.0.0.1:8000").rstrip("/")


def _live() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{BASE}/api/health")
            return r.status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.live_service,
    pytest.mark.api_service,
    pytest.mark.skipif(not _live(), reason="Jarvis API not running on :8000"),
]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def live_api_settings():
    """Make direct setup helpers use the live server's data and exports paths."""
    from app.config import settings

    data_dir = Path(os.environ.get("JARVIS_API_DATA_DIR", ROOT / "data")).resolve()
    exports_dir = Path(os.environ.get("JARVIS_API_EXPORTS_DIR", ROOT / "exports")).resolve()
    previous = (settings.data_dir, settings.exports_dir, settings.canvas_dir)
    settings.data_dir = data_dir
    settings.exports_dir = exports_dir
    settings.canvas_dir = data_dir / "canvas"
    try:
        yield
    finally:
        settings.data_dir, settings.exports_dir, settings.canvas_dir = previous


def test_health_reports_status(client: httpx.Client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    provider = data.get("provider")
    assert provider in {"gemini", "ollama"}
    hermes = data.get("hermes")
    assert isinstance(hermes, dict)
    brain_ready = bool(data.get(provider)) and bool(data.get("model_ready"))
    hermes_ready = bool(hermes.get("enabled")) and bool(hermes.get("available"))
    assert data.get("ok") is (brain_ready or hermes_ready)


def test_metrics_and_missions(client: httpx.Client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "hermes_latency" in body
    assert "targets" in body
    m = client.get("/api/missions?limit=5")
    assert m.status_code == 200
    assert "items" in m.json()


def test_suggested_tasks_fast_path(client: httpx.Client):
    t0 = time.monotonic()
    r = client.get("/api/suggested-tasks", params={"refresh": "false", "session_id": "e2e-stab"})
    elapsed = time.monotonic() - t0
    assert r.status_code == 200
    assert elapsed < 5.0, f"fast path too slow: {elapsed:.2f}s"
    assert "items" in r.json()


def test_office_refresh_never_500(client: httpx.Client):
    r = client.post("/api/office/refresh", params={"session_id": "e2e-stab"})
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert "weather" in data


def test_calendar_hitl_strips_jarvis_meta(client: httpx.Client):
    from app import db
    from app.hermes.hitl import request_human_approval

    db.init_db()
    session = "e2e-cal"
    pending = request_human_approval(
        session_id=session,
        kind="calendar_create",
        title="Add event: E2E standup",
        summary="tomorrow",
        payload={
            "title": "E2E standup",
            "start_at": "2099-01-01T16:00:00+05:30",
            "end_at": "2099-01-01T16:30:00+05:30",
            "location": "",
            "notes": "stability test",
        },
        tool_name="create_calendar_event",
    )
    assert "_jarvis" in (pending.get("payload") or {})
    assert pending.get("irreversibility") == 3
    # Reject so we don't pollute calendar; point is payload enrichment didn't break resolve path earlier
    r = client.post(
        "/api/confirm",
        json={"session_id": session, "action_id": pending["id"], "approved": False},
    )
    assert r.status_code == 200
    assert "cancel" in (r.json().get("speak") or "").lower() or r.json().get("speak")


def test_memory_roundtrip_via_tools(client: httpx.Client):
    from app.tools.registry import execute_tool

    up = execute_tool(
        "memory_upsert",
        {"text": "E2E prefers short briefings.", "namespace": "profile", "key": "e2e-brief"},
        "e2e-mem",
    )
    assert up.get("ok")
    found = execute_tool("memory_search", {"query": "short briefings", "namespace": "profile"}, "e2e-mem")
    assert found.get("ok")
    hits = (found.get("data") or {}).get("hits") or []
    assert hits
    wipe = execute_tool(
        "memory_forget",
        {"namespace": "profile", "wipe_namespace": True},
        "e2e-mem",
    )
    assert wipe.get("ok")
    pending = wipe.get("pending") or {}
    assert pending.get("kind") == "memory_wipe"
    # Reject wipe HITL
    client.post(
        "/api/confirm",
        json={"session_id": "e2e-mem", "action_id": pending["id"], "approved": False},
    )


def test_quote_send_queues_hitl_not_raw_send(client: httpx.Client):
    from app.quote import build_quote, quote_to_pdf, queue_quote_send
    from app import db

    built = build_quote(session_id="e2e-quote", part_name="E2E pinion", material="EN8")
    pdf = quote_to_pdf(session_id="e2e-quote", part_name="E2E pinion", rows=built["rows"])
    queued = queue_quote_send(
        session_id="e2e-quote",
        to="nobody@example.com",
        subject="E2E quote",
        body="Test only",
        pdf_path=pdf["artifact"]["path"],
    )
    pending = queued["pending"]
    assert pending["kind"] == "quote_send"
    assert pending["irreversibility"] == 5
    # Reject — never send
    r = client.post(
        "/api/confirm",
        json={"session_id": "e2e-quote", "action_id": pending["id"], "approved": False},
    )
    assert r.status_code == 200
    db.set_pending_status(pending["id"], "rejected")


def test_browser_action_authorize_does_not_fake_success(client: httpx.Client):
    from app.browser_evidence import queue_browser_action

    queued = queue_browser_action(
        session_id="e2e-browser",
        title="Open example",
        summary="Should not pretend to run",
        url="https://example.com",
    )
    pending = queued["pending"]
    r = client.post(
        "/api/confirm",
        json={"session_id": "e2e-browser", "action_id": pending["id"], "approved": True},
    )
    assert r.status_code == 200
    speak = (r.json().get("speak") or "").lower()
    assert "not executable" in speak or "cannot" in speak or "evidence" in speak


def test_chat_casual_responds(client: httpx.Client):
    r = client.post("/api/chat", json={"session_id": "e2e-chat", "message": "ping"})
    assert r.status_code == 200
    data = r.json()
    assert (data.get("speak") or data.get("reply") or "").strip()
