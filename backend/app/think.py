from __future__ import annotations

import base64
import json
import re
from typing import Any

from .connectors.search import notes_for_model, outlet_name
from .brain import OllamaError, chat as ollama_chat
from .familiarity import first_name, reply_only, speak_draft, speak_mail
_FILLER = re.compile(
    r"further updates will be provided|it is recommended to consult|as an ai|reliable source for news|as necessary",
    re.I,
)
_AGO = re.compile(r"^\s*\d+\s+(hours?|minutes?|days?)\s+ago\s*[-–:·.]*\s*", re.I)
_URL = re.compile(r"https?://\S+")
_DOMAIN = re.compile(r"\b[\w.-]+\.(com|in|org|net|io)\b", re.I)


def _digits(text: str) -> set[str]:
    return {item.replace(",", "") for item in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text or "")}


def _grounded(claim: str, notes: str) -> bool:
    if not claim or _FILLER.search(claim):
        return False
    facts = _digits(notes)
    if not facts:
        return True
    for number in _digits(claim):
        if number in facts:
            continue
        if len(number) <= 2 and any(number in item for item in facts):
            continue
        return False
    return True


def _fits_one_source(claim: str, notes: str) -> bool:
    claimed = _digits(claim)
    if not claimed:
        return True
    for line in (notes or "").splitlines():
        have = _digits(line)
        if claimed <= have:
            return True
    return False


def _from_notes(notes: str) -> tuple[str, str]:
    items: list[tuple[str, str]] = []
    for line in (notes or "").splitlines():
        if ":" not in line:
            continue
        who, rest = line.split(":", 1)
        rest = _AGO.sub("", rest).strip().rstrip(".")
        if rest:
            items.append((who.strip(), rest))
    if not items:
        return "I opened the pages; they did not give a clean figure.", ""
    who, rest = items[0]
    speak = rest if rest.endswith((".", "!", "?")) else f"{rest}."
    if who:
        speak = f"{speak} That is {who}."
    briefing = "\n".join(f"{name} — {fact}." for name, fact in items[:4])
    return speak, briefing


def _grounded_briefing(speak: str, notes: str) -> bool:
    if not speak:
        return False
    allowed: set[str] = set()
    event_titles: list[str] = []
    for line in (notes or "").splitlines():
        if line.startswith("mail|"):
            parts = line.split("|", 2)
            if len(parts) >= 2:
                sender = parts[1].strip()
                allowed.add(first_name(sender).lower())
                allowed.add(sender.split()[0].lower() if sender else "")
        elif line.startswith("next|"):
            parts = line.split("|", 2)
            if len(parts) >= 2:
                title = parts[1].strip().lower()
                event_titles.append(title)
                for word in re.findall(r"[a-z]{3,}", title):
                    allowed.add(word)
    skip = {
        "tony", "morning", "afternoon", "evening", "next", "jarvis", "sir",
        "the", "and", "you", "your", "at", "on", "up", "is", "are", "waiting",
        "work", "mail", "nobody", "nothing",
    }
    for match in re.finditer(r"\b([A-Z][a-z]+)\b", speak):
        word = match.group(1).lower()
        if word in skip:
            continue
        if word not in allowed and not any(word in title for title in event_titles):
            return False
    return True


def refine_briefing(prefs: dict[str, Any], asked: str, result: dict[str, Any]) -> dict[str, Any]:
    from .briefing import (
        briefing_notes,
        briefing_scene,
        fallback_briefing_speak,
        gather_briefing_facts,
    )

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if "priority_mail" not in data:
        data = gather_briefing_facts()
    notes = briefing_notes(data)
    fallback = fallback_briefing_speak(data)
    model = _ask_briefing_model(prefs, asked, notes) if notes else {}
    speak = _clean_voice(str(model.get("speak") or ""))
    if not speak or "@" in speak or not _grounded_briefing(speak, notes):
        speak = fallback
    result["speak"] = speak
    result["scene"] = briefing_scene(data, speak)
    result["data"] = data
    return result


