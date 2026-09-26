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


def test_api_tts_returns_503_not_502_on_voicebox_error():
    client = TestClient(app)
    with patch.object(vb, "synthesize", side_effect=vb.VoiceboxTtsError("Voicebox generate failed (422): bad")):
        response = client.post("/api/tts", json={"text": "Hello there"})
    assert response.status_code == 503
    assert "Voicebox generate failed" in response.json()["detail"]
