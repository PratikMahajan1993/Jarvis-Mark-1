from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Hermes-first routing (Aspect 7)
# When Hermes is available, `run_agent` owns judgment for almost everything.
# Jarvis keeps ONLY:
#   - tight mail_draft compose chrome (modal UX)
#   - pending Authorize / drawing-session exceptions (in agent.py)
#   - this tiny safety deny surface (phrases that must never auto-execute)
# Legacy RULES below remain for Gemini/legacy fallback when Hermes is down.
# ---------------------------------------------------------------------------

SAFETY_DENY_PHRASES = (
    "send without approval",
    "skip authorize",
    "bypass hitl",
    "auto send all mail",
    "delete all memory",
    "wipe all memory",
)


@dataclass(frozen=True)
class Intent:
    kind: str
    query: str = ""
    person: str = ""
    unread_only: bool = False
    last: bool = False


@dataclass(frozen=True)
class Route:
    kind: str
    tools: tuple[str, ...] = ()
    job: str = ""
    pref: str = ""
    complete: str = ""


_SKIP_NAME = {
    "what", "whats", "did", "mail", "email", "from", "said", "reply", "replied",
    "the", "a", "an", "to", "in", "is", "show", "read", "please", "jarvis", "draft",
    "open", "spreadsheet", "sheet", "and", "make", "same", "this", "that",
    "last", "latest", "newest", "morning", "afternoon", "tonight", "today", "yesterday",
    "note", "message", "wrote", "say", "about", "your", "our", "them", "they",
    "him", "her", "his", "hers", "she", "he", "we", "you", "inbox", "unread",
    "pricing", "calendar", "gemini", "briefing", "document", "file", "me", "my",
}

_NAME = re.compile(
    r"\b(?:from|by)\s+([A-Za-z][A-Za-z'-]+)"
    r"|\bwhat did\s+([A-Za-z][A-Za-z'-]+)"
    r"|\breply to\s+([A-Za-z][A-Za-z'-]+)"
    r"|\b(?:read|show|open)\s+([A-Za-z][A-Za-z'-]+)"
    r"|\b([A-Za-z][A-Za-z'-]+)'s\s+(?:mail|email|note|message|quote|quotation|enquiry|inquiry)"
    r"|\b([A-Za-z][A-Za-z'-]+)\s+(?:said|wrote|replied|sent|mailed)"
    r"|\b(?:quote|quotation|enquiry|inquiry|mail|email)\s+from\s+([A-Za-z][A-Za-z'-]+)",
    re.I,
)

