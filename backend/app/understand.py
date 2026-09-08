from __future__ import annotations

import difflib
import re
from typing import Any
from zoneinfo import ZoneInfo

from .compose import calendar_event_spec, document_spec, spreadsheet_spec, wants_calendar_create
from .config import settings
from .intent import wants_briefing, wants_mail, wants_research

WORK_WORDS = (
    "spreadsheet",
    "excel",
    "xlsx",
    "calendar",
    "schedule",
    "agenda",
    "email",
    "inbox",
    "draft",
    "reply",
    "document",
    "docx",
    "research",
    "briefing",
    "brief",
)

PHRASE_ALIASES = (
    ("thread sheet", "spreadsheet"),
    ("spread sheet", "spreadsheet"),
    ("speed sheet", "spreadsheet"),
    ("spread seat", "spreadsheet"),
    ("one pager", "one-pager"),
    ("e mail", "email"),
    ("g mail", "gmail"),
    ("in box", "inbox"),
    ("meetin notes", "meeting notes"),
    ("work book", "workbook"),
    ("calender", "calendar"),
)

TOKEN_ALIASES = {
    "threadsheet": "spreadsheet",
    "thredsheet": "spreadsheet",
    "speadsheet": "spreadsheet",
    "spreedsheet": "spreadsheet",
    "spreadshit": "spreadsheet",
    "spreadseat": "spreadsheet",
    "excell": "excel",
    "calender": "calendar",
    "calandar": "calendar",
    "scheduel": "schedule",
    "docxument": "document",
    "gemeni": "gemini",
    "jemeni": "gemini",
}

_SHEETISH = re.compile(r"(sheet|spread|excel|xlsx|calen|sched|inbox|docu)", re.I)
_CLAUSE_SPLIT = re.compile(r"\b(?:and|then|also|plus|as well as)\b", re.I)
_INTENT = re.compile(
    r"\b(make|create|write|build|prepare|draft|send|add|put|do|get|show|open|export|research|look|reply)\b",
    re.I,
)
_VAGUE = re.compile(r"\b(the thing|that thing|the other one|you know|whatever|something)\b", re.I)
_SKIP_CLAUSE = re.compile(
    r"\b(how are you|hello|hi|thanks|thank you|good morning|good evening|good night)\b",
    re.I,
)

FAMILY_WORDS: dict[str, tuple[str, ...]] = {
    "gemini": ("gemini", "ask gemini", "task for gemini"),
    "drive": ("drive", "google drive"),
    "mail": ("draft", "reply", "email", "e-mail", "mail", "inbox"),
    "sheet": ("spreadsheet", "excel", "xlsx"),
    "calendar": ("calendar", "schedule", "agenda"),
    "doc": ("document", "docx", "one-pager", "meeting notes"),
    "research": ("research", "look up", "search the web", "search for", "search the", "google this"),
    "brief": ("brief me", "briefing", "what's on", "whats on", "standup", "catch me up"),
    "file": ("dropped", "this file", "review the dropped"),
}

FAMILY_TOOLS: dict[str, tuple[str, ...]] = {
    "mail": ("draft_email", "send_email", "search_emails", "read_email", "forward_email", "save_mail_attachments", "reply_with_attachments"),
    "sheet": ("create_spreadsheet", "show_artifact"),
    "calendar": ("list_calendar", "create_calendar_event"),
    "doc": ("create_document", "create_pdf"),
    "research": ("research",),
    "brief": ("get_briefing",),
    "file": ("review_inbox",),
    "drive": ("drive_upload", "drive_find"),
    "gemini": ("task_for_gemini",),
}


def _close_work_word(token: str) -> str | None:
    lowered = token.lower()
    if lowered in WORK_WORDS:
        return None
    if not _SHEETISH.search(lowered) and len(lowered) < 8:
        return None
    matches = difflib.get_close_matches(lowered, WORK_WORDS, n=1, cutoff=0.74)
    return matches[0] if matches else None


