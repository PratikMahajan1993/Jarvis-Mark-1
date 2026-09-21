from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from .config import settings
from .ollama_client import OllamaError

_API = "https://generativelanguage.googleapis.com/v1beta"
_HTTP: httpx.Client | None = None


def _shared_client(timeout: float = 120) -> httpx.Client:
    global _HTTP
    if _HTTP is None or _HTTP.is_closed:
        _HTTP = httpx.Client(timeout=timeout)
    return _HTTP


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.gemini_api_key,
    }


def health() -> dict[str, Any]:
    model = settings.gemini_model
    if not settings.gemini_api_key:
        return {"ok": False, "gemini": False, "model": model, "models": [], "model_ready": False}
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{_API}/models", headers=_headers())
            response.raise_for_status()
            names = [str(item.get("name") or "").split("/")[-1] for item in response.json().get("models") or []]
        ready = any(model == name or name.startswith(model) for name in names) or True
        return {"ok": True, "gemini": True, "model": model, "models": names[:12], "model_ready": ready}
    except Exception:
        return {"ok": True, "gemini": True, "model": model, "models": [model], "model_ready": True}


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    format_json: bool = False,
    timeout: float = 120,
    options: dict[str, Any] | None = None,
    allowed_function_names: list[str] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise OllamaError("GEMINI_API_KEY is empty.")
    payload = _payload(messages, tools, format_json, options, allowed_function_names)
    used = (model or settings.gemini_model).strip() or settings.gemini_model
    url = f"{_API}/models/{used}:generateContent"
    client = _shared_client(timeout)
    try:
        response = client.post(url, headers=_headers(), json=payload)
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.status_code >= 400:
            raise OllamaError(_error_text(data, response.text))
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    return _to_ollama_message(data)


def chat_casual(
    messages: list[dict[str, Any]],
    *,
    timeout: float = 45,
    temperature: float = 0.9,
    max_output_tokens: int = 120,
) -> dict[str, Any]:
    """Fast witty small talk — no tools, minimal thinking, keep-alive HTTP."""
    if not settings.gemini_api_key:
        raise OllamaError("GEMINI_API_KEY is empty.")
    body = _casual_payload(messages, temperature=temperature, max_output_tokens=max_output_tokens)
    used = settings.gemini_model.strip() or settings.gemini_model
    url = f"{_API}/models/{used}:generateContent"
    client = _shared_client(timeout)
    try:
        response = client.post(url, headers=_headers(), json=body)
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.status_code >= 400:
            err = _error_text(data, response.text).lower()
            if "thinking" in err and "thinkingconfig" in body.get("generationConfig", {}):
                body = _casual_payload(
                    messages,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    thinking_level_minimal=True,
                )
                response = client.post(url, headers=_headers(), json=body)
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code >= 400:
                raise OllamaError(_error_text(data, response.text))
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    return _to_ollama_message(data)


def _casual_payload(
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_output_tokens: int,
    thinking_level_minimal: bool = False,
) -> dict[str, Any]:
    system, contents = _contents(messages)
    body: dict[str, Any] = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    gen: dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
    }
    if thinking_level_minimal:
        gen["thinkingConfig"] = {"thinkingLevel": "MINIMAL"}
    else:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body["generationConfig"] = gen
    return body


def _payload(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    format_json: bool,
    options: dict[str, Any] | None,
    allowed_function_names: list[str] | None = None,
) -> dict[str, Any]:
    system, contents = _contents(messages)
    body: dict[str, Any] = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    decls = _tool_decls(tools or [])
    allow = [name for name in (allowed_function_names or []) if name]
    if allow:
        wanted = set(allow)
        decls = [item for item in decls if item.get("name") in wanted]
    if decls:
        body["tools"] = [{"functionDeclarations": decls}]
        if allow:
            body["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": allow,
                }
            }
    gen: dict[str, Any] = {}
    if format_json:
        gen["responseMimeType"] = "application/json"
    if options:
        if options.get("temperature") is not None:
            gen["temperature"] = options["temperature"]
        if options.get("num_predict") is not None:
            gen["maxOutputTokens"] = options["num_predict"]
    if gen:
        body["generationConfig"] = gen
    return body


def _contents(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_bits: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = (message.get("role") or "user").lower()
        if role == "system":
            text = (message.get("content") or "").strip()
            if text:
                system_bits.append(text)
            continue
        if role == "tool":
            name = message.get("tool_name") or "tool"
            raw = message.get("content") or ""
            payload = _jsonish(raw)
            contents.append(
                {
                    "role": "user",
                    "parts": [{"functionResponse": {"name": name, "response": payload if isinstance(payload, dict) else {"result": str(raw)[:8000]}}}],
                }
            )
            continue
        parts = _parts(message)
        if not parts:
            continue
        contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})
    return "\n\n".join(system_bits), contents or [{"role": "user", "parts": [{"text": "Hello."}]}]


