from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.config import REPO_ROOT, settings
from app.live_log import _jsonl_path, _md_path, log_paths, recent_events, record


def test_live_log_writes_jsonl_and_markdown(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    work_dir = tmp_path / "work"
    data_dir.mkdir()
    work_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr("app.live_log._jsonl_path", data_dir / "live_test.jsonl")
    monkeypatch.setattr("app.live_log._md_path", work_dir / "LIVE_TEST.md")
    monkeypatch.setattr("app.live_log._hydrated", True)
    monkeypatch.setattr("app.live_log._recent", __import__("collections").deque(maxlen=150))

    record(
        source="api",
        kind="chat_in",
        session_id="test-session",
        fields={"message": "hello live log"},
    )
    record(
        source="hud",
        kind="workspace",
        session_id="test-session",
        fields={"from": "monitor", "to": "casual", "reason": "switcher"},
    )

    jsonl = data_dir / "live_test.jsonl"
    assert jsonl.is_file()
    lines = [json.loads(ln) for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0]["kind"] == "chat_in"
    assert lines[1]["fields"]["to"] == "casual"

    md = work_dir / "LIVE_TEST.md"
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "live test log" in text.lower()
    assert "workspace" in text
    assert "switcher" in text

    recent = recent_events(limit=10)
    assert len(recent) == 2
    assert recent[0]["kind"] == "workspace"


def test_api_live_log_endpoint(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    work_dir = tmp_path / "work"
    data_dir.mkdir()
    work_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr("app.live_log._jsonl_path", data_dir / "live_test.jsonl")
    monkeypatch.setattr("app.live_log._md_path", work_dir / "LIVE_TEST.md")
    monkeypatch.setattr("app.live_log._hydrated", True)
    monkeypatch.setattr("app.live_log._recent", __import__("collections").deque(maxlen=150))

    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/live-log",
            json={
                "source": "hud",
                "kind": "hud_boot",
                "session_id": "default",
                "fields": {"workspace": "monitor"},
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        listed = client.get("/api/live-log/recent?limit=5")
        assert listed.status_code == 200
        body = listed.json()
        assert "items" in body
        assert body["items"][0]["kind"] == "hud_boot"
        assert "paths" in body
