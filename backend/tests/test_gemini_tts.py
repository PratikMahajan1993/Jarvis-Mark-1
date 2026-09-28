"""Gemini desk speech: model order, quota silence, and WAV wrapping. Offline."""

from __future__ import annotations

import pytest

from app import gemini_tts as gt


def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gt, "_quota_until", 0.0)
    monkeypatch.setattr(gt, "_cache_get", lambda _key: None)
    monkeypatch.setattr(gt, "_cache_put", lambda _key, _wav: None)
    monkeypatch.setattr(gt.settings, "gemini_tts_model", "gemini-3.8-flash-lite-tts")
    monkeypatch.setattr(gt.settings, "gemini_tts_fallback_model", "gemini-3.8-flash-tts")
    monkeypatch.setattr(gt.settings, "gemini_tts_economy_model", "gemini-2.5-flash-preview-tts")
    monkeypatch.setattr(gt.settings, "gemini_tts_voice", "Charon")


def test_lite_success_does_not_call_later_models(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)
    calls: list[str] = []

    def _generate(model: str, voice: str, text: str) -> bytes:
        calls.append(model)
        assert voice == "Charon"
        assert text == "Hello"
        return b"RIFFxxxxWAVE"

    monkeypatch.setattr(gt, "_generate", _generate)
    assert gt.synthesize("Hello") == b"RIFFxxxxWAVE"
    assert calls == ["gemini-3.8-flash-lite-tts"]


def test_lite_error_falls_through_to_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)
    calls: list[str] = []

    def _generate(model: str, voice: str, text: str) -> bytes:
        del voice, text
        calls.append(model)
        if model.endswith("lite-tts"):
            raise gt.GeminiTtsError("temporary")
        return b"RIFFxxxxWAVE"

    monkeypatch.setattr(gt, "_generate", _generate)
    assert gt.synthesize("Hello").startswith(b"RIFF")
    assert calls == ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]


def test_economy_model_runs_only_after_both_are_out_of_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)
    calls: list[str] = []

    def _generate(model: str, voice: str, text: str) -> bytes:
        del voice, text
        calls.append(model)
        if model == "gemini-2.5-flash-preview-tts":
            return b"RIFFxxxxWAVE"
        raise gt.GeminiTtsError("quota", exhausted=True)

    monkeypatch.setattr(gt, "_generate", _generate)
    assert gt.synthesize("Hello").startswith(b"RIFF")
    assert calls == [
        "gemini-3.8-flash-lite-tts",
        "gemini-3.8-flash-tts",
        "gemini-2.5-flash-preview-tts",
    ]


def test_non_quota_failure_does_not_use_the_economy_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)
    calls: list[str] = []

    def _generate(model: str, voice: str, text: str) -> bytes:
        del voice, text
        calls.append(model)
        raise gt.GeminiTtsError("upstream")

    monkeypatch.setattr(gt, "_generate", _generate)
    with pytest.raises(gt.GeminiTtsError, match="upstream"):
        gt.synthesize("Hello")
    assert "gemini-2.5-flash-preview-tts" not in calls


def test_all_models_exhausted_stays_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)

    def _generate(model: str, voice: str, text: str) -> bytes:
        del model, voice, text
        raise gt.GeminiTtsError("quota", exhausted=True)

    monkeypatch.setattr(gt, "_generate", _generate)
    with pytest.raises(gt.GeminiTtsError, match="quota is exhausted") as caught:
        gt.synthesize("Hello")
    assert caught.value.exhausted is True
    with pytest.raises(gt.GeminiTtsError, match="quota is exhausted"):
        gt.synthesize("Again")


def test_older_pcm_is_wrapped_as_wav() -> None:
    pcm = b"\x00\x01" * 8
    wav = gt._as_wav(pcm, "audio/L16;codec=pcm;rate=24000")
    assert wav.startswith(b"RIFF")
    assert wav[8:12] == b"WAVE"
    assert wav.endswith(pcm)


def test_lite_wav_is_not_rewrapped() -> None:
    original = b"RIFF\x24\x00\x00\x00WAVEfmt "
    assert gt._as_wav(original, "audio/wav") is original
