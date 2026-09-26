"""Local Voicebox TTS client (desktop app API on :17493).

Docs: https://docs.voicebox.sh/
- POST /generate synthesizes a profile and returns a generation id.
- GET /audio/{generation_id} is the WAV the browser plays.
- Never POST /speak. That plays on the machine as well as the browser.
- Never invent a profile. The named Voicebox profile is the only voice.
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
_prefetch_inflight: set[str] = set()
_MEM_LIMIT = 48
_TTS_CACHE_TTL_SEC = 7 * 24 * 60 * 60
_CACHE_VERSION = "vb3"


class VoiceboxTtsError(RuntimeError):
    """Voicebox could not produce audio. The desk stays silent rather than using another voice."""


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


def _preset_identity(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("id") or row.get("profile_id") or "").strip(),
            str(row.get("voice_type") or "").strip(),
            str(row.get("default_engine") or row.get("preset_engine") or "").strip(),
            str(row.get("preset_voice_id") or "").strip(),
        ]
    )


def resolve_profile(client: httpx.Client, profile: str) -> dict[str, Any]:
    """Return the Voicebox profile with this exact name. Never create or substitute one."""
    name = (profile or "").strip() or "Mark"
    rows = _profiles(client)
    matches = []
    for row in rows:
        row_name = str(row.get("name") or "").strip()
        row_id = str(row.get("id") or row.get("profile_id") or "").strip()
        if row_id and row_name.lower() == name.lower():
            matches.append(row)
    if not matches:
        known = ", ".join(str(row.get("name") or "").strip() for row in rows if row.get("name")) or "none"
        raise VoiceboxTtsError(
            f"Voicebox has no profile named {name}. Profiles on this server: {known}. "
            "Create that voice in Voicebox. Jarvis will not invent a preset."
        )
    if len(matches) > 1:
        raise VoiceboxTtsError(f"Voicebox has more than one profile named {name}")
    chosen = matches[0]
    row_id = str(chosen.get("id") or chosen.get("profile_id") or "").strip()
    cached = _profile_cache.get(name.lower())
    identity = _preset_identity(chosen)
    if not cached or cached.get("identity") != identity:
        _profile_cache[name.lower()] = {
            "id": row_id,
            "engine": str(chosen.get("default_engine") or chosen.get("preset_engine") or "").strip(),
            "identity": identity,
        }
    return chosen


def _cache_key(text: str, profile_row: dict[str, Any], language: str) -> str:
    raw = "|".join(
        [
            _CACHE_VERSION,
            _preset_identity(profile_row),
            language or "en",
            text,
        ]
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_dir() -> Path:
    path = Path(settings.data_dir) / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remember_audio(key: str, wav: bytes) -> None:
    """Store WAV bytes. Caller holds `_audio_lock`."""
    _audio_mem[key] = wav
    while len(_audio_mem) > _MEM_LIMIT:
        _audio_mem.pop(next(iter(_audio_mem)))


def _expire_old_tts_files() -> None:
    """Delete cache files older than 7 days. Caller holds `_audio_lock`."""
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
        if not data:
            return None
        _remember_audio(key, data)
        return data


def _cache_put(key: str, wav: bytes) -> None:
    if not wav:
        return
    path = _cache_dir() / f"{key}.wav"
    with _audio_lock:
        _remember_audio(key, wav)
        try:
            path.write_bytes(wav)
        except OSError:
            return
        _expire_old_tts_files()


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
    timeout = max(5.0, float(settings.voicebox_timeout_sec or 45.0))
    base = voicebox_base()

    with httpx.Client(timeout=timeout) as client:
        profile_row = resolve_profile(client, voice)
        profile_id = str(profile_row.get("id") or profile_row.get("profile_id") or "").strip()
        if not profile_id:
            raise VoiceboxTtsError(f"Voicebox profile missing id: {voice}")
        key = _cache_key(line, profile_row, lang)
        cached = _cache_get(key)
        if cached:
            return cached
        # Preset profiles are locked to their engine. Sending a different engine
        # makes Voicebox skip the profile. Clones omit engine so the server default
        # (the profile's own engine) is used.
        voice_type = str(profile_row.get("voice_type") or "").strip().lower()
        engine = str(profile_row.get("default_engine") or profile_row.get("preset_engine") or "").strip()
        body: dict[str, Any] = {
            "text": line[:5000],
            "profile_id": profile_id,
            "language": lang,
            "personality": False,
        }
        if voice_type == "preset" and engine:
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
    with _audio_lock:
        inflight = f"{voice}|{lang}|{line}"
        if inflight in _prefetch_inflight:
            return
        _prefetch_inflight.add(inflight)

    def _run() -> None:
        try:
            synthesize(line, profile=voice, language=lang)
        except Exception:
            pass
        finally:
            with _audio_lock:
                _prefetch_inflight.discard(inflight)

    threading.Thread(target=_run, name="jarvis-tts-prefetch", daemon=True).start()


def warm_voicebox() -> None:
    """Prime the configured Voicebox profile so the first spoken line is less cold."""
    if not settings.voicebox_enabled:
        return

    def _run() -> None:
        try:
            if voicebox_reachable(timeout=2.0):
                synthesize("Ready.", profile=settings.voicebox_profile or "Mark")
        except Exception:
            pass

    threading.Thread(target=_run, name="jarvis-tts-warm", daemon=True).start()
