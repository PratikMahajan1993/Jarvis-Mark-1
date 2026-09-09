from __future__ import annotations

import re
from typing import Any
from datetime import datetime, timedelta

from . import db
from .connectors import email as email_conn

_NAME_HINT = re.compile(
    r"\b(?:from|by)\s+([A-Za-z][A-Za-z'-]+)"
    r"|\bwhat did\s+([A-Za-z][A-Za-z'-]+)"
    r"|\breply to\s+([A-Za-z][A-Za-z'-]+)"
    r"|\b(?:read|show|open)\s+([A-Za-z][A-Za-z'-]+)"
    r"|\b([A-Za-z][A-Za-z'-]+)'s\s+(?:mail|email|note|message|quote|quotation|enquiry|inquiry)"
    r"|\b([A-Za-z][A-Za-z'-]+)\s+(?:said|wrote|replied|sent|mailed)"
    r"|\b(?:quote|quotation|enquiry|inquiry|mail|email)\s+from\s+([A-Za-z][A-Za-z'-]+)",
    re.I,
)
_MAIL_ASK = re.compile(
    r"\b(mail|email|e-mail|gmail|inbox|reply|draft|said|say|wrote|note|message|quote|quotation|enquiry|inquiry)\b",
    re.I,
)
_NAME_SKIP = {
    "what", "whats", "did", "mail", "email", "from", "said", "reply", "replied",
    "the", "a", "an", "to", "in", "is", "show", "read", "please", "jarvis", "draft",
    "open", "spreadsheet", "sheet", "and", "make", "same", "this", "that",
    "last", "latest", "newest", "morning", "afternoon", "tonight", "today", "yesterday", "note",
    "message", "wrote", "say", "about", "your", "our", "them", "they",
    "him", "her", "his", "hers", "she", "he", "we", "you", "inbox", "unread",
    "pricing", "calendar", "gemini", "briefing", "document", "file",
}
_SKIP_LINE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|best|regards|cheers|dear)\b"
    r"|^(two|a few|several|some)\s+items\b"
    r"|:\s*$",
    re.I,
)
_QUOTE_SPLIT = re.compile(
    r"\nOn .{8,90} wrote:"
    r"|^-{3,}.*Original Message.*-{3,}"
    r"|^\s*From:\s+\S+.*\nSent:",
    re.I | re.M,
)
_INSTRUCTION = re.compile(
    r"^(file|do this|reply like this|instructions)\b"
    r"|extract the totals"
    r"|reply with a table"
    r"|task for gemini"
    r"|here are the facts and totals extracted"
    r"|trailing mail|please find (enclosed|attached)|as per your requirement"
    r"|with reference to|item codes have been selected|for your kind information",
    re.I,
)
_POINTER = re.compile(
    r"\b(that|the|this|last|same|him|her|his|open|show|again)\b",
    re.I,
)
_OPEN_SHEET = re.compile(
    r"\b(open|show|bring up|get|where's|where is)\b.*\b(spread\s*sheet|sheet|excel|xlsx|workbook)\b"
    r"|\b(the|that|last)\s+(spread\s*sheet|sheet|excel|workbook)\b",
    re.I,
)
_READ_MAIL = re.compile(
    r"\b(what('?s| is) in|what did|read|show|open|summarise|summarize)\b.*\b(mail|email|e-mail|gmail|said|say|wrote|replied|reply|note|message|quote|quotation|enquiry|inquiry)\b"
    r"|\b(mail|email|e-mail|note|message|quote|quotation)\s+(from|by)\b"
    r"|\b(last|latest|newest)\s+(email|mail|message)\b",
    re.I,
)
_REPLY = re.compile(r"\b(reply|draft|write back|respond|tell her|tell him)\b", re.I)
_MAKE_SHEET = re.compile(r"\b(make|create|new|write|build|prepare)\b.*\b(spread\s*sheet|excel|xlsx|workbook)\b", re.I)
_SAME_MORNING = re.compile(r"\b(same as|like|from)\s+(this\s+)?morning\b|\bthis morning'?s\b", re.I)

