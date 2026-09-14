from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import db
from .connectors import calendar as calendar_conn
from .connectors import email as email_conn
from .familiarity import display_name, first_name


def _now():
    return datetime.now(_tz())


_SKIP_SUBSTR = (
    "amazon",
    "linkedin",
    "noreply",
    "no-reply",
    "newsletter",
    "marketing",
    "notification",
    "notifications",
    "au small finance",
    "ausmallfinance",
    "bank",
    "billing@",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "facebook",
    "twitter",
    "instagram",
    "promo",
    "unsubscribe",
    "google alerts",
    "github",
    "slack",
    "zoom.us",
    "calendar-notification",
    "flipkart",
    "myntra",
    "swiggy",
    "zomato",
    "cred",
    "paytm",
)

_BRAND_ONLY = re.compile(
    r"^(billing|support|info|hello|team|admin|service|sales|news|"
    r"accounts|security|updates|notify|notification)s?$",
    re.I,
)

_BRAND_TOKENS = frozenset({
    "team", "inc", "ltd", "llc", "corp", "bank", "finance", "billing", "support",
    "adobe", "cursor", "ollama", "google", "microsoft", "apple", "amazon", "linkedin",
    "newsletter", "notification", "updates", "mail", "service", "account", "security",
    "acrobat", "github", "slack", "notion", "figma", "dropbox", "zoom", "labs",
    "group", "media", "marketing", "store", "shop", "pay", "wallet", "cloud",
})

_ORG_SUFFIX = frozenset({
    "team", "inc", "ltd", "llc", "corp", "bank", "finance", "labs", "group", "media",
    "store", "shop", "cloud", "pay", "wallet", "service", "services", "support",
})

_COMPANY_TOKENS = frozenset({
    "technology", "technologies", "india", "industries", "industry", "solutions",
    "systems", "digital", "global", "international", "enterprises", "enterprise",
    "consulting", "consultancy", "pvt", "private", "limited",
})

_PRIORITY_CAP = 6


def _tz() -> ZoneInfo:
    prefs = db.get_preferences()
    try:
        return ZoneInfo(prefs.get("timezone") or "Asia/Kolkata")
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def greeting_slot() -> str:
    hour = _now().hour
    if hour < 12:
        return "Morning"
    if hour < 17:
        return "Afternoon"
    return "Evening"


def _sender_skipped(sender: str) -> bool:
    match = re.search(r"<([^>]+)>", sender or "")
    email = match.group(1) if match else ""
    blob = f"{sender} {email}".lower()
    return any(skip in blob for skip in _SKIP_SUBSTR)


def _looks_like_person(sender: str) -> bool:
    name = display_name(sender)
    if not name or _sender_skipped(sender):
        return False
    email_match = re.search(r"<([^>]+)>", sender or "")
    email = (email_match.group(1) if email_match else "").lower()
    if not email and "@" in name:
        email = name.lower()
    local = email.split("@")[0] if "@" in email else ""
    if local and any(token in local for token in ("noreply", "no-reply", "donotreply", "newsletter", "marketing", "notification", "bot", "daemon")):
        return False
    if "@" in name and "<" not in (sender or ""):
        if re.match(r"^[a-z][a-z'.-]*\.[a-z][a-z'.-]+", local, re.I):
            return True
        if re.match(r"^[a-z]{3,15}$", local, re.I) and local not in _BRAND_TOKENS:
            return True
        return False
    tokens = [part for part in re.split(r"\s+", name) if part]
    if not tokens:
        return False
    lower_tokens = [token.lower().strip('"') for token in tokens]
    if any(token in _BRAND_TOKENS or token in _COMPANY_TOKENS for token in lower_tokens):
        return False
    if len(tokens) >= 2:
        if lower_tokens[-1] in _ORG_SUFFIX:
            return False
        if len(tokens) > 2:
            return False
        if tokens[0][:1].isupper() and tokens[1][:1].isupper() and not tokens[1].isupper():
            return True
        return False
    if len(tokens) == 1:
        word = tokens[0].strip('"')
        if _BRAND_ONLY.match(word) or word.lower() in _BRAND_TOKENS:
            return False
        if word.isupper() and len(word) > 1:
            return False
        if word[:1].isupper() and word[1:].islower() and len(word) >= 3:
            return True
    return False


def _person_label(sender: str) -> str:
    name = display_name(sender)
    if "@" in name and "<" not in (sender or ""):
        local = name.split("@")[0]
        if "." in local:
            return local.split(".")[0].replace("_", " ").title()
        return local.replace("_", " ").title()
    return name


