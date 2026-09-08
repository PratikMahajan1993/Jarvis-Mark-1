from __future__ import annotations

from typing import Any

from . import gemini_client, ollama_client
from .config import settings
from .ollama_client import OllamaError

__all__ = ["OllamaError", "chat", "health", "provider"]


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
    kind = provider()
    if kind == "gemini":
        status = gemini_client.health()
        local = ollama_client.health()
        status["provider"] = "gemini"
        status["ollama"] = bool(local.get("ollama"))
        status["ok"] = True
        return status
    status = ollama_client.health()
    status["provider"] = "ollama"
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
