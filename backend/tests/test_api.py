"""Lightweight API smoke tests (offline)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import gemini_tts
from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body


def test_tts_endpoint():
    client = TestClient(app)
    fake_wav = b"RIFF\x00\x00\x00\x00WAVE"
    with patch.object(gemini_tts, "synthesize", return_value=fake_wav):
        r = client.post("/api/tts", json={"text": "test"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/wav")