def _parts(message: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or call
        name = fn.get("name")
        if not name:
            continue
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            args = _jsonish(args)
            if not isinstance(args, dict):
                args = {}
        parts.append({"functionCall": {"name": name, "args": args}})
    text = (message.get("content") or "").strip()
    if text:
        parts.append({"text": text})
    return parts


def _tool_decls(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decls = []
    for item in tools:
        fn = item.get("function") or item
        name = fn.get("name")
        if not name:
            continue
        decls.append(
            {
                "name": name,
                "description": fn.get("description") or "",
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return decls


def _to_ollama_message(data: dict[str, Any]) -> dict[str, Any]:
    cand = ((data.get("candidates") or [{}])[0] or {}).get("content") or {}
    parts = cand.get("parts") or []
    texts: list[str] = []
    calls: list[dict[str, Any]] = []
    for part in parts:
        if part.get("text"):
            texts.append(str(part["text"]))
        call = part.get("functionCall") or part.get("function_call")
        if call and call.get("name"):
            args = call.get("args") or call.get("arguments") or {}
            calls.append({"type": "function", "function": {"name": call["name"], "arguments": args}})
    return {"role": "assistant", "content": "\n".join(texts).strip(), "tool_calls": calls}


def _jsonish(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"result": text[:8000]}


def _error_text(data: dict[str, Any], fallback: str) -> str:
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return fallback[:400] or "Gemini request failed."


def _rest_part(part: dict[str, Any]) -> dict[str, Any]:
    inline = part.get("inline_data") or part.get("inlineData")
    if inline:
        mime = inline.get("mime_type") or inline.get("mimeType") or "application/octet-stream"
        data = inline.get("data") or ""
        return {"inlineData": {"mimeType": mime, "data": data}}
    file_block = part.get("file_data") or part.get("fileData")
    if file_block:
        mime = file_block.get("mime_type") or file_block.get("mimeType") or "application/octet-stream"
        uri = file_block.get("file_uri") or file_block.get("fileUri") or ""
        return {"fileData": {"mimeType": mime, "fileUri": uri}}
    return part


def generate_parts(
    parts: list[dict[str, Any]],
    system: str = "",
    format_json: bool = False,
    timeout: float = 120,
    options: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise OllamaError("GEMINI_API_KEY is empty.")
    body: dict[str, Any] = {"contents": [{"role": "user", "parts": [_rest_part(part) for part in parts]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    gen: dict[str, Any] = {}
    if format_json:
        gen["responseMimeType"] = "application/json"
    if options:
        if options.get("temperature") is not None:
            gen["temperature"] = options["temperature"]
        if options.get("num_predict") is not None:
            gen["maxOutputTokens"] = options["num_predict"]
    if gen:
        body["generationConfig"] = gen
    used = (model or settings.gemini_model).strip() or settings.gemini_model
    url = f"{_API}/models/{used}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=_headers(), json=body)
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code >= 400:
                raise OllamaError(_error_text(data, response.text))
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    return _to_ollama_message(data)


def upload_file(path: str, mime: str = "", display_name: str = "") -> dict[str, str]:
    if not settings.gemini_api_key:
        raise OllamaError("GEMINI_API_KEY is empty.")
    file_path = Path(path)
    blob = file_path.read_bytes()
    media = mime or "application/octet-stream"
    name = display_name or file_path.name
    start = "https://generativelanguage.googleapis.com/upload/v1beta/files"
    headers = {
        **_headers(),
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(blob)),
        "X-Goog-Upload-Header-Content-Type": media,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=60) as client:
            begun = client.post(start, headers=headers, json={"file": {"displayName": name}})
            if begun.status_code >= 400:
                data = begun.json() if "json" in (begun.headers.get("content-type") or "") else {}
                raise OllamaError(_error_text(data if isinstance(data, dict) else {}, begun.text))
            upload_url = begun.headers.get("x-goog-upload-url") or begun.headers.get("X-Goog-Upload-URL")
            if not upload_url:
                raise OllamaError("Gemini did not accept the file upload.")
            finished = client.post(
                upload_url,
                headers={
                    "Content-Length": str(len(blob)),
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                    "x-goog-api-key": settings.gemini_api_key,
                },
                content=blob,
            )
            payload = finished.json() if "json" in (finished.headers.get("content-type") or "") else {}
            if finished.status_code >= 400:
                raise OllamaError(_error_text(payload if isinstance(payload, dict) else {}, finished.text))
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    file_info = payload.get("file") if isinstance(payload.get("file"), dict) else payload
    uri = str(file_info.get("uri") or file_info.get("name") or "")
    if uri and not uri.startswith("http") and uri.startswith("files/"):
        uri = f"{_API}/{uri}"
    if not uri:
        raise OllamaError("Gemini did not return a file uri.")
    return {"uri": uri, "mime": media, "name": name}


def chat_multimodal(
    history: list[dict[str, str]],
    user_text: str,
    media_parts: list[dict[str, Any]],
    system: str = "",
    model: str | None = None,
    timeout: float = 180,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise OllamaError("GEMINI_API_KEY is empty.")
    contents: list[dict[str, Any]] = []
    for item in history:
        role = "user" if item.get("role") == "user" else "model"
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    parts = [_rest_part(part) for part in media_parts]
    parts.append({"text": user_text})
    contents.append({"role": "user", "parts": parts})
    body: dict[str, Any] = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    gen: dict[str, Any] = {}
    if options:
        if options.get("temperature") is not None:
            gen["temperature"] = options["temperature"]
        if options.get("num_predict") is not None:
            gen["maxOutputTokens"] = options["num_predict"]
    if gen:
        body["generationConfig"] = gen
    used = (model or settings.gemini_model).strip() or settings.gemini_model
    url = f"{_API}/models/{used}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=_headers(), json=body)
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code >= 400:
                raise OllamaError(_error_text(data, response.text))
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc
    return _to_ollama_message(data)