FEMALE = {
    "priya", "sarah", "sara", "anita", "neha", "aisha", "maya", "lisa", "emma",
    "muskaan", "pooja", "kavita", "deepa", "ritu", "sneha", "meera", "nisha",
    "shreya", "anjali", "divya", "kavya", "isha", "riya", "tanvi", "kiran",
}
MALE = {
    "ashutosh", "amit", "rahul", "raj", "arjun", "vikram", "tony", "john", "david",
    "pratik", "rohit", "sanjay", "vivek", "nikhil", "aditya", "manish", "suresh",
    "ramesh", "kunal", "rajesh", "siddharth", "harsh", "yash", "arnav",
}


def empty_set() -> dict[str, Any]:
    return {
        "person": None,
        "thread": None,
        "artifact": None,
        "client": None,
        "drive": None,
        "mail_attachments": None,
        "calendar": [],
        "aliases": {},
        "people": [],
        "artifacts": [],
        "drives": [],
    }


def get_set(session_id: str) -> dict[str, Any]:
    data = db.get_working_set(session_id)
    base = empty_set()
    if data:
        base.update({key: data.get(key, base[key]) for key in base})
        if isinstance(data.get("aliases"), dict):
            base["aliases"] = data["aliases"]
    return base


def save_set(session_id: str, data: dict[str, Any]) -> None:
    db.save_working_set(session_id, data)


def first_name(value: str) -> str:
    text = (value or "").split("<")[0].strip()
    if not text:
        return ""
    return text.split()[0]


def display_name(value: str) -> str:
    return (value or "").split("<")[0].strip() or value


def person_from_sender(sender: str) -> dict[str, str]:
    name = display_name(sender)
    match = re.search(r"<([^>]+)>", sender or "")
    email = match.group(1) if match else sender
    return {"name": name, "email": email, "first": first_name(name), "sender": sender}


def _push(stack: list[dict[str, Any]] | None, item: dict[str, Any], key: str, limit: int = 3) -> list[dict[str, Any]]:
    ident = item.get(key)
    out = [row for row in (stack or []) if row.get(key) != ident]
    out.insert(0, item)
    return out[:limit]


def remember_person(
    session_id: str,
    sender: str,
    mail_id: str | None = None,
    subject: str | None = None,
    client: str | None = None,
) -> None:
    data = get_set(session_id)
    person = person_from_sender(sender)
    data["people"] = _push(data.get("people"), {**person, "mail_id": mail_id, "subject": subject or ""}, "sender")
    data["person"] = data["people"][0]
    if mail_id:
        data["thread"] = {"id": mail_id, "subject": subject or "", "sender": sender}
    if client:
        data["client"] = client
    first = person["first"].lower()
    if first:
        data.setdefault("aliases", {})[first] = {"kind": "person", "sender": sender, "name": person["name"]}
    save_set(session_id, data)


def remember_artifact(session_id: str, artifact: dict[str, Any], title: str = "") -> None:
    data = get_set(session_id)
    item = {
        "id": artifact.get("id"),
        "kind": artifact.get("kind"),
        "name": artifact.get("name"),
        "title": title or artifact.get("name") or "Spreadsheet",
    }
    data["artifacts"] = _push(data.get("artifacts"), item, "id")
    data["artifact"] = data["artifacts"][0]
    aliases = data.setdefault("aliases", {})
    aliases["the spreadsheet"] = {"kind": "artifact", "id": data["artifact"]["id"]}
    aliases["the sheet"] = {"kind": "artifact", "id": data["artifact"]["id"]}
    if len(data["artifacts"]) > 1:
        other = data["artifacts"][1]
        aliases["the other spreadsheet"] = {"kind": "artifact", "id": other["id"]}
        aliases["the other sheet"] = {"kind": "artifact", "id": other["id"]}
    for art in data["artifacts"]:
        label = (art.get("title") or art.get("name") or "").lower()
        stem = re.sub(r"-[0-9a-f]{4,}.*$", "", label).split(".")[0].strip()
        if stem:
            aliases[stem] = {"kind": "artifact", "id": art["id"]}
            aliases[f"the {stem}"] = {"kind": "artifact", "id": art["id"]}
        if "pricing" in label:
            aliases["the pricing sheet"] = {"kind": "artifact", "id": art["id"]}
            aliases["pricing spreadsheet"] = {"kind": "artifact", "id": art["id"]}
    save_set(session_id, data)


