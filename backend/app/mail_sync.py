"""Background bulk Gmail → SQLite sync with spam filtering and RAG reindex."""

from __future__ import annotations

import threading
import time
from typing import Any

from . import db
from .connectors.email import _merge_gmail_fields
from .connectors.mail_filter import should_keep_mail

DEFAULT_DAYS = 100
PAGE_SIZE = 50
RAG_BATCH = 50

_lock = threading.Lock()
_thread: threading.Thread | None = None


def _sync_thread_alive() -> bool:
    return _thread is not None and _thread.is_alive()


def _query_for_days(days: int) -> str:
    days = max(1, min(int(days or DEFAULT_DAYS), 365))
    return f"in:inbox -in:spam -in:trash newer_than:{days}d"


def get_state() -> dict[str, Any]:
    return db.get_mail_sync_state()


def bulk_complete() -> bool:
    state = get_state()
    status = str(state.get("status") or "")
    return status == "done" and int(state.get("synced_count") or 0) > 0


def kick_bulk(*, days: int = DEFAULT_DAYS, force: bool = False) -> dict[str, Any]:
    """Start (or no-op) a background bulk sync. Safe to call from OAuth/startup/API."""
    global _thread
    with _lock:
        current = get_state()
        if current.get("status") == "running" and _sync_thread_alive():
            return {"ok": True, "started": False, **current}
        if bulk_complete() and not force:
            return {"ok": True, "started": False, **current}
        db.set_mail_sync_state(
            status="running",
            days=days,
            synced_count=0,
            skipped_count=0,
            page_token="",
            started_at=db.utc_now(),
            finished_at="",
            error="",
        )
        _thread = threading.Thread(
            target=_run_bulk,
            kwargs={"days": days},
            daemon=True,
            name="jarvis-mail-bulk",
        )
        _thread.start()
    return {"ok": True, "started": True, **get_state()}


def sync_bulk_inline(*, days: int = DEFAULT_DAYS, force: bool = False) -> dict[str, Any]:
    """Run bulk sync on the caller thread (tests / desk inline mode)."""
    current = get_state()
    if current.get("status") == "running" and _sync_thread_alive():
        return {"ok": False, "error": "sync already running", **current}
    if bulk_complete() and not force:
        return {"ok": True, "skipped": True, **current}
    db.set_mail_sync_state(
        status="running",
        days=days,
        synced_count=0,
        skipped_count=0,
        page_token="",
        started_at=db.utc_now(),
        finished_at="",
        error="",
    )
    _run_bulk(days=days)
    return {"ok": True, **get_state()}


def _run_bulk(*, days: int) -> None:
    from .connectors import gmail as gmail_conn

    synced = 0
    skipped = 0
    page_token = ""
    query = _query_for_days(days)
    try:
        if not gmail_conn.live():
            db.set_mail_sync_state(status="error", error="Gmail not connected", finished_at=db.utc_now())
            return
        for ids, next_token in gmail_conn.iter_message_id_pages(query=query, page_size=PAGE_SIZE):
            rows: list[dict[str, Any]] = []
            for gmail_id in ids:
                try:
                    row = gmail_conn.get_message(gmail_id)
                except Exception:
                    skipped += 1
                    continue
                if not row:
                    skipped += 1
                    continue
                keep, _reason = should_keep_mail(row)
                if not keep:
                    skipped += 1
                    continue
                _merge_gmail_fields(row)
                synced += 1
                rows.append(row)
            page_token = next_token or ""
            db.set_mail_sync_state(
                synced_count=synced,
                skipped_count=skipped,
                page_token=page_token,
            )
            if rows:
                _reindex_batch(rows)
            # Yield the GIL briefly so chat/API stay responsive on desk.
            time.sleep(0.05)
        try:
            from .rfq import detect_inbound_drawings

            detect_inbound_drawings()
        except Exception:
            pass
        try:
            from .memory.ingest import reindex_all_mail_in_db

            reindex_all_mail_in_db(batch_size=RAG_BATCH)
        except Exception:
            pass
        db.set_work_snapshot(
            mail_synced_at=db.utc_now(),
            mail_count=db.count_gmail_emails_local(),
            status="ok",
        )
        db.set_mail_sync_state(
            status="done",
            synced_count=synced,
            skipped_count=skipped,
            page_token="",
            finished_at=db.utc_now(),
            error="",
        )
    except Exception as exc:
        db.set_mail_sync_state(
            status="error",
            synced_count=synced,
            skipped_count=skipped,
            page_token=page_token,
            finished_at=db.utc_now(),
            error=str(exc)[:200],
        )


def _reindex_batch(rows: list[dict[str, Any]]) -> None:
    try:
        from .memory.ingest import reindex_mail_rows

        reindex_mail_rows(rows)
    except Exception:
        pass


def maybe_kick_on_startup() -> None:
    """First connect or empty corpus: start bulk sync without blocking startup."""
    from .connectors import gmail as gmail_conn

    if not gmail_conn.live():
        return
    state = get_state()
    if state.get("status") == "running" and _sync_thread_alive():
        return
    meta = db.get_work_snapshot()
    gmail_count = db.count_gmail_emails_local()
    if not bulk_complete() and gmail_count < 30:
        kick_bulk(days=DEFAULT_DAYS, force=False)
