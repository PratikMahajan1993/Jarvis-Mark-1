from __future__ import annotations

import json
import re
from typing import Any

from . import db
from .briefing import build_briefing
from .config import settings
from .ollama_client import OllamaError, chat as ollama_chat, health
from .schemas import Artifact, ChatResponse, PendingAction, Scene, Widget
from .tools.registry import TOOL_SCHEMAS, execute_tool
from .familiarity import remember_person, resolve as resolve_refs, speak_sent, wants_familiarity
from .understand import clarification_thought, normalize_speech, unmatched_clauses

_YES = re.compile(
    r"^(yes|yeah|yep|yup|yea|ok|okay|sure|confirm|send( it)?|do it|go ahead|proceed|please|affirmative|that'?s fine)\b",
    re.I,
)
_NO = re.compile(r"^(no|nope|nah|cancel|stop|don'?t|do not|never|reject|negative|abort|wait)\b", re.I)


def classify_decision(text: str) -> bool | None:
    cleaned = re.sub(r"[!.?,]", "", (text or "").strip())
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered == "n" or _NO.match(cleaned):
        return False
    if lowered == "y" or _YES.match(cleaned):
        return True
    return None


def _enabled_tools(prefs: dict[str, Any]) -> list[dict[str, Any]]:
    flags = {
        "search_emails": prefs.get("email_enabled", True),
        "draft_email": prefs.get("email_enabled", True),
        "send_email": prefs.get("email_enabled", True),
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


def _chat_prompt(prefs: dict[str, Any]) -> str:
    return f"""You are {prefs.get('assistant_name', 'Jarvis')}, a present and slightly dry British aide.
Address the user as {prefs.get('display_name', 'Sir')}.
Persona: {prefs.get('persona')}
Verbosity: {prefs.get('verbosity', 'concise')}.
Answer ordinary conversation in 1-3 natural sentences. Do not mention tools, JSON, or that you are a model.
Do not invent emails, files, or calendar changes.
"""


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


def _wants_work(message: str) -> bool:
    text = message.lower()
    phrases = (
        "brief me",
        "briefing",
        "what's on",
        "whats on",
        "inbox",
        "email",
        "e-mail",
        "mail",
        "draft",
        "reply",
        "calendar",
        "schedule",
        "agenda",
        "spreadsheet",
        "excel",
        "xlsx",
        "document",
        "docx",
        "one-pager",
        "dropped a file",
        "dropped",
        "summarize",
        "review the dropped",
        "this file",
        "research",
        "look up",
        "search the web",
        "meeting notes",
        "open the",
        "the spreadsheet",
        "the sheet",
        "what did",
        "what's in",
        "whats in",
        "reply to him",
        "reply to her",
        "gemini",
        "drive",
        "google drive",
        "analyze this",
        "open in excel",
    )
    return any(phrase in text for phrase in phrases) or wants_familiarity(message)


def _heuristic_tools(message: str, prefs: dict[str, Any], session_id: str = "default") -> list[dict[str, Any]]:
    if not _wants_work(message):
        return []
    text = message.lower()
    refs = resolve_refs(session_id, message)
    calls: list[dict[str, Any]] = []
    gemini_ask = any(
        phrase in text
        for phrase in (
            "ask gemini",
            "send this to gemini",
            "send it to gemini",
            "task for gemini",
            "analyze this",
            "have gemini",
        )
    )
    drive_up = any(phrase in text for phrase in ("on drive", "to drive", "upload to drive", "put it on drive", "share it"))
    drive_find = ("drive" in text) and not drive_up and not gemini_ask
    briefing_ask = any(phrase in text for phrase in ("brief me", "briefing", "standup")) or (
        ("what's on" in text or "whats on" in text) and "mail" not in text and "email" not in text
    )
    if briefing_ask:
        calls.append({"name": "get_briefing", "arguments": {}})
    if prefs.get("email_enabled") and not gemini_ask and (refs["read_mail"] or any(word in text for word in ("email", "e-mail", "inbox", "mail", "reply", "draft"))):
        if refs["read_mail"]:
            mail = refs.get("mail") or (email_conn_get(refs.get("thread") or {}))
            if mail:
                calls.append({"name": "read_email", "arguments": {"email_id": mail["id"]}})
            elif refs.get("person"):
                calls.append({"name": "read_email", "arguments": {"query": refs["person"]["first"]}})
        elif "unread" in text or "inbox" in text or ("mail" in text and not refs["reply"]):
            calls.append({"name": "search_emails", "arguments": {"unread_only": "unread" in text}})
        if refs["reply"] or any(word in text for word in ("reply", "draft")):
            inbox = refs.get("mail")
            if not inbox and refs.get("thread") and refs["thread"].get("id"):
                inbox = email_conn_get(refs["thread"])
            pointed = bool(re.search(r"\b(him|her|them|that)\b", text))
            if not inbox and not pointed:
                inbox = email_hint()
            if inbox:
                calls.append(
                    {
                        "name": "draft_email",
                        "arguments": {
                            "to": inbox["sender"],
                            "subject": f"Re: {inbox['subject']}",
                            "body": (
                                f"Thank you for the note on {inbox['subject']}. "
                                "I will send the revised pricing sheet before the 4pm review "
                                "and confirm the 12-week rollout including the on-site week."
                            ),
                            "in_reply_to": inbox["id"],
                        },
                    }
                )
    if prefs.get("calendar_enabled") and any(word in text for word in ("calendar", "schedule", "agenda")):
        calls.append({"name": "list_calendar", "arguments": {"days": 2}})
    if prefs.get("research_enabled") and any(word in text for word in ("research", "look up", "search the web")):
        calls.append({"name": "research", "arguments": {"query": message}})
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
        return calls
    if prefs.get("files_enabled") and refs["open_sheet"] and refs.get("artifact") and refs["artifact"].get("id"):
        calls.append({"name": "show_artifact", "arguments": {"artifact_id": refs["artifact"]["id"]}})
    elif (
        prefs.get("files_enabled")
        and any(word in text for word in ("spreadsheet", "excel", "xlsx"))
        and not refs["open_sheet"]
        and not drive_up
        and not gemini_ask
    ):
        title = "Pricing" if "pricing" in text else "Follow-up"
        calls.append(
            {
                "name": "create_spreadsheet",
                "arguments": {
                    "title": title,
                    "columns": ["Item", "Owner", "Status"],
                    "rows": [
                        ["Revised pricing sheet", "You", "In progress"],
                        ["MSA redlines", "Legal", "Waiting"],
                        ["Client review", "You", "16:00 today"],
                    ],
                    "chart": False,
                },
            }
        )
    if prefs.get("files_enabled") and any(
        word in text for word in ("dropped", "summarize", "this file", "review the dropped")
    ):
        calls.append({"name": "review_inbox", "arguments": {}})
    if prefs.get("files_enabled") and drive_up:
        calls.append({"name": "drive_upload", "arguments": {}})
    if prefs.get("files_enabled") and drive_find:
        title = ((refs.get("drive") or {}).get("title") or "")
        calls.append({"name": "drive_find", "arguments": {"title": title}})
    if prefs.get("email_enabled") and gemini_ask:
        drive = refs.get("drive") or {}
        artifact = refs.get("artifact") or {}
        steps = re.sub(
            r"(?i)\b(jarvis|please|ask gemini|send (this|it) to gemini|task for gemini|put it on drive|and)\b",
            " ",
            message,
        )
        calls.append(
            {
                "name": "task_for_gemini",
                "arguments": {
                    "steps": re.sub(r"\s+", " ", steps).strip() or message,
                    "file_link": drive.get("link") or "",
                    "file_title": drive.get("title") or artifact.get("title") or artifact.get("name") or "",
                },
            }
        )
    if prefs.get("files_enabled") and any(word in text for word in ("word document", "document", "docx", "one-pager", "meeting notes")):
        calls.append(
            {
                "name": "create_document",
                "arguments": {
                    "title": "Meeting notes",
                    "body": "Prepared by Jarvis from the current briefing.",
                    "bullets": ["Confirm rollout", "Send pricing sheet", "Review MSA"],
                },
            }
        )
    seen = set()
    unique = []
    for call in calls:
        if call["name"] not in seen:
            unique.append(call)
            seen.add(call["name"])
    return unique


def email_hint() -> dict[str, Any] | None:
    from .connectors.email import search_emails

    rows = search_emails(limit=1)
    return rows[0] if rows else None


def email_conn_get(thread: dict[str, Any]) -> dict[str, Any] | None:
    from .connectors.email import get_email

    mail_id = thread.get("id")
    return get_email(mail_id) if mail_id else None


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
        widgets=[Widget(type="markdown", title="Explanation", text=text or "Standing by.")],
    )