def remember_drive(session_id: str, file: dict[str, Any]) -> None:
    data = get_set(session_id)
    item = {
        "id": file.get("id"),
        "name": file.get("name"),
        "title": file.get("title") or file.get("name") or "Drive file",
        "link": file.get("link") or "",
    }
    data["drives"] = _push(data.get("drives"), item, "id")
    data["drive"] = data["drives"][0]
    aliases = data.setdefault("aliases", {})
    for drive in data["drives"]:
        if drive.get("title"):
            aliases[str(drive["title"]).lower()] = {"kind": "drive", "id": drive["id"], "link": drive["link"]}
    aliases["the drive file"] = {"kind": "drive", "id": data["drive"]["id"], "link": data["drive"]["link"]}
    if len(data["drives"]) > 1:
        other = data["drives"][1]
        aliases["the other drive file"] = {"kind": "drive", "id": other["id"], "link": other["link"]}
    save_set(session_id, data)


def remember_alias(session_id: str, phrase: str, target: dict[str, Any]) -> None:
    data = get_set(session_id)
    data.setdefault("aliases", {})[phrase.strip().lower()] = target
    save_set(session_id, data)


def _find_named_mail(message: str) -> dict[str, Any] | None:
    if not _MAIL_ASK.search(message or "") and not _NAME_HINT.search(message or ""):
        return None
    names = [group for match in _NAME_HINT.finditer(message or "") for group in match.groups() if group]
    for token in names:
        name = re.sub(r"['’]s$", "", token)
        if name.lower() in _NAME_SKIP or len(name) < 3:
            continue
        rows = email_conn.search_emails(query=f"from:{name}", limit=5) or email_conn.search_emails(query=name, limit=5)
        lowered = name.lower()
        for row in rows:
            sender = (row.get("sender") or "").lower()
            if lowered in sender:
                return row
        if rows:
            return rows[0]
    return None


def gender_of(name: str) -> str | None:
    text = name or ""
    if re.search(r"\b(sir|mr)\b", text, re.I):
        return "m"
    if re.search(r"\b(ma'?am|madam|mrs|ms)\b", text, re.I):
        return "f"
    key = first_name(text).lower()
    if key in FEMALE:
        return "f"
    if key in MALE:
        return "m"
    return None


def pronoun_gender(message: str) -> str | None:
    if re.search(r"\b(her|hers|she)\b", message or "", re.I):
        return "f"
    if re.search(r"\b(him|his|he)\b", message or "", re.I):
        return "m"
    return None


def mail_for_pronoun(session_id: str, message: str) -> dict[str, Any] | None:
    want = pronoun_gender(message)
    data = get_set(session_id)
    person = data.get("person") or {}
    thread = data.get("thread") or {}
    if person.get("first") and (not want or gender_of(person.get("first") or "") == want):
        if thread.get("id"):
            found = email_conn.get_email(str(thread["id"]))
            if found:
                return found
        rows = email_conn.search_emails(query=person["first"], limit=1)
        return rows[0] if rows else None
    if not want:
        return None
    matches = [
        row
        for row in email_conn.search_emails(limit=8)
        if gender_of(row.get("sender") or "") == want
    ]
    return matches[0] if matches else None


