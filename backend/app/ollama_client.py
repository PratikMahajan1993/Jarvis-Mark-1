from __future__ import annotations

from typing import Any

import httpx

from .config import settings


class OllamaError(RuntimeError):
    pass


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.ollama_host, timeout=120)


def health() -> dict[str, Any]:
    try:
        with _client() as client:
            tags = client.get("/api/tags")
            tags.raise_for_status()
            models = [item.get("name", "") for item in tags.json().get("models", [])]
            wanted = settings.ollama_model
            ready = any(wanted == name or wanted in name or name.startswith(wanted) for name in models)
            return {
                "ok": True,
                "ollama": True,
                "model": wanted,
                "models": models,
                "model_ready": ready,
            }
    except Exception:
        return {
            "ok": False,
            "ollama": False,
            "model": settings.ollama_model,
            "models": [],
            "model_ready": False,
        }


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    format_json: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    if format_json:
        payload["format"] = "json"
    try:
        with _client() as client:
            response = client.post("/api/chat", json=payload)
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code >= 400 or data.get("error"):
                raise OllamaError(data.get("error") or response.text)
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    return data.get("message") or {}
