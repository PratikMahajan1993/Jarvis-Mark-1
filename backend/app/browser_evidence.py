"""Browser / computer-use evidence capture (foundation Phase 4 stretch)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from . import db
from .config import settings
from .hermes.hitl import request_human_approval


def _evidence_dir() -> Path:
    path = settings.data_dir / "browser_evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def record_evidence(
    *,
    session_id: str,
    url: str,
    title: str = "",
    notes: str = "",
    screenshot_b64: str = "",
) -> dict[str, Any]:
    """Persist a browser-task evidence pack (screenshot optional)."""
    eid = f"bev-{uuid.uuid4().hex[:10]}"
    folder = _evidence_dir() / eid
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": eid,
        "url": url,
        "title": title or url,
        "notes": notes,
        "session_id": session_id,
        "created_at": db.utc_now(),
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    shot_path = ""
    if screenshot_b64:
        import base64

        raw = base64.b64decode(screenshot_b64)
        shot_path = str(folder / "screenshot.png")
        Path(shot_path).write_bytes(raw)
        meta["screenshot"] = shot_path
    db.add_audit(session_id, "browser_evidence", f"{title or url} → {eid}", "ok")
    return {"ok": True, "evidence": meta, "path": str(folder)}


def queue_browser_action(
    *,
    session_id: str,
    title: str,
    summary: str,
    url: str,
    evidence_id: str = "",
) -> dict[str, Any]:
    pending = request_human_approval(
        session_id=session_id,
        kind="browser_action",
        title=title,
        summary=summary,
        payload={"url": url, "evidence_id": evidence_id},
        tool_name="browser_action",
    )
    return {"ok": True, "pending": pending}
