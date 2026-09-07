from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import db
from .connectors import calendar as calendar_conn
from .connectors import email as email_conn


def _tz() -> ZoneInfo:
    prefs = db.get_preferences()
    try:
        return ZoneInfo(prefs.get("timezone") or "Asia/Kolkata")
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def greeting_slot() -> str:
    hour = datetime.now(_tz()).hour
    if hour < 12:
        return "Morning"
    if hour < 17:
        return "Afternoon"
    return "Evening"


def build_briefing() -> dict:
    prefs = db.get_preferences()
    mails = email_conn.search_emails(unread_only=False, limit=6)
    unread = [mail for mail in mails if mail.get("unread")]
    events = calendar_conn.list_events(days=1)
    inbox_files = db.list_inbox_files(4)
    memories = db.list_memories("default", 4)
    next_event = events[0]["title"] if events else "Clear calendar"
    slot = greeting_slot()
    name = prefs.get("display_name") or "Sir"
    speak = (
        f"{slot}, {name}. {len(unread)} unread "
        f"{'message' if len(unread) == 1 else 'messages'} "
        f"and {len(events)} event{'s' if len(events) != 1 else ''} on the board. "
        f"Next up: {next_event}."
    )
    widgets = [
        {"type": "kpi", "label": "Unread", "value": len(unread), "hint": "Inbox"},
        {"type": "kpi", "label": "Today", "value": len(events), "hint": "Calendar"},
        {"type": "kpi", "label": "Inbox files", "value": len(inbox_files), "hint": "Dropped docs"},
        {
            "type": "table",
            "title": "Priority mail",
            "columns": ["From", "Subject"],
            "rows": [[mail["sender"], mail["subject"]] for mail in unread[:5] or mails[:5]],
        },
        {
            "type": "timeline",
            "title": "Today",
            "items": [
                {
                    "time": event["start_at"][11:16] if len(event["start_at"]) > 16 else event["start_at"],
                    "title": event["title"],
                    "detail": event.get("location") or "",
                }
                for event in events
            ],
        },
    ]
    if memories:
        widgets.append(
            {
                "type": "markdown",
                "title": "Session memory",
                "text": "\n".join(f"- **{item['key']}**: {item['value']}" for item in memories),
            }
        )
    scene = {
        "title": f"{slot} briefing",
        "subtitle": datetime.now(_tz()).strftime("%A | %d %b %Y"),
        "widgets": widgets,
    }
    return {
        "speak": speak,
        "scene": scene,
        "unread": unread,
        "events": events,
        "files": inbox_files,
    }


_WORDS = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
    13: "Thirteen",
    14: "Fourteen",
    15: "Fifteen",
    16: "Sixteen",
    17: "Seventeen",
    18: "Eighteen",
    19: "Nineteen",
    20: "Twenty",
    30: "Thirty",
    40: "Forty",
    45: "Forty-five",
    50: "Fifty",
}


def _parse_when(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=_tz())
    return moment.astimezone(_tz())


def _minutes_phrase(minutes: int) -> str:
    if minutes in _WORDS:
        return _WORDS[minutes]
    if minutes < 60:
        return str(minutes)
    return ""


def build_glance() -> dict:
    from .watch import watch_payload

    watch = watch_payload("default")
    if watch.get("ready") and watch.get("speak") and watch.get("status") == "ready":
        return {
            "line": "Gemini replied",
            "whisper": watch["speak"],
            "speak": watch["speak"],
            "key": watch.get("key") or f"gemini:{watch.get('status')}:{(watch.get('scene') or {}).get('subtitle')}",
            "minutes": None,
        }
    now = datetime.now(_tz())
    upcoming = []
    for event in calendar_conn.list_events(days=2):
        try:
            start = _parse_when(event["start_at"])
            end = _parse_when(event["end_at"]) if event.get("end_at") else start
        except Exception:
            continue
        if end < now:
            continue
        upcoming.append((start, end, event))
    upcoming.sort(key=lambda item: item[0])
    unread = email_conn.unread_count()

    if not upcoming:
        line = f"{unread} unread" if unread else ""
        return {
            "line": line,
            "whisper": f"{unread} unread messages." if unread >= 3 else "",
            "speak": "",
            "key": f"mail:{unread}" if unread >= 3 else "",
            "minutes": None,
        }

    start, end, event = upcoming[0]
    title = event["title"]
    short = title.split("—")[0].split("-")[0].strip()
    clock = start.strftime("%H:%M")
    line = f"{clock}  {short}"
    if start <= now <= end:
        whisper = f"{short} is on now."
        return {
            "line": line,
            "whisper": whisper,
            "speak": whisper,
            "key": f"{event['id']}:now",
            "minutes": 0,
        }
    minutes = int((start - now).total_seconds() // 60)
    if minutes <= 60:
        amount = _minutes_phrase(max(minutes, 1))
        unit = "minute" if minutes <= 1 else "minutes"
        whisper = f"{amount} {unit} to {short}."
        bucket = 5 if minutes <= 5 else 15 if minutes <= 15 else 30 if minutes <= 30 else 60
        return {
            "line": line,
            "whisper": whisper,
            "speak": whisper if minutes <= 30 else "",
            "key": f"{event['id']}:{bucket}",
            "minutes": minutes,
        }
    return {
        "line": line,
        "whisper": "",
        "speak": "",
        "key": f"{event['id']}:later",
        "minutes": minutes,
    }
