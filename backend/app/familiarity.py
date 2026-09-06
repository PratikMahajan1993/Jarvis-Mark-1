from __future__ import annotations

import re
from typing import Any

from . import db
from .connectors import email as email_conn

_SKIP_LINE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|best|regards|cheers|dear)\b"
    r"|^(two|a few|several|some)\s+items\b"
    r"|:\s*$",
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
    r"\b(what('?s| is) in|what did|read|show|summarise|summarize)\b.*\b(mail|email|e-mail|said|say|wrote|replied|reply|note|message)\b"
    r"|\b(mail|email|e-mail|note|message)\s+(from|by)\b",
    re.I,
)
_REPLY = re.compile(r"\b(reply|draft)\b", re.I)
_MAKE_SHEET = re.compile(r"\b(make|create|new|write|build|prepare)\b.*\b(spread\s*sheet|excel|xlsx|workbook)\b", re.I)
_SAME_MORNING = re.compile(r"\b(same as|like|from)\s+(this\s+)?morning\b|\bthis morning'?s\b", re.I)

FEMALE = {"priya", "sarah", "sara", "anita", "neha", "aisha", "maya", "lisa", "emma"}
MALE = {"ashutosh", "amit", "rahul", "raj", "arjun", "vikram", "tony", "john", "david"}


def empty_set() -> dict[str, Any]:
    return {"person": None, "thread": None, "artifact": None, "client": None, "drive": None, "aliases": {}}


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


def remember_person(
    session_id: str,
    sender: str,
    mail_id: str | None = None,
    subject: str | None = None,
    client: str | None = None,
) -> None:
    data = get_set(session_id)
    person = person_from_sender(sender)
    data["person"] = person
    if mail_id:
        data["thread"] = {"id": mail_id, "subject": subject or "", "sender": sender}
    if client:
        data["client"] = client
    elif "northline" in (sender or "").lower() or "northline" in (subject or "").lower():
        data["client"] = "Northline"
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
    data["artifact"] = item
    aliases = data.setdefault("aliases", {})
    aliases["the spreadsheet"] = {"kind": "artifact", "id": item["id"]}
    aliases["the sheet"] = {"kind": "artifact", "id": item["id"]}
    label = (title or item["name"] or "").lower()
    if "pricing" in label:
        aliases["the pricing sheet"] = {"kind": "artifact", "id": item["id"]}
        aliases["pricing spreadsheet"] = {"kind": "artifact", "id": item["id"]}
    client = (data.get("client") or "").lower()
    if client:
        aliases[f"the {client} sheet"] = {"kind": "artifact", "id": item["id"]}
    save_set(session_id, data)


def remember_drive(session_id: str, file: dict[str, Any]) -> None:
    data = get_set(session_id)
    item = {
        "id": file.get("id"),
        "name": file.get("name"),
        "title": file.get("title") or file.get("name") or "Drive file",
        "link": file.get("link") or "",
    }
    data["drive"] = item
    aliases = data.setdefault("aliases", {})
    if item.get("title"):
        aliases[str(item["title"]).lower()] = {"kind": "drive", "id": item["id"], "link": item["link"]}
    aliases["the drive file"] = {"kind": "drive", "id": item["id"], "link": item["link"]}
    save_set(session_id, data)


def remember_alias(session_id: str, phrase: str, target: dict[str, Any]) -> None:
    data = get_set(session_id)
    data.setdefault("aliases", {})[phrase.strip().lower()] = target
    save_set(session_id, data)


def _find_named_mail(message: str) -> dict[str, Any] | None:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", message)
    skip = {
        "what", "whats", "did", "mail", "email", "from", "said", "reply", "replied",
        "the", "a", "to", "in", "is", "show", "read", "please", "jarvis", "draft",
        "open", "spreadsheet", "sheet", "and", "make", "same", "this", "that",
        "last", "morning", "afternoon", "tonight", "today", "yesterday", "note",
        "message", "wrote", "say", "about", "your", "our", "them", "they",
        "him", "her", "his", "hers", "she", "he", "we", "you",
    }
    for token in tokens:
        name = re.sub(r"['’]s$", "", token)
        if name.lower() in skip or len(name) < 3:
            continue
        rows = email_conn.search_emails(query=name, limit=1)
        if rows:
            return rows[0]
    return None


