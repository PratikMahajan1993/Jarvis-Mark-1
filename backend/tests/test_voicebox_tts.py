"""Voicebox TTS client and /api/tts degradation (offline)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import voicebox as vb
from app.main import app


def test_resolve_profile_does_not_invent_a_voice():
    client = MagicMock(spec=httpx.Client)
    empty = httpx.Response(200, json=[])
    client.get.return_value = empty
    vb._profile_cache.clear()
    with pytest.raises(vb.VoiceboxTtsError, match="no profile named Mark"):
        vb.resolve_profile(client, "Mark")
    client.post.assert_not_called()


def test_resolve_profile_does_not_substitute_another_name():
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = httpx.Response(
        200,
        json=[{"id": "other", "name": "Alloy", "default_engine": "kokoro", "preset_voice_id": "af_alloy"}],
    )
    vb._profile_cache.clear()
    with pytest.raises(vb.VoiceboxTtsError, match="no profile named Mark"):
        vb.resolve_profile(client, "Mark")


def test_api_tts_returns_503_when_speech_fails():
    client = TestClient(app)
    from app import gemini_tts

    with patch.object(gemini_tts, "synthesize", side_effect=gemini_tts.GeminiTtsError("Gemini speech quota is exhausted", exhausted=True)):
        response = client.post("/api/tts", json={"text": "Hello there"})
    assert response.status_code == 503
    assert "quota" in response.json()["detail"].lower()
