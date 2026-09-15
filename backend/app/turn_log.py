"""Rolling last-N Jarvis turns for capability-test review.

Writes:
- <DATA_DIR>/last_turns.json  (durable, gitignored; DATA_DIR resolves to <repo>/data)
- work/LAST_TURNS.md          (agent-readable; gitignored)
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, settings

TURN_LIMIT = 20
_lock = threading.Lock()

_JSON_PATH = settings.data_dir / "last_turns.json"
_MD_PATH = ROOT.parent / "work" / "LAST_TURNS.md"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _load() -> list[dict[str, Any]]:
    if not _JSON_PATH.is_file():
        return []
    try:
        raw = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
    except Exception:
        pass
    return []


def _pending_summary(pending: Any) -> str:
    if not isinstance(pending, list) or not pending:
        return ""
    parts: list[str] = []
    for item in pending[:4]:
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


def _render_md(turns: list[dict[str, Any]]) -> str:
    lines = [
        "# Jarvis — last turns",
        "",
        f"_Rolling log of the last {TURN_LIMIT} chat/confirm exchanges. "
        "Updated automatically by the API. Read this after each capability test._",
        "",
        f"_Updated: {_utc_stamp()} · {len(turns)} turn(s)_",
        "",
        "---",
        "",
    ]
    for idx, turn in enumerate(reversed(turns), start=1):
        ts = turn.get("at") or ""
        source = turn.get("source") or "chat"
        session = turn.get("session_id") or "default"
        user = str(turn.get("user") or "").strip() or "(empty)"
        speak = str(turn.get("speak") or "").strip()
        reply = str(turn.get("reply") or "").strip()
        scene = str(turn.get("scene_title") or "").strip()
        pending = str(turn.get("pending") or "").strip()
        mail_id = str(turn.get("mail_id") or "").strip()
        lines.append(f"## Turn −{idx} · {ts}")
        lines.append("")
        lines.append(f"- **source:** `{source}` · **session:** `{session}`")
        if scene:
            lines.append(f"- **board:** {scene}")
        if pending:
            lines.append(f"- **pending:** {pending}")
        if mail_id:
            lines.append(f"- **mail_id:** `{mail_id}`")
        lines.append("")
        lines.append("**User**")
        lines.append("")
        lines.append("```")
        lines.append(user[:4000])
        lines.append("```")
        lines.append("")
        lines.append("**Jarvis**")
        lines.append("")
        body = speak or reply or "(no speak)"
        lines.append("```")
        lines.append(body[:4000])
        if reply and speak and reply.strip() != speak.strip():
            lines.append("")
            lines.append("--- reply ---")
            lines.append(reply[:2000])
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _persist(turns: list[dict[str, Any]]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _JSON_PATH.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")
    md_dir = _MD_PATH.parent
    md_dir.mkdir(parents=True, exist_ok=True)
    _MD_PATH.write_text(_render_md(turns), encoding="utf-8")


def record_turn(
    *,
    session_id: str,
    user: str,
    response: dict[str, Any] | None,
    source: str = "chat",
) -> None:
    """Append one exchange and keep only the last TURN_LIMIT turns."""
    data = response or {}
    entry = {
        "at": _utc_stamp(),
        "source": source,
        "session_id": session_id or "default",
        "user": (user or "").strip(),
        "speak": str(data.get("speak") or "").strip(),
        "reply": str(data.get("reply") or "").strip(),
        "scene_title": _scene_title(data.get("scene")),
        "pending": _pending_summary(data.get("pending")),
        "mail_id": str(data.get("mail_id") or "").strip() or None,
    }
    with _lock:
        turns = _load()
        turns.append(entry)
        turns = turns[-TURN_LIMIT:]
        try:
            _persist(turns)
        except OSError:
            pass


def recent_turns(limit: int = TURN_LIMIT) -> list[dict[str, Any]]:
    with _lock:
        turns = _load()
    return turns[-max(1, min(limit, TURN_LIMIT)) :]


def log_paths() -> dict[str, str]:
    return {"markdown": str(_MD_PATH), "json": str(_JSON_PATH)}
