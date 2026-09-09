from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any

from . import db

STALE_SECONDS = 180
SNAPSHOT_KINDS = frozenset({"briefing", "mail_search", "mail_read", "calendar_list"})
SKIP_MODEL = SNAPSHOT_KINDS | {"calendar_create", "rfq_reason", "cnc_suggest"}

_FRESH = re.compile(
    r"\b("
    r"anything new|what's new|whats new|any new(?: mail| emails?)?"
    r"|refresh|check again|update me"
    r")\b",
    re.I,
)

_lock = threading.Lock()
_thread: threading.Thread | None = None


def wants_fresh(message: str) -> bool:
    return bool(_FRESH.search(message or ""))


def uses_snapshot(kind: str) -> bool:
    return kind in SNAPSHOT_KINDS


def skips_model(kind: str) -> bool:
    return kind in SKIP_MODEL


def calendar_ready() -> bool:
    from .connectors import calendar as calendar_conn

    if not calendar_conn.live():
        return True
    return bool(str(status().get("calendar_synced_at") or "").strip())


def status() -> dict[str, Any]:
    meta = db.get_work_snapshot()
    synced = str(meta.get("mail_synced_at") or "")
    age = _age_seconds(synced)
    return {
        "ready": bool(synced),
        "stale": (age is None) or age > STALE_SECONDS,
        "age_seconds": age,
        "mail_synced_at": synced,
        "calendar_synced_at": meta.get("calendar_synced_at") or "",
        "mail_count": int(meta.get("mail_count") or 0),
        "status": meta.get("status") or "",
    }


def ready() -> bool:
    return status()["ready"]


def refresh(force: bool = False) -> dict[str, Any]:
    with _lock:
        current = status()
        if current["ready"] and not current["stale"] and calendar_ready() and not force:
            return current
        db.set_work_snapshot(status="syncing")
        mail_count = 0
        mail_at = ""
        cal_at = ""
        try:
            mail_count = _pull_mail()
            mail_at = db.utc_now()
        except Exception as exc:
            db.set_work_snapshot(status=f"mail:{str(exc)[:120]}")
        try:
            _pull_calendar()
            cal_at = db.utc_now()
        except Exception as exc:
            db.set_work_snapshot(
                mail_synced_at=mail_at or None,
                mail_count=mail_count,
                status=f"calendar:{str(exc)[:120]}",
            )
            return status()
        db.set_work_snapshot(
            mail_synced_at=mail_at or current.get("mail_synced_at") or "",
            calendar_synced_at=cal_at,
            mail_count=mail_count,
            status="ok" if mail_at else current.get("status") or "ok",
        )
        return status()


def kick() -> None:
    global _thread
    current = status()
    if current["ready"] and not current["stale"]:
        return
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_kick_run, daemon=True, name="jarvis-snapshot")
        _thread.start()


def _kick_run() -> None:
    try:
        refresh(force=False)
    except Exception:
        db.set_work_snapshot(status="error")


def _age_seconds(stamp: str) -> float | None:
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - moment.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        return None


def _pull_mail() -> int:
    from .connectors import gmail as gmail_conn
    from .connectors.email import _merge_gmail_fields

    if not gmail_conn.live():
        return db.unread_count_local()
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for query, unread_only, limit in (
        ("", True, 20),
        ("in:inbox newer_than:2d", False, 20),
    ):
        try:
            fetched = gmail_conn.list_messages(query=query, unread_only=unread_only, limit=limit)
        except Exception:
            continue
        for row in fetched:
            ident = str(row.get("id") or "")
            if not ident or ident in seen:
                continue
            seen.add(ident)
            rows.append(_merge_gmail_fields(row))
    try:
        from .rfq import detect_inbound_drawings

        detect_inbound_drawings()
    except Exception:
        pass
    return len(rows) or db.unread_count_local()


def _pull_calendar() -> None:
    from .connectors import calendar as calendar_conn

    if not calendar_conn.live():
        return
    rows = calendar_conn.pull_google(days=7)
    db.replace_calendar_events(rows)
