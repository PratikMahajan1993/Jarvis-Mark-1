"""Drawing bytes withheld from the model say why, and that dimensions must not be invented."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversations import _chat_with_fallback


def test_withhold_copy_states_bytes_removed_because_owner_spend_is_false(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake(history, user_text, media_parts, system="", **kwargs):
        seen["media"] = media_parts
        seen["system"] = system
        return {"content": "local only", "model": "stub"}

    monkeypatch.setattr("app.gemini_client.chat_multimodal", _fake)
    media = [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]
    out = _chat_with_fallback([], "what is the bore?", media, "sys", "gemini-test", owner_spend=False)
    assert out["content"] == "local only"
    text = str(seen["media"][0]["text"])
    assert "bytes were present" in text
    assert "removed because owner_spend is false" in text
    assert "invent dimensions" in text
    assert "inline_data" not in str(seen["media"])
    assert "owner_spend is false" in str(seen["system"])
    assert "invent dimensions" in str(seen["system"])


def test_owner_spend_keeps_drawing_bytes(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake(history, user_text, media_parts, system="", **kwargs):
        seen["media"] = media_parts
        return {"content": "saw it", "model": "stub"}

    monkeypatch.setattr("app.gemini_client.chat_multimodal", _fake)
    media = [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]
    _chat_with_fallback([], "what is the bore?", media, "sys", "gemini-test", owner_spend=True)
    assert seen["media"] == media