def resolve(session_id: str, message: str) -> dict[str, Any]:
    data = get_set(session_id)
    text = message.lower()
    found_mail = None if _SAME_MORNING.search(message) else _find_named_mail(message)
    artifact = data.get("artifact")
    person = data.get("person")
    thread = data.get("thread")
    aliases = data.get("aliases") or {}
    for phrase, target in sorted((aliases or {}).items(), key=lambda item: len(str(item[0])), reverse=True):
        if phrase and phrase in text:
            if target.get("kind") == "artifact" and target.get("id"):
                found = db.get_artifact(str(target["id"]))
                if found:
                    artifact = found
                    if "title" not in artifact:
                        artifact = {**artifact, "title": artifact.get("name")}
                else:
                    stacked = next((row for row in (data.get("artifacts") or []) if row.get("id") == target["id"]), None)
                    artifact = stacked or {"id": target["id"], "title": phrase, "name": phrase}
            if target.get("kind") == "person" and target.get("sender"):
                person = person_from_sender(target["sender"])
                if not found_mail:
                    rows = email_conn.search_emails(query=person["first"], limit=1)
                    found_mail = rows[0] if rows else found_mail
            if target.get("kind") == "drive":
                data["drive"] = {
                    "id": target.get("id"),
                    "link": target.get("link") or (data.get("drive") or {}).get("link"),
                    "title": phrase,
                    "name": phrase,
                }
    if found_mail:
        person = person_from_sender(found_mail["sender"])
        thread = {"id": found_mail["id"], "subject": found_mail["subject"], "sender": found_mail["sender"]}
    elif pronoun_gender(message) or any(
        phrase in text
        for phrase in (
            "that mail",
            "the mail",
            "that note",
            "that email",
            "the email",
            "that message",
            "last email",
            "last mail",
            "the last email",
            "the last mail",
            "latest email",
            "latest mail",
            "forward this",
            "forward that",
            "forward it",
        )
    ) or re.search(r"\b(this|that|it)\b", text) and "forward" in text:
        found_mail = mail_for_pronoun(session_id, message)
        if found_mail:
            person = person_from_sender(found_mail["sender"])
            thread = {"id": found_mail["id"], "subject": found_mail["subject"], "sender": found_mail["sender"]}
    return {
        "person": person,
        "thread": thread,
        "mail": found_mail,
        "artifact": artifact,
        "client": data.get("client"),
        "open_sheet": bool(_OPEN_SHEET.search(message) and not _MAKE_SHEET.search(message)),
        "read_mail": bool(_READ_MAIL.search(message)),
        "reply": bool(_REPLY.search(message)),
        "make_sheet": bool(_MAKE_SHEET.search(message)),
        "same_morning": bool(_SAME_MORNING.search(message)),
        "pointer": bool(_POINTER.search(message)),
        "drive": data.get("drive"),
    }


def _clean_fact(item: str) -> str:
    piece = re.sub(r"^\s*(?:\d+[).]|[-*])\s+", "", item or "")
    piece = re.sub(r"\s+", " ", piece).strip().rstrip(".?")
    piece = re.sub(r"^(please|can you|could you)\s+", "", piece, flags=re.I)
    if piece[:1].isupper() and len(piece) > 1:
        piece = piece[0].lower() + piece[1:]
    return piece


def reply_only(body: str) -> str:
    text = (body or "").replace("\r\n", "\n")
    cut = _QUOTE_SPLIT.search(text)
    if cut:
        text = text[: cut.start()]
    return text.strip()


def facts_from_body(body: str, limit: int = 3) -> list[str]:
    text = reply_only(body)
    section = re.search(r"(?is)\bfacts?\s*:\s*(.+?)(?:\n\s*\n|summary totals|items in sheet|$)", text)
    source = (section.group(1) if section else text).strip()
    items = re.findall(r"^\s*(?:\d+[).]|[-*])\s+(.+)$", source, re.M)
    seen = {_clean_fact(item) for item in items}
    chunks = re.split(r"(?<=[.!?])\s+|\n+", source)
    for chunk in chunks:
        line = chunk.strip()
        if len(line) < 18 or _SKIP_LINE.search(line) or _INSTRUCTION.search(line):
            continue
        piece = _clean_fact(line)
        if not piece or piece in seen or _INSTRUCTION.search(piece):
            continue
        seen.add(piece)
        items.append(line)
    clean = []
    for item in items:
        piece = _clean_fact(item)
        if piece and piece not in clean:
            clean.append(piece)
        if len(clean) >= limit:
            break
    return clean


def join_facts(facts: list[str]) -> str:
    if not facts:
        return "the note is on the board"
    if len(facts) == 1:
        return facts[0]
    if len(facts) == 2:
        return f"{facts[0]}, and {facts[1]}"
    return f"{facts[0]}, {facts[1]}, and {facts[2]}"


def speak_mail(mail: dict[str, Any]) -> str:
    name = first_name(mail.get("sender") or "") or "them"
    facts = facts_from_body(mail.get("body") or "")
    verb = "replied" if str(mail.get("subject") or "").lower().startswith("re:") else "wrote"
    if not facts or facts == ["the note is on the board"]:
        subject = (mail.get("subject") or "a note").strip()
        return f"{name}'s note is on the board — {subject}."
    return f"{name} {verb}: {join_facts(facts)}."


def speak_draft(to_addr: str, source: dict[str, Any] | None = None) -> str:
    name = first_name(to_addr) or "them"
    return f"Draft for {name} is ready — shall I send it?"