def gender_of(name: str) -> str | None:
    key = first_name(name).lower()
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
    for phrase, target in aliases.items():
        if phrase in text:
            if target.get("kind") == "artifact" and target.get("id"):
                artifact = db.get_artifact(str(target["id"])) or artifact
                if artifact and "title" not in artifact:
                    artifact = {**artifact, "title": artifact.get("name")}
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
    elif pronoun_gender(message) or any(phrase in text for phrase in ("that mail", "the mail", "that note")):
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


def facts_from_body(body: str, limit: int = 3) -> list[str]:
    text = body or ""
    items = re.findall(r"^\s*(?:\d+[).]|[-*])\s+(.+)$", text, re.M)
    seen = {_clean_fact(item) for item in items}
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    for chunk in chunks:
        line = chunk.strip()
        if len(line) < 18 or _SKIP_LINE.search(line):
            continue
        piece = _clean_fact(line)
        if not piece or piece in seen:
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
    return f"Here is what {name} {verb}: {join_facts(facts)}."


def speak_draft(to_addr: str, source: dict[str, Any] | None = None) -> str:
    name = first_name(to_addr) or "them"
    if source:
        facts = facts_from_body(source.get("body") or "", limit=2)
        if facts:
            return f"{name} asked you to {join_facts(facts)}. Draft is on the board — shall I send it?"
    return f"Draft for {name} is on the board — shall I send it?"


def speak_sent(to_addr: str) -> str:
    name = first_name(to_addr) or "them"
    first = name.lower()
    if first in FEMALE:
        return f"Sent to {name}. She'll have the note."
    if first in MALE:
        return f"Sent to {name}. He'll have the note."
    return f"Sent to {name}."


def speak_sheet(title: str, reused: bool = False) -> str:
    label = (title or "spreadsheet").split(".")[0].strip()
    nice = label.lower()
    if nice in {"follow-up", "followup"}:
        nice = "spreadsheet"
    if "pricing" in nice and "sheet" not in nice:
        nice = "pricing sheet"
    if reused:
        return f"The {nice} you made is on the board."
    return f"The {nice} is on the board."


def speak_calendar(events: list[dict[str, Any]]) -> str:
    if not events:
        return "The board is clear for the next couple of days."
    nxt = events[0]
    title = nxt.get("title") or "the next meeting"
    short = title.split("—")[0].split("-")[0].strip()
    when = ""
    start = nxt.get("start_at") or ""
    if len(start) > 16:
        when = f" at {start[11:16]}"
    extra = f" {len(events)} on the board." if len(events) > 1 else ""
    return f"Next up is {short}{when}.{extra}"


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
        return f"{title} is drafted — shall I put it on the calendar?"
    if name == "drive_upload":
        title = (data or {}).get("title") or (data or {}).get("name") or "file"
        return f"The {title} is on Drive."
    if name == "drive_find":
        return scene.get("title") and f"{scene['title']} is on the board." or "I found that on Drive."
    if name == "task_for_gemini":
        return result.get("speak") or "Task for Gemini is on the board — shall I send it?"
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
    if name == "draft_email":
        remember_person(
            session_id,
            payload.get("to") or "",
            payload.get("source_id"),
            payload.get("subject"),
        )
    if name == "create_spreadsheet" and isinstance(data, dict) and data.get("id"):
        scene = result.get("scene") or {}
        remember_artifact(session_id, data, scene.get("title") or data.get("name") or "")
    if name == "show_artifact" and isinstance(data, dict) and data.get("id"):
        remember_artifact(session_id, data, data.get("title") or data.get("name") or "")
    if name in {"drive_upload", "drive_find"} and isinstance(data, dict) and data.get("link"):
        remember_drive(session_id, data)


def ensure_demo_people() -> None:
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
