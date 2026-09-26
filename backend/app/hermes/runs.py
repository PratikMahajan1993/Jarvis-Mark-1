"""Hermes Runs API client: start a run, read its event stream, stop, approve.

The browser never sees the Hermes API key. Jarvis sends one new sentence plus
the stored Hermes session id, and forwards tool and text events only.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import httpx

from ..config import settings
from ..intent import is_quote_start

# Spoken text is message deltas only. Reasoning traces stay off the voice line.
_SPEAK_EVENTS = frozenset({"message.delta"})
_FORWARD_EVENTS = frozenset(
    {
        "tool.started",
        "tool.completed",
        "message.delta",
        "approval.request",
        "run.completed",
        "run.failed",
        "run.cancelled",
    }
)


class HermesRunStopped(RuntimeError):
    """The operator cancelled the run. Callers must not fall through to another brain."""


@dataclass
class RunHooks:
    publish: Callable[[dict[str, Any]], None]
    stopped: Callable[[], bool]


_hooks: ContextVar[RunHooks | None] = ContextVar("hermes_run_hooks", default=None)


def set_run_hooks(hooks: RunHooks | None):
    return _hooks.set(hooks)


def reset_run_hooks(token) -> None:
    _hooks.reset(token)


def reasoning_effort_for(message: str, *, casual: bool) -> str:
    """minimal for short chat, low for ordinary shop work, medium only on a quote start."""
    if is_quote_start(message):
        return "medium"
    if casual:
        return "minimal"
    return "low"


def tool_activity_line(tool: str) -> str:
    name = (tool or "").lower()
    if "mail" in name or "email" in name:
        return "reading mail"
    if "quote" in name:
        return "quoting"
    if "calendar" in name:
        return "checking the calendar"
    if "sheet" in name or "shop" in name:
        return "checking the shop"
    pretty = (tool or "a tool").replace("_", " ").strip() or "a tool"
    return f"using {pretty}"


def approval_action(event: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Shape the existing Authorize card understands. Reject stops the run."""
    request_id = str(event.get("request_id") or event.get("id") or "")
    summary = str(
        event.get("command")
        or event.get("description")
        or event.get("preview")
        or event.get("summary")
        or "Hermes is waiting for approval."
    ).strip()
    action_id = f"hermes-approval-{request_id or run_id}"
    return {
        "id": action_id,
        "kind": "hermes_approval",
        "title": "Authorize Hermes",
        "summary": summary[:500],
        "payload": {
            "run_id": run_id,
            "request_id": request_id,
            "hermes_event": "approval.request",
        },
        "agent_id": "ops",
        "tool_name": "hermes_approval",
        "irreversibility": 3,
        "consequence": "Lets this Hermes step continue. Reject stops the run.",
    }


def parse_sse_line(line: str | bytes) -> dict[str, Any] | None:
    """One SSE line. Keepalive comments (`: keepalive`) and reasoning are not events."""
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    text = text.strip()
    if not text or text.startswith(":"):
        return None
    if text.startswith("event:"):
        return None
    if not text.startswith("data:"):
        return None
    raw = text[5:].strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("event") or "")
    if name.startswith("reasoning"):
        return None
    return payload


def _emit(event: dict[str, Any]) -> None:
    hooks = _hooks.get()
    if hooks is None:
        return
    if hooks.stopped():
        raise HermesRunStopped("Hermes run stopped")
    hooks.publish(dict(event))


def _check_stopped() -> None:
    hooks = _hooks.get()
    if hooks is not None and hooks.stopped():
        raise HermesRunStopped("Hermes run stopped")


def iter_sse_payloads(lines: Iterator[str | bytes]) -> Iterator[dict[str, Any]]:
    for line in lines:
        _check_stopped()
        payload = parse_sse_line(line)
        if payload is None:
            continue
        name = str(payload.get("event") or "")
        if name.startswith("reasoning"):
            continue
        yield payload


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.hermes_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


def stop_hermes_run(hermes_run_id: str, *, base_url: str | None = None) -> dict[str, Any]:
    base = (base_url or settings.hermes_gateway_url or "").rstrip("/")
    if not base or not hermes_run_id:
        raise RuntimeError("Hermes run is not active")
    url = f"{base}/v1/runs/{hermes_run_id}/stop"
    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, headers=_headers(), json={})
    if response.status_code >= 400:
        raise RuntimeError(f"Hermes stop HTTP {response.status_code}: {(response.text or '')[:300]}")
    try:
        body = response.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {"status": "stopping"}


