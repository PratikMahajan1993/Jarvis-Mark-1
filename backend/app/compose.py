from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .familiarity import facts_from_body, first_name, reply_only

_CREATE_CAL = re.compile(
    r"\b(add|put|book|create|make|set|block|hold|reserve|fix)\b.+\b"
    r"(calendar|event|meeting|call|lunch|dinner|sync|appointment|slot)\b"
    r"|\bschedule (a|an|me)\b"
    r"|\b(set|fix)\s+up\s+a\s+(call|meeting|lunch|sync)"
    r"|\b(meeting|call|lunch|dinner|sync|appointment)\s+with\b"
    r"|\bremind me to\b"
    r"|\bblock\s+\d",
    re.I,
)
_TIME = re.compile(
    r"\b(?:at|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|o'?clock)?"
    r"|\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?"
    r"|\b(\d{1,2})\s*(?:o'?clock|in the (morning|evening|afternoon)|am|pm)\b"
    r"|\bhalf past\s+(\d{1,2})\b"
    r"|\bquarter (to|past)\s+(\d{1,2})\b",
    re.I,
)
_DURATION = re.compile(r"\b(?:for\s+)?(\d+)\s*(min|mins|minutes|hour|hours|hr|hrs)\b|\b(half an hour|an hour|one hour)\b", re.I)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_STRIP_EVENT = re.compile(
    r"\b(jarvis|please|add|put|book|create|make|set|schedule|block|hold|reserve|fix|up|"
    r"an|a|the|on|to|my|our|me|"
    r"calendar|event|appointment|slot|reminder|"
    r"tomorrow|today|tonight|morning|evening|afternoon|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|next)\b",
    re.I,
)
_MAKE_TITLE = re.compile(
    r"\b(?:make|create|new|write|build|prepare|draft)\b(?:\s+a|\s+an|\s+me)?\s+"
    r"(?:spread\s*)?sheet(?:\s+of|\s+for|\s+called|\s+named)?\s+(.+)$",
    re.I,
)
_BOILER = re.compile(
    r"trailing mail|please find (enclosed|attached)|as per your requirement|"
    r"for your kind information|with reference to|item codes have been selected|"
    r"this is with reference|hope (this|you)|kind(ly)? (do the needful|revert)",
    re.I,
)


def reply_draft(source: dict[str, Any] | None) -> str:
    if not source:
        return "Thank you for the note. I will follow up shortly."
    subject = (source.get("subject") or "your note").strip()
    if subject.lower().startswith("re:"):
        subject = subject[3:].strip()
    name = first_name(source.get("sender") or "") or "there"
    body = reply_only(source.get("body") or "")
    low = f"{subject} {body}".lower()
    questions = [
        re.sub(r"^\s*(?:\d+[).]|[-*])\s+", "", line.strip())
        for line in body.splitlines()
        if "?" in line and len(line.strip()) > 8 and not _BOILER.search(line)
    ]
    facts = [item for item in facts_from_body(body, limit=4) if not _BOILER.search(item)]
    lines = [f"Hi {name},", ""]
    if any(word in low for word in ("quot", "enquiry", "inquiry", "proforma", "po ", "purchase order")):
        lines.append(f"Thank you for the note on {subject}.")
        lines.append("I am reviewing it and will confirm shortly.")
    elif questions:
        lines.append(f"Thank you for the note on {subject}.")
        lines.append("I will confirm on this and come back to you.")
    elif facts:
        lines.append(f"Thank you for the note on {subject}. Noted — I will follow up shortly.")
    else:
        lines.append(f"Thank you for the note on {subject}. I have it and will follow up shortly.")
    return "\n".join(lines)


def spreadsheet_spec(message: str) -> dict[str, Any]:
    text = message.lower()
    title = ""
    if any(word in text for word in ("pricing", "quote", "quotation", "cost", "rate")):
        title = "Pricing"
    elif "blocker" in text:
        title = "Blockers"
    elif "follow" in text:
        title = "Follow-up"
    if not title:
        named = _MAKE_TITLE.search(message.strip())
        if named:
            title = re.sub(r"[.?!].*$", "", named.group(1)).strip(" .")[:40]
        title = title or "Notes"
    title = (title[:1].upper() + title[1:]) if title else "Notes"
    if any(word in text for word in ("pricing", "quote", "quotation", "cost", "invoice", "amount", "rate")):
        columns = ["Item", "Amount", "Notes"]
    else:
        columns = ["Item", "Owner", "Status"]
    return {"title": title[:40] or "Notes", "columns": columns, "rows": [["", "", ""]], "chart": False}


def document_spec(message: str) -> dict[str, Any]:
    text = message.lower()
    if "one-pager" in text or "one pager" in text:
        title = "One-pager"
    elif "minutes" in text or "mom" in text or "meeting" in text:
        title = "Meeting notes"
    else:
        title = "Notes"
    return {
        "title": title,
        "body": "Notes from this session.",
        "bullets": [],
    }


def wants_calendar_create(message: str) -> bool:
    text = message or ""
    if re.search(r"meeting notes|one-pager|spreadsheet|document|word file", text, re.I) and not re.search(
        r"\bcalendar\b", text, re.I
    ):
        return False
    if re.search(r"\b(what'?s|what is|show|list|open)\b.+\b(calendar|schedule|agenda)\b", text, re.I):
        return False
    return bool(_CREATE_CAL.search(text))