def _looks_like_error(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("does not support tools", "traceback", '"error"', "could not complete"))


def _speak_from_scene(scene: Scene | None, used_tools: bool) -> str:
    if scene and scene.title:
        extra = scene.subtitle
        if extra:
            return f"{scene.title}. {extra}."
        return f"{scene.title} is on the board."
    if used_tools:
        return "Done. The board is updated."
    return "Standing by."


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
        "scene": scene,
        "pending_id": pending.get("id") if pending else None,
        "artifact_id": _artifact_from_tool(result),
        "tool": tool_name,
    }


def _artifacts_for(artifact_id: str | None) -> list[Artifact]:
    if not artifact_id:
        return []
    item = db.get_artifact(artifact_id)
    return [Artifact(**item)] if item else []


def _response_from_thought(session_id: str, thought: dict[str, Any], offline: bool) -> ChatResponse:
    scene = _scene_from_dict(thought.get("scene")) or Scene(title="", widgets=[])
    speak = str(thought.get("speak") or _speak_from_scene(scene, True))
    db.set_focus_pending(session_id, thought.get("pending_id") or "")
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=scene,
        artifacts=_artifacts_for(thought.get("artifact_id")),
        pending=_pending_models(session_id),
        more=db.thought_count(session_id),
        offline=offline,
        watching=bool((db.get_watch(session_id) or {}).get("status") == "waiting"),
    )


