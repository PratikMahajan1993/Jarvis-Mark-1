from __future__ import annotations

import json
import re
from typing import Any
from zoneinfo import ZoneInfo

from . import db
from .briefing import build_briefing
from .compose import calendar_event_spec, document_spec, gemini_steps, reply_draft, spreadsheet_spec
from .config import settings
from .connectors import email as email_conn
from .brain import OllamaError, chat as ollama_chat, health
from .schemas import Artifact, ChatResponse, MailAttachment, PendingAction, Scene, Widget
from .tools.registry import TOOL_SCHEMAS, _guess_file_title, execute_tool
from .familiarity import get_set, remember_person, resolve as resolve_refs, speak_sent, wants_familiarity
from .think import refine_research, refine_mail, refine_briefing, MAIL_TOOLS
from .intent import (
    ROUTES,
    Intent,
    calendar_span,
    classify,
    intent_for_kind,
    is_rfq_definition,
    looks_like_work,
    prepare,
    route_for,
)
from .snapshot import (
    calendar_ready,
    ready as snapshot_ready,
    refresh as refresh_snapshot,
    skips_model,
    uses_snapshot,
    wants_fresh,
)
from .understand import clarification_thought, normalize_speech, unmatched_clauses

_YES_SHORT = {
    "y", "yes", "yeah", "yep", "yup", "yea", "confirm", "send", "send it", "do it",
    "go ahead", "proceed", "affirmative", "yes please", "yes send it", "yeah do it",
    "yes do it", "go for it", "do that", "ship it", "do so", "that's a yes", "thats a yes",
    "authorize", "authorise", "authorize it", "authorise it", "authorize to send",
    "authorise to send", "send the email", "send the mail", "send email", "send mail",
}
_NO_SHORT = {
    "n", "no", "nope", "nah", "cancel", "stop", "dont", "don't", "do not", "never",
    "reject", "negative", "abort", "wait", "no thanks", "no thank you", "not now",
    "hold on", "leave it", "later", "not yet", "hold off", "dont send", "don't send",
    "do not send", "discard", "throw it away",
}

_YES_RE = re.compile(
    r"\b(authorize|authorise|send it|send the (?:e-?mail|mail)|go ahead|ship it|yes)\b",
    re.I,
)
_NO_RE = re.compile(
    r"\b(reject|cancel|don'?t send|do not send|discard|nope|nah|abort)\b|\bno\b",
    re.I,
)

_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+,[A-Za-z]{2,})\b"
)
_DRAFT_REVISE_RE = re.compile(
    r"\b(shorter|brief|concise|tighten|rewrite|trim|subject|body|edit|change|update)\b",
    re.I,
)


def _extract_email_address(message: str) -> str:
    """Pull a compose target out of free text; fix common speech/typo forms."""
    from .mail_compose import extract_email_address

    return extract_email_address(message)


