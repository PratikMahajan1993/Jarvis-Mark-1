"""Append-only live capability-test recorder.

Writes:
- <DATA_DIR>/live_test.jsonl  (full history, gitignored)
- work/LIVE_TEST.md           (newest-first ~150 events, gitignored)
"""

from __future__ import annotations

import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .config import REPO_ROOT, settings

MD_LIMIT = 150
MAX_STRING = 1500
_lock = threading.Lock()
_jsonl_path = settings.data_dir / "live_test.jsonl"
_md_path = REPO_ROOT / "work" / "LIVE_TEST.md"
_recent: deque[dict[str, Any]] = deque(maxlen=MD_LIMIT)
_hydrated = False

_SENSITIVE_KEY = re.compile(
    r"(token|password|secret|credential|refresh|api_key|apikey|authorization|cookie|private_key|"
    r"google_token|access_token|id_token|wav|audio_bytes|image_base64)",
    re.I,
)
_AUDIO_PREFIX = re.compile(r"^(data:audio|UklGR|RIFF)", re.I)


def _utc_local_stamp() -> tuple[str, str]:
    now = datetime.now(timezone.utc).astimezone()
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")
    local = now.strftime("%Y-%m-%d %H:%M:%S %z")
    return utc, local


def _truncate_str(text: str) -> str:
    if _AUDIO_PREFIX.search(text.strip()[:32]):
        return "<audio omitted>"
    if len(text) > MAX_STRING:
        return text[:MAX_STRING] + "…"
    return text


def _sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, bytes):
        return "<bytes omitted>"
    if isinstance(value, str):
        return _truncate_str(value)
    if isinstance(value, dict):
        return _sanitize_dict(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:48]]
    text = str(value)
    return _truncate_str(text)


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in data.items():
        if _SENSITIVE_KEY.search(str(key)):
            out[str(key)] = "<redacted>"
            continue
        out[str(key)] = _sanitize_value(val)
    return out


def _pending_brief(pending: Any) -> str:
    if not isinstance(pending, list) or not pending:
        return ""
    parts: list[str] = []
    for item in pending[:6]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "pending")
        title = str(item.get("title") or item.get("id") or "")[:80]
        parts.append(f"{kind}: {title}" if title else kind)
    return "; ".join(parts)


def _scene_title(scene: Any) -> str:
    if isinstance(scene, dict):
        return str(scene.get("title") or "").strip()
    return ""


def _hydrate_recent() -> None:
    global _hydrated
    if _hydrated:
        return
    _hydrated = True
    if not _jsonl_path.is_file():
        return
    try:
        lines = [ln for ln in _jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        rows: list[dict[str, Any]] = []
        for line in lines[-MD_LIMIT:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
        _recent.clear()
        for row in rows:
            _recent.append(row)
    except Exception:
        pass


def _render_md() -> str:
    _, local = _utc_local_stamp()
    lines = [
        "# Jarvis — live test log",
        "",
        "_Append-only recorder while the owner exercises the HUD. Newest first (~150 events). "
        "Full history: `data/live_test.jsonl`._",
        "",
        f"_Updated: {local} · showing {len(_recent)} event(s)_",
        "",
        "---",
        "",
    ]
    for idx, ev in enumerate(reversed(list(_recent)), start=1):
        ts = ev.get("at_local") or ev.get("at_utc") or ""
        source = ev.get("source") or "?"
        kind = ev.get("kind") or "event"
        session = ev.get("session_id") or "default"
        latency = ev.get("latency_ms")
        fields = ev.get("fields") if isinstance(ev.get("fields"), dict) else {}
        lines.append(f"## −{idx} · {ts} · `{source}` · `{kind}`")
        lines.append("")
        lines.append(f"- **session:** `{session}`" + (f" · **latency:** {latency}ms" if latency is not None else ""))
        if fields:
            for key, val in fields.items():
                if val is None or val == "":
                    continue
                if isinstance(val, (dict, list)):
                    snippet = json.dumps(val, ensure_ascii=False)
                    if len(snippet) > 400:
                        snippet = snippet[:400] + "…"
                    lines.append(f"- **{key}:** `{snippet}`")
                else:
                    text = str(val)
                    if len(text) > 400:
                        text = text[:400] + "…"
                    lines.append(f"- **{key}:** {text}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _persist_md() -> None:
    md_dir = _md_path.parent
    md_dir.mkdir(parents=True, exist_ok=True)
    _md_path.write_text(_render_md(), encoding="utf-8")


def record(
    *,
    source: str,
    kind: str,
    session_id: str = "default",
    latency_ms: int | None = None,
    fields: dict[str, Any] | None = None,
) -> None:
    """Append one live-test event. Never raises."""
    utc, local = _utc_local_stamp()
    entry: dict[str, Any] = {
        "at_utc": utc,
        "at_local": local,
        "source": source,
        "kind": kind,
        "session_id": session_id or "default",
        "fields": _sanitize_dict(fields or {}),
    }
    if latency_ms is not None:
        entry["latency_ms"] = int(latency_ms)
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        try:
            _hydrate_recent()
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            with _jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            _recent.append(entry)
            _persist_md()
        except OSError:
            pass


def recent_events(limit: int = 80) -> list[dict[str, Any]]:
    with _lock:
        _hydrate_recent()
        cap = max(1, min(limit, MD_LIMIT))
        return list(reversed(list(_recent)))[:cap]


def log_paths() -> dict[str, str]:
    return {"jsonl": str(_jsonl_path), "markdown": str(_md_path)}


def chat_out_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Build chat_out field dict from an API response payload."""
    return {
        "speak": str(data.get("speak") or "").strip(),
        "reply": str(data.get("reply") or "").strip(),
        "route_intent": data.get("route_intent"),
        "target_agent": data.get("target_agent"),
        "pending": _pending_brief(data.get("pending")),
        "mail_id": str(data.get("mail_id") or "").strip() or None,
        "scene_title": _scene_title(data.get("scene")),
        "ui_action": data.get("ui_action"),
    }
