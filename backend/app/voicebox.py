"""Local Voicebox TTS client (desktop app API on :17493).

Docs: https://docs.voicebox.sh/
- POST /speak generates *and plays* on the machine (speaking pill).
- POST /generate synthesizes only — we use this so the browser plays once.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .config import settings

_STATUS_RE = re.compile(r'"status"\s*:\s*"([^"]+)"')
_profile_cache: dict[str, dict[str, str]] = {}
_audio_mem: dict[str, bytes] = {}
_audio_lock = threading.Lock()
_profile_ensure_lock = threading.Lock()
_prefetch_inflight: set[str] = set()
_MEM_LIMIT = 48

# Jarvis default voice name → Kokoro preset when Voicebox has no cloned profiles yet.
_PRESET_VOICE_BY_NAME: dict[str, tuple[str, str]] = {
    "mark": ("kokoro", "bm_george"),
    "george": ("kokoro", "bm_george"),
    "daniel": ("kokoro", "bm_daniel"),
    "adam": ("kokoro", "am_adam"),
    "liam": ("kokoro", "am_liam"),
}
_DEFAULT_PRESET: tuple[str, str] = ("kokoro", "bm_george")


class VoiceboxTtsError(RuntimeError):
    """Voicebox could not produce audio (HUD should fall back to browser TTS)."""


def voicebox_base() -> str:
    return (settings.voicebox_url or "http://127.0.0.1:17493").rstrip("/")


def voicebox_reachable(timeout: float = 1.5) -> bool:
    if not settings.voicebox_enabled:
        return False
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{voicebox_base()}/profiles")
            return response.status_code < 500
    except Exception:
        return False


def _named_profile_exists(client: httpx.Client, profile: str) -> bool:
    name = (profile or "").strip() or "Mark"
    for row in _profiles(client):
        row_name = str(row.get("name") or "").strip()
        row_id = str(row.get("id") or row.get("profile_id") or "").strip()
        if row_id and row_name.lower() == name.lower():
            return True
    cached = _profile_cache.get(name.lower())
    return bool(cached and cached.get("id"))


def status_payload() -> dict[str, Any]:
    up = voicebox_reachable()
    profile_ready = False
    profile_count = 0
    if up and settings.voicebox_enabled:
        try:
            with httpx.Client(timeout=2.0) as client:
                rows = _profiles(client)
                profile_count = len(rows)
                profile_ready = profile_count > 0 and _named_profile_exists(
                    client, settings.voicebox_profile or "Mark"
                )
        except Exception:
            profile_ready = False
    return {
        "enabled": bool(settings.voicebox_enabled),
        "available": up,
        "profile_ready": profile_ready,
        "profile_count": profile_count,
        "url": voicebox_base(),
        "profile": settings.voicebox_profile or "Mark",
        "cached_clips": len(_audio_mem),
    }


def _parse_status(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("data:"):
        text = text.split("data:", 1)[1].strip()
    match = _STATUS_RE.search(text)
    if match:
        return match.group(1).lower()
    try:
        import json

        payload = json.loads(text)
        return str(payload.get("status") or "").lower()
    except Exception:
        return ""


def _profiles(client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"{voicebox_base()}/profiles")
    if response.status_code >= 400:
        return []
    payload = response.json() if response.content else {}
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    for key in ("profiles", "items", "value"):
        rows = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _preset_for_name(name: str) -> tuple[str, str]:
    key = (name or "").strip().lower() or "mark"
    return _PRESET_VOICE_BY_NAME.get(key, _DEFAULT_PRESET)


def _ensure_preset_profile(client: httpx.Client, name: str) -> dict[str, Any]:
    """Create a Kokoro preset profile when Voicebox returns an empty /profiles list."""
    voice_name = (name or "").strip() or "Mark"
    engine, voice_id = _preset_for_name(voice_name)
    body = {
        "name": voice_name,
        "voice_type": "preset",
        "preset_engine": engine,
        "preset_voice_id": voice_id,
        "default_engine": engine,
        "language": "en",
    }
    response = client.post(f"{voicebox_base()}/profiles", json=body)
    if response.status_code >= 400:
        raise VoiceboxTtsError(
            f"Voicebox profile create failed ({response.status_code}): {response.text[:240]}"
        )
    row = response.json() if response.content else {}
    if not isinstance(row, dict):
        raise VoiceboxTtsError("Voicebox profile create returned invalid payload")
    row_id = str(row.get("id") or row.get("profile_id") or "").strip()
    if not row_id:
        raise VoiceboxTtsError(f"Voicebox profile missing id after create: {voice_name}")
    eng = str(row.get("default_engine") or row.get("preset_engine") or engine).strip()
    _profile_cache[voice_name.lower()] = {"id": row_id, "engine": eng}
    return row


def resolve_profile(client: httpx.Client, profile: str) -> dict[str, Any]:
    name = (profile or "").strip() or "Mark"
    cached = _profile_cache.get(name.lower())
    if cached and cached.get("id"):
        return {
            "id": cached["id"],
            "name": name,
            "default_engine": cached.get("engine") or "",
            "preset_engine": cached.get("engine") or "",
        }
    rows = _profiles(client)
    chosen: dict[str, Any] | None = None
    for row in rows:
        row_name = str(row.get("name") or "").strip()
        row_id = str(row.get("id") or row.get("profile_id") or "").strip()
        if row_id and row_name.lower() == name.lower():
            chosen = row
            break
    if chosen is None:
        for row in rows:
            row_id = str(row.get("id") or row.get("profile_id") or "").strip()
            if row_id:
                chosen = row
                break
    if not chosen:
        with _profile_ensure_lock:
            rows = _profiles(client)
            for row in rows:
                row_name = str(row.get("name") or "").strip()
                row_id = str(row.get("id") or row.get("profile_id") or "").strip()
                if row_id and row_name.lower() == name.lower():
                    chosen = row
                    break
            if not chosen and rows:
                for row in rows:
                    row_id = str(row.get("id") or row.get("profile_id") or "").strip()
                    if row_id:
                        chosen = row
                        break
            if not chosen:
                chosen = _ensure_preset_profile(client, name)
    if not chosen:
        raise VoiceboxTtsError(f"Voicebox profile not found: {name}")
    row_id = str(chosen.get("id") or chosen.get("profile_id") or "").strip()
    engine = str(chosen.get("default_engine") or chosen.get("preset_engine") or "").strip()
    if row_id:
        _profile_cache[name.lower()] = {"id": row_id, "engine": engine}
    return chosen


def _cache_key(text: str, profile: str, language: str) -> str:
    raw = f"{profile}|{language}|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _cache_dir() -> Path:
    path = Path(settings.data_dir) / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mem_put(key: str, wav: bytes) -> None:
    with _audio_lock:
        _audio_mem[key] = wav
        while len(_audio_mem) > _MEM_LIMIT:
            _audio_mem.pop(next(iter(_audio_mem)))


def _cache_get(key: str) -> bytes | None:
    with _audio_lock:
        hit = _audio_mem.get(key)
    if hit:
        return hit
    path = _cache_dir() / f"{key}.wav"
    if path.is_file():
        try:
            data = path.read_bytes()
            if data:
                _mem_put(key, data)
                return data
        except OSError:
            return None
    return None


def _cache_put(key: str, wav: bytes) -> None:
    if not wav:
        return
    _mem_put(key, wav)
    try:
        (_cache_dir() / f"{key}.wav").write_bytes(wav)
    except OSError:
        pass


def synthesize(
    text: str,
    *,
    profile: str | None = None,
    language: str = "en",
) -> bytes:
    """
    Generate speech via Voicebox POST /generate (no local autoplay) and return WAV bytes.
    Uses an in-memory + disk cache so repeated / fast-follow lines play instantly.
    """
    line = (text or "").strip()
    if not line:
        raise VoiceboxTtsError("Empty speech text")
    if not settings.voicebox_enabled:
        raise VoiceboxTtsError("Voicebox disabled")

    voice = (profile or settings.voicebox_profile or "Mark").strip() or "Mark"
    lang = language or "en"
    key = _cache_key(line, voice, lang)
    cached = _cache_get(key)
    if cached:
        return cached

    timeout = max(5.0, float(settings.voicebox_timeout_sec or 45.0))
    base = voicebox_base()

    with httpx.Client(timeout=timeout) as client:
        profile_row = resolve_profile(client, voice)
        profile_id = str(profile_row.get("id") or profile_row.get("profile_id") or "").strip()
        if not profile_id:
            raise VoiceboxTtsError(f"Voicebox profile missing id: {voice}")
        engine = (
            str(profile_row.get("default_engine") or profile_row.get("preset_engine") or "").strip()
            or None
        )
        body: dict[str, Any] = {
            "text": line[:5000],
            "profile_id": profile_id,
            "language": lang,
            "personality": False,
        }
        if engine:
            body["engine"] = engine
        started = client.post(f"{base}/generate", json=body)
        if started.status_code >= 400:
            raise VoiceboxTtsError(
                f"Voicebox generate failed ({started.status_code}): {started.text[:240]}"
            )
        payload = started.json() if started.content else {}
        generation_id = str(payload.get("id") or "").strip()
        if not generation_id:
            raise VoiceboxTtsError("Voicebox did not return a generation id")

        if payload.get("audio_path") or str(payload.get("status") or "").lower() in {
            "completed",
            "complete",
            "done",
            "ready",
        }:
            audio = client.get(f"{base}/audio/{generation_id}")
            if audio.status_code < 400 and audio.content:
                _cache_put(key, audio.content)
                return audio.content

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_resp = client.get(f"{base}/generate/{generation_id}/status")
            state = _parse_status(status_resp.text)
            if state in {"completed", "complete", "done", "ready"}:
                break
            if state in {"failed", "error", "cancelled", "canceled"}:
                raise VoiceboxTtsError(f"Voicebox generation {state}")
            time.sleep(0.05)
        else:
            raise VoiceboxTtsError("Voicebox generation timed out")

        audio = client.get(f"{base}/audio/{generation_id}")
        if audio.status_code >= 400 or not audio.content:
            raise VoiceboxTtsError(f"Voicebox audio failed ({audio.status_code})")
        _cache_put(key, audio.content)
        return audio.content


def prefetch_tts(text: str, *, profile: str | None = None, language: str = "en") -> None:
    """Kick Voicebox generation in the background so /api/tts can hit cache."""
    line = (text or "").strip()
    if not line or not settings.voicebox_enabled:
        return
    voice = (profile or settings.voicebox_profile or "Mark").strip() or "Mark"
    lang = language or "en"
    key = _cache_key(line, voice, lang)
    if _cache_get(key):
        return
    with _audio_lock:
        if key in _prefetch_inflight:
            return
        _prefetch_inflight.add(key)

    def _run() -> None:
        try:
            synthesize(line, profile=voice, language=lang)
        except Exception:
            pass
        finally:
            with _audio_lock:
                _prefetch_inflight.discard(key)

    threading.Thread(target=_run, name="jarvis-tts-prefetch", daemon=True).start()


def warm_voicebox() -> None:
    """Prime profile resolution + Kokoro so the first real line is less cold."""
    if not settings.voicebox_enabled:
        return

    def _run() -> None:
        try:
            if voicebox_reachable(timeout=2.0):
                synthesize("Ready.", profile=settings.voicebox_profile or "Mark")
        except Exception:
            pass

    threading.Thread(target=_run, name="jarvis-tts-warm", daemon=True).start()