def classify_decision(text: str) -> bool | None:
    cleaned = re.sub(r"[!.?,]", "", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None
    lowered = cleaned.lower().replace("'", "")
    words = lowered.split()
    no = {item.replace("'", "") for item in _NO_SHORT}
    yes = {item.replace("'", "") for item in _YES_SHORT}
    if lowered in no:
        return False
    if lowered in yes:
        return True
    # Long utterances are content (body dictation), not authorize/reject —
    # e.g. "please confirm copper prices" must not approve a draft.
    if len(words) > 6:
        return None
    # Prefer reject phrases before authorize/send (e.g. "don't send")
    if _NO_RE.search(cleaned) and not re.search(r"\b(yes|authorize|authorise)\b", cleaned, re.I):
        if re.search(r"\bdon'?t\b|\bdo not\b|\breject\b|\bcancel\b|\bdiscard\b|\bnope\b|\bnah\b", cleaned, re.I):
            return False
        if re.fullmatch(r"no", lowered):
            return False
    if _YES_RE.search(cleaned) and not re.search(r"\bdon'?t\b|\bdo not\b|\breject\b", cleaned, re.I):
        return True
    return None


def _attachment_models(rows: list[dict[str, Any]] | None) -> list[MailAttachment]:
    out: list[MailAttachment] = []
    for row in rows or []:
        try:
            out.append(MailAttachment.model_validate(row))
        except Exception:
            continue
    return out


def _chat_response(
    session_id: str,
    *,
    speak: str,
    reply: str = "",
    scene: Scene | None = None,
    artifacts: list[Artifact] | None = None,
    pending: list[PendingAction] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    mail_id: str | None = None,
    offline: bool = False,
    more: int = 0,
    watching: bool = False,
    critical: dict[str, Any] | None = None,
) -> ChatResponse:
    return ChatResponse(
        speak=speak,
        reply=reply or speak,
        scene=scene or Scene(title="", widgets=[]),
        artifacts=artifacts if artifacts is not None else _collect_artifacts(),
        pending=pending if pending is not None else _pending_models(session_id),
        attachments=_attachment_models(attachments),
        mail_id=mail_id,
        offline=offline,
        more=more,
        watching=watching,
        critical=critical,
    )


def _apply_tool(
    name: str,
    arguments: dict[str, Any],
    session_id: str,
    prefs: dict[str, Any],
    asked: str,
) -> dict[str, Any]:
    result = execute_tool(name, arguments, session_id)
    if name == "research":
        return refine_research(prefs, asked, result)
    if name == "get_briefing":
        return refine_briefing(prefs, asked, result)
    if name in MAIL_TOOLS:
        return refine_mail(prefs, asked, name, result)
    return result


def run_attachment_save(session_id: str, email_id: str, attachment_ids: list[str], filenames: list[str] | None = None) -> ChatResponse:
    prefs = db.get_preferences()
    result = _apply_tool(
        "save_mail_attachments",
        {"email_id": email_id, "attachment_ids": attachment_ids, "filenames": filenames or []},
        session_id,
        prefs,
        "",
    )
    thought = _thought_from_result(result, "save_mail_attachments")
    if thought:
        return _response_from_thought(session_id, thought, False)
    speak = str(result.get("speak") or "Done.")
    return _chat_response(
        session_id,
        speak=speak,
        scene=_scene_from_dict(result.get("scene")),
        attachments=result.get("attachments"),
        mail_id=result.get("mail_id"),
    )


def run_attachment_reply(session_id: str, email_id: str, attachment_ids: list[str], filenames: list[str] | None = None) -> ChatResponse:
    prefs = db.get_preferences()
    result = _apply_tool(
        "reply_with_attachments",
        {"email_id": email_id, "attachment_ids": attachment_ids, "filenames": filenames or []},
        session_id,
        prefs,
        "",
    )
    thought = _thought_from_result(result, "reply_with_attachments")
    if thought:
        return _response_from_thought(session_id, thought, False)
    speak = str(result.get("speak") or "Draft is ready.")
    return _chat_response(
        session_id,
        speak=speak,
        scene=_scene_from_dict(result.get("scene")),
        attachments=result.get("attachments"),
        mail_id=result.get("mail_id"),
    )


def _fill_tool_args(
    name: str,
    arguments: dict[str, Any],
    asked: str,
    prefs: dict[str, Any] | None = None,
    intent=None,
) -> dict[str, Any]:
    args = dict(arguments or {})
    intent = intent or classify(asked)
    prefs = prefs or {}
    if name == "read_email":
        if intent.person and not args.get("email_id"):
            current = str(args.get("query") or "")
            if "from:" not in current.lower():
                args["query"] = intent.query or f"from:{intent.person}"
        elif not args.get("email_id") and not args.get("query") and intent.query:
            args["query"] = intent.query
        if intent.last:
            args["last"] = True
    if name == "search_emails":
        if intent.unread_only:
            args["unread_only"] = True
        if intent.query and not args.get("query"):
            args["query"] = intent.query
    if name in {"save_mail_attachments", "reply_with_attachments", "forward_email"} and not args.get("query"):
        args["query"] = asked
    if name == "research" and not args.get("query"):
        from .connectors.search import clean_query

        args["query"] = clean_query(intent.query or asked) or asked
    if name == "list_calendar":
        span = str(args.get("span") or "").strip().lower()
        if span not in {"today", "tomorrow"}:
            span = str(intent.query or "").strip().lower()
        if span not in {"today", "tomorrow"}:
            span = calendar_span(asked)
        args["span"] = span
        if span == "today":
            args["days"] = 1
        elif span == "tomorrow":
            args["days"] = 2
        else:
            try:
                days = int(args.get("days") or 7)
            except (TypeError, ValueError):
                days = 7
            args["days"] = min(max(days, 1), 7)
    if name == "create_calendar_event" and not args.get("title"):
        try:
            tz = ZoneInfo(prefs.get("timezone") or settings.tz or "Asia/Kolkata")
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")
        event = calendar_event_spec(asked, tz)
        if event:
            args.update(event)
    if name == "drive_find" and not args.get("title"):
        args["title"] = _guess_file_title(asked) or asked
    if name == "task_for_gemini" and not args.get("steps"):
        args["steps"] = gemini_steps(asked)
    if name == "create_spreadsheet" and not args.get("title"):
        args.update(spreadsheet_spec(asked))
    if name == "create_document" and not args.get("title"):
        args.update(document_spec(asked))
    return args


def _try_model_route(
    message: str,
    prefs: dict[str, Any],
    session_id: str,
    tools: list[dict[str, Any]],
    intent=None,
) -> tuple[list[dict[str, Any]], list[str]]:
    intent = intent or classify(message)
    route = route_for(intent.kind)
    allowed = list(route.tools)
    if not allowed:
        return [], []
    if route.pref and not prefs.get(route.pref, True):
        return [], []
    wanted = set(allowed)
    selected = [item for item in tools if (item.get("function") or {}).get("name") in wanted]
    if not selected:
        return [], []
    name = prefs.get("assistant_name") or "Jarvis"
    who = prefs.get("display_name") or "Sir"
    steer = (
        f"You are {name}, {who}'s aide. {route.job} "
        "Do not invent senders, prices, or calendar facts. Use only the provided tools."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": steer},
        {"role": "user", "content": message},
    ]
    try:
        response = ollama_chat(
            messages,
            tools=selected,
            timeout=180,
            allowed_function_names=allowed,
        )
    except OllamaError:
        return [], []
    thoughts: list[dict[str, Any]] = []
    used: list[str] = []
    calls = [call for call in _tool_calls_from_message(response) if call.get("name") in wanted]
    if not calls:
        args = _fill_tool_args(allowed[0], {}, message, prefs, intent)
        calls = [{"name": allowed[0], "arguments": args}]
    if len(allowed) == 1:
        calls = calls[:1]
    for call in calls:
        if call["name"] not in wanted:
            continue
        arguments = _fill_tool_args(call["name"], call.get("arguments") or {}, message, prefs, intent)
        result = _apply_tool(call["name"], arguments, session_id, prefs, message)
        used.append(call["name"])
        thought = _thought_from_result(result, call["name"])
        if thought:
            thoughts.append(thought)
    return thoughts, used


def _model_label(message: str, prefs: dict[str, Any]) -> str:
    kinds = ", ".join(sorted(ROUTES))
    name = prefs.get("assistant_name") or "Jarvis"
    prompt = f"""The user said: {message}

Pick one kind. Greeting, thanks, or small talk → chat.
If they clearly want mail, calendar, research, files, Drive, a briefing, or Gemini, pick that work kind.
Kinds: {kinds}

JSON only: {{"kind": "chat"}}"""
    try:
        response = ollama_chat(
            [
                {"role": "system", "content": f"You route jobs for {name}. Do not invent kinds."},
                {"role": "user", "content": prompt},
            ],
            format_json=True,
            timeout=45,
            options={"temperature": 0, "num_predict": 40},
        )
    except OllamaError:
        return ""
    data = _extract_json(response.get("content") or "") or {}
    kind = str(data.get("kind") or "").strip().lower()
    return kind if kind in ROUTES else ""


def _enabled_tools(prefs: dict[str, Any]) -> list[dict[str, Any]]:
    flags = {
        "search_emails": prefs.get("email_enabled", True),
        "draft_email": prefs.get("email_enabled", True),
        "send_email": prefs.get("email_enabled", True),
        "forward_email": prefs.get("email_enabled", True),
        "read_email": prefs.get("email_enabled", True),
        "list_calendar": prefs.get("calendar_enabled", True),
        "create_calendar_event": prefs.get("calendar_enabled", True),
        "create_spreadsheet": prefs.get("files_enabled", True),
        "create_document": prefs.get("files_enabled", True),
        "create_pdf": prefs.get("files_enabled", True),
        "review_inbox": prefs.get("files_enabled", True),
        "research": prefs.get("research_enabled", True),
    }
    tools = []
    for schema in TOOL_SCHEMAS:
        name = schema["function"]["name"]
        if flags.get(name, True):
            tools.append(schema)
    return tools


def _system_prompt(prefs: dict[str, Any], memories: list[dict[str, str]], inbox: list[dict[str, str]]) -> str:
    memory_lines = "\n".join(f"- {item['key']}: {item['value']}" for item in memories) or "- none"
    inbox_lines = "\n".join(f"- {item['name']}: {item['text'][:240]}" for item in inbox) or "- none"
    return f"""You are {prefs.get('assistant_name', 'Jarvis')}, a work-operations command center.
Address the user as {prefs.get('display_name', 'Sir')}.
Persona: {prefs.get('persona')}
Verbosity: {prefs.get('verbosity', 'concise')}.
Context: {prefs.get('job_context')}
Timezone: {prefs.get('timezone')}
Sign-off for mail: {prefs.get('sign_off')}

You help with email, calendar, documents, Excel, research, and briefings.
Use tools for live data and file creation. Never claim you sent mail or saved an event until a tool ran.
Sends and calendar writes always need user confirmation.

Session memory:
{memory_lines}

Dropped inbox files:
{inbox_lines}

After tools finish, respond with JSON only:
{{
  "speak": "1-3 spoken sentences",
  "reply": "short on-screen explanation",
  "scene": {{
    "title": "string",
    "subtitle": "string",
    "widgets": [
      {{"type":"kpi","label":"Unread","value":3,"hint":"optional"}},
      {{"type":"table","title":"Mail","columns":["From","Subject"],"rows":[["a","b"]]}},
      {{"type":"markdown","title":"Notes","text":"..."}},
      {{"type":"chart","title":"Mix","chart_type":"bar","points":[{{"label":"A","value":2}}]}},
      {{"type":"timeline","title":"Today","items":[{{"time":"16:00","title":"Review","detail":"..."}}]}},
      {{"type":"quote","text":"...","cite":"optional"}}
    ]
  }}
}}
Widget types: kpi, table, markdown, chart, timeline, quote.
Keep speak suitable for text-to-speech. Do not mention you are an AI model.
"""


def _chat_prompt(prefs: dict[str, Any], session_id: str = "default") -> str:
    focus = ""
    data = get_set(session_id) if session_id else {}
    thread = data.get("thread") if isinstance(data, dict) else None
    email_id = (thread or {}).get("id") if isinstance(thread, dict) else ""
    mail = email_conn.get_email(email_id) if email_id else None
    if mail and mail.get("body"):
        body = re.sub(r"\s+", " ", str(mail.get("body") or "")).strip()[:1200]
        focus = (
            "\nLast mail in focus (use only if they ask about it; ignore for small talk):\n"
            f"From: {mail.get('sender') or ''}\n"
            f"Subject: {mail.get('subject') or ''}\n"
            f"{body}\n"
        )
    cal_focus = ""
    try:
        from .connectors import calendar as calendar_conn

        rows = calendar_conn.upcoming(days=7)[:4]
    except Exception:
        rows = []
    if rows:
        lines = []
        for event in rows:
            stamp = calendar_conn.clock(event.get("start_at") or "")
            title = event.get("title") or "event"
            loc = event.get("location") or ""
            extra = f" ({loc})" if loc else ""
            lines.append(f"- {stamp} {title}{extra}".strip())
        cal_focus = (
            "\nUpcoming on the calendar (use only if they ask; ignore for small talk):\n"
            + "\n".join(lines)
            + "\n"
        )
    return f"""You are {prefs.get('assistant_name', 'Jarvis')}, a present and slightly dry British aide.
Address the user as {prefs.get('display_name', 'Sir')}.
Persona: {prefs.get('persona')}
Verbosity: {prefs.get('verbosity', 'concise')}.
They may put your name anywhere in the sentence. Answer in one or two spoken sentences.
Be present. Do not mention tools, JSON, or that you are a model.
Do not invent emails, files, or calendar changes.
{focus}{cal_focus}"""


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        candidates.insert(0, fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.insert(0, text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("tool_calls") or []
    parsed = []
    for call in calls:
        function = call.get("function") or {}
        args = function.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        parsed.append({"name": function.get("name"), "arguments": args})
    return [item for item in parsed if item.get("name")]


def _session_mail(refs: dict[str, Any], session_id: str, pointed: bool = False) -> dict[str, Any] | None:
    mail = refs.get("mail") or (email_conn_get(refs.get("thread") or {}) if refs.get("thread") else None)
    if not mail:
        from .mail_attachments import get_mail_context

        ctx = get_mail_context(session_id)
        mail = email_conn_get({"id": ctx.get("email_id")}) if ctx.get("email_id") else None
    if not mail and pointed:
        mail = email_hint()
    return mail


def _heuristic_tools(
    message: str,
    prefs: dict[str, Any],
    session_id: str = "default",
    intent=None,
) -> list[dict[str, Any]]:
    intent = intent or classify(message)
    if intent.kind == "chat" and not wants_familiarity(message):
        return []
    text = message.lower()
    refs = resolve_refs(session_id, message)
    calls: list[dict[str, Any]] = []
    pointed = bool(re.search(r"\b(that|this|last|latest|newest|it)\b", text))

    if intent.kind == "briefing":
        calls.append({"name": "get_briefing", "arguments": {}})

    if prefs.get("email_enabled") and intent.kind.startswith("mail_"):
        if intent.kind == "mail_save":
            mail = _session_mail(refs, session_id, pointed)
            args = {"query": message}
            if mail:
                args["email_id"] = mail["id"]
            calls.append({"name": "save_mail_attachments", "arguments": args})
        elif intent.kind == "mail_reply_attach":
            mail = _session_mail(refs, session_id, pointed)
            args = {"query": message}
            if mail:
                args["email_id"] = mail["id"]
            calls.append({"name": "reply_with_attachments", "arguments": args})
        elif intent.kind == "mail_read":
            args = _fill_tool_args("read_email", {}, message, prefs, intent)
            mail = None
            if not intent.person:
                if intent.last:
                    mail = email_hint()
                elif refs.get("mail") or refs.get("thread") or pointed:
                    mail = _session_mail(refs, session_id, pointed)
            if mail:
                calls.append({"name": "read_email", "arguments": {"email_id": mail["id"]}})
            else:
                calls.append({"name": "read_email", "arguments": args})
        elif intent.kind == "mail_search":
            calls.append({"name": "search_emails", "arguments": _fill_tool_args("search_emails", {}, message, prefs, intent)})
        elif intent.kind == "mail_draft":
            # Prefer an explicit address in the user message over inbox reply context
            raw_addr = _extract_email_address(message)
            if raw_addr:
                local = raw_addr.split("@", 1)[0]
                person_name = re.sub(r"[._+-]+", " ", local).strip().title() or "there"
                subject_match = re.search(r"\b(?:subject|about|re:?)\s+(.+)$", message, re.I)
                saying = re.search(
                    r"\b(?:saying|that says|that says that|to say)\s+(.+)$",
                    message,
                    re.I,
                )
                body_core = (saying.group(1).strip() if saying else "").rstrip(" .")
                if subject_match and not saying:
                    subject = subject_match.group(1).strip()[:80]
                elif body_core:
                    subject = body_core[:60]
                else:
                    subject = "Quick note"
                body = f"Hi {person_name},\n\n"
                if body_core:
                    body += f"{body_core}.\n"
                calls.append(
                    {
                        "name": "draft_email",
                        "arguments": {
                            "to": raw_addr,
                            "subject": subject,
                            "body": body,
                        },
                    }
                )
            else:
                inbox = refs.get("mail")
                if not inbox and refs.get("thread") and refs["thread"].get("id"):
                    inbox = email_conn_get(refs["thread"])
                if not inbox and pointed:
                    inbox = email_hint()
                if inbox:
                    calls.append(
                        {
                            "name": "draft_email",
                            "arguments": {
                                "to": inbox["sender"],
                                "subject": f"Re: {inbox['subject']}" if not str(inbox.get("subject") or "").lower().startswith("re:") else inbox["subject"],
                                "body": reply_draft(inbox),
                                "in_reply_to": inbox["id"],
                            },
                        }
                    )
                else:
                    compose_match = re.search(r"\b(?:mail|email|write to)\s+([A-Za-z][A-Za-z'-]+)\b", text)
                    person_name = (compose_match.group(1) if compose_match else intent.person) or ""
                    to_addr = ""
                    if refs.get("person") and refs["person"].get("first", "").lower() == person_name.lower():
                        to_addr = refs["person"].get("email") or refs["person"].get("sender") or ""
                    if not to_addr and person_name:
                        rows = email_conn_search(person_name, limit=1)
                        if rows:
                            to_addr = rows[0].get("sender") or ""
                    if to_addr:
                        subject_match = re.search(r"\b(?:that|about|re:?)\s+(.+)$", message, re.I)
                        subject = subject_match.group(1).strip()[:80] if subject_match else f"Note for {person_name}"
                        calls.append(
                            {
                                "name": "draft_email",
                                "arguments": {
                                    "to": to_addr,
                                    "subject": subject,
                                    "body": f"Hi {person_name},\n\n",
                                },
                            }
                        )
        elif intent.kind == "mail_forward":
            mail = _session_mail(refs, session_id, pointed)
            forward_match = re.search(
                r"\bforward(?:\s+(?:this|that|it|the(?:\s+mail|\s+email|\s+message)?))?(?:\s+to)?\s+([A-Za-z][A-Za-z'@.\s-]+?)(?:\s+|$|[?.!,])",
                text,
            )
            to_addr = (forward_match.group(1).strip() if forward_match else "").strip(" .")
            if mail and to_addr:
                if "@" not in to_addr:
                    rows = email_conn_search(to_addr, limit=1) if to_addr else []
                    if rows and "<" in (rows[0].get("sender") or ""):
                        to_addr = rows[0]["sender"]
                    elif refs.get("person") and refs["person"].get("first", "").lower() == to_addr.lower():
                        to_addr = refs["person"].get("email") or refs["person"].get("sender") or to_addr
                calls.append({"name": "forward_email", "arguments": {"to": to_addr, "email_id": mail["id"]}})

    if prefs.get("calendar_enabled"):
        try:
            tz = ZoneInfo(prefs.get("timezone") or settings.tz or "Asia/Kolkata")
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")
        if intent.kind == "calendar_create":
            event = calendar_event_spec(message, tz)
            if event:
                calls.append({"name": "create_calendar_event", "arguments": event})
        elif intent.kind == "calendar_list":
            span = intent.query if intent.query in {"today", "tomorrow"} else calendar_span(message)
            days = 1 if span == "today" else 2 if span == "tomorrow" else 7
            calls.append({"name": "list_calendar", "arguments": {"days": days, "span": span}})

    if prefs.get("research_enabled") and intent.kind == "research":
        from .connectors.search import clean_query

        calls.append({"name": "research", "arguments": {"query": clean_query(message) or message}})

    if refs.get("same_morning"):
        have_sheet = bool(refs.get("artifact") and refs["artifact"].get("id"))
        have_mail = bool(refs.get("mail") or (refs.get("thread") and refs["thread"].get("id")))
        if have_sheet and have_mail:
            pass
        elif have_sheet and prefs.get("files_enabled"):
            calls.append({"name": "show_artifact", "arguments": {"artifact_id": refs["artifact"]["id"]}})
        elif have_mail and prefs.get("email_enabled"):
            mail = refs.get("mail") or email_conn_get(refs.get("thread") or {})
            if mail:
                calls.append({"name": "read_email", "arguments": {"email_id": mail["id"]}})
        return _gate_calls(calls, intent.kind)

    if intent.kind == "sheet_open" and prefs.get("files_enabled") and refs.get("artifact") and refs["artifact"].get("id"):
        calls.append({"name": "show_artifact", "arguments": {"artifact_id": refs["artifact"]["id"]}})
    elif intent.kind == "sheet_create" and prefs.get("files_enabled"):
        calls.append({"name": "create_spreadsheet", "arguments": spreadsheet_spec(message)})

    if intent.kind == "file_review" and prefs.get("files_enabled"):
        calls.append({"name": "review_inbox", "arguments": {}})
    if intent.kind == "drive_upload" and prefs.get("files_enabled"):
        calls.append({"name": "drive_upload", "arguments": {}})
    if intent.kind == "drive_find" and prefs.get("files_enabled"):
        title = ((refs.get("drive") or {}).get("title") or "") or _guess_file_title(message)
        calls.append({"name": "drive_find", "arguments": {"title": title}})
    if intent.kind == "gemini" and prefs.get("email_enabled"):
        drive = refs.get("drive") or {}
        artifact = refs.get("artifact") or {}
        steps = gemini_steps(message)
        calls.append(
            {
                "name": "task_for_gemini",
                "arguments": {
                    "steps": steps,
                    "file_link": drive.get("link") or "",
                    "file_title": drive.get("title") or artifact.get("title") or artifact.get("name") or "",
                },
            }
        )
    if intent.kind == "doc_create" and prefs.get("files_enabled"):
        calls.append({"name": "create_document", "arguments": document_spec(message)})
    if intent.kind == "rfq_reason":
        calls.append({"name": "reason_rfq", "arguments": {"message": message}})
    if intent.kind == "cnc_suggest":
        calls.append({"name": "cnc_suggest", "arguments": {}})
    if intent.kind == "shop_bind":
        calls.append({"name": "bind_shop_sheet", "arguments": {"query": message}})
    if intent.kind == "shop_create":
        calls.append({"name": "ensure_shop_sheet", "arguments": {}})
    if intent.kind == "shop_read":
        calls.append({"name": "read_shop_sheet", "arguments": {}})
    if intent.kind == "shop_write":
        calls.append({"name": "update_shop_sheet", "arguments": {"message": message}})

    seen = set()
    unique = []
    for call in calls:
        if call["name"] not in seen:
            unique.append(call)
            seen.add(call["name"])
    return _gate_calls(unique, intent.kind)


def _gate_calls(calls: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    allowed = set(route_for(kind).tools)
    if not allowed:
        return calls
    return [call for call in calls if call.get("name") in allowed]


def email_hint() -> dict[str, Any] | None:
    from .connectors.email import search_emails

    rows = search_emails(limit=1)
    return rows[0] if rows else None


def email_conn_get(thread: dict[str, Any]) -> dict[str, Any] | None:
    from .connectors.email import get_email

    mail_id = thread.get("id")
    return get_email(mail_id) if mail_id else None


def email_conn_search(query: str, limit: int = 1) -> list[dict[str, Any]]:
    from .connectors.email import search_emails

    return search_emails(query=query, limit=limit)


def _scene_from_dict(data: dict[str, Any] | None) -> Scene | None:
    if not data:
        return None
    try:
        widgets = []
        for widget in data.get("widgets") or []:
            if isinstance(widget, dict) and widget.get("type"):
                widgets.append(Widget(**{k: v for k, v in widget.items() if k in Widget.model_fields}))
        return Scene(
            title=data.get("title") or "Command Center",
            subtitle=data.get("subtitle"),
            widgets=widgets,
        )
    except Exception:
        return None


def _fallback_scene(text: str) -> Scene:
    return Scene(
        title="Jarvis",
        subtitle="Conversation",
        widgets=[Widget(type="markdown", title="Explanation", text=text or "Here.")],
    )


def _looks_like_error(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("does not support tools", "traceback", '"error"', "could not complete"))


def _social_reply(message: str, prefs: dict[str, Any]) -> str:
    text = prepare(message)
    cleaned = re.sub(r"[!.?,]", "", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).lower()
    who = prefs.get("display_name") or "Sir"
    replies = {
        "how are you": f"In order, {who}. What do you need?",
        "how are you doing": f"In order, {who}. What do you need?",
        "thanks": "Of course.",
        "thank you": "Of course.",
        "thanks jarvis": "Of course.",
        "who are you": "Jarvis. Your aide.",
        "hello": "Yes?",
        "hi": "Yes?",
        "hey": "Yes?",
        "good morning": "Good morning.",
        "good evening": "Good evening.",
        "good afternoon": "Good afternoon.",
        "don't reply": "Understood. I will not reply.",
        "dont reply": "Understood. I will not reply.",
        "do not reply": "Understood. I will not reply.",
        "do not send this email": "Understood. I will not send it.",
        "don't send": "Understood. I will not send it.",
        "dont send": "Understood. I will not send it.",
    }
    return replies.get(cleaned, "")


def _speak_from_scene(scene: Scene | None, used_tools: bool) -> str:
    if scene and scene.title:
        extra = scene.subtitle
        if extra:
            return f"{scene.title}. {extra}."
        return f"{scene.title} is on the board."
    if used_tools:
        return "Done. The board is updated."
    return "Here."


def _collect_artifacts() -> list[Artifact]:
    return [Artifact(**item) for item in db.list_artifacts(8)]


def _pending_models(session_id: str) -> list[PendingAction]:
    return [PendingAction(**item) for item in db.list_focused_pending(session_id)]


def _artifact_from_tool(result: dict[str, Any]) -> str | None:
    data = result.get("data")
    if isinstance(data, dict) and data.get("id") and data.get("path"):
        return str(data["id"])
    return None


def _thought_from_result(result: dict[str, Any], tool_name: str = "") -> dict[str, Any] | None:
    scene = result.get("scene")
    if not scene:
        return None
    pending = result.get("pending") if isinstance(result.get("pending"), dict) else {}
    model = _scene_from_dict(scene)
    return {
        "speak": result.get("speak") or _speak_from_scene(model, True),
        "reply": result.get("reply") or result.get("speak") or _speak_from_scene(model, True),
        "scene": scene,
        "pending_id": pending.get("id") if pending else None,
        "artifact_id": _artifact_from_tool(result),
        "tool": tool_name,
        "attachments": result.get("attachments"),
        "mail_id": result.get("mail_id"),
        "critical": result.get("critical"),
    }


def _artifacts_for(artifact_id: str | None) -> list[Artifact]:
    if not artifact_id:
        return []
    item = db.get_artifact(artifact_id)
    return [Artifact(**item)] if item else []


def _response_from_thought(session_id: str, thought: dict[str, Any], offline: bool) -> ChatResponse:
    scene = _scene_from_dict(thought.get("scene")) or Scene(title="", widgets=[])
    speak = str(thought.get("speak") or _speak_from_scene(scene, True))
    reply = str(thought.get("reply") or speak)
    db.set_focus_pending(session_id, thought.get("pending_id") or "")
    return _chat_response(
        session_id,
        speak=speak,
        reply=reply,
        scene=scene,
        artifacts=_artifacts_for(thought.get("artifact_id")),
        attachments=thought.get("attachments"),
        mail_id=thought.get("mail_id"),
        offline=offline,
        more=db.thought_count(session_id),
        watching=bool((db.get_watch(session_id) or {}).get("status") == "waiting"),
        critical=thought.get("critical"),
    )


def next_thought(session_id: str = "default") -> ChatResponse:
    thought = db.pop_thought(session_id)
    if not thought:
        db.set_focus_pending(session_id, None)
        return ChatResponse(speak="", reply="", scene=Scene(title="", widgets=[]), more=0)
    return _response_from_thought(session_id, thought, False)


def _skip_brain(kind: str, message: str) -> bool:
    if kind in {"calendar_create", "calendar_list", "rfq_reason", "cnc_suggest", "shop_bind", "shop_create", "shop_read", "shop_write", "mail_draft", "mail_forward"}:
        return True
    return uses_snapshot(kind) and snapshot_ready() and not wants_fresh(message)


def _revise_pending_email(session_id: str, message: str, pending: dict[str, Any]) -> ChatResponse | None:
    """Revise an awaiting email draft instead of starting a new Hermes/legacy loop."""
    if (pending.get("kind") or "") != "email_send":
        return None
    if not _DRAFT_REVISE_RE.search(message or ""):
        return None
    payload = dict(pending.get("payload") or {})
    to_addr = str(payload.get("to") or "")
    subject = str(payload.get("subject") or "")
    body = str(payload.get("body") or "")
    if not to_addr or not body:
        return None
    try:
        revised = ollama_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You revise email drafts. Reply with JSON only: "
                        '{"subject":"...","body":"...","speak":"one short confirmation"}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Operator request: {message}\n\n"
                        f"To: {to_addr}\nSubject: {subject}\nBody:\n{body}"
                    ),
                },
            ],
            tools=None,
            timeout=45,
        )
        text = (revised.get("content") or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        data = json.loads(text[start : end + 1]) if start >= 0 and end > start else {}
    except Exception:
        data = {}
    new_subject = str(data.get("subject") or subject).strip() or subject
    new_body = str(data.get("body") or "").strip()
    if not new_body:
        parts = [p.strip() for p in body.split("\n\n") if p.strip()]
        new_body = parts[0] if parts else body[:400].rstrip()
    payload["subject"] = new_subject
    payload["body"] = new_body
    db.update_pending_payload(pending["id"], payload, title=f"Send: {new_subject}", summary=f"To {to_addr}")
    speak = str(data.get("speak") or "").strip() or f"Shortened the draft to {to_addr}. Authorize when ready."
    db.add_message(session_id, "assistant", speak)
    db.set_focus_pending(session_id, pending["id"])
    action = PendingAction(
        id=pending["id"],
        kind=pending["kind"],
        title=f"Send: {new_subject}",
        summary=f"To {to_addr}",
        payload=payload,
        agent_id=pending.get("agent_id") or "ops",
        tool_name=pending.get("tool_name") or "draft_email",
    )
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=Scene(
            title="Authorization required",
            subtitle=action.title,
            widgets=[Widget(type="markdown", text=f"**{new_subject}**\n\n{new_body}")],
        ),
        pending=[action],
        offline=False,
    )