def _ask_briefing_model(prefs: dict[str, Any], asked: str, notes: str) -> dict[str, Any]:
    name = prefs.get("assistant_name") or "Jarvis"
    who = prefs.get("display_name") or "Sir"
    persona = prefs.get("persona") or "Calm, precise, slightly dry British aide."
    prompt = f"""{who} asked: {asked}

Briefing facts (use only these; do not invent senders, subjects, or meetings):
{notes}

Write one or two spoken sentences: who at work needs {who}, and what is next on the clock.
Mention unread count only if several work people are waiting — never lead with a big inbox number.
Only name people and events that appear in the facts.

Reply as {name}. JSON only:
{{
  "speak": "one or two sentences for voice. No invented names or times."
}}
Persona: {persona}
Do not mention tools, JSON, or that you are a model."""
    try:
        message = ollama_chat(
            [
                {"role": "system", "content": f"You are {name}, a present aide for morning briefings. Ground every claim in the facts."},
                {"role": "user", "content": prompt},
            ],
            format_json=True,
            timeout=180,
            options={"temperature": 0.35, "num_predict": 400},
        )
    except OllamaError:
        return {}
    return _parse_model_json(message.get("content") or "")


def refine_research(prefs: dict[str, Any], asked: str, result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    notes = notes_for_model(data)
    hits = data.get("hits") or []
    topic = data.get("query") or asked
    fallback_speak, fallback_brief = _from_notes(notes)
    model = _ask_model(prefs, asked, notes) if notes else {}
    speak = _clean_voice(str(model.get("speak") or ""))
    if not (_grounded(speak, notes) and _fits_one_source(speak, notes)):
        speak = fallback_speak
    briefing = fallback_brief or speak
    points: list[Any] = []
    result["speak"] = speak
    result["scene"] = _scene(topic, speak, briefing, points, hits)
    return result


def _ask_model(prefs: dict[str, Any], asked: str, notes: str) -> dict[str, Any]:
    name = prefs.get("assistant_name") or "Jarvis"
    who = prefs.get("display_name") or "Sir"
    persona = prefs.get("persona") or "Calm, precise, slightly dry British aide."
    prompt = f"""{who} asked: {asked}

Facts gathered from the web (use only these; do not invent numbers or dates):
{notes}

Every number you write must already appear in those facts. If you are unsure, restate the first fact in your own words.
Do not pad with 'further updates' or 'consult this source'.

Reply as {name}. JSON only:
{{
  "speak": "two spoken sentences. No URLs, no domain names, no 'I found N sources', no search-engine names.",
  "briefing": "a short paragraph in your own words for the board. Name newspapers in English (Economic Times, not economictimes.indiatimes.com).",
  "points": [{{"who": "Economic Times", "said": "one concrete fact from that outlet"}}]
}}
Persona: {persona}
Do not mention tools, JSON, Ollama, or that you are a model."""
    try:
        message = ollama_chat(
            [
                {
                    "role": "system",
                    "content": f"You are {name}, a present aide, not a search-result printer.",
                },
                {"role": "user", "content": prompt},
            ],
            format_json=True,
            timeout=180,
            options={"temperature": 0.35, "num_predict": 900},
        )
    except OllamaError:
        return {}
    raw = (message.get("content") or "").strip()
    return _parse_model_json(raw)


def _parse_model_json(raw: str) -> dict[str, Any]:
    blob = (raw or "").strip()
    blob = re.sub(r"^```(?:json)?\s*|\s*```$", "", blob)
    for candidate in (blob, blob[blob.find("{") : blob.rfind("}") + 1] if "{" in blob else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    speak = _json_string_field(blob, "speak")
    briefing = _json_string_field(blob, "briefing")
    if speak or briefing:
        return {"speak": speak, "briefing": briefing or speak, "points": []}
    cleaned = _clean_voice(blob)
    return {"speak": cleaned, "briefing": cleaned, "points": []} if cleaned else {}


def _json_string_field(text: str, key: str) -> str:
    match = re.search(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)(?:"|$)', text, re.S)
    if not match:
        return ""
    value = match.group(1).replace('\\"', '"').replace("\\n", " ").strip()
    return _clean_voice(value)


def _clean_voice(text: str) -> str:
    blob = (text or "").strip()
    blob = re.sub(r'^\{?\s*"speak"\s*:\s*"?', "", blob)
    blob = _URL.sub("", blob)
    blob = re.sub(r"\s+", " ", blob).strip()
    blob = _DOMAIN.sub("", blob)
    blob = re.sub(r"\s{2,}", " ", blob).strip(" -—,.{}\"")
    if blob and blob[0].islower():
        blob = blob[0].upper() + blob[1:]
    return blob


def _fallback_speak(notes: str) -> str:
    first = (notes.split("\n") or [""])[0]
    if ":" in first:
        who, rest = first.split(":", 1)
        rest = rest.strip().rstrip(".")
        if rest:
            return f"{who.strip()} puts it at {rest}." if re.search(r"\d", rest) else f"{who.strip()} says {rest[0].lower() + rest[1:]}."
    return "I have a short briefing on the board from the pages I opened."


def _scene(
    topic: str,
    speak: str,
    briefing: str,
    points: list[Any],
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    pages: list[str] = []
    seen = set()
    for hit in hits:
        who = outlet_name(hit.get("url") or hit.get("site") or "")
        url = (hit.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        pages.append(f"{who}\n{url}")
    widgets: list[dict[str, Any]] = [
        {"type": "quote", "text": speak, "cite": "Jarvis"},
        {"type": "markdown", "title": "What I gathered", "text": briefing or speak},
    ]
    if pages:
        widgets.append({"type": "markdown", "title": "Pages", "text": "\n\n".join(pages)})
    return {
        "title": _title(topic),
        "subtitle": None,
        "widgets": widgets,
    }


def _title(topic: str) -> str:
    text = re.sub(r"\s+", " ", (topic or "").strip())
    if not text:
        return "Research"
    return text[:1].upper() + text[1:]


MAIL_TOOLS = frozenset({
    "search_emails",
    "read_email",
    "draft_email",
    "send_email",
    "forward_email",
    "save_mail_attachments",
    "reply_with_attachments",
})


def _mail_notes(tool_name: str, result: dict[str, Any]) -> str:
    data = result.get("data")
    lines: list[str] = []
    if tool_name == "search_emails" and isinstance(data, list):
        for row in data[:6]:
            sender = (row.get("sender") or "").split("<")[0].strip()
            lines.append(
                f"{sender}|{row.get('subject') or ''}|{str(row.get('created_at') or '')[:16]}|unread={row.get('unread')}"
            )
        return "\n".join(lines)
    if tool_name == "read_email" and isinstance(data, dict):
        sender = (data.get("sender") or "").split("<")[0].strip()
        lines.append(f"from={sender}")
        lines.append(f"subject={data.get('subject') or ''}")
        lines.append(f"when={str(data.get('created_at') or '')[:16]}")
        body = reply_only(data.get("body") or "")
        if body:
            lines.append(f"body={body[:2400]}")
        for item in data.get("attachments") or []:
            lines.append(
                f"attachment={item.get('filename')}|mime={item.get('mime')}|readable={item.get('readable')}|cad={item.get('cad')}"
            )
        for note in data.get("vision_notes") or []:
            lines.append(f"vision={note}")
        return "\n".join(lines)
    if tool_name in {"draft_email", "send_email", "forward_email"}:
        pending = result.get("pending") if isinstance(result.get("pending"), dict) else {}
        payload = pending.get("payload") or {}
        lines.append(f"to={payload.get('to') or ''}")
        lines.append(f"subject={payload.get('subject') or ''}")
        if payload.get("body"):
            lines.append(f"draft={str(payload.get('body'))[:1200]}")
        return "\n".join(lines)
    return ""


def _vision_notes(prefs: dict[str, Any], mail: dict[str, Any]) -> list[str]:
    from . import gemini_client
    from .connectors import gmail as gmail_conn

    gmail_id = mail.get("gmail_id") or ""
    if not gmail_id or not gmail_conn.live():
        return []
    notes: list[str] = []
    vision_items = [item for item in (mail.get("attachments") or []) if item.get("vision")][:2]
    for item in vision_items:
        att_id = item.get("attachment_id") or ""
        if not att_id:
            continue
        try:
            blob = gmail_conn.download_attachment(gmail_id, att_id)
        except Exception:
            continue
        if len(blob) > 8 * 1024 * 1024:
            continue
        mime = item.get("mime") or "application/octet-stream"
        name = item.get("filename") or "attachment"
        b64 = base64.b64encode(blob).decode("ascii")
        prompt = (
            f"Describe what is visible in this drawing or document ({name}). "
            "Include dimensions or numbers only if they are clearly readable. "
            'Reply JSON only: {"summary": "two sentences max"}'
        )
        try:
            message = gemini_client.generate_parts(
                [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ],
                system="You describe engineering drawings and PDFs factually. Do not invent dimensions.",
                format_json=True,
                timeout=120,
                options={"temperature": 0.2, "num_predict": 400},
            )
            parsed = _parse_model_json(message.get("content") or "")
            summary = str(parsed.get("summary") or "").strip()
            if summary:
                notes.append(f"{name}: {summary}")
                continue
        except OllamaError:
            pass
        extracted = _pdf_text_note(name, mime, blob)
        if extracted:
            notes.append(extracted)
    return notes


def _pdf_text_note(name: str, mime: str, blob: bytes) -> str:
    if mime != "application/pdf" and not name.lower().endswith(".pdf"):
        return ""
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(blob))
        pages = []
        for page in reader.pages[:2]:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)
        if not pages:
            return f"{name}: PDF attached; no readable text and vision could not open it."
        return f"{name}: {' '.join(pages)[:800]}"
    except Exception:
        return f"{name}: PDF attached; I could not read the drawing."


def _search_speak(data: list[dict[str, Any]]) -> str:
    if not data:
        return "Nothing in the inbox right now."
    if len(data) == 1:
        return speak_mail(data[0])
    bits: list[str] = []
    for row in data[:3]:
        name = first_name(row.get("sender") or "")
        subject = re.sub(r"\s+", " ", (row.get("subject") or "").strip())
        if name and subject:
            bits.append(f"{name} on {subject[:56]}")
        elif name:
            bits.append(name)
        elif subject:
            bits.append(subject[:56])
    if not bits:
        return f"{len(data)} messages are on the board."
    if len(bits) == 1:
        return f"{bits[0]} is on the board."
    if len(bits) == 2:
        return f"{bits[0]}, and {bits[1]}."
    return f"{bits[0]}; {bits[1]}; {bits[2]}."


def _read_speak(mail: dict[str, Any], vision_notes: list[str]) -> str:
    base = speak_mail(mail)
    cad = [item.get("filename") for item in (mail.get("attachments") or []) if item.get("cad")]
    if cad:
        names = ", ".join(str(name) for name in cad[:2])
        base = f"{base} Attached {names} — I cannot read CAD here."
    if vision_notes:
        base = f"{base} The drawing is on the board."
    return base


def _mail_scene(
    tool_name: str,
    data: Any,
    speak: str,
    briefing: str,
    extra_widgets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    widgets: list[dict[str, Any]] = [{"type": "quote", "text": speak, "cite": "Jarvis"}]
    if briefing:
        widgets.append({"type": "markdown", "title": "Mail", "text": briefing})
    if extra_widgets:
        widgets.extend(extra_widgets)
    if tool_name == "search_emails" and isinstance(data, list) and data:
        widgets.append(
            {
                "type": "table",
                "title": "Messages",
                "columns": ["From", "Subject", "When"],
                "rows": [
                    [
                        (row.get("sender") or "").split("<")[0].strip(),
                        row.get("subject") or "",
                        str(row.get("created_at") or "")[:16],
                    ]
                    for row in data[:8]
                ],
            }
        )
    if tool_name == "read_email" and isinstance(data, dict):
        from .tables import widgets_from_body

        name = first_name(data.get("sender") or "") or "Mail"
        widgets = [
            {"type": "kpi", "label": "From", "value": name},
            *widgets_from_body(data.get("body") or "", data.get("subject") or ""),
        ]
        attachments = data.get("attachments") or []
        if attachments:
            from .mail_attachments import attachment_widget

            widgets.append(attachment_widget(data.get("id") or "", attachments))
        for note in data.get("vision_notes") or []:
            widgets.append({"type": "markdown", "title": "Drawing", "text": note})
    if tool_name == "draft_email":
        pending = data if isinstance(data, dict) else {}
        subject = pending.get("subject") or "Draft"
        body = pending.get("body") or ""
        widgets = [
            {"type": "kpi", "label": "To", "value": first_name(pending.get("to") or "") or pending.get("to") or ""},
            {"type": "markdown", "title": "Draft", "text": f"**{subject}**\n\n{body}"},
            {"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"},
        ]
    if tool_name == "forward_email":
        pending = data if isinstance(data, dict) else {}
        widgets = [
            {"type": "kpi", "label": "To", "value": pending.get("to") or ""},
            {"type": "markdown", "title": "Forward", "text": pending.get("note") or pending.get("body") or ""},
            {"type": "quote", "text": "Confirm in the bar below to send.", "cite": "Jarvis"},
        ]
    title = "Inbox"
    subtitle = None
    if tool_name == "read_email" and isinstance(data, dict):
        title = first_name(data.get("sender") or "") or "Mail"
        subtitle = data.get("subject")
    elif tool_name == "draft_email" and isinstance(data, dict):
        title = "Draft ready"
        subtitle = data.get("subject")
    elif tool_name == "forward_email":
        title = "Forward ready"
    return {"title": title, "subtitle": subtitle, "widgets": widgets}


def refine_mail(prefs: dict[str, Any], asked: str, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    notes = _mail_notes(tool_name, result)
    if tool_name == "read_email" and isinstance(data, dict) and not data.get("empty"):
        vision = _vision_notes(prefs, data)
        if vision:
            data = {**data, "vision_notes": vision}
            result["data"] = data
            notes = _mail_notes(tool_name, result)
    model = _ask_mail_model(prefs, asked, tool_name, notes) if notes else {}
    speak = _clean_voice(str(model.get("speak") or ""))
    briefing = str(model.get("briefing") or "").strip()

    if tool_name == "search_emails" and isinstance(data, list):
        fallback = _search_speak(data)
        if not speak or not _grounded(speak, notes):
            speak = fallback
        briefing = briefing or "\n".join(
            f"{(row.get('sender') or '').split('<')[0].strip()} — {row.get('subject') or ''}"
            for row in data[:4]
        )
    elif tool_name == "read_email" and isinstance(data, dict) and data.get("body"):
        fallback = _read_speak(data, data.get("vision_notes") or [])
        if not speak or not _grounded(speak, notes):
            speak = fallback
        briefing = briefing or reply_only(data.get("body") or "")[:1800]
    elif tool_name in {"draft_email", "forward_email"}:
        pending = result.get("pending") if isinstance(result.get("pending"), dict) else {}
        payload = pending.get("payload") or {}
        if tool_name == "draft_email":
            speak = speak_draft(payload.get("to") or "", data if isinstance(data, dict) else None)
        else:
            name = first_name(payload.get("to") or "") or "them"
            speak = f"Forward to {name} is ready — shall I send it?"
        briefing = briefing or str(payload.get("body") or payload.get("note") or "")[:1200]
    elif tool_name == "save_mail_attachments":
        speak = str(result.get("speak") or "Saved.")
        briefing = briefing or speak
    elif tool_name == "reply_with_attachments":
        speak = str(result.get("speak") or speak_draft("", data if isinstance(data, dict) else None))
        briefing = briefing or speak

    if not speak:
        speak = "Mail is on the board."
    result["speak"] = speak
    pending_payload = (result.get("pending") or {}).get("payload") if isinstance(result.get("pending"), dict) else {}
    scene_data = data
    if tool_name in {"draft_email", "forward_email", "send_email", "reply_with_attachments"}:
        scene_data = pending_payload or data
    if tool_name in {"save_mail_attachments", "reply_with_attachments"} and result.get("scene"):
        pass
    elif tool_name == "read_email" and isinstance(data, dict) and data.get("attachments"):
        from .mail_attachments import build_mail_scene

        result["scene"] = build_mail_scene(data, data.get("attachments") or [])
        result["attachments"] = data.get("attachments")
        result["mail_id"] = data.get("id")
    else:
        result["scene"] = _mail_scene(tool_name, scene_data if tool_name != "search_emails" else data, speak, briefing)
    if tool_name == "save_mail_attachments" and result.get("attachments") is None:
        result["attachments"] = (result.get("data") or {}).get("attachments")
    if tool_name == "reply_with_attachments" and result.get("attachments") is None:
        result["attachments"] = result.get("attachments")
    return result


def _ask_mail_model(prefs: dict[str, Any], asked: str, tool_name: str, notes: str) -> dict[str, Any]:
    name = prefs.get("assistant_name") or "Jarvis"
    who = prefs.get("display_name") or "Sir"
    persona = prefs.get("persona") or "Calm, precise, slightly dry British aide."
    sign_off = prefs.get("sign_off") or ""
    prompt = f"""{who} asked: {asked}

Mail tool: {tool_name}
Facts from Gmail (use only these; do not invent senders, addresses, amounts, or drawing dimensions):
{notes}

Every number must already appear in those facts. For drafts, write a short professional reply from the letter only.
Sign-off if drafting: {sign_off or 'none'}

Reply as {name}. JSON only:
{{
  "speak": "one or two spoken sentences. No invented facts.",
  "briefing": "short board text grounded in the facts"
}}
Persona: {persona}
Do not mention tools, JSON, or that you are a model."""
    try:
        message = ollama_chat(
            [
                {"role": "system", "content": f"You are {name}, a present aide for mail. Ground every claim in the facts."},
                {"role": "user", "content": prompt},
            ],
            format_json=True,
            timeout=180,
            options={"temperature": 0.35, "num_predict": 900},
        )
    except OllamaError:
        return {}
    return _parse_model_json(message.get("content") or "")