_GEMINI = (
    "ask gemini",
    "tell gemini",
    "task for gemini",
    "send to gemini",
    "send this to gemini",
    "send it to gemini",
    "forward to gemini",
    "get gemini",
    "have gemini",
    "gemini to",
    "gemini this",
    "run this by gemini",
    "throw this at gemini",
    "analyze this",
)
_BRIEF = (
    "brief me",
    "briefing",
    "standup",
    "catch me up",
    "morning brief",
    "evening brief",
    "what's my day",
    "whats my day",
)
# Tight mail compose / reply: must START with these phrases (after prepare()).
_COMPOSE_START = re.compile(
    r"^(?:"
    r"draft\s+an?\s+(?:e-?mails?|mails?)|draft\s+(?:e-?mails?|mails?)|"
    r"send\s+an?\s+(?:e-?mails?|mails?)|send\s+(?:e-?mails?|mails?)|"
    r"compose\s+an?\s+(?:e-?mails?|mails?)|compose\s+a\s+mails?|"
    r"write\s+an?\s+(?:e-?mails?|mails?)"
    r")\b[\s,]*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_FORWARD = re.compile(r"\bforward\b", re.IGNORECASE)
_SAVE = re.compile(
    r"\b(save|download)\b.*\b(pdf|drawing|drawings|attachment|attachments|file|files|dpis|rfnw)\b"
    r"|\b(save|download)\b.*\b(?:DPIS[0-9A-Z_-]+|RFNW[-_]?[0-9]+)\b",
    re.I,
)
_REPLY_ATTACH = re.compile(r"\b(attach|with)\b.*\b(reply|draft)\b|\breply\b.*\b(with|attach)\b", re.IGNORECASE)
_READ = re.compile(
    r"\b(open|read|show|summarise|summarize|what's in|whats in|what is in|what did)\b"
    r".*\b(mail|email|e-mail|gmail|message|note|letter|enquiry|inquiry|said|say|wrote)\b"
    r"|\b(mail|email|e-mail|note|message|letter)\s+(from|by)\b"
    r"|\b(last|latest|newest|most recent)\s+(email|mail|message|note)\b"
    r"|\b(the|that)\s+(email|mail|message)\b",
    re.I,
)
_SEARCH = re.compile(
    r"\b(inbox|unread|check (?:my )?mail|any mail|new mail|what's in (?:my )?inbox)\b"
    r"|\bsearch\b.+\b(mail|email|emails|e-mail|gmail|inbox)\b"
    r"|\bcheck\b.+\b(mail|email|emails|inbox|gmail)\b",
    re.I,
)
_NEGATE = re.compile(r"\b(don't|dont|do not|never)\b", re.IGNORECASE)
_LAST = re.compile(r"\b(last|latest|newest|most recent)\b", re.IGNORECASE)
_CAL_CREATE = re.compile(
    r"\b(add|put|book|create|make|set|block|hold|reserve|fix)\b.+\b"
    r"(calendar|event|meeting|call|lunch|dinner|sync|appointment|slot)\b"
    r"|\bschedule (a|an|me)\b"
    r"|\b(meeting|call)\s+with\b",
    re.I,
)
_CAL_LIST = re.compile(
    r"\b(calendar|schedule|agenda)\b"
    r"|\b(next|upcoming)\s+(meeting|call|event|appointment)\b"
    r"|\b(any|my)\s+meetings?\b"
    r"|\bmeetings?\s+(today|tomorrow)\b"
    r"|\bwhat(?:'s|s| is)\s+tomorrow\b"
    r"|\bwhat do i have\s+tomorrow\b"
    r"|\bwhen is (?:my )?next (meeting|call|event|appointment)\b",
    re.I,
)
_RESEARCH = (
    "research",
    "look up",
    "look this up",
    "look into",
    "search the web",
    "search for",
    "google this",
    "find out about",
    "find online",
)

ROUTES: dict[str, Route] = {
    "chat": Route("chat"),
    "briefing": Route(
        "briefing",
        tools=("get_briefing",),
        job="Call get_briefing only.",
        complete="get_briefing",
    ),
    "mail_read": Route(
        "mail_read",
        tools=("read_email",),
        job="Call read_email only. Do not draft, send, or forward.",
        pref="email_enabled",
        complete="read_email",
    ),
    "mail_search": Route(
        "mail_search",
        tools=("search_emails",),
        job="Call search_emails only. Do not draft or send.",
        pref="email_enabled",
        complete="search_emails",
    ),
    "mail_draft": Route(
        "mail_draft",
        tools=(),
        job="Open the compose modal with LLM-filled to/subject/body. Never claim it was sent.",
        pref="email_enabled",
        complete="",
    ),
    "mail_forward": Route(
        "mail_forward",
        tools=("read_email", "forward_email"),
        job="Read the message if needed, then forward_email. Never send.",
        pref="email_enabled",
        complete="forward_email",
    ),
    "mail_save": Route(
        "mail_save",
        tools=("save_mail_attachments",),
        job="Call save_mail_attachments only.",
        pref="email_enabled",
        complete="save_mail_attachments",
    ),
    "mail_reply_attach": Route(
        "mail_reply_attach",
        tools=("reply_with_attachments",),
        job="Call reply_with_attachments only. Never send.",
        pref="email_enabled",
        complete="reply_with_attachments",
    ),
    "research": Route(
        "research",
        tools=("research",),
        job="Call research only. Do not answer prices or news from memory.",
        pref="research_enabled",
        complete="research",
    ),
    "calendar_list": Route(
        "calendar_list",
        tools=("list_calendar",),
        job="Call list_calendar only.",
        pref="calendar_enabled",
        complete="list_calendar",
    ),
    "calendar_create": Route(
        "calendar_create",
        tools=("create_calendar_event",),
        job="Call create_calendar_event only. Do not claim it is saved.",
        pref="calendar_enabled",
        complete="create_calendar_event",
    ),
    "drive_upload": Route(
        "drive_upload",
        tools=("drive_upload",),
        job="Call drive_upload only.",
        pref="files_enabled",
        complete="drive_upload",
    ),
    "drive_find": Route(
        "drive_find",
        tools=("drive_find",),
        job="Call drive_find only.",
        pref="files_enabled",
        complete="drive_find",
    ),
    "sheet_open": Route(
        "sheet_open",
        tools=("show_artifact",),
        job="Call show_artifact only. Do not create a new spreadsheet.",
        pref="files_enabled",
        complete="show_artifact",
    ),
    "sheet_create": Route(
        "sheet_create",
        tools=("create_spreadsheet",),
        job="Call create_spreadsheet only.",
        pref="files_enabled",
        complete="create_spreadsheet",
    ),
    "doc_create": Route(
        "doc_create",
        tools=("create_document",),
        job="Call create_document only.",
        pref="files_enabled",
        complete="create_document",
    ),
    "file_review": Route(
        "file_review",
        tools=("review_inbox",),
        job="Call review_inbox only.",
        pref="files_enabled",
        complete="review_inbox",
    ),
    "gemini": Route(
        "gemini",
        tools=("task_for_gemini",),
        job="Call task_for_gemini only. Never send without confirmation.",
        pref="email_enabled",
        complete="task_for_gemini",
    ),
    "rfq_reason": Route(
        "rfq_reason",
        tools=("reason_rfq",),
        job="Call reason_rfq only. Do not suggest CNC or send mail.",
        complete="reason_rfq",
    ),
    "cnc_suggest": Route(
        "cnc_suggest",
        tools=("cnc_suggest",),
        job="Call cnc_suggest only. Draft a program; never send it to a machine.",
        complete="cnc_suggest",
    ),
    "shop_bind": Route(
        "shop_bind",
        tools=("bind_shop_sheet",),
        job="Call bind_shop_sheet only.",
        complete="bind_shop_sheet",
    ),
    "shop_create": Route(
        "shop_create",
        tools=("ensure_shop_sheet",),
        job="Call ensure_shop_sheet only.",
        complete="ensure_shop_sheet",
    ),
    "shop_read": Route(
        "shop_read",
        tools=("read_shop_sheet",),
        job="Call read_shop_sheet only. Do not write numbers.",
        complete="read_shop_sheet",
    ),
    "shop_write": Route(
        "shop_write",
        tools=("update_shop_sheet",),
        job="Call update_shop_sheet only. Never claim the sheet was saved.",
        complete="update_shop_sheet",
    ),
}


def route_for(kind: str) -> Route:
    return ROUTES.get(kind) or ROUTES["chat"]


def allowed_tools(kind: str) -> tuple[str, ...]:
    return route_for(kind).tools


def allowed_mail_tools(kind: str) -> tuple[str, ...]:
    return allowed_tools(kind)


def planned_tools(message: str) -> tuple[str, ...]:
    return allowed_tools(classify(message).kind)


def prepare(message: str) -> str:
    text = (message or "").replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:hey\s+|ok\s+|okay\s+)?jarvis[,.]?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,.]?\s+jarvis[.!?]*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(please|pls|plz|can you|could you|would you)\s+", "", text, flags=re.IGNORECASE)
    return text