def run_agent(message: str, session_id: str = "default") -> ChatResponse:
    from .conversations import brain_lock

    with brain_lock():
        return _run_agent(message, session_id)


def _run_agent(message: str, session_id: str = "default") -> ChatResponse:
    waiting = db.list_pending(session_id)
    decision = classify_decision(message)
    if waiting and decision is not None:
        return resolve_pending(waiting[0]["id"], decision, session_id)

    from .conversations import chat_drawing, is_drawing_session
    from .config import settings as app_settings
    from .hermes.bridge import hermes_available, run_hermes_turn

    prefs = db.get_preferences()
    db.clear_thoughts(session_id)
    heard = message
    message, _repairs = normalize_speech(message)
    db.add_message(session_id, "user", message)
    if not message.strip():
        return _chat_response(session_id, speak="Yes?")

    intent = classify(message)
    if is_drawing_session(session_id) and intent.kind == "chat":
        return chat_drawing(session_id, message)

    # Fill / revise focused email compose from chat before other routing
    if waiting:
        from .intent import match_mail_trigger
        from .mail_compose import merge_compose_from_message, start_email_compose

        top = waiting[0]
        if top.get("kind") == "email_compose" and match_mail_trigger(message):
            db.set_pending_status(top["id"], "rejected")
            db.set_focus_pending(session_id, None)
            if prefs.get("email_enabled", True):
                result = start_email_compose(session_id, message, intent)
                db.add_message(session_id, "assistant", result.speak or "")
                return result
        merged = merge_compose_from_message(session_id, message, top)
        if merged is not None:
            return merged
        revised = _revise_pending_email(session_id, message, top)
        if revised is not None:
            return revised

    # Tight draft/reply triggers → LLM fill + compose modal (no Hermes, no instant send)
    if intent.kind == "mail_draft" and prefs.get("email_enabled", True):
        from .mail_compose import start_email_compose

        result = start_email_compose(session_id, message, intent)
        db.add_message(session_id, "assistant", result.speak or "")
        return result

    # Local mail/calendar/briefing: skip Hermes (avoids 30s gateway timeouts) and
    # read from the local mailbox / snapshot first. Refresh when asked.
    from .snapshot import wants_fresh, refresh as snapshot_refresh

    local_fast = intent.kind in {
        "mail_read",
        "mail_search",
        "mail_save",
        "mail_reply_attach",
        "calendar_list",
        "briefing",
    }
    mail_pref_ok = (not intent.kind.startswith("mail_")) or prefs.get("email_enabled", True)
    if local_fast and mail_pref_ok:
        if wants_fresh(message):
            try:
                snapshot_refresh(force=True)
            except Exception:
                pass
        return _run_agent_legacy(message, session_id, prefs=prefs, intent=intent, heard=heard)

    # Prefer Hermes for other turns. On timeout/error → Gemini legacy.
    # mail_draft / drawing / pending authorize / local mail already returned above.
    use_hermes = app_settings.hermes_enabled and hermes_available()
    if use_hermes:
        try:
            result = run_hermes_turn(message, session_id)
            db.add_message(session_id, "assistant", result.speak or result.reply or "")
            db.add_audit(session_id, "hermes", (result.speak or "")[:400], "ok")
            return result
        except Exception as exc:
            db.add_audit(session_id, "hermes", str(exc)[:400], "error")
            # Fall through to Gemini / legacy agent loop

    # Soft fallback / Hermes-down: definitional RFQ must be chat, never reason_rfq.
    if is_rfq_definition(message):
        intent = Intent("chat")

    return _run_agent_legacy(message, session_id, prefs=prefs, intent=intent, heard=heard)