def speak_sent(to_addr: str) -> str:
    name = first_name(to_addr) or "them"
    gender = gender_of(to_addr)
    if gender == "f":
        return f"Sent to {name}. She has it."
    if gender == "m":
        return f"Sent to {name}. He has it."
    return f"Sent to {name}."


def speak_sheet(title: str, reused: bool = False) -> str:
    label = re.sub(r"-[0-9a-f]{4,}.*$", "", (title or "spreadsheet").split(".")[0], flags=re.I).strip() or "spreadsheet"
    if label.lower() in {"follow-up", "followup"}:
        label = "spreadsheet"
    if reused:
        return f"{label} is back on the board."
    return f"{label} is on the board."


def speak_calendar(
    events: list[dict[str, Any]],
    upcoming: list[dict[str, Any]] | None = None,
    span: str = "",
    note: str = "",
) -> str:
    from .connectors.calendar import clock

    upcoming = list(upcoming) if upcoming is not None else list(events or [])
    events = list(events or [])
    label = (span or "").strip().lower()

    def _line(event: dict[str, Any]) -> str:
        title = (event.get("title") or "the next meeting").split("—")[0].split("-")[0].strip()
        raw = event.get("start_at") or ""
        try:
            from .connectors.calendar import parse_when

            when = parse_when(raw)
        except Exception:
            when = None
        if when and when.hour == 0 and when.minute == 0:
            today = datetime.now(when.tzinfo).date()
            if when.date() == today:
                return f"{title} today"
            if when.date() == today + timedelta(days=1):
                return f"{title} tomorrow"
            return f"{title} on {when.strftime('%A')}"
        stamp = clock(raw)
        return f"{title} at {stamp}" if stamp else title

    if not events:
        if note:
            return note.split(".")[0] + "."
        if label == "today":
            return "Clear today."
        if label == "tomorrow":
            return "Nothing tomorrow."
        return "Nothing on the calendar this week."
    if not upcoming:
        if label == "today":
            return f"{len(events)} already done today. Rest of the day is clear."
        nxt = events[0]
        return f"Next was {_line(nxt)}."
    shown = upcoming[:3]
    bits = [_line(event) for event in shown]
    extra = f" {len(upcoming) - 3} more." if len(upcoming) > 3 else ""
    if label == "tomorrow":
        return "Tomorrow: " + ", ".join(bits) + "." + extra
    if label == "today":
        return "Today: " + ", ".join(bits) + "." + extra
    nxt = upcoming[0]
    rest = f" {len(upcoming)} on the board." if len(upcoming) > 1 else ""
    return f"Next is {_line(nxt)}.{rest}"


def speak_for_tool(name: str, result: dict[str, Any], session_id: str = "default") -> str:
    data = result.get("data")
    scene = result.get("scene") or {}
    if name == "search_emails" and isinstance(data, list) and len(data) == 1:
        return speak_mail(data[0])
    if name == "read_email" and isinstance(data, dict) and data.get("body"):
        return speak_mail(data)
    if name == "draft_email":
        payload = (result.get("pending") or {}).get("payload") or {}
        source = email_conn.get_email(payload.get("source_id")) if payload.get("source_id") else None
        return speak_draft(payload.get("to") or "", source)
    if name == "forward_email":
        payload = (result.get("pending") or {}).get("payload") or {}
        name_to = first_name(payload.get("to") or "") or "them"
        return f"Forward to {name_to} is ready — shall I send it?"
    if name == "show_artifact":
        title = (data or {}).get("title") or (data or {}).get("name") or scene.get("title") or "spreadsheet"
        return speak_sheet(str(title), reused=True)
    if name == "create_spreadsheet":
        title = scene.get("title") or (data or {}).get("name") or "spreadsheet"
        return speak_sheet(str(title), reused=False)
    if name == "list_calendar" and isinstance(data, list):
        return speak_calendar(data)
    if name == "create_calendar_event":
        title = scene.get("subtitle") or scene.get("title") or "that event"
        return f"{title} is ready — shall I put it on the calendar?"
    if name == "drive_upload":
        title = (data or {}).get("title") or (data or {}).get("name") or "file"
        return result.get("speak") or f"{title} is on Drive."
    if name == "save_mail_attachments":
        return result.get("speak") or "Saved."
    if name == "reply_with_attachments":
        return result.get("speak") or "Draft is ready — shall I send it?"
    if name == "drive_find":
        label = scene.get("title") or "that file"
        return f"{label} is on the board."
    if name == "task_for_gemini":
        return result.get("speak") or "Task for Gemini is ready — shall I send it?"
    if name == "research":
        return result.get("speak") or "Research is on the board."
    if name == "open_artifact":
        title = (data or {}).get("name") or "file"
        return f"Opening {title}."
    if scene.get("title"):
        extra = scene.get("subtitle")
        if extra and extra != scene.get("title"):
            return f"{scene['title']}. {extra}."
        return f"{scene['title']} is on the board."
    return "Done."


