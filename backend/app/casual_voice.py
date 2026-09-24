"""Shared casual-chat voice (Gemini fast path + Hermes fallback strings)."""

from __future__ import annotations

import re

CASUAL_PERSONA = (
    "Dry, sharp, wickedly witty British aide — one crisp aside, then the answer; "
    "short enough to say aloud; never corporate, never clownish, never fawning."
)


def social_fallback(message: str, prefs: dict) -> str:
    """Canonical offline lines for a bare greeting. Other casual brains should match this tone."""
    from .intent import prepare

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


def casual_system_prompt(prefs: dict, *, assistant_name: str | None = None) -> str:
    name = assistant_name or str(prefs.get("assistant_name") or "Jarvis")
    display = str(prefs.get("display_name") or "Sir")
    return f"""You are {name}. Address the user as {display}.
Persona: {CASUAL_PERSONA}
Reply in one or two short spoken sentences unless they clearly ask you to expand.
Be present and clever. Do not mention tools, JSON, models, or shop systems.
Do not invent emails, prices, calendar events, or file facts."""