def _run_agent_legacy(
    message: str,
    session_id: str = "default",
    *,
    prefs: dict[str, Any] | None = None,
    intent: Any = None,
    heard: str = "",
) -> ChatResponse:
    prefs = prefs or db.get_preferences()
    if intent is None:
        intent = classify(message)
    memories = db.list_memories(session_id)
    inbox = db.list_inbox_files(6)
    tools = _enabled_tools(prefs)
    from .conversations import chat_drawing, is_drawing_session

    if is_drawing_session(session_id) and intent.kind == "chat":
        return chat_drawing(session_id, message)
    skip_brain = _skip_brain(intent.kind, message)
    if skip_brain:
        status = {"model_ready": True, "model": "snapshot"}
        offline = False
    else:
        status = health()
        offline = not bool(status.get("model_ready"))
        if not offline and intent.kind == "chat" and looks_like_work(message):
            labeled = _model_label(message, prefs)
            if labeled:
                intent = intent_for_kind(labeled, message)
                skip_brain = _skip_brain(intent.kind, message)
                if skip_brain:
                    offline = False
    work = intent.kind != "chat" or wants_familiarity(message)
    route = route_for(intent.kind)
    system = _system_prompt(prefs, memories, inbox) if work else _chat_prompt(prefs, session_id)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for item in db.recent_messages(session_id, 12):
        messages.append({"role": item["role"], "content": item["content"]})

    last_scene = None
    last_text = ""
    used_tools = False
    parsed: dict[str, Any] | None = None
    thoughts: list[dict[str, Any]] = []
    used_names: list[str] = []

    if work:
        need_sync = wants_fresh(message)
        if uses_snapshot(intent.kind) and intent.kind != "mail_read" and not snapshot_ready():
            need_sync = True
        if intent.kind in {"calendar_list", "briefing"} and not calendar_ready():
            need_sync = True
        if need_sync:
            try:
                refresh_snapshot(force=wants_fresh(message))
            except Exception:
                pass
        if route.tools and not offline and not skips_model(intent.kind):
            extra, names = _try_model_route(message, prefs, session_id, tools, intent)
            used_names.extend(names)
            if names:
                used_tools = True
            if extra:
                thoughts.extend(extra)
                last_scene = extra[-1].get("scene")
        done = bool(route.complete and route.complete in used_names)
        if not done:
            for call in _heuristic_tools(message, prefs, session_id, intent):
                if call["name"] in used_names:
                    continue
                result = _apply_tool(call["name"], call.get("arguments") or {}, session_id, prefs, message)
                used_tools = True
                used_names.append(call["name"])
                thought = _thought_from_result(result, call["name"])
                if thought:
                    thoughts.append(thought)
                    last_scene = thought["scene"]
                if route.complete and route.complete in used_names:
                    break

    if not work:
        try:
            if offline:
                raise OllamaError(f"{status.get('model') or 'The model'} is not online yet")
            response = ollama_chat(messages, tools=None, timeout=180)
            last_text = response.get("content") or ""
            parsed = None
        except OllamaError as exc:
            detail = str(exc).lower()
            if "does not support tools" not in detail and "not online yet" not in detail:
                db.add_audit(session_id, "ollama", str(exc)[:400], "error")
            last_text = ""
            parsed = None
        if not last_text and not offline:
            try:
                last_text = ollama_chat(messages, tools=None, timeout=180).get("content") or ""
            except OllamaError as exc:
                db.add_audit(session_id, "ollama", str(exc)[:400], "error")

    speak = ""
    reply = ""
    scene = _scene_from_dict(last_scene)
    if parsed and not _looks_like_error(str(parsed.get("speak") or "")):
        speak = str(parsed.get("speak") or "")
        reply = str(parsed.get("reply") or speak)
        scene = _scene_from_dict(parsed.get("scene")) or scene
    if used_tools and scene and (len(speak) < 16 or _looks_like_error(speak)):
        speak = _speak_from_scene(scene, True)
        reply = speak
    if not speak:
        cleaned = re.sub(r"<think>.*?</think>", "", last_text, flags=re.S).strip()
        if _looks_like_error(cleaned):
            cleaned = ""
        if not work and cleaned.startswith("{"):
            cleaned = ""
        speak = cleaned[:320] or _speak_from_scene(scene, used_tools)
        reply = cleaned or speak
    if not work and (not speak or speak in {"Here.", "Standing by."}):
        social = _social_reply(message, prefs)
        speak = social or ("Yes?" if speak in {"Here.", "Standing by.", ""} else speak)
        reply = speak
    if work and intent.kind == "calendar_create" and not used_tools and (not speak or speak in {"Here.", "Standing by."}):
        speak = "I need a time for that. When should I put it on the calendar?"
        reply = speak
    if offline and not used_tools and (not speak or speak in {"Standing by.", "Here.", "Yes?"}):
        speak = "The model is still coming online. Ask me to brief you, draft mail, or make a file."
        reply = speak
    if not scene:
        if work and intent.kind == "briefing":
            payload = build_briefing()
            scene = _scene_from_dict(payload["scene"])
            if not speak:
                speak = str(payload.get("speak") or "")
                reply = speak
        else:
            # Speak-only replies: VoiceLine carries text — no duplicate quote board
            scene = Scene(title="", widgets=[])

    refs = resolve_refs(session_id, message)
    if refs["open_sheet"] and "show_artifact" not in used_names and "create_spreadsheet" not in used_names and "task_for_gemini" not in used_names:
        guess = {
            "tool": "create_spreadsheet",
            "arguments": spreadsheet_spec(message or "spreadsheet"),
            "label": "spreadsheet",
        }
        extra = clarification_thought({"heard": "the spreadsheet", "guess": guess})
        extra["speak"] = "I do not have a spreadsheet from this session yet. Shall I make one?"
        extra["scene"]["widgets"] = [{"type": "quote", "text": extra["speak"], "cite": "Jarvis"}]
        pending = db.add_pending(
            f"ask-{db.utc_now()}",
            session_id,
            "clarify",
            "Make a spreadsheet",
            "I do not have one from this session yet",
            guess,
        )
        extra["pending_id"] = pending["id"]
        thoughts.append(extra)
    if refs.get("same_morning") and "show_artifact" not in used_names and "read_email" not in used_names:
        have_sheet = bool(refs.get("artifact") and refs["artifact"].get("id"))
        have_mail = bool(refs.get("mail") or (refs.get("thread") and refs["thread"].get("id")))
        raw = (refs.get("artifact") or {}).get("title") or (refs.get("artifact") or {}).get("name") or "spreadsheet"
        sheet_name = re.sub(r"-[0-9a-f]{4,}.*$", "", str(raw).split(".")[0], flags=re.I).strip() or "spreadsheet"
        if "pricing" in sheet_name.lower() and "sheet" not in sheet_name.lower():
            sheet_name = "pricing sheet"
        person_name = ((refs.get("person") or {}).get("first") or "them")
        if have_sheet and have_mail:
            ask = f"The {sheet_name}, or {person_name}'s note? Say which."
        else:
            ask = "I do not have that from this morning. A name or a file?"
        thoughts.append({
            "speak": ask,
            "scene": {"title": "Say that again", "subtitle": "", "widgets": [{"type": "quote", "text": ask, "cite": "Jarvis"}]},
            "pending_id": None,
            "artifact_id": None,
        })
    if intent.kind in {"mail_draft", "mail_read", "mail_forward"} and (refs["reply"] or refs["read_mail"]) and not any(
        name in used_names for name in ("draft_email", "read_email", "search_emails", "forward_email")
    ):
        thoughts.append({
            "speak": "Who is that? Give me a name.",
            "scene": {"title": "Say that again", "subtitle": "", "widgets": [{"type": "quote", "text": "Who is that? Give me a name.", "cite": "Jarvis"}]},
            "pending_id": None,
            "artifact_id": None,
        })

    if work and intent.kind not in {"rfq_reason", "cnc_suggest", "shop_bind", "shop_create", "shop_read", "shop_write"}:
        for item in unmatched_clauses(heard, message, used_names):
            if "task_for_gemini" in used_names:
                continue
            extra = clarification_thought(item)
            guess = item.get("guess")
            if guess:
                pending = db.add_pending(
                    f"ask-{db.utc_now()}",
                    session_id,
                    "clarify",
                    f"Make a {guess['label']}",
                    f'I heard "{item["heard"]}"',
                    guess,
                )
                extra["pending_id"] = pending["id"]
            thoughts.append(extra)

    if work and not used_tools and not thoughts:
        if re.search(r"\bwhat('?s| is| did)\b", message, re.I):
            speak = "Mail, the calendar, or a file — which one?"
        else:
            speak = "I don't handle that yet. Mail, calendar, a file, or Gemini."
        reply = speak
        scene = Scene(title="Say that again", widgets=[Widget(type="quote", text=speak, cite="Jarvis")])

    if thoughts:
        first, rest = thoughts[0], thoughts[1:]
        db.set_thoughts(session_id, rest, focus=first.get("pending_id") or "")
        first["speak"] = first.get("speak") or speak
        response = _response_from_thought(session_id, first, offline)
        db.add_message(session_id, "assistant", response.speak)
        return response

    db.add_message(session_id, "assistant", speak)
    return ChatResponse(
        speak=speak,
        reply=reply or speak,
        scene=scene,
        artifacts=_collect_artifacts(),
        pending=_pending_models(session_id),
        offline=offline,
        more=0,
    )