def next_thought(session_id: str = "default") -> ChatResponse:
    thought = db.pop_thought(session_id)
    if not thought:
        db.set_focus_pending(session_id, None)
        return ChatResponse(speak="", reply="", scene=Scene(title="", widgets=[]), more=0)
    return _response_from_thought(session_id, thought, False)


def run_agent(message: str, session_id: str = "default") -> ChatResponse:
    waiting = db.list_pending(session_id)
    decision = classify_decision(message)
    if waiting and decision is not None:
        return resolve_pending(waiting[0]["id"], decision, session_id)

    prefs = db.get_preferences()
    db.clear_thoughts(session_id)
    heard = message
    message, _repairs = normalize_speech(message)
    db.add_message(session_id, "user", message)
    memories = db.list_memories(session_id)
    inbox = db.list_inbox_files(6)
    tools = _enabled_tools(prefs)
    status = health()

    model_ready = bool(status.get("model_ready"))
    offline = not status["ollama"] or not model_ready
    work = _wants_work(message)
    system = _system_prompt(prefs, memories, inbox) if work else _chat_prompt(prefs)
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
        for call in _heuristic_tools(message, prefs, session_id):
            result = execute_tool(call["name"], call.get("arguments") or {}, session_id)
            used_tools = True
            used_names.append(call["name"])
            thought = _thought_from_result(result, call["name"])
            if thought:
                thoughts.append(thought)
                last_scene = thought["scene"]

    try:
        if offline:
            raise OllamaError(f"{settings.ollama_model} is not online yet")
        if work:
            raise OllamaError("skip model tools")
        response = ollama_chat(messages, tools=tools if work else None)
        last_text = response.get("content") or ""
        calls = _tool_calls_from_message(response)
        parsed = _extract_json(last_text)
        if parsed and parsed.get("tool"):
            calls.append({"name": parsed["tool"], "arguments": parsed.get("arguments") or {}})
        for _ in range(5):
            if not calls:
                break
            used_tools = True
            messages.append(response)
            for call in calls:
                result = execute_tool(call["name"], call.get("arguments") or {}, session_id)
                used_names.append(call["name"])
                thought = _thought_from_result(result, call["name"])
                if thought:
                    thoughts.append(thought)
                    last_scene = thought["scene"]
                messages.append({"role": "tool", "content": json.dumps(result, default=str)[:6000]})
            messages.append({"role": "user", "content": "If you need another tool, call it. Otherwise return the final JSON scene."})
            response = ollama_chat(messages, tools=tools)
            last_text = response.get("content") or last_text
            calls = _tool_calls_from_message(response)
            parsed = _extract_json(last_text) or parsed
        if used_tools and not parsed:
            messages.append({"role": "user", "content": "Return the final JSON scene now. Do not call more tools."})
            final = ollama_chat(messages, format_json=True)
            last_text = final.get("content") or last_text
            parsed = _extract_json(last_text) or parsed
    except OllamaError as exc:
        detail = str(exc).lower()
        if "does not support tools" not in detail and "not online yet" not in detail and "skip model tools" not in detail:
            db.add_audit(session_id, "ollama", str(exc)[:400], "error")
        if "skip model tools" not in detail:
            last_text = ""
            parsed = None

    if not used_tools and not last_text and not offline:
        try:
            last_text = (ollama_chat(messages).get("content") or "")
            parsed = _extract_json(last_text) or parsed
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
        speak = cleaned[:320] or _speak_from_scene(scene, used_tools)
        reply = cleaned or speak
    if offline and not used_tools and (not speak or speak == "Standing by."):
        speak = "The model is still coming online. Ask me to brief you, draft mail, or make a file."
        reply = speak
    if not scene:
        if work and any(phrase in message.lower() for phrase in ("brief me", "briefing", "what's on", "whats on")):
            scene = _scene_from_dict(build_briefing()["scene"])
        else:
            scene = Scene(
                title="",
                widgets=[Widget(type="quote", text=reply)] if reply else [],
            )

    refs = resolve_refs(session_id, message)
    if refs["open_sheet"] and "show_artifact" not in used_names and "create_spreadsheet" not in used_names:
        guess = {
            "tool": "create_spreadsheet",
            "arguments": {
                "title": "Follow-up",
                "columns": ["Item", "Owner", "Status"],
                "rows": [["Revised pricing sheet", "You", "In progress"]],
                "chart": False,
            },
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
    if (refs["reply"] or refs["read_mail"]) and not any(
        name in used_names for name in ("draft_email", "read_email", "search_emails")
    ):
        thoughts.append({
            "speak": "Who is that? Give me a name.",
            "scene": {"title": "Say that again", "subtitle": "", "widgets": [{"type": "quote", "text": "Who is that? Give me a name.", "cite": "Jarvis"}]},
            "pending_id": None,
            "artifact_id": None,
        })

    for item in unmatched_clauses(heard, message, used_names):
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
        speak = "Alright." if action["kind"] == "clarify" else "Cancelled."
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene(title="Alright" if action["kind"] == "clarify" else "Cancelled", widgets=[Widget(type="quote", text=action["title"])]),
            artifacts=_collect_artifacts(),
            pending=_pending_models(session_id),
            more=remaining,
        )

    payload = action["payload"]
    watching = False
    if action["kind"] == "email_send":
        from .connectors.email import send_email

        try:
            sent = send_email(
                payload["to"],
                payload["subject"],
                payload["body"],
                payload.get("source_id"),
                payload.get("thread_id") or "",
            )
        except Exception:
            db.set_pending_status(action_id, "rejected")
            speak = "Gmail did not take it."
            return ChatResponse(speak=speak, reply=speak, scene=_fallback_scene(speak), watching=False)
        remember_person(session_id, payload["to"], sent.get("id") or payload.get("source_id"), payload.get("subject"))
        if payload.get("watch") or payload.get("subject") == "Task for Gemini":
            from .watch import start_gemini_watch

            start_gemini_watch(session_id, sent.get("thread_id") or "", sent.get("gmail_id") or sent.get("id") or "")
            watching = True
            detail = "Sent the task to Gemini. I will watch the thread."
        else:
            detail = speak_sent(payload["to"])
        scene = Scene(
            title="Sent",
            subtitle=payload["subject"],
            widgets=[
                Widget(type="kpi", label="To", value=payload["to"]),
                Widget(type="markdown", title="Message", text=payload["body"]),
            ],
        )
    elif action["kind"] == "calendar_create":
        from .connectors.calendar import create_event

        create_event(**payload)
        detail = f"Added {payload['title']}"
        scene = Scene(
            title="On the calendar",
            subtitle=payload["title"],
            widgets=[
                Widget(type="timeline", title="New event", items=[{"time": payload["start_at"][11:16], "title": payload["title"], "detail": payload.get("location") or ""}]),
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
    else:
        detail = f"Approved {action['kind']}"
        scene = _fallback_scene(detail)

    db.set_pending_status(action_id, "approved")
    db.add_audit(session_id, action["kind"], detail, "approved")
    remaining = db.thought_count(session_id)
    db.set_focus_pending(session_id, "" if remaining else None)
    speak = detail
    return ChatResponse(
        speak=speak,
        reply=detail,
        watching=watching,
        scene=scene,
        artifacts=_collect_artifacts(),
        pending=_pending_models(session_id),
        more=remaining,
    )
