"""Voicebox TTS client and /api/tts degradation (offline)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import voicebox as vb
from app.main import app


def test_resolve_profile_creates_kokoro_preset_when_empty():
    client = MagicMock(spec=httpx.Client)
    empty = httpx.Response(200, json=[])
    created = httpx.Response(
        200,
        json={
            "id": "prof-1",
            "name": "Mark",
            "default_engine": "kokoro",
            "preset_engine": "kokoro",
        },
    )

    def fake_get(url: str, *args, **kwargs):
        if url.endswith("/profiles"):
            return empty
        raise AssertionError(url)

    def fake_post(url: str, *args, **kwargs):
        if url.endswith("/profiles"):
            body = kwargs.get("json") or {}
            assert body.get("voice_type") == "preset"
            assert body.get("preset_engine") == "kokoro"
            assert body.get("name") == "Mark"
            return created
        raise AssertionError(url)

    client.get.side_effect = fake_get
    client.post.side_effect = fake_post

    vb._profile_cache.clear()
    row = vb.resolve_profile(client, "Mark")
    assert row["id"] == "prof-1"
    assert client.post.call_count == 1


def test_api_tts_returns_503_not_502_on_voicebox_error():
    client = TestClient(app)
    with patch.object(vb, "synthesize", side_effect=vb.VoiceboxTtsError("Voicebox generate failed (422): bad")):
        response = client.post("/api/tts", json={"text": "Hello there"})
    assert response.status_code == 503
    assert "Voicebox generate failed" in response.json()["detail"]
