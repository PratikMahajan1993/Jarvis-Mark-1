"""LLM-assisted email compose fill for the HUD draft modal."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from . import db
from .agents import agent_code, agent_status_payload
from .brain import chat as brain_chat
from .hermes.hitl import request_human_approval
from .intent import match_mail_trigger
from .schemas import ActivityEvent, AgentStatus, ChatResponse, PendingAction, Scene, Widget

_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+,[A-Za-z]{2,})\b"
)


def extract_email_address(message: str) -> str:
    text = message or ""
    # Speech pauses mid-address: "pratik.28 1293@gmail.com" → "pratik.281293@gmail.com"
    text = re.sub(
        r"([A-Za-z0-9._%+-]*\d)\s+(\d+[A-Za-z0-9._%+-]*@)",
        r"\1\2",
        text,
    )
    # "name @ gmail.com" / "gmail . com"
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"@([A-Za-z0-9-]+)\s*\.\s*([A-Za-z]{2,})\b", r"@\1.\2", text)
    match = _EMAIL_RE.search(text)
    if not match:
        return ""
    addr = match.group(1).strip()
    if "," in addr.rsplit("@", 1)[-1]:
        local, domain = addr.rsplit("@", 1)
        addr = f"{local}@{domain.replace(',', '.', 1)}"
    return addr


def _missing_fields(to_addr: str, subject: str, body: str) -> list[str]:
    """Subject is never user-required — LLM derives it from body when ready."""
    missing: list[str] = []
    if not (to_addr or "").strip():
        missing.append("to")
    if not (body or "").strip():
        missing.append("body")
    return missing


def _subject_from_body(body: str) -> str:
    line = re.sub(r"\s+", " ", (body or "").strip().split("\n")[0]).strip()
    if not line:
        return "Update"
    # Drop greeting / soft-ask openers common in spoken dictation
    line = re.sub(
        r"^(?:hi|hello|hey|dear)\s+[^,.\n]+[,.\s]+",
        "",
        line,
        flags=re.I,
    ).strip() or line
    line = re.sub(
        r"^(?:can you please|could you please|please|can you|could you|would you|yes please|yes)\s+",
        "",
        line,
        flags=re.I,
    ).strip() or line
    line = re.sub(
        r"^(?:check and tell me|tell me|let me know|asking about|send(?:\s+me)?(?:\s+the)?)\s+",
        "",
        line,
        flags=re.I,
    ).strip() or line
    # Prefer first clause; drop trailing urgency tags from subject
    line = re.split(r"(?<=[.!?])\s+", line, maxsplit=1)[0].strip()
    line = re.sub(
        r"[,.]?\s*\b(?:need this urgently|urgently|asap|as soon as possible)\b.*$",
        "",
        line,
        flags=re.I,
    ).strip() or line
    # Capitalize first letter for a cleaner subject line
    if line:
        line = line[0].upper() + line[1:]
    if len(line) > 72:
        cut = line[:72].rsplit(" ", 1)[0].strip() or line[:72]
        return cut.rstrip(".,;:?")
    return line.rstrip(".,;:?")


def _is_address_only_remainder(remainder: str) -> bool:
    text = (remainder or "").strip()
    if not text:
        return True
    without = _EMAIL_RE.sub("", text)
    without = re.sub(r"\bto\b", "", without, flags=re.I)
    without = re.sub(r"[^\w\s]", " ", without)
    return not without.strip()


def _speak_for(missing: list[str], to_addr: str, subject: str) -> str:
    if not missing:
        target = to_addr or "the recipient"
        return f"Draft ready for {target}. Authorize to send."
    labels = {"to": "recipient", "body": "body"}
    need = ", ".join(labels[m] for m in missing if m in labels)
    if to_addr and "to" not in missing and "body" in missing:
        return "What should the email say?"
    if to_addr and "to" not in missing:
        return f"I need the {need} before we can send."
    return f"I need the {need} to finish this draft."


def llm_fill_compose(
    *,
    user_message: str,
    remainder: str,
    mode: str,
    seed_to: str = "",
    seed_subject: str = "",
    seed_body: str = "",
    reply_mail: dict[str, Any] | None = None,
    follow_up: bool = False,
) -> dict[str, Any]:
    """Return {to, subject, body, missing, speak} refined by Hermes (preferred) or Gemini."""
    explicit = extract_email_address(user_message) or extract_email_address(remainder)
    seed_to = seed_to or explicit
    context = ""
    if reply_mail:
        context = (
            f"Replying to mail from {reply_mail.get('sender') or ''} "
            f"subject {reply_mail.get('subject') or ''}.\n"
            f"Body excerpt:\n{(reply_mail.get('body') or '')[:1200]}\n"
        )
        if not seed_to:
            seed_to = str(reply_mail.get("sender") or "")

    system = (
        "You help Jarvis draft emails for a machining-firm operator. "
        "Refine non-fluent English into a clear professional body. "
        "Subject is optional from the user. "
        "If body content exists and subject is empty, invent a short subject from the body. "
        "Never invent a subject when body is empty. "
        "Never use an email address or a bare 'to …' phrase as the subject. "
        "Never invent a recipient address if none was given. "
        "In speak, only ask for recipient or body — never ask for subject. "
        "Reply with JSON only: "
        '{"to":"","subject":"","body":"","speak":"one short line for the HUD"}'
    )
    follow = ""
    if follow_up and not (seed_body or "").strip():
        follow = (
            "This utterance is likely the email body (or body revision). "
            "Rewrite it as a clear professional email body (greeting + request + close). "
            "Invent a short subject (under 8 words) from the body meaning — "
            "do not paste the whole body into subject.\n"
        )
    user = (
        f"Mode: {mode}\n"
        f"{follow}"
        f"Full user message: {user_message}\n"
        f"Text after trigger: {remainder}\n"
        f"Seed to: {seed_to}\n"
        f"Seed subject: {seed_subject}\n"
        f"Seed body: {seed_body}\n"
        f"{context}"
    )
    to_addr, subject, body, speak = seed_to, seed_subject, seed_body, ""

    def _apply_json(text: str) -> bool:
        nonlocal to_addr, subject, body, speak
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return False
        data = json.loads(text[start : end + 1])
        to_addr = str(data.get("to") or to_addr or "").strip() or seed_to
        subject = str(data.get("subject") or subject or "").strip()
        body = str(data.get("body") or body or "").strip()
        speak = str(data.get("speak") or "").strip()
        return True

    filled = False
    # Prefer warm Hermes gateway (no tools) for compose fill when available
    try:
        from .config import settings
        from .hermes.bridge import hermes_gateway_reachable

        if settings.hermes_enabled and hermes_gateway_reachable():
            import httpx

            headers = {
                "Authorization": f"Bearer {settings.hermes_api_key}",
                "Content-Type": "application/json",
            }
            chat_body = {
                "model": "hermes-agent",
                "messages": [
                    {"role": "system", "content": system + " Do not use tools."},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            }
            with httpx.Client(timeout=min(25.0, float(settings.hermes_timeout_sec))) as client:
                r = client.post(
                    f"{settings.hermes_gateway_url.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json=chat_body,
                )
            if r.status_code < 400:
                data = r.json()
                choice = (data.get("choices") or [None])[0] or {}
                msg = choice.get("message") or {}
                content = str(msg.get("content") or "")
                filled = _apply_json(content)
    except Exception:
        filled = False

    if not filled:
        try:
            raw = brain_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                tools=None,
                timeout=45,
            )
            text = (raw.get("content") or "").strip()
            filled = _apply_json(text)
        except Exception:
            filled = False

    if not filled:
        if not body and remainder and not _is_address_only_remainder(remainder):
            saying = re.search(r"\b(?:saying|that says|to say)\s+(.+)$", remainder, re.I)
            core = (saying.group(1) if saying else "").strip()
            if not core and follow_up:
                core = remainder.strip()
            if core:
                body = core if core.endswith(".") else f"{core}."
        if not subject and body:
            subject = _subject_from_body(body)

    if explicit:
        to_addr = explicit
    elif seed_to:
        to_addr = seed_to
    elif mode == "compose" and to_addr and "@" in to_addr:
        blob = f"{user_message} {remainder}"
        if extract_email_address(to_addr) not in blob and extract_email_address(to_addr) != extract_email_address(blob):
            to_addr = ""

    # Follow-up body salvage: if still empty, treat utterance as body text
    if follow_up and not body and (user_message or "").strip():
        candidate = (user_message or "").strip()
        if not match_mail_trigger(candidate) and not _is_address_only_remainder(candidate):
            body = candidate if candidate.endswith((".", "!", "?")) else f"{candidate}."

    # Never keep a subject that is just the remainder address line
    if subject and _is_address_only_remainder(subject):
        subject = ""
    if subject and extract_email_address(subject) and _is_address_only_remainder(subject):
        subject = ""

    if body and not subject:
        subject = _subject_from_body(body)
    if not body:
        # Do not leave a dangling invented subject without body
        if not seed_subject or _is_address_only_remainder(seed_subject):
            subject = ""

    missing = _missing_fields(to_addr, subject, body)
    if not missing:
        speak = f"Draft ready for {to_addr or 'the recipient'}. Authorize to send."
    elif not speak or "subject" in speak.lower():
        speak = _speak_for(missing, to_addr, subject)
    return {
        "to": to_addr,
        "subject": subject,
        "body": body,
        "missing": missing,
        "speak": speak,
    }


def _resolve_reply_mail(session_id: str, intent: Any) -> dict[str, Any] | None:
    from .connectors import email as email_conn
    from .familiarity import resolve as resolve_refs

    refs = resolve_refs(session_id, "")
    if intent.last or not intent.person:
        mail = refs.get("mail")
        if mail:
            return mail
        rows = email_conn.search_emails(limit=1)
        return rows[0] if rows else None
    if intent.person:
        rows = email_conn.search_emails(query=f"from:{intent.person}", limit=1)
        if rows:
            return rows[0]
        rows = email_conn.search_emails(query=intent.person, limit=1)
        return rows[0] if rows else None
    return None


def start_email_compose(session_id: str, message: str, intent: Any) -> ChatResponse:
    trigger = match_mail_trigger(message) or {
        "mode": "compose",
        "remainder": intent.query or "",
        "person": intent.person or "",
        "last": intent.last,
    }
    mode = str(trigger.get("mode") or "compose")
    remainder = str(trigger.get("remainder") or intent.query or "")
    reply_mail = _resolve_reply_mail(session_id, intent) if mode == "reply" else None

    filled = llm_fill_compose(
        user_message=message,
        remainder=remainder,
        mode=mode,
        reply_mail=reply_mail,
    )
    payload = {
        "to": filled["to"],
        "subject": filled["subject"],
        "body": filled["body"],
        "missing": filled["missing"],
        "mode": mode,
        "source_id": (reply_mail or {}).get("id") or "",
        "thread_id": (reply_mail or {}).get("thread_id") or "",
        "attachment_paths": [],
    }
    title = f"Draft: {payload['subject']}" if payload["subject"] else "Draft email"
    summary = f"To {payload['to']}" if payload["to"] else "Recipient needed"
    pending = request_human_approval(
        session_id=session_id,
        kind="email_compose",
        title=title,
        summary=summary,
        payload=payload,
        action_id=f"compose-{uuid.uuid4().hex[:10]}",
        tool_name="draft_email",
        agent_id="ops",
    )
    db.set_focus_pending(session_id, pending["id"])
    speak = filled["speak"]
    action = PendingAction(
        id=pending["id"],
        kind="email_compose",
        title=title,
        summary=summary,
        payload=payload,
        agent_id="ops",
        tool_name="draft_email",
        irreversibility=int(pending.get("irreversibility") or 2),
        consequence=str(pending.get("consequence") or ""),
    )
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=Scene(
            title="Draft email",
            subtitle=summary,
            widgets=[
                Widget(type="kpi", label="To", value=payload["to"] or "—"),
                Widget(type="markdown", title=payload["subject"] or "Subject", text=payload["body"] or ""),
            ],
        ),
        pending=[action],
        activity=[
            ActivityEvent(
                id=pending["id"],
                time="",
                agent=agent_code("ops"),
                message="Compose modal ready",
            )
        ],
        agents=[AgentStatus(**row) for row in agent_status_payload({"ops": "waiting"})],
        offline=False,
    )


def merge_compose_from_message(session_id: str, message: str, pending: dict[str, Any]) -> ChatResponse | None:
    """Update focused email_compose from a follow-up utterance."""
    if (pending.get("kind") or "") != "email_compose":
        return None
    payload = dict(pending.get("payload") or {})
    filled = llm_fill_compose(
        user_message=message,
        remainder=message,
        mode=str(payload.get("mode") or "compose"),
        seed_to=str(payload.get("to") or ""),
        seed_subject=str(payload.get("subject") or ""),
        seed_body=str(payload.get("body") or ""),
        follow_up=True,
    )
    new_addr = extract_email_address(message)
    if new_addr:
        filled["to"] = new_addr
    payload["to"] = filled["to"] or payload.get("to") or ""
    payload["subject"] = filled["subject"] or payload.get("subject") or ""
    payload["body"] = filled["body"] or payload.get("body") or ""
    payload["missing"] = _missing_fields(payload["to"], payload["subject"], payload["body"])
    title = f"Draft: {payload['subject']}" if payload["subject"] else "Draft email"
    summary = f"To {payload['to']}" if payload["to"] else "Recipient needed"
    db.update_pending_payload(pending["id"], payload, title=title, summary=summary)
    db.set_focus_pending(session_id, pending["id"])
    speak = filled["speak"] or _speak_for(payload["missing"], payload["to"], payload["subject"])
    if not payload["missing"]:
        speak = f"Draft ready for {payload['to'] or 'the recipient'}. Authorize to send."
    db.add_message(session_id, "assistant", speak)
    action = PendingAction(
        id=pending["id"],
        kind="email_compose",
        title=title,
        summary=summary,
        payload=payload,
        agent_id=pending.get("agent_id") or "ops",
        tool_name=pending.get("tool_name") or "draft_email",
        irreversibility=int(pending.get("irreversibility") or 2),
        consequence=str(pending.get("consequence") or ""),
    )
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=Scene(title="Draft email", subtitle=summary, widgets=[]),
        pending=[action],
        agents=[AgentStatus(**row) for row in agent_status_payload({"ops": "waiting"})],
        offline=False,
    )


def update_compose_fields(
    session_id: str,
    action_id: str,
    *,
    to_addr: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> ChatResponse:
    pending = db.get_pending(action_id)
    if not pending or pending.get("session_id") != session_id:
        speak = "That draft is gone."
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene(title="", widgets=[]),
            pending=[],
            agents=[AgentStatus(**row) for row in agent_status_payload({})],
        )
    if pending.get("kind") != "email_compose" or pending.get("status") != "pending":
        speak = "That draft is no longer open."
        return ChatResponse(
            speak=speak,
            reply=speak,
            scene=Scene(title="", widgets=[]),
            pending=[],
            agents=[AgentStatus(**row) for row in agent_status_payload({})],
        )
    payload = dict(pending.get("payload") or {})
    if to_addr is not None:
        payload["to"] = to_addr.strip()
    if subject is not None:
        payload["subject"] = subject.strip()
    if body is not None:
        payload["body"] = body.strip()
    payload["missing"] = _missing_fields(payload.get("to") or "", payload.get("subject") or "", payload.get("body") or "")
    title = f"Draft: {payload['subject']}" if payload.get("subject") else "Draft email"
    summary = f"To {payload['to']}" if payload.get("to") else "Recipient needed"
    db.update_pending_payload(action_id, payload, title=title, summary=summary)
    db.set_focus_pending(session_id, action_id)
    speak = _speak_for(payload["missing"], payload.get("to") or "", payload.get("subject") or "")
    action = PendingAction(
        id=action_id,
        kind="email_compose",
        title=title,
        summary=summary,
        payload=payload,
        agent_id=pending.get("agent_id") or "ops",
        tool_name=pending.get("tool_name") or "draft_email",
        irreversibility=int(pending.get("irreversibility") or 2),
        consequence=str(pending.get("consequence") or ""),
    )
    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=Scene(title="Draft email", subtitle=summary, widgets=[]),
        pending=[action],
        agents=[AgentStatus(**row) for row in agent_status_payload({"ops": "waiting"})],
        offline=False,
    )
