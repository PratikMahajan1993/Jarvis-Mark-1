"""Append-only quote-workflow debug recorder.

Writes:
- <DATA_DIR>/quote_run.jsonl  (full history, gitignored via data/)
- work/QUOTE_RUN.md           (human readable, oldest first, gitignored)
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from typing import Any

from .config import REPO_ROOT, settings

MAX_STRING = 12000
_TRUNC_MARKER = "… [truncated]"
_WAITING_LINE = "_Waiting for the first turn._"
_lock = threading.Lock()
_jsonl_path = settings.data_dir / "quote_run.jsonl"
_md_path = REPO_ROOT / "work" / "QUOTE_RUN.md"

_SENSITIVE_KEY = re.compile(
    r"(token|password|secret|credential|api_key|authorization|cookie)",
    re.I,
)
_AUDIO_PREFIX = re.compile(r"^(data:audio|UklGR|RIFF)", re.I)

_HEADER = "\n".join(
    [
        "# Quote run log",
        "",
        "Live quote-workflow debug log. Each chat turn, brain choice, and quote_* tool call is appended below.",
        "",
        _WAITING_LINE,
        "",
    ]
)


def _local_stamp() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S %z")


def _truncate_str(text: str) -> str:
    if _AUDIO_PREFIX.search(text.strip()[:32]):
        return "<audio omitted>"
    if len(text) > MAX_STRING:
        return text[:MAX_STRING] + _TRUNC_MARKER
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
        return [_sanitize_value(item) for item in value[:96]]
    return _truncate_str(str(value))


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in data.items():
        if _SENSITIVE_KEY.search(str(key)):
            out[str(key)] = "<redacted>"
            continue
        out[str(key)] = _sanitize_value(val)
    return out


def _pending_brief(pending: Any) -> list[dict[str, str]]:
    if not isinstance(pending, list) or not pending:
        return []
    rows: list[dict[str, str]] = []
    for item in pending[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "kind": str(item.get("kind") or "pending"),
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or "")[:240],
            }
        )
    return rows


def _format_md_block(entry: dict[str, Any]) -> str:
    ts = entry.get("at_local") or ""
    kind = entry.get("kind") or "event"
    session = entry.get("session_id") or "default"
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    lines = [f"### {ts} · `{kind}` · session `{session}`", ""]
    for key, val in fields.items():
        if val is None or val == "":
            continue
        if isinstance(val, (dict, list)):
            snippet = json.dumps(val, ensure_ascii=False)
            if len(snippet) > 2000:
                snippet = snippet[:2000] + _TRUNC_MARKER
            lines.append(f"- **{key}:** `{snippet}`")
        else:
            text = str(val)
            if len(text) > 2000:
                text = text[:2000] + _TRUNC_MARKER
            lines.append(f"- **{key}:** {text}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _append_md_block(block: str) -> None:
    md_dir = _md_path.parent
    md_dir.mkdir(parents=True, exist_ok=True)
    if not _md_path.is_file():
        _md_path.write_text(_HEADER, encoding="utf-8")
    text = _md_path.read_text(encoding="utf-8")
    if _WAITING_LINE in text:
        text = text.replace(_WAITING_LINE + "\n", "").replace(_WAITING_LINE, "")
    if not text.endswith("\n"):
        text += "\n"
    _md_path.write_text(text + block, encoding="utf-8")


def seed_markdown() -> None:
    """Ensure QUOTE_RUN.md exists with header only. Never raises."""
    try:
        with _lock:
            if _md_path.is_file():
                return
            md_dir = _md_path.parent
            md_dir.mkdir(parents=True, exist_ok=True)
            _md_path.write_text(_HEADER, encoding="utf-8")
    except OSError:
        pass


def record(
    *,
    kind: str,
    session_id: str = "default",
    fields: dict[str, Any] | None = None,
) -> None:
    """Append one quote-run event. Never raises."""
    entry: dict[str, Any] = {
        "at_local": _local_stamp(),
        "kind": kind,
        "session_id": session_id or "default",
        "fields": _sanitize_dict(fields or {}),
    }
    line = json.dumps(entry, ensure_ascii=False)
    block = _format_md_block(entry)
    with _lock:
        try:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            with _jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            _append_md_block(block)
        except OSError:
            pass


def chat_out_fields(data: dict[str, Any], *, latency_ms: int | None = None) -> dict[str, Any]:
    pending = _pending_brief(data.get("pending"))
    out: dict[str, Any] = {
        "speak": str(data.get("speak") or "").strip(),
        "reply": str(data.get("reply") or "").strip(),
        "route_intent": data.get("route_intent"),
        "target_agent": data.get("target_agent"),
        "pending": pending,
    }
    if latency_ms is not None:
        out["latency_ms"] = int(latency_ms)
    return out


def confirm_fields(
    *,
    decision: str,
    action_id: str,
    data: dict[str, Any],
    latency_ms: int | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "decision": decision,
        "action_id": action_id,
        "speak": str(data.get("speak") or "").strip(),
        "pending": _pending_brief(data.get("pending")),
    }
    if latency_ms is not None:
        out["latency_ms"] = int(latency_ms)
    return out


def route_fields(classification: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "intent": getattr(classification, "intent", None),
        "target_agent": getattr(classification, "target_agent", None),
    }
    conf = getattr(classification, "confidence", None)
    if conf is not None:
        out["confidence"] = conf
    return out