def person_in(message: str) -> str:
    for match in _NAME.finditer(message or ""):
        for group in match.groups():
            if not group:
                continue
            name = group
            if len(name) > 2 and name[-1] in "sS" and name[-2] in "'\u2019\u2018":
                name = name[:-2]
            if name.isupper() and len(name) > 1:
                name = name.capitalize()
            if name.lower() in _SKIP_NAME or len(name) < 3:
                continue
            return name
    return ""


def _rule_gemini(_text: str, low: str, _person: str) -> Intent | None:
    if any(phrase in low for phrase in _GEMINI):
        return Intent("gemini")
    if "gemini" in low and any(word in low for word in ("forward", "send", "ask", "task", "tell", "review")):
        return Intent("gemini")
    return None


def _rule_briefing(_text: str, low: str, _person: str) -> Intent | None:
    if any(phrase in low for phrase in _BRIEF):
        return Intent("briefing")
    if (
        ("what's on" in low or "whats on" in low or "what do i have" in low)
        and "mail" not in low
        and "email" not in low
        and not any(word in low for word in ("calendar", "schedule", "agenda"))
        and not re.search(r"\btomorrow\b|\bmeetings?\b|\bcalls?\b", low)
    ):
        return Intent("briefing")
    return None


def _rule_reply_attach(text: str, _low: str, person: str) -> Intent | None:
    if _REPLY_ATTACH.search(text):
        return Intent("mail_reply_attach", person=person, last=_LAST.search(text) is not None)
    return None