def approve_hermes_run(
    hermes_run_id: str,
    choice: str,
    request_id: str = "",
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    base = (base_url or settings.hermes_gateway_url or "").rstrip("/")
    if not base or not hermes_run_id:
        raise RuntimeError("Hermes run is not active")
    url = f"{base}/v1/runs/{hermes_run_id}/approval"
    body: dict[str, Any] = {"choice": choice}
    if request_id:
        body["request_id"] = request_id
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"Hermes approval HTTP {response.status_code}: {(response.text or '')[:300]}")
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {"choice": choice}


def consume_hermes_run(
    *,
    base_url: str,
    message: str,
    session_id: str | None,
    instructions: str,
    casual: bool,
    timeout: float,
) -> tuple[str, str, int, list[dict[str, Any]]]:
    """POST /v1/runs and read the event stream until the run finishes.

    Returns (speak, hermes_session_id, elapsed_ms, forwarded_events).
    `session_id` is the stored Hermes session, not a replay of Jarvis messages.
    """
    import time

    _check_stopped()
    effort = reasoning_effort_for(message, casual=casual)
    body: dict[str, Any] = {
        "model": "hermes-agent",
        "input": message,
        "instructions": instructions,
        "model_options": {"reasoning_effort": effort},
    }
    if session_id:
        body["session_id"] = session_id
    headers = _headers()
    started = time.monotonic()
    forwarded: list[dict[str, Any]] = []
    deltas: list[str] = []
    output = ""
    failed = ""
    run_id = ""
    try:
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.post(f"{base_url}/v1/runs", headers=headers, json=body)
            except httpx.TimeoutException as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                raise RuntimeError(
                    f"Hermes timed out after {timeout:.0f}s ({elapsed_ms}ms)"
                ) from exc
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Hermes runs HTTP {response.status_code}: {(response.text or '')[:500]}"
                )
            accepted = response.json() if response.content else {}
            if not isinstance(accepted, dict):
                accepted = {}
            run_id = str(accepted.get("run_id") or "")
            if not run_id:
                raise RuntimeError("Hermes runs response did not include run_id")
            hooks = _hooks.get()
            if hooks is not None and hooks.stopped():
                try:
                    stop_hermes_run(run_id, base_url=base_url)
                except Exception:
                    pass
                raise HermesRunStopped("Hermes run stopped")
            _emit({"event": "run.started", "run_id": run_id})
            try:
                with client.stream(
                    "GET",
                    f"{base_url}/v1/runs/{run_id}/events",
                    headers=headers,
                ) as streamed:
                    if streamed.status_code >= 400:
                        raise RuntimeError(
                            f"Hermes events HTTP {streamed.status_code}"
                        )
                    for payload in iter_sse_payloads(streamed.iter_lines()):
                        name = str(payload.get("event") or "")
                        if name in {"tool.started", "tool.completed"}:
                            tool = str(payload.get("tool") or "")
                            payload = dict(payload)
                            payload["message"] = tool_activity_line(tool)
                        if name == "approval.request":
                            payload = dict(payload)
                            payload["pending"] = approval_action(payload, run_id)
                        if name in _SPEAK_EVENTS:
                            deltas.append(str(payload.get("delta") or ""))
                        if name == "run.completed":
                            output = str(payload.get("output") or "")
                        if name == "run.failed":
                            failed = str(payload.get("error") or "Hermes run failed")
                        if name == "run.cancelled":
                            raise HermesRunStopped("Hermes run cancelled")
                        if name in _FORWARD_EVENTS:
                            forwarded.append(payload)
                            _emit(payload)
                        if name in {"run.completed", "run.failed"}:
                            break
            except httpx.TimeoutException as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                raise RuntimeError(
                    f"Hermes timed out after {timeout:.0f}s ({elapsed_ms}ms)"
                ) from exc
    except HermesRunStopped:
        raise
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if failed:
        raise RuntimeError(failed)
    speak = "".join(deltas).strip() or output.strip()
    hermes_session = session_id or run_id
    return speak, hermes_session, elapsed_ms, forwarded
