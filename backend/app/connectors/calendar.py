from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings
from ..db import connect
from . import google_auth

_LIST_CACHE: dict[str, Any] = {"at": 0.0, "days": 0, "rows": []}


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.tz)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def live() -> bool:
    return google_auth.has_calendar()


def parse_when(value: str) -> datetime:
    moment = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return moment.replace(tzinfo=_tz())
    return moment.astimezone(_tz())


def clock(value: str) -> str:
    if not value:
        return ""
    try:
        return parse_when(value).strftime("%H:%M")
    except Exception:
        return value[11:16] if len(value) > 16 else value


def _invalidate_cache() -> None:
    _LIST_CACHE["at"] = 0.0


def _service():
    return google_auth.google_service("calendar", "v3")


def _google_fail(exc: BaseException) -> str:
    text = str(exc).lower()
    if "accessnotconfigured" in text or "has not been used" in text or "is disabled" in text:
        return "Enable the Google Calendar API in Cloud Console, then try again."
    if "insufficient" in text or "invalid_grant" in text:
        return "Calendar is not connected. Reconnect Google in preferences."
    return "Calendar did not take it."


def _normalize_google(event: dict[str, Any]) -> dict[str, Any] | None:
    if (event.get("status") or "").lower() == "cancelled":
        return None
    start_block = event.get("start") or {}
    end_block = event.get("end") or {}
    start_raw = start_block.get("dateTime") or start_block.get("date") or ""
    end_raw = end_block.get("dateTime") or end_block.get("date") or start_raw
    if not start_raw:
        return None
    try:
        start_at = parse_when(start_raw if "T" in start_raw else f"{start_raw}T00:00:00").isoformat()
        end_at = parse_when(end_raw if "T" in end_raw else f"{end_raw}T00:00:00").isoformat()
    except Exception:
        return None
    event_id = event.get("id") or uuid.uuid4().hex[:10]
    return {
        "id": f"gcal-{event_id}",
        "title": event.get("summary") or "(No title)",
        "start_at": start_at,
        "end_at": end_at,
        "location": event.get("location") or "",
        "notes": event.get("description") or "",
    }


def _calendar_ids() -> list[str]:
    if not google_auth.has_calendar_list():
        return ["primary"]
    try:
        listed = _service().calendarList().list(maxResults=50).execute()
    except Exception:
        return ["primary"]
    ids: list[str] = []
    for item in listed.get("items") or []:
        if item.get("selected") is False:
            continue
        cal_id = (item.get("id") or "").strip()
        if cal_id:
            ids.append(cal_id)
    return ids or ["primary"]


def _google_list(days: int) -> list[dict[str, Any]]:
    start = datetime.now(_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=max(days, 1))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for calendar_id in _calendar_ids():
        listed = (
            _service()
            .events()
            .list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=40,
            )
            .execute()
        )
        for item in listed.get("items") or []:
            row = _normalize_google(item)
            if not row or row["id"] in seen:
                continue
            seen.add(row["id"])
            rows.append(row)
    rows.sort(key=lambda item: item.get("start_at") or "")
    return rows


def _google_create(
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
    notes: str = "",
) -> dict[str, Any]:
    zone = str(_tz())
    start = parse_when(start_at)
    end = parse_when(end_at)
    body = {
        "summary": title,
        "location": location or "",
        "description": notes or "",
        "start": {"dateTime": start.isoformat(), "timeZone": zone},
        "end": {"dateTime": end.isoformat(), "timeZone": zone},
    }
    created = _service().events().insert(calendarId="primary", body=body).execute()
    row = _normalize_google(created)
    if not row:
        raise RuntimeError("Calendar did not take it.")
    _invalidate_cache()
    from ..db import upsert_calendar_event

    upsert_calendar_event(row)
    return row


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


def _window(days: int, span: str = "") -> tuple[datetime, datetime]:
    start = datetime.now(_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    label = (span or "").strip().lower()
    if label == "today":
        return start, start + timedelta(days=1)
    if label == "tomorrow":
        return start + timedelta(days=1), start + timedelta(days=2)
    return start, start + timedelta(days=max(int(days or 2), 1))


def day_bucket(start_at: str) -> str:
    try:
        when = parse_when(start_at)
    except Exception:
        return ""
    today = datetime.now(_tz()).date()
    stamp = when.date()
    if stamp == today:
        return "today"
    if stamp == today + timedelta(days=1):
        return "tomorrow"
    return when.strftime("%Y-%m-%d")


def day_heading(start_at: str) -> str:
    bucket = day_bucket(start_at)
    if bucket == "today":
        return "Today"
    if bucket == "tomorrow":
        return "Tomorrow"
    try:
        when = parse_when(start_at)
    except Exception:
        return "Upcoming"
    return f"{when.strftime('%A')} {when.day} {when.strftime('%b')}"


def when_label(start_at: str) -> str:
    try:
        when = parse_when(start_at)
    except Exception:
        return clock(start_at)
    if when.hour == 0 and when.minute == 0:
        return "All day"
    bucket = day_bucket(start_at)
    if bucket in {"today", "tomorrow"}:
        return clock(start_at)
    return when.strftime("%H:%M")


def _local_list(days: int, span: str = "") -> list[dict[str, Any]]:
    start, end = _window(days, span)
    with connect() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM calendar_events ORDER BY start_at").fetchall()]
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            when = parse_when(row.get("start_at") or "")
        except Exception:
            continue
        if start <= when < end:
            out.append(row)
    out.sort(key=lambda item: item.get("start_at") or "")
    return out


def calendar_note(empty: bool = False) -> str:
    if google_auth.connected() and not live():
        return "Reconnect Google in preferences (**Add Calendar**) so briefing uses your real day."
    if live() and not google_auth.has_calendar_list() and empty:
        return "I can only see the primary calendar, and it is empty today. Allow all calendars in preferences if your day lives on another calendar."
    return ""


def pull_google(days: int = 2) -> list[dict[str, Any]]:
    rows = _google_list(days)
    _LIST_CACHE["at"] = time.monotonic()
    _LIST_CACHE["days"] = days
    _LIST_CACHE["rows"] = rows
    return list(rows)


def list_events(days: int = 2, span: str = "") -> list[dict[str, Any]]:
    if google_auth.connected() and not live():
        return []
    return _local_list(days, span=span)


def upcoming(days: int = 2, span: str = "") -> list[dict[str, Any]]:
    now = datetime.now(_tz())
    rows = []
    for event in list_events(days, span=span):
        raw_end = event.get("end_at") or event.get("start_at") or ""
        try:
            end = parse_when(raw_end)
        except Exception:
            continue
        if end < now:
            continue
        rows.append(event)
    return rows


def create_event(
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
    notes: str = "",
) -> dict[str, Any]:
    if google_auth.connected() or live():
        if not live():
            raise RuntimeError("Calendar is not connected. Reconnect Google in preferences.")
        try:
            return _google_create(title, start_at, end_at, location, notes)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(_google_fail(exc)) from exc
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
