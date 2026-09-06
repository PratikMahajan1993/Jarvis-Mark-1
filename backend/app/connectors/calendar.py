from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings
from ..db import connect


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.tz)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def seed_calendar() -> None:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM calendar_events").fetchone()["n"]
        if count:
            return
        today = datetime.now(_tz()).replace(minute=0, second=0, microsecond=0)
        day = today.replace(hour=9)
        events = [
            {
                "id": "cal-standup",
                "title": "Team standup",
                "start_at": day.replace(hour=10).isoformat(),
                "end_at": day.replace(hour=10, minute=20).isoformat(),
                "location": "Meet / Daily",
                "notes": "Blockers and client-review prep.",
            },
            {
                "id": "cal-design",
                "title": "Internal design review",
                "start_at": day.replace(hour=14).isoformat(),
                "end_at": day.replace(hour=14, minute=45).isoformat(),
                "location": "Studio",
                "notes": "Walk through the HUD scenes and briefing cards.",
            },
            {
                "id": "cal-client",
                "title": "Northline client review",
                "start_at": day.replace(hour=16).isoformat(),
                "end_at": day.replace(hour=17).isoformat(),
                "location": "Conference B",
                "notes": "Proposal redlines and revised pricing sheet.",
            },
            {
                "id": "cal-tomorrow-sync",
                "title": "Legal MSA sync",
                "start_at": (day + timedelta(days=1)).replace(hour=11).isoformat(),
                "end_at": (day + timedelta(days=1)).replace(hour=11, minute=30).isoformat(),
                "location": "Phone",
                "notes": "Confirm language before circulation.",
            },
        ]
        conn.executemany(
            """
            INSERT INTO calendar_events (id, title, start_at, end_at, location, notes)
            VALUES (:id, :title, :start_at, :end_at, :location, :notes)
            """,
            events,
        )


def list_events(days: int = 2) -> list[dict[str, Any]]:
    start = datetime.now(_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            WHERE start_at >= ? AND start_at < ?
            ORDER BY start_at
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]


def create_event(
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
    notes: str = "",
) -> dict[str, Any]:
    record = {
        "id": f"cal-{uuid.uuid4().hex[:10]}",
        "title": title,
        "start_at": start_at,
        "end_at": end_at,
        "location": location,
        "notes": notes,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO calendar_events (id, title, start_at, end_at, location, notes)
            VALUES (:id, :title, :start_at, :end_at, :location, :notes)
            """,
            record,
        )
    return record