def _next_slot(now: datetime) -> datetime:
    now = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        return now.replace(minute=30)
    return (now + timedelta(hours=1)).replace(minute=0)


def _apply_meridiem(hour: int, minute: int, blob: str, now: datetime) -> tuple[int, int]:
    if "pm" in blob or "evening" in blob or "afternoon" in blob:
        if hour < 12:
            hour += 12
    elif "am" in blob or "morning" in blob:
        if hour == 12:
            hour = 0
    elif hour <= 7 and now.hour >= 12:
        hour += 12
    return hour % 24, min(minute, 59)


def _parse_time(message: str, now: datetime) -> tuple[int, int] | None:
    text = message or ""
    half = re.search(r"\bhalf past\s+(\d{1,2})\b", text, re.I)
    if half:
        return _apply_meridiem(int(half.group(1)), 30, text.lower(), now)
    quarter = re.search(r"\bquarter (to|past)\s+(\d{1,2})\b", text, re.I)
    if quarter:
        hour = int(quarter.group(2))
        if quarter.group(1).lower() == "to":
            hour = (hour - 1) % 24
            minute = 45
        else:
            minute = 15
        return _apply_meridiem(hour, minute, text.lower(), now)
    match = re.search(r"\b(?:at|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|o'?clock)?\b", text, re.I)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        return _apply_meridiem(hour, minute, match.group(0).lower() + " " + text.lower(), now)
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text, re.I)
    if match:
        return _apply_meridiem(int(match.group(1)), int(match.group(2)), match.group(0).lower() + " " + text.lower(), now)
    match = re.search(r"\b(\d{1,2})\s+(am|pm|o'?clock)\b", text, re.I)
    if match:
        return _apply_meridiem(int(match.group(1)), 0, match.group(0).lower() + " " + text.lower(), now)
    match = re.search(r"\b(?:block|book)\s+(\d{1,2})(?::(\d{2}))?\b", text, re.I)
    if match:
        return _apply_meridiem(int(match.group(1)), int(match.group(2) or 0), text.lower(), now)
    if re.search(r"\bin the evening\b|\btonight\b", text, re.I):
        return 19, 0
    if re.search(r"\bin the afternoon\b", text, re.I):
        return 15, 0
    if re.search(r"\bin the morning\b", text, re.I):
        return 10, 0
    return None


def _parse_duration(message: str) -> int:
    match = _DURATION.search(message or "")
    if not match:
        return 30
    if match.group(3):
        return 30 if "half" in match.group(3).lower() else 60
    amount = int(match.group(1) or 30)
    unit = (match.group(2) or "min").lower()
    if unit.startswith("hour") or unit.startswith("hr"):
        return amount * 60
    return amount


def _parse_day(message: str, now: datetime) -> datetime:
    text = (message or "").lower()
    day = now
    if re.search(r"\btomorrow\b", text):
        return (now + timedelta(days=1)).replace(second=0, microsecond=0)
    if re.search(r"\btoday\b|\btonight\b", text):
        return now.replace(second=0, microsecond=0)
    for index, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b{name}\b", text):
            delta = (index - now.weekday()) % 7
            if re.search(r"\bnext\b", text) and delta == 0:
                delta = 7
            return (now + timedelta(days=delta)).replace(second=0, microsecond=0)
    return day.replace(second=0, microsecond=0)


def calendar_event_spec(message: str, tz: ZoneInfo) -> dict[str, str] | None:
    if not wants_calendar_create(message):
        return None
    now = datetime.now(tz)
    parsed = _parse_time(message or "", now)
    day = _parse_day(message or "", now)
    if parsed:
        hour, minute = parsed
        start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start <= now:
            weekday = any(re.search(rf"\b{name}\b", message or "", re.I) for name in _WEEKDAYS)
            start = start + timedelta(days=7 if weekday else 1)
    else:
        start = _next_slot(now)
        if re.search(r"\btomorrow\b", message or "", re.I):
            start = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif day.date() != now.date():
            start = day.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=_parse_duration(message or ""))
    title = re.sub(r"\b(?:at|@|block|book)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm|o'?clock)?\b", " ", message or "", flags=re.I)
    title = re.sub(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", " ", title, flags=re.I)
    title = _DURATION.sub(" ", title)
    title = _STRIP_EVENT.sub(" ", title)
    title = re.sub(r"\bfor\b", " ", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" .,!-")
    title = title[:80] or "Meeting"
    if title.lower() in {"with", "call", "meeting"}:
        title = "Meeting"
    return {
        "title": title,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "location": "",
        "notes": "",
    }


def gemini_steps(message: str) -> str:
    text = (message or "").strip()
    text = re.sub(r"(?i)^(jarvis[,:]?\s*)+", "", text)
    text = re.sub(
        r"(?i)\b(please\s+)?("
        r"ask gemini|tell gemini|get gemini|have gemini|"
        r"send (this|it )?to gemini|forward (this|it )?to gemini|"
        r"run (this|it )?by gemini|task for gemini|gemini to|"
        r"throw this at gemini|gemini this"
        r")\b[:\s]*",
        "",
        text,
        count=1,
    )
    text = re.sub(r"(?i)^please\s+", "", text.strip())
    text = re.sub(r"(?i)^to\s+", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip(" .,")
    return text or (message or "").strip()