def _rule_save(text: str, low: str, person: str) -> Intent | None:
    if _SAVE.search(text) and any(word in low for word in ("pdf", "drawing", "attachment", "file", "dpis", "rfnw")):
        return Intent("mail_save", query=text, person=person, last=_LAST.search(low) is not None)
    return None


def _rule_forward(text: str, low: str, person: str) -> Intent | None:
    if _FORWARD.search(text) and "gemini" not in low:
        return Intent("mail_forward", person=person)
    return None


def _rule_cancel(text: str, _low: str, _person: str) -> Intent | None:
    if _NEGATE.search(text) and (match_mail_trigger(text) is not None or _FORWARD.search(text)):
        return Intent("chat")
    return None


def match_mail_trigger(message: str) -> dict[str, str | bool] | None:
    """Return compose/reply trigger match: mode, remainder, person, last — or None."""
    text = prepare(message)
    if not text:
        return None
    fixed = re.match(
        r"^(reply\s+to\s+that|reply\s+to\s+this|reply\s+to\s+the\s+last\s+(?:e-?mail|mails?)|"
        r"draft\s+a\s+reply|write\s+a\s+reply)\b[\s,]*(.*)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if fixed:
        starter = fixed.group(1).lower()
        return {
            "mode": "reply",
            "remainder": (fixed.group(2) or "").strip(),
            "person": "",
            "last": "last" in starter,
        }
    named = re.match(r"^reply\s+to\s+([A-Za-z][A-Za-z'-]+)\b[\s,]*(.*)$", text, re.IGNORECASE | re.DOTALL)
    if named:
        return {
            "mode": "reply",
            "remainder": (named.group(2) or "").strip(),
            "person": named.group(1).strip(),
            "last": False,
        }
    compose = _COMPOSE_START.match(text)
    if compose:
        return {
            "mode": "compose",
            "remainder": (compose.group(1) or "").strip(),
            "person": "",
            "last": False,
        }
    return None


_CNC = re.compile(
    r"\b(?:write|suggest|draft|make|generate)\b.{0,40}\b(?:cnc\s+)?(?:program|g-?code)\b"
    r"|\b(?:cnc|g-?code)\s+program\b"
    r"|\bfrom scratch\b.{0,40}\b(?:program|g-?code|cnc)\b"
    r"|\b(?:program|g-?code|cnc)\b.{0,40}\bfrom scratch\b"
    r"|\bsuggest g-?code\b",
    re.I,
)
_RFQ = re.compile(
    r"\brfq\b|request for quot"
    r"|treat this as (?:an?\s+)?rfq"
    r"|(?:\bquote\b|\bquotation\b).{0,48}\bdrawing\b"
    r"|\bdrawing\b.{0,48}(?:\bquote\b|\bquotation\b|\brfq\b)",
    re.I,
)
# Definitional / explanatory RFQ asks → chat (not reason_rfq / email_send).
# Keep "what's in this RFQ" as work; do not match "what's in …".
_RFQ_DEFINITION = re.compile(
    r"\bwhat(?:'s|s)?\s+(?:an?\s+)?rfq\b"
    r"|\bwhat\s+is\s+(?:an?\s+)?rfq\b"
    r"|\bwhat\s+are\s+rfqs?\b"
    r"|\b(?:explain|define|meaning of)\s+(?:an?\s+)?rfq\b"
    r"|\b(?:summar(?:y|ise|ize)|tell me)\b.{0,64}\b(?:what\s+)?(?:an?\s+)?rfq\s+is\b"
    r"|\b(?:an?\s+)?rfq\b.{0,32}\b(?:mean|means|stand(?:s)? for|definition)\b",
    re.I,
)


def is_rfq_definition(message: str) -> bool:
    """True when the user asks what an RFQ is, not to process one."""
    return bool(_RFQ_DEFINITION.search(prepare(message)))


def _rule_cnc(text: str, _low: str, _person: str) -> Intent | None:
    if _CNC.search(text):
        return Intent("cnc_suggest")
    return None


def _rule_rfq(text: str, _low: str, person: str) -> Intent | None:
    if is_rfq_definition(text):
        return None
    if _RFQ.search(text):
        return Intent("rfq_reason", person=person)
    return None


_SHOP_CREATE = re.compile(
    r"\b(?:create|make|new|start|ensure)\b.{0,48}\b(?:jarvis\s+)?shop\s+(?:log|sheet|book|spreadsheet)"
    r"|\b(?:create|make|new|start)\b.{0,32}\bproduction\s+(?:log|sheet|book)\b",
    re.I,
)
_SHOP_BIND = re.compile(
    r"\b(?:bind|use|connect|link)\b.{0,48}\b(?:shop|production|google\s+sheet|this\s+sheet)"
    r"|docs\.google\.com/spreadsheets/",
    re.I,
)
_SHOP_WRITE = re.compile(
    r"\b(?:set|put|write|update|change)\b.{0,48}\b(?:oee|efficiency|shop\s+(?:log|sheet)|production\s+sheet|cell\s+[A-Z]+\d+)"
    r"|\b(?:set|put|write|update)\b.{0,24}\b[A-Z]+\d+\b.{0,16}\b(?:to|=)"
    r"|\b(?:set|put|write|update)\s+.+\s+(?:in|into|at)\s+(?:cell\s+)?[A-Z]+\d+\b",
    re.I,
)
_SHOP_READ = re.compile(
    r"\b(?:oee|efficiency|shop log|shop sheet|production numbers|production sheet)\b"
    r"|\bwhat(?:'s|s| is)\s+(?:the\s+)?(?:shop|oee|efficiency)\b",
    re.I,
)


def _rule_shop(text: str, low: str, _person: str) -> Intent | None:
    if _SHOP_CREATE.search(text):
        return Intent("shop_create")
    if _SHOP_BIND.search(text):
        return Intent("shop_bind", query=text)
    if _SHOP_WRITE.search(text) or _SHOP_WRITE.search(low):
        return Intent("shop_write", query=text)
    if _SHOP_READ.search(text) or _SHOP_READ.search(low):
        return Intent("shop_read")
    return None


def _rule_draft(text: str, low: str, person: str) -> Intent | None:
    hit = match_mail_trigger(text)
    if not hit:
        return None
    reply_person = str(hit.get("person") or "") or person
    return Intent(
        "mail_draft",
        query=str(hit.get("remainder") or ""),
        person=reply_person,
        last=bool(hit.get("last")),
    )


def _rule_read(text: str, low: str, person: str) -> Intent | None:
    if _READ.search(text) or (
        person
        and any(word in low for word in ("mail", "email", "note", "message", "said", "say", "wrote", "write", "enquiry", "inquiry"))
    ):
        query = f"from:{person}" if person else ""
        return Intent("mail_read", query=query, person=person, last=_LAST.search(low) is not None)
    return None


def _rule_search(text: str, low: str, person: str) -> Intent | None:
    if _SEARCH.search(text):
        return Intent(
            "mail_search",
            unread_only="unread" in low,
            person=person,
            query=f"from:{person}" if person else "",
        )
    return None


def _rule_mail_loose(text: str, low: str, person: str) -> Intent | None:
    # Do not steal tight compose/reply phrasing that failed for other reasons
    if match_mail_trigger(text) is not None:
        return None
    if re.search(r"\b(mail|email|gmail)\b", low) and not person:
        # Bare "send this email" / vague "email them" stay chat unless a tight starter matched
        if re.search(r"\b(send this|maybe|them|someone)\b", low):
            return Intent("chat")
        if re.search(r"^(?:don'?t|do not)\b", low):
            return Intent("chat")
        return Intent("mail_search", unread_only="unread" in low)
    return None


def _rule_research(text: str, low: str, _person: str) -> Intent | None:
    if any(phrase in low for phrase in _RESEARCH) or (
        re.search(r"\bsearch\b", low) and not re.search(r"\b(mail|inbox|email|gmail|calendar|drive)\b", low)
    ) or re.search(r"\b(current|latest|today'?s)\b.+\b(price|prices|rate|rates)\b", low) or re.search(
        r"\b(price|prices|rate|rates)\s+(of|in|for)\b", low
    ) or re.search(r"\b(aluminium|aluminum|steel|hrc|crc|copper)\b.+\b(price|prices|rate|rates)\b", low) or re.search(
        r"\b(price|prices|rate|rates)\b.+\b(aluminium|aluminum|steel|hrc|crc|copper)\b", low
    ):
        return Intent("research", query=text)
    return None


def calendar_span(message: str) -> str:
    low = (message or "").lower()
    if re.search(r"\btomorrow\b", low):
        return "tomorrow"
    if re.search(r"\btoday\b|\bthis afternoon\b|\bthis evening\b|\btonight\b|\bthis morning\b", low):
        return "today"
    return ""


def _rule_calendar(text: str, low: str, _person: str) -> Intent | None:
    if _CAL_CREATE.search(text):
        return Intent("calendar_create")
    if _CAL_LIST.search(low):
        return Intent("calendar_list", query=calendar_span(low))
    return None


def _rule_drive(_text: str, low: str, _person: str) -> Intent | None:
    if any(
        phrase in low
        for phrase in ("upload to drive", "put it on drive", "save to drive", "save it on drive")
    ):
        return Intent("drive_upload")
    if "drive" in low:
        return Intent("drive_find", query=_text)
    return None


def _rule_sheet(_text: str, low: str, _person: str) -> Intent | None:
    if re.search(r"\b(open|show)\b.*\b(spread\s*sheet|spreadsheet|sheet|excel|xlsx|workbook)\b", low):
        return Intent("sheet_open")
    if re.search(r"\b(make|create|new|write|build|prepare)\b.*\b(spread\s*sheet|spreadsheet|sheet|excel|xlsx|workbook)\b", low):
        return Intent("sheet_create")
    return None


def _rule_file(_text: str, low: str, _person: str) -> Intent | None:
    if any(word in low for word in ("dropped", "this file", "review the dropped")):
        return Intent("file_review")
    return None


def _rule_refresh(_text: str, low: str, person: str) -> Intent | None:
    if not re.search(
        r"\b(anything new|what's new|whats new|any new(?: mail| emails?)?|refresh|check again|update me)\b",
        low,
    ):
        return None
    if any(word in low for word in ("calendar", "schedule", "agenda")):
        return Intent("calendar_list")
    if any(word in low for word in ("brief", "day", "standup")):
        return Intent("briefing")
    return Intent("mail_search", unread_only="unread" in low, person=person, query=f"from:{person}" if person else "")


def _rule_doc(_text: str, low: str, _person: str) -> Intent | None:
    if any(word in low for word in ("word document", "docx", "one-pager", "meeting notes")) or (
        "document" in low and "google" not in low and re.search(r"\b(make|create|write)\b", low)
    ):
        return Intent("doc_create")
    return None


# First match wins. Add a new capability by appending a rule and a ROUTES row.
RULES = (
    _rule_gemini,
    _rule_briefing,
    _rule_cnc,
    _rule_rfq,
    _rule_shop,
    _rule_refresh,
    _rule_reply_attach,
    _rule_save,
    _rule_forward,
    _rule_cancel,
    _rule_draft,
    _rule_search,
    _rule_read,
    _rule_mail_loose,
    _rule_research,
    _rule_calendar,
    _rule_drive,
    _rule_sheet,
    _rule_file,
    _rule_doc,
)


def classify(message: str) -> Intent:
    text = prepare(message)
    if not text:
        return Intent("chat")
    low = text.lower()
    # Tiny safety deny-list — never treat as a normal work intent
    if any(phrase in low for phrase in SAFETY_DENY_PHRASES):
        return Intent("chat", query=text)
    person = person_in(text)
    for rule in RULES:
        hit = rule(text, low, person)
        if hit:
            return hit
    return Intent("chat")


_WORK_HINTS = (
    "mail", "email", "e-mail", "gmail", "inbox", "unread", "calendar", "schedule",
    "agenda", "brief", "briefing", "research", "look up", "look this up", "drive",
    "spreadsheet", "excel", "xlsx", "gemini", "pdf", "drawing", "attachment",
    "enquiry", "inquiry", "quotation", "quote", "price", "prices", "meeting",
    "draft", "reply", "forward", "document", "docx", "workbook", "sheet",
    "rfq", "cnc", "g-code", "gcode", "program from scratch",
    "oee", "shop log", "shop sheet", "production sheet", "efficiency",
)


def looks_like_work(message: str) -> bool:
    if is_rfq_definition(message):
        return False
    low = prepare(message).lower()
    return any(hint in low for hint in _WORK_HINTS)


def intent_for_kind(kind: str, message: str) -> Intent:
    if kind not in ROUTES:
        kind = "chat"
    seeded = classify(message)
    if seeded.kind == kind:
        return seeded
    if kind == "chat":
        return Intent("chat")
    text = prepare(message)
    low = text.lower()
    person = person_in(text)
    last = _LAST.search(low) is not None
    unread = "unread" in low
    if kind == "mail_read":
        query = f"from:{person}" if person else ""
        return Intent("mail_read", query=query, person=person, last=last)
    if kind == "mail_search":
        query = f"from:{person}" if person else ""
        return Intent("mail_search", query=query, person=person, unread_only=unread)
    if kind == "research":
        return Intent("research", query=text)
    if kind == "calendar_list":
        return Intent("calendar_list", query=calendar_span(low))
    if kind.startswith("mail_"):
        return Intent(kind, query=text, person=person, last=last, unread_only=unread)
    return Intent(kind, query=text, person=person)


def wants_mail(message: str) -> bool:
    return classify(message).kind.startswith("mail_")


def wants_briefing(message: str) -> bool:
    return classify(message).kind == "briefing"


def wants_research(message: str) -> bool:
    return classify(message).kind == "research"


def is_work(message: str) -> bool:
    return classify(message).kind != "chat"


CASES: list[tuple[str, str]] = [
    ("brief me", "briefing"),
    ("catch me up", "briefing"),
    ("what's on", "briefing"),
    ("what do I have", "briefing"),
    ("morning brief", "briefing"),
    ("standup", "briefing"),
    ("open the last email", "mail_read"),
    ("open Neha's last email", "mail_read"),
    ("open the last mail", "mail_read"),
    ("open the latest email", "mail_read"),
    ("read the last email", "mail_read"),
    ("show the last email", "mail_read"),
    ("what's in that email", "mail_read"),
    ("open the mail from Neha", "mail_read"),
    ("open mail from Neha", "mail_read"),
    ("read Neha's email", "mail_read"),
    ("show Neha's mail", "mail_read"),
    ("what did Neha say", "mail_read"),
    ("what did Deepak write", "mail_read"),
    ("read Deepak's enquiry", "mail_read"),
    ("read the email from Deepak about RFNW-2600105", "mail_read"),
    ("read Deepak mail RFNW-2600105", "mail_read"),
    ("summarise Neha's email", "mail_read"),
    ("show me that message", "mail_read"),
    ("any unread mail", "mail_search"),
    ("check my mail", "mail_search"),
    ("check mail", "mail_search"),
    ("check mail from Neha", "mail_search"),
    ("any mail from Neha", "mail_search"),
    ("show Neha's unread mail", "mail_search"),
    ("show unread mail", "mail_search"),
    ("search my mail", "mail_search"),
    ("search emails from Deepak", "mail_search"),
    ("what's in my inbox", "mail_search"),
    ("new mail", "mail_search"),
    ("unread from Neha", "mail_search"),
    ("reply to that", "mail_draft"),
    ("reply to Neha", "mail_draft"),
    ("reply to the last email", "mail_draft"),
    ("reply to the last mail", "mail_draft"),
    ("draft a reply", "mail_draft"),
    ("write a reply", "mail_draft"),
    ("draft an email to ops@example.com", "mail_draft"),
    ("draft a mail saying hello", "mail_draft"),
    ("send an email to ops@example.com", "mail_draft"),
    ("compose an email to Pratik", "mail_draft"),
    ("write an email to Deepak", "mail_draft"),
    ("read the last email and reply", "mail_read"),
    ("open Neha's last email and reply", "mail_read"),
    ("write to Deepak", "chat"),
    ("write back to Neha", "chat"),
    ("send this email", "chat"),
    ("can you maybe email them", "chat"),
    ("don't reply", "chat"),
    ("do not send this email", "chat"),
    ("forward this to Pratik", "mail_forward"),
    ("forward that mail to Rahul", "mail_forward"),
    ("forward this to Gemini", "gemini"),
    ("forward it to gemini", "gemini"),
    ("send this to Gemini", "gemini"),
    ("save the piston PDF", "mail_save"),
    ("save DPIS000377", "mail_save"),
    ("download the drawing", "mail_save"),
    ("save it on Drive", "drive_upload"),
    ("save to Drive", "drive_upload"),
    ("attach the drawing to the reply", "mail_reply_attach"),
    ("reply with the PDF", "mail_reply_attach"),
    ("view the piston PDF", "chat"),
    ("open DPIS000377", "chat"),
    ("open the piston drawing", "chat"),
    ("what's on my calendar", "calendar_list"),
    ("what's on my schedule", "calendar_list"),
    ("show my schedule", "calendar_list"),
    ("show my agenda", "calendar_list"),
    ("when is my next meeting", "calendar_list"),
    ("any meetings today", "calendar_list"),
    ("what's tomorrow", "calendar_list"),
    ("what do I have tomorrow", "calendar_list"),
    ("anything new on the calendar", "calendar_list"),
    ("book a call with Rahul at 4pm", "calendar_create"),
    ("meeting with Rahul tomorrow", "calendar_create"),
    ("add lunch to my calendar", "calendar_create"),
    ("aluminium prices in India", "research"),
    ("look up HRC steel price", "research"),
    ("search the web for Paladon", "research"),
    ("search for Paladon", "research"),
    ("current aluminium price", "research"),
    ("google this", "research"),
    ("ask Gemini to review the drawing", "gemini"),
    ("task for Gemini", "gemini"),
    ("put it on Drive", "drive_upload"),
    ("find the pricing sheet on Drive", "drive_find"),
    ("make a spreadsheet of blockers", "sheet_create"),
    ("create an excel sheet", "sheet_create"),
    ("open the spreadsheet", "sheet_open"),
    ("open the excel workbook", "sheet_open"),
    ("write meeting notes", "doc_create"),
    ("create a word document", "doc_create"),
    ("review the dropped file", "file_review"),
    ("what's in this RFQ", "rfq_reason"),
    ("whats in this RFQ", "rfq_reason"),
    ("treat this as an RFQ from Deepak", "rfq_reason"),
    ("treat this as RFQ from Deepak", "rfq_reason"),
    ("quote on this drawing", "rfq_reason"),
    ("this drawing quotation", "rfq_reason"),
    ("what is an RFQ for a machine shop", "chat"),
    ("what is an RFQ for our shop", "chat"),
    ("In one short sentence, what is an RFQ for a machine shop?", "chat"),
    ("Summarize what an RFQ is for our shop", "chat"),
    ("explain RFQ", "chat"),
    ("what does RFQ mean", "chat"),
    ("write a program from scratch", "cnc_suggest"),
    ("write a program", "cnc_suggest"),
    ("suggest G-code for this", "cnc_suggest"),
    ("CNC program for this", "cnc_suggest"),
    ("suggest G-code", "cnc_suggest"),
    ("what's the OEE", "shop_read"),
    ("what's the shop OEE", "shop_read"),
    ("read the shop log", "shop_read"),
    ("bind this google sheet", "shop_bind"),
    ("use this as the shop log https://docs.google.com/spreadsheets/d/abc123XYZ_def-456/edit", "shop_bind"),
    ("create a shop log", "shop_create"),
    ("make a jarvis shop log", "shop_create"),
    ("set CNC-1 OEE to 92", "shop_write"),
    ("write 88 in B2", "shop_write"),
    ("update the shop sheet", "shop_write"),
    ("how are you", "chat"),
    ("thanks Jarvis", "chat"),
    ("who are you", "chat"),
    ("good evening", "chat"),
    ("hello", "chat"),
    ("yes", "chat"),
    ("no", "chat"),
    ("ok", "chat"),
    ("Jarvis, open Neha's last email", "mail_read"),
    ("please check my mail", "mail_search"),
    ("can you read Neha's email", "mail_read"),
    ("e mail from Neha", "mail_read"),
    ("anything new", "mail_search"),
    ("what's new", "mail_search"),
    ("any new mail", "mail_search"),
]