def resolve_pending(action_id: str, approved: bool, session_id: str) -> ChatResponse:
    action = db.get_pending(action_id)
    if not action:
        speak = "That confirmation is no longer pending."
        return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak))
    if action.get("status") != "pending":
        speak = "Already handled."
        return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak))

    if not approved:
        db.set_pending_status(action_id, "rejected")
        db.add_audit(session_id, action["kind"], f"Rejected {action['title']}", "rejected")
        remaining = db.thought_count(session_id)
        db.set_focus_pending(session_id, "" if remaining else None)
        rfq_id = str((action.get("payload") or {}).get("rfq_id") or "")
        if rfq_id and action["kind"] in {"email_send", "calendar_create"}:
            from .rfq import mark_rfq_idle_if_gates_cleared

            mark_rfq_idle_if_gates_cleared(session_id, rfq_id)
        from .conversations import is_drawing_session

        drawing = is_drawing_session(session_id)
        if action["kind"] == "cnc_promote":
            speak = "Left the draft."
        elif action["kind"] == "sheets_write":
            speak = "Left the sheet."
        elif action["kind"] == "clarify":
            speak = "Alright."
        else:
            speak = "Cancelled."
        if drawing:
            scene = Scene(title="", widgets=[])
        else:
            scene = Scene(
                title="Alright" if action["kind"] == "clarify" else "Cancelled",
                widgets=[Widget(type="quote", text=action["title"])],
            )
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=scene,
            artifacts=_collect_artifacts(),
            pending=_pending_models(session_id),
            more=remaining,
        )

    payload = action["payload"]
    watching = False
    spoken_line = ""
    if action["kind"] in {"email_send", "email_compose", "quote_send"}:
        from .connectors.email import send_email

        to_addr = str(payload.get("to") or "").strip()
        subject = str(payload.get("subject") or "").strip()
        body = str(payload.get("body") or "").strip()
        if action["kind"] == "email_compose":
            from .mail_compose import _subject_from_body

            if body and not subject:
                subject = _subject_from_body(body)
                payload["subject"] = subject
            if not to_addr or not body:
                db.set_pending_status(action_id, "pending")
                need = []
                if not to_addr:
                    need.append("recipient")
                if not body:
                    need.append("body")
                speak = f"I still need the {', '.join(need)} before I can send."
                db.set_focus_pending(session_id, action_id)
                return ChatResponse(
                    speak=speak,
                    reply=speak,
                    scene=Scene(title="Draft incomplete", widgets=[]),
                    pending=_pending_models(session_id),
                    watching=False,
                )
        elif action["kind"] in {"email_send", "quote_send"}:
            if not to_addr or not body:
                db.set_pending_status(action_id, "pending")
                speak = "I still need recipient and body before I can send."
                db.set_focus_pending(session_id, action_id)
                return ChatResponse(
                    speak=speak,
                    reply=speak,
                    scene=Scene(title="Send incomplete", widgets=[]),
                    pending=_pending_models(session_id),
                    watching=False,
                )
        try:
            sent = send_email(
                to_addr,
                subject,
                body,
                payload.get("source_id"),
                payload.get("thread_id") or "",
                attachment_paths=payload.get("attachment_paths") or None,
            )
        except Exception:
            db.set_pending_status(action_id, "rejected")
            speak = "Gmail did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        remember_person(session_id, to_addr, sent.get("id") or payload.get("source_id"), subject)
        if payload.get("watch") or subject == "Task for Gemini":
            from .watch import start_gemini_watch

            start_gemini_watch(session_id, sent.get("thread_id") or "", sent.get("gmail_id") or sent.get("id") or "")
            watching = True
            spoken_line = "Sent the task to Gemini. I will watch the thread."
            detail = spoken_line
        else:
            spoken_line = speak_sent(to_addr)
            preview = re.sub(r"\s+", " ", body).strip()
            if len(preview) > 220:
                preview = preview[:217].rstrip() + "…"
            detail = f"Sent to {to_addr}.\nSubject: {subject}.\n\n{preview}"
        scene = Scene(
            title="Sent",
            subtitle=subject,
            widgets=[
                Widget(type="kpi", label="To", value=to_addr),
                Widget(type="kpi", label="Subject", value=subject),
                Widget(type="markdown", title="Message", text=body),
            ],
        )
    elif action["kind"] == "email_forward":
        from .connectors.email import forward_email

        try:
            sent = forward_email(
                payload["to"],
                payload.get("source_id") or "",
                note=payload.get("note") or "",
            )
        except Exception:
            db.set_pending_status(action_id, "rejected")
            speak = "Gmail did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        remember_person(session_id, payload["to"], sent.get("id") or payload.get("source_id"), payload.get("subject"))
        detail = speak_sent(payload["to"])
        scene = Scene(
            title="Forwarded",
            subtitle=payload.get("subject") or "",
            widgets=[
                Widget(type="kpi", label="To", value=payload["to"]),
                Widget(type="markdown", title="Forward", text=payload.get("note") or sent.get("body") or ""),
            ],
        )
    elif action["kind"] == "calendar_create":
        from .connectors.calendar import clock, create_event

        try:
            event_kwargs = {
                "title": str(payload.get("title") or ""),
                "start_at": str(payload.get("start_at") or ""),
                "end_at": str(payload.get("end_at") or ""),
                "location": str(payload.get("location") or ""),
                "notes": str(payload.get("notes") or ""),
            }
            create_event(**event_kwargs)
        except Exception as exc:
            db.set_pending_status(action_id, "rejected")
            speak = str(exc).strip() or "Calendar did not take it."
            if "traceback" in speak.lower() or len(speak) > 160:
                speak = "Calendar did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        detail = f"Added {payload['title']}"
        scene = Scene(
            title="On the calendar",
            subtitle=payload["title"],
            widgets=[
                Widget(
                    type="timeline",
                    title="New event",
                    items=[{"time": clock(payload.get("start_at") or ""), "title": payload["title"], "detail": payload.get("location") or ""}],
                ),
            ],
        )
    elif action["kind"] == "clarify":
        result = execute_tool(payload.get("tool") or "", payload.get("arguments") or {}, session_id)
        thought = _thought_from_result(result)
        db.set_pending_status(action_id, "approved")
        db.add_audit(session_id, "clarify", f"Approved {payload.get('label') or payload.get('tool')}", "approved")
        if thought:
            remaining = db.thought_count(session_id)
            response = _response_from_thought(session_id, thought, False)
            response.more = remaining
            return response
        detail = "Done."
        scene = _fallback_scene(detail)
    elif action["kind"] == "cnc_promote":
        from .rfq import promote_cnc_draft

        promoted = promote_cnc_draft(payload, session_id, True)
        detail = str(promoted.get("detail") or promoted.get("speak") or "Draft accepted.")
        label = str(promoted.get("path") or payload.get("path") or "draft").rsplit("/", 1)[-1]
        scene = Scene(
            title="CNC draft kept",
            subtitle=label,
            widgets=[
                Widget(type="quote", text=detail, cite="Jarvis"),
                Widget(type="markdown", text="Not proven on the machine. Not emailed."),
            ],
        )
    elif action["kind"] == "sheets_write":
        from .shop_log import apply_write

        try:
            written = apply_write(payload)
        except Exception:
            db.set_pending_status(action_id, "rejected")
            speak = "Google Sheets did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        cells = ", ".join(str(item) for item in (written.get("updated") or []))
        detail = "Updated the shop log."
        scene = Scene(
            title="Shop log updated",
            subtitle=payload.get("title") or payload.get("sheet_name") or "",
            widgets=[
                Widget(type="quote", text=detail, cite="Jarvis"),
                Widget(type="markdown", text=cells or str(payload.get("updates") or "")),
            ],
        )
    elif action["kind"] == "handoff_gemini":
        from .connectors import drive as drive_conn
        from .connectors.email import send_email
        from .tools.registry import DEFAULT_GEMINI_REPLY, gemini_body
        from .watch import start_gemini_watch

        inbox = db.get_inbox_file(payload.get("inbox_id") or "") if payload.get("inbox_id") else None
        artifact = db.get_artifact(payload.get("artifact_id") or "") if payload.get("artifact_id") else None
        path = (inbox or artifact or {}).get("path") or ""
        title = (inbox or artifact or {}).get("name") or "file"
        if not path:
            speak = "I do not have that file anymore."
            db.set_pending_status(action_id, "rejected")
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak))
        if not drive_conn.live():
            db.set_pending_status(action_id, "rejected")
            speak = "Drive is not connected."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak))
        try:
            uploaded = drive_conn.upload_file(path, title)
            file_line = uploaded.get("link") or uploaded.get("title") or title
            body = gemini_body(file_line, payload.get("steps") or f"Analyze {title}.", payload.get("reply_format") or DEFAULT_GEMINI_REPLY)
            sent = send_email(settings.gemini_task_to or settings.google_account, "Task for Gemini", body)
        except Exception:
            db.set_pending_status(action_id, "rejected")
            speak = "Gmail did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak))
        if uploaded:
            from .familiarity import remember_drive

            remember_drive(session_id, uploaded)
        start_gemini_watch(session_id, sent.get("thread_id") or "", sent.get("gmail_id") or sent.get("id") or "")
        watching = True
        detail = "Sent the task to Gemini. I will watch the thread."
        scene = Scene(
            title="Task for Gemini",
            subtitle=title,
            widgets=[Widget(type="markdown", title="Envelope", text=body)],
        )
    elif action["kind"] == "memory_wipe":
        from .memory import forget

        ns = str(payload.get("namespace") or "").strip()
        if not ns:
            db.set_pending_status(action_id, "rejected")
            speak = "No memory namespace to wipe."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        result = forget(namespace=ns, wipe_namespace=True)
        detail = f"Wiped local memory namespace `{ns}` ({result.get('deleted') or 0} docs)."
        scene = Scene(title="Memory wiped", subtitle=ns, widgets=[Widget(type="quote", text=detail)])
    elif action["kind"] == "browser_action":
        # Foundation stretch: evidence-only; do not pretend a browser ran.
        db.set_pending_status(action_id, "rejected")
        speak = "Browser actions are not executable yet — evidence can be recorded, but I will not Authorize a live browse until that path is wired."
        return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
    else:
        # Unknown kinds must not look like success
        db.set_pending_status(action_id, "rejected")
        speak = f"I cannot execute `{action['kind']}` yet."
        return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)

    db.set_pending_status(action_id, "approved")
    db.add_audit(session_id, action["kind"], detail, "approved")
    remaining = db.thought_count(session_id)
    db.set_focus_pending(session_id, "" if remaining else None)
    speak = spoken_line or detail
    return ChatResponse(
        speak=speak,
        reply=detail,
        watching=watching,
        scene=scene,
        artifacts=_collect_artifacts(),
        pending=_pending_models(session_id),
        more=remaining,
    )
