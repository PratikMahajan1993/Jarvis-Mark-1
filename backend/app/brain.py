from __future__ import annotations

import time
from typing import Any

from . import gemini_client, ollama_client
from .config import settings
from .ollama_client import OllamaError

__all__ = ["OllamaError", "chat", "health", "provider"]

_HEALTH_TTL = 60.0
_HEALTH: dict[str, Any] = {"at": 0.0, "data": None}


def provider() -> str:
    choice = (settings.llm_provider or "auto").strip().lower()
    if choice in {"gemini", "google"}:
        return "gemini"
    if choice in {"ollama", "local"}:
        return "ollama"
    if settings.gemini_api_key:
        return "gemini"
    return "ollama"


def health() -> dict[str, Any]:
    now = time.monotonic()
    cached = _HEALTH.get("data")
    if isinstance(cached, dict) and now - float(_HEALTH.get("at") or 0) < _HEALTH_TTL:
        return dict(cached)
    kind = provider()
    if kind == "gemini":
        status = gemini_client.health()
        status["provider"] = "gemini"
        status["ollama"] = False
        status["ok"] = True
    else:
        status = ollama_client.health()
        status["provider"] = "ollama"
    _HEALTH["at"] = now
    _HEALTH["data"] = dict(status)
    return status


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    format_json: bool = False,
    timeout: float = 120,
    options: dict[str, Any] | None = None,
    allowed_function_names: list[str] | None = None,
) -> dict[str, Any]:
    if provider() == "gemini":
        return gemini_client.chat(
            messages,
            tools=tools,
            format_json=format_json,
            timeout=timeout,
            options=options,
            allowed_function_names=allowed_function_names,
        )
    return ollama_client.chat(messages, tools=tools, format_json=format_json, timeout=timeout, options=options)