def normalize_speech(message: str) -> tuple[str, list[tuple[str, str]]]:
    text = (message or "").strip().replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    repairs: list[tuple[str, str]] = []
    lowered = f" {text.lower()} "
    for src, dest in PHRASE_ALIASES:
        if src in lowered:
            text = re.sub(re.escape(src), dest, text, flags=re.I)
            repairs.append((src, dest))
            lowered = f" {text.lower()} "
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    for token in tokens:
        key = token.lower()
        replacement = TOKEN_ALIASES.get(key) or _close_work_word(key)
        if replacement and replacement != key:
            text = re.sub(rf"\b{re.escape(token)}\b", replacement, text, count=1)
            repairs.append((token, replacement))
    return re.sub(r"\s+", " ", text).strip(), repairs


def _clauses(message: str) -> list[str]:
    parts = [re.sub(r"\s+", " ", part).strip(" ,.") for part in _CLAUSE_SPLIT.split(message or "")]
    return [part for part in parts if part]


def _clause_family(clause: str) -> str | None:
    text = clause.lower()
    for family, words in FAMILY_WORDS.items():
        if any(word in text for word in words):
            return family
    return None


def _guess_from_clause(clause: str) -> dict[str, Any] | None:
    text = clause.lower()
    family = _clause_family(clause)
    if family == "calendar":
        if wants_calendar_create(clause):
            try:
                tz = ZoneInfo(settings.tz or "Asia/Kolkata")
            except Exception:
                tz = ZoneInfo("Asia/Kolkata")
            spec = calendar_event_spec(clause, tz)
            if spec:
                return {"tool": "create_calendar_event", "arguments": spec, "label": "calendar event"}
        return {"tool": "list_calendar", "arguments": {"days": 2}, "label": "calendar"}
    if family == "sheet" or (
        family not in {"calendar", "doc", "mail", "brief", "gemini", "drive"}
        and re.search(r"\b(make|create|new|write|build|prepare)\b", text)
        and ("pricing" in text or re.search(r"(spread\s*sheet|excel|xlsx|\bsheet\b)", text))
    ):
        args = spreadsheet_spec(clause)
        return {"tool": "create_spreadsheet", "arguments": args, "label": f"{args['title'].lower()} spreadsheet"}
    if family == "doc":
        return {
            "tool": "create_document",
            "arguments": document_spec(clause),
            "label": "Word document",
        }
    if family == "brief":
        return {"tool": "get_briefing", "arguments": {}, "label": "briefing"}
    return None


def unmatched_clauses(original: str, normalized: str, used_tools: list[str]) -> list[dict[str, Any]]:
    covered = set()
    for family, tools in FAMILY_TOOLS.items():
        if any(tool in used_tools for tool in tools):
            covered.add(family)
    gemini = "gemini" in f"{original} {normalized}".lower()
    unclear: list[dict[str, Any]] = []
    for raw, clean in zip(_clauses(original), _clauses(normalized) or _clauses(original)):
        if _SKIP_CLAUSE.search(raw) and not _INTENT.search(raw):
            continue
        family = _clause_family(clean)
        if family and family in covered:
            continue
        if gemini and family in {"sheet", "file"}:
            continue
        looks_like_work = bool(_INTENT.search(raw) or _VAGUE.search(raw) or family or _SHEETISH.search(raw))
        if not looks_like_work:
            continue
        if gemini and not family and _SHEETISH.search(clean):
            continue
        if family and family not in covered:
            guess = _guess_from_clause(clean)
            if family == "mail" and not guess:
                continue
            unclear.append({"heard": raw, "guess": guess})
            continue
        if _INTENT.search(raw) or _VAGUE.search(raw) or _SHEETISH.search(raw):
            unclear.append({"heard": raw, "guess": _guess_from_clause(clean)})
    return unclear


def clarification_thought(item: dict[str, Any]) -> dict[str, Any]:
    heard = item.get("heard") or "that last part"
    guess = item.get("guess")
    if guess:
        speak = f"Did you want a {guess['label']}?"
        title = "Confirm"
    else:
        speak = f"I didn't catch \"{heard}\". Mail, calendar, a file, or Gemini?"
        title = "Say that again"
    scene = {
        "title": title,
        "subtitle": heard,
        "widgets": [
            {"type": "quote", "text": speak, "cite": "Jarvis"},
        ],
    }
    return {"speak": speak, "scene": scene, "pending_id": None, "artifact_id": None, "guess": guess, "heard": heard}