def note_tool(session_id: str, name: str, result: dict[str, Any]) -> None:
    data = result.get("data")
    pending = result.get("pending") if isinstance(result.get("pending"), dict) else {}
    payload = pending.get("payload") or {}
    if name in {"search_emails"} and isinstance(data, list) and data:
        first = data[0]
        remember_person(session_id, first.get("sender") or "", first.get("id"), first.get("subject"))
    if name == "read_email" and isinstance(data, dict) and data.get("sender"):
        remember_person(session_id, data.get("sender") or "", data.get("id"), data.get("subject"))
        if data.get("attachments"):
            from .mail_attachments import remember_mail_context

            remember_mail_context(session_id, data, data.get("attachments") or [])
    if name == "save_mail_attachments" and isinstance(data, dict):
        saved = data.get("attachments") or []
        if isinstance(saved, list) and saved:
            ctx = get_set(session_id).get("mail_attachments") or {}
            mail = email_conn.get_email(ctx.get("email_id") or "") if ctx.get("email_id") else None
            if mail:
                from .mail_attachments import remember_mail_context

                remember_mail_context(session_id, mail, saved)
    if name == "draft_email":
        remember_person(
            session_id,
            payload.get("to") or "",
            payload.get("source_id"),
            payload.get("subject"),
        )
    if name == "reply_with_attachments":
        remember_person(
            session_id,
            payload.get("to") or "",
            payload.get("source_id"),
            payload.get("subject"),
        )
    if name == "forward_email" and isinstance(data, dict):
        source = email_conn.get_email(data.get("source_id") or payload.get("source_id") or "")
        if source:
            remember_person(session_id, source.get("sender") or "", source.get("id"), source.get("subject"))
        remember_person(session_id, payload.get("to") or "", None, payload.get("subject"))
    if name == "list_calendar" and isinstance(data, list):
        working = get_set(session_id)
        working["calendar"] = data[:8]
        save_set(session_id, working)
    if name == "create_spreadsheet" and isinstance(data, dict) and data.get("id"):
        scene = result.get("scene") or {}
        remember_artifact(session_id, data, scene.get("title") or data.get("name") or "")
    if name == "show_artifact" and isinstance(data, dict) and data.get("id"):
        remember_artifact(session_id, data, data.get("title") or data.get("name") or "")
    if name in {"drive_upload", "drive_find"} and isinstance(data, dict) and data.get("link"):
        remember_drive(session_id, data)


def ensure_demo_people() -> None:
    from .connectors.gmail import live as gmail_live

    if gmail_live():
        return
    if email_conn.get_email("mail-ashutosh"):
        return
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO emails (id, sender, to_addr, subject, body, unread, created_at, folder)
            VALUES (?, ?, ?, ?, ?, 1, ?, 'INBOX')
            """,
            (
                "mail-ashutosh",
                "Ashutosh Mehta <ashutosh@northline.example>",
                "you@jarvis.local",
                "Re: Q3 proposal — your note",
                (
                    "Price is fine on our side.\n"
                    "Please send the MSA redlines by Thursday.\n"
                    "Can you confirm the on-site week?\n"
                ),
                (now - timedelta(hours=1)).isoformat(),
            ),
        )


def wants_familiarity(message: str) -> bool:
    text = message.lower()
    return bool(
        _OPEN_SHEET.search(text)
        or _READ_MAIL.search(text)
        or re.search(r"\breply to (him|her|them|that)\b", text)
        or _SAME_MORNING.search(text)
        or "gemini" in text
        or "drive" in text
    )
