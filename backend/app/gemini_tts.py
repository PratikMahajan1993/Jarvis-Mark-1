"""Desk speech through Gemini TTS.

The browser plays one WAV from ``POST /api/tts``. Voicebox is not on this path.
Primary model is Gemini 3.8 Flash Lite TTS. A failed call falls through to
Gemini 3.8 Flash TTS. The older 2.5 Flash preview model is used only after both
of those are out of calls. When every model is out of calls, synthesis raises
and the desk stays silent. The reply text is already on the HUD.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import struct
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .config import settings

log = logging.getLogger("jarvis.tts")

_API = "https://generativelanguage.googleapis.com/v1beta"
_CACHE_VERSION = "g1"
_MEM_LIMIT = 48
_TTS_CACHE_TTL_SEC = 7 * 24 * 3600
_QUOTA_COOLDOWN_SEC = 60.0

_audio_mem: dict[str, bytes] = {}
_audio_lock = threading.Lock()
_quota_until = 0.0
_quota_lock = threading.Lock()


class GeminiTtsError(RuntimeError):
    """Speech did not produce audio. ``exhausted`` means this model is out of calls."""

    def __init__(self, message: str, *, exhausted: bool = False) -> None:
        super().__init__(message)
        self.exhausted = exhausted


def _models() -> tuple[str, str]:
    primary = (settings.gemini_tts_model or "gemini-3.8-flash-lite-tts").strip()
    fallback = (settings.gemini_tts_fallback_model or "gemini-3.8-flash-tts").strip()
    return primary or "gemini-3.8-flash-lite-tts", fallback or "gemini-3.8-flash-tts"


def _economy_model() -> str:
    return (settings.gemini_tts_economy_model or "gemini-2.5-flash-preview-tts").strip() or "gemini-2.5-flash-preview-tts"


def _voice() -> str:
    return (settings.gemini_tts_voice or "Charon").strip() or "Charon"


def status_payload() -> dict[str, Any]:
    primary, fallback = _models()
    return {
        "provider": "gemini",
        "voice": _voice(),
        "model": primary,
        "fallback_model": fallback,
        "economy_model": _economy_model(),
        "quota_blocked": time.time() < _quota_until,
    }


def _cache_key(text: str, voice: str) -> str:
    raw = "|".join([_CACHE_VERSION, voice, text]).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_dir() -> Path:
    path = Path(settings.data_dir) / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remember_audio(key: str, wav: bytes) -> None:
    _audio_mem[key] = wav
    while len(_audio_mem) > _MEM_LIMIT:
        _audio_mem.pop(next(iter(_audio_mem)))


def _expire_old_tts_files() -> None:
    cutoff = time.time() - _TTS_CACHE_TTL_SEC
    for item in _cache_dir().glob("*.wav"):
        try:
            if item.is_file() and item.stat().st_mtime < cutoff:
                item.unlink()
        except OSError:
            continue


def _cache_get(key: str) -> bytes | None:
    path = _cache_dir() / f"{key}.wav"
    with _audio_lock:
        hit = _audio_mem.get(key)
        if hit:
            return hit
        try:
            if not path.is_file():
                return None
            data = path.read_bytes()
        except OSError:
            return None
        if not data.startswith(b"RIFF"):
            return None
        _remember_audio(key, data)
        return data


def _cache_put(key: str, wav: bytes) -> None:
    if not wav.startswith(b"RIFF"):
        return
    path = _cache_dir() / f"{key}.wav"
    with _audio_lock:
        _remember_audio(key, wav)
        try:
            path.write_bytes(wav)
        except OSError:
            return
        _expire_old_tts_files()


def _error_message(data: dict[str, Any], raw: str) -> str:
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        message = str(err.get("message") or err.get("status") or "").strip()
        if message:
            return message[:400]
    return (raw or "Gemini speech failed")[:400]


def _is_exhausted(status: int, data: dict[str, Any], raw: str) -> bool:
    if status == 429:
        return True
    err = data.get("error") if isinstance(data, dict) else None
    status_name = str(err.get("status") or "") if isinstance(err, dict) else ""
    blob = f"{status_name} {_error_message(data, raw)}".lower()
    return any(token in blob for token in ("resource_exhausted", "resource exhausted", "quota", "rate limit", "rate-limit"))


def _as_wav(raw: bytes, mime: str) -> bytes:
    """Lite TTS returns WAV. The older Flash model returns headerless PCM."""
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return raw
    rate = 24000
    bits = 16
    for param in (mime or "").split(";"):
        piece = param.strip()
        lower = piece.lower()
        if lower.startswith("rate="):
            try:
                rate = int(piece.split("=", 1)[1])
            except ValueError:
                pass
        elif lower.startswith("audio/l"):
            try:
                bits = int(lower.split("l", 1)[1])
            except ValueError:
                pass
    if bits not in (8, 16, 24, 32) or rate <= 0 or not raw:
        raise GeminiTtsError("Gemini speech returned audio the desk cannot play")
    channels = 1
    block_align = channels * (bits // 8)
    byte_rate = rate * block_align
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(raw),
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        len(raw),
    )
    return header + raw


def _generate(model: str, voice: str, text: str) -> bytes:
    if not settings.gemini_api_key:
        raise GeminiTtsError("GEMINI_API_KEY is empty")
    timeout = max(5.0, float(settings.gemini_tts_timeout_sec or 30.0))
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    url = f"{_API}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
                json=body,
            )
    except httpx.HTTPError as exc:
        raise GeminiTtsError(f"Gemini speech request failed: {exc}") from exc
    raw_text = response.text[:500]
    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if response.status_code >= 400:
        raise GeminiTtsError(
            _error_message(data, raw_text),
            exhausted=_is_exhausted(response.status_code, data, raw_text),
        )
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    inline: dict[str, Any] = {}
    for part in parts:
        if not isinstance(part, dict):
            continue
        found = part.get("inlineData") or part.get("inline_data") or {}
        if isinstance(found, dict) and found.get("data"):
            inline = found
            break
    encoded = str(inline.get("data") or "")
    if not encoded:
        raise GeminiTtsError(f"{model} returned no audio")
    try:
        audio = base64.b64decode(encoded)
    except ValueError as exc:
        raise GeminiTtsError(f"{model} returned audio the desk cannot read") from exc
    mime = str(inline.get("mimeType") or inline.get("mime_type") or "")
    return _as_wav(audio, mime)


def _open_quota() -> None:
    global _quota_until
    with _quota_lock:
        _quota_until = time.time() + _QUOTA_COOLDOWN_SEC


def synthesize(text: str, *, profile: str | None = None, language: str = "en") -> bytes:
    """Return a WAV for this line. ``profile`` is ignored; the desk voice is Charon."""
    del profile, language
    line = (text or "").strip()
    if not line:
        raise GeminiTtsError("Empty speech text")
    if time.time() < _quota_until:
        raise GeminiTtsError("Gemini speech quota is exhausted", exhausted=True)
    voice = _voice()
    key = _cache_key(line, voice)
    cached = _cache_get(key)
    if cached:
        return cached

    primary, fallback = _models()
    order: list[str] = []
    for name in (primary, fallback):
        if name and name not in order:
            order.append(name)
    errors: list[GeminiTtsError] = []
    for model in order:
        try:
            wav = _generate(model, voice, line)
        except GeminiTtsError as exc:
            errors.append(exc)
            if exc.exhausted:
                log.info("Gemini speech model %s is out of calls", model)
                continue
            if model == primary and fallback and fallback != primary:
                log.info("Gemini speech model %s failed; trying %s", model, fallback)
                continue
            raise
        else:
            _cache_put(key, wav)
            return wav

    both_exhausted = bool(errors) and all(item.exhausted for item in errors) and len(errors) == len(order)
    economy = _economy_model()
    if both_exhausted and economy and economy not in order:
        log.info("Gemini speech models are out of calls; trying %s", economy)
        try:
            wav = _generate(economy, voice, line)
        except GeminiTtsError as exc:
            if exc.exhausted:
                _open_quota()
                raise GeminiTtsError("Gemini speech quota is exhausted", exhausted=True) from exc
            raise
        else:
            _cache_put(key, wav)
            return wav

    if both_exhausted:
        _open_quota()
        raise GeminiTtsError("Gemini speech quota is exhausted", exhausted=True)
    if errors:
        raise errors[-1]
    raise GeminiTtsError("Gemini speech failed")


def prefetch_tts(text: str, *, profile: str | None = None, language: str = "en") -> None:
    """Warm the speech cache for a line the desk is about to play."""
    line = (text or "").strip()
    if not line or not settings.gemini_api_key:
        return

    def _run() -> None:
        try:
            synthesize(line, profile=profile, language=language)
        except Exception:
            return

    threading.Thread(target=_run, name="jarvis-tts-prefetch", daemon=True).start()