def filter_priority_mail(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        sender = str(row.get("sender") or "")
        key = sender.lower()
        if key in seen:
            continue
        if _looks_like_person(sender):
            out.append(row)
            seen.add(key)
        if len(out) >= _PRIORITY_CAP:
            break
    return out


def _shop_facts() -> dict:
    from .shop_log import efficiency_snapshot

    snap = efficiency_snapshot()
    oee = snap.get("oee_percent")
    return {
        "shop_oee": oee if isinstance(oee, (int, float)) else None,
        "shop_reason": snap.get("reason"),
        "shop_bottlenecks": snap.get("bottlenecks") or [],
        "shop_url": snap.get("url") or "",
        "shop_sheet": snap.get("sheet") or "",
    }


def gather_briefing_facts() -> dict:
    prefs = db.get_preferences()
    unread_total = email_conn.unread_count()
    unread = email_conn.search_emails(unread_only=True, limit=24)
    priority_mail = filter_priority_mail(unread)
    upcoming = calendar_conn.upcoming(days=2)
    next_event = upcoming[0] if upcoming else None
    slot = greeting_slot()
    weather: dict = {}
    try:
        from .office_day import fetch_weather

        weather = fetch_weather()
    except Exception:
        weather = {"speak": ""}
    return {
        "slot": slot,
        "name": prefs.get("display_name") or "Sir",
        "unread_total": unread_total,
        "priority_mail": priority_mail,
        "next_event": next_event,
        "date_subtitle": _now().strftime("%A | %d %b %Y"),
        "weather": weather,
        "weather_speak": weather.get("speak") or "",
        **_shop_facts(),
    }


def briefing_notes(facts: dict) -> str:
    lines: list[str] = []
    for mail in facts.get("priority_mail") or []:
        sender = _person_label(str(mail.get("sender") or ""))
        lines.append(f"mail|{sender}|{mail.get('subject') or ''}")
    nxt = facts.get("next_event")
    if isinstance(nxt, dict) and nxt.get("title"):
        lines.append(
            f"next|{nxt.get('title') or ''}|{calendar_conn.clock(str(nxt.get('start_at') or ''))}"
        )
    total = facts.get("unread_total")
    if total:
        lines.append(f"unread_total|{total}")
    lines.append(f"slot|{facts.get('slot') or ''}")
    lines.append(f"name|{facts.get('name') or ''}")
    oee = facts.get("shop_oee")
    if isinstance(oee, (int, float)):
        lines.append(f"shop_oee|{oee:.1f}")
    return "\n".join(lines)


def fallback_briefing_speak(facts: dict) -> str:
    slot = str(facts.get("slot") or greeting_slot())
    name = str(facts.get("name") or "Sir")
    priority = facts.get("priority_mail") or []
    next_event = facts.get("next_event") if isinstance(facts.get("next_event"), dict) else None
    unread_total = int(facts.get("unread_total") or 0)

    parts = [f"{slot}, {name}."]
    weather_speak = str(facts.get("weather_speak") or "").strip()
    if weather_speak:
        parts.append(weather_speak + ".")
    if priority:
        names: list[str] = []
        for mail in priority[:4]:
            who = _person_label(str(mail.get("sender") or ""))
            first = first_name(who) or who
            if first and first not in names:
                names.append(first)
        if names:
            if len(names) == 1:
                parts.append(f"{names[0]} is waiting on you.")
            elif len(names) == 2:
                parts.append(f"{names[0]} and {names[1]} are waiting on you.")
            else:
                parts.append(f"{names[0]}, {names[1]}, and others at work need you.")
        if len(priority) >= 4 and unread_total > len(priority):
            parts.append(f"{len(priority)} work threads in the unread pile.")
    else:
        parts.append("Nobody at work is waiting on mail.")

    if next_event and next_event.get("title"):
        title = str(next_event["title"])
        clock = calendar_conn.clock(str(next_event.get("start_at") or ""))
        if clock:
            parts.append(f"Next up: {title} at {clock}.")
        else:
            parts.append(f"Next up: {title}.")
    oee = facts.get("shop_oee")
    if isinstance(oee, (int, float)):
        parts.append(f"Shop OEE is {oee:.0f} percent.")
        labels = [
            str(item.get("label") or "").strip()
            for item in (facts.get("shop_bottlenecks") or [])
            if item.get("label")
        ]
        if labels:
            parts.append("Watch " + ", ".join(labels[:3]) + ".")
    return " ".join(parts)


def briefing_scene(facts: dict, speak: str) -> dict:
    widgets: list[dict] = []
    priority = facts.get("priority_mail") or []
    if priority:
        widgets.append(
            {
                "type": "table",
                "title": "Who needs you",
                "columns": ["From", "Subject"],
                "rows": [
                    [_person_label(str(mail.get("sender") or "")), str(mail.get("subject") or "")]
                    for mail in priority
                ],
            }
        )
    next_event = facts.get("next_event") if isinstance(facts.get("next_event"), dict) else None
    if next_event and next_event.get("title"):
        widgets.append(
            {
                "type": "timeline",
                "title": "Next",
                "items": [
                    {
                        "time": calendar_conn.clock(str(next_event.get("start_at") or "")),
                        "title": str(next_event["title"]),
                        "detail": str(next_event.get("location") or next_event.get("notes") or ""),
                    }
                ],
            }
        )
    oee = facts.get("shop_oee")
    if isinstance(oee, (int, float)):
        widgets.append(
            {
                "type": "kpi",
                "label": "Shop OEE",
                "value": f"{oee:.0f}%",
                "hint": facts.get("shop_sheet") or "",
            }
        )
        necks = facts.get("shop_bottlenecks") or []
        if necks:
            widgets.append(
                {
                    "type": "table",
                    "title": "Below 90%",
                    "columns": ["Machine", "OEE"],
                    "rows": [
                        [item.get("label") or "", f"{float(item.get('oee_percent') or 0):.0f}%"]
                        for item in necks[:6]
                    ],
                }
            )
    if speak:
        widgets.append({"type": "quote", "text": speak, "cite": "Jarvis"})
    return {
        "title": f"{facts.get('slot') or greeting_slot()} briefing",
        "subtitle": facts.get("date_subtitle") or _now().strftime("%A | %d %b %Y"),
        "widgets": widgets,
    }


def build_briefing() -> dict:
    facts = gather_briefing_facts()
    speak = fallback_briefing_speak(facts)
    scene = briefing_scene(facts, speak)
    return {"speak": speak, "scene": scene, **facts}


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
    now = _now()
    upcoming = []
    for event in calendar_conn.upcoming(days=7):
        try:
            start = calendar_conn.parse_when(event["start_at"])
            end = calendar_conn.parse_when(event["end_at"]) if event.get("end_at") else start
        except Exception:
            continue
        upcoming.append((start, end, event))

    glance = {
        "line": "",
        "whisper": "",
        "speak": "",
        "key": "",
        "minutes": None,
    }
    if upcoming:
        start, end, event = upcoming[0]
        title = event["title"]
        short = title.split("—")[0].split("-")[0].strip()
        today = now.date()
        if start.hour == 0 and start.minute == 0:
            stamp = start.strftime("%a")
        elif start.date() == today or start.date() == today + timedelta(days=1):
            stamp = start.strftime("%H:%M")
        else:
            stamp = start.strftime("%a %H:%M")
        line = f"{stamp}  {short}"
        if start <= now <= end:
            whisper = f"{short} is on now."
            glance = {
                "line": line,
                "whisper": whisper,
                "speak": whisper,
                "key": f"{event['id']}:now",
                "minutes": 0,
            }
        else:
            minutes = int((start - now).total_seconds() // 60)
            if minutes <= 60:
                amount = _minutes_phrase(max(minutes, 1))
                unit = "minute" if minutes <= 1 else "minutes"
                whisper = f"{amount} {unit} to {short}."
                bucket = 5 if minutes <= 5 else 15 if minutes <= 15 else 30 if minutes <= 30 else 60
                glance = {
                    "line": line,
                    "whisper": whisper,
                    "speak": whisper if minutes <= 30 else "",
                    "key": f"{event['id']}:{bucket}",
                    "minutes": minutes,
                }
            else:
                glance = {
                    "line": line,
                    "whisper": "",
                    "speak": "",
                    "key": f"{event['id']}:later",
                    "minutes": minutes,
                }

    if now.hour == 9 and now.minute < 5:
        facts = gather_briefing_facts()
        speak = fallback_briefing_speak(facts)
        glance["speak"] = speak
        glance["whisper"] = speak
        glance["key"] = f"briefing:{now.date().isoformat()}:0900"
        if not glance.get("line"):
            glance["line"] = "Morning briefing"
    return glance
