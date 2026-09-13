"""Bridge: Jarvis chat turns → Hermes (warm API gateway, CLI oneshot fallback)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .. import db
from ..agents import agent_code, agent_for_kind, agent_status_payload
from ..config import settings
from ..intent import classify, looks_like_work
from ..schemas import ActivityEvent, AgentStatus, ChatResponse, PendingAction, Scene, Widget

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_SESSION_FILE = "hermes_sessions.json"
_SESSION_ID_RE = re.compile(r"(?im)^\s*session_id:\s*(\S+)\s*$")
_RESUME_RE = re.compile(r"hermes\s+--resume\s+(\S+)")


def hermes_cli_available() -> bool:
    return bool(shutil.which(settings.hermes_bin) or Path(settings.hermes_bin).exists())


def hermes_gateway_url() -> str:
    return (settings.hermes_gateway_url or "").rstrip("/")


def hermes_gateway_reachable(timeout: float = 1.5) -> bool:
    """True when the warm API server answers /health."""
    base = hermes_gateway_url()
    if not base or not settings.hermes_api_key:
        return False
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{base}/health")
            return r.status_code == 200
    except Exception:
        return False


def hermes_available() -> bool:
    if not settings.hermes_enabled:
        return False
    if settings.hermes_prefer_gateway and hermes_gateway_reachable():
        return True
    return hermes_cli_available()


def _sessions_path() -> Path:
    return settings.data_dir / _SESSION_FILE


def _load_hermes_session(session_id: str) -> str | None:
    path = _sessions_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get(session_id)
    return str(value) if value else None


def _save_hermes_session(session_id: str, hermes_id: str) -> None:
    path = _sessions_path()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    data[session_id] = hermes_id
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def hermes_session_title(session_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", (session_id or "default").strip()) or "default"
    return f"jarvis-{safe}"


def ensure_jarvis_mcp_registered() -> bool:
    """Idempotently register the Jarvis MCP stdio server with Hermes."""
    if not hermes_cli_available():
        return False
    python = sys_executable()
    module = "app.hermes.mcp_server"
    backend = str(Path(__file__).resolve().parents[2])
    listed = subprocess.run(
        [settings.hermes_bin, "mcp", "list"],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ},
    )
    if listed.returncode == 0 and settings.hermes_mcp_name in (listed.stdout or ""):
        return True
    cmd = [
        settings.hermes_bin,
        "mcp",
        "add",
        settings.hermes_mcp_name,
        "--command",
        python,
        "--env",
        f"PYTHONPATH={backend}",
        "JARVIS_SESSION_ID=default",
        "--args",
        "-m",
        module,
    ]
    result = subprocess.run(
        cmd,
        input="Y\n",
        capture_output=True,
        text=True,
        timeout=120,
        cwd=backend,
        env={**os.environ},
    )
    return result.returncode == 0 or settings.hermes_mcp_name in ((result.stdout or "") + (result.stderr or ""))


def sys_executable() -> str:
    return str(Path(sys_path_python()))


def sys_path_python() -> str:
    import sys

    return sys.executable


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text or "")


def _extract_session_id(*blobs: str) -> str | None:
    for blob in blobs:
        text = _strip_ansi(blob or "")
        match = _SESSION_ID_RE.search(text)
        if match:
            return match.group(1).strip()
        match = _RESUME_RE.search(text)
        if match:
            return match.group(1).strip()
        for line in text.splitlines():
            raw = line.strip()
            if raw.lower().startswith("session:"):
                parts = raw.split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip().split()[0]
    return None


def _clean_speak(text: str) -> str:
    speak = _strip_ansi(text or "").strip()
    if not speak:
        return ""
    for marker in ("\nsession_id:", "\nResume this session", "\nSession:"):
        if marker in speak:
            speak = speak.split(marker, 1)[0].strip()
    lines = []
    for ln in speak.splitlines():
        raw = ln.strip()
        if not raw:
            lines.append("")
            continue
        if raw.startswith(("──", "╭", "╰", "│", "☤")):
            inner = raw.strip("╭╮╰╯─│ ☤").strip()
            if inner:
                lines.append(inner)
            continue
        if raw.startswith(("Query:", "Initializing agent", "Title:", "Duration:", "Messages:", "Goodbye")):
            continue
        lines.append(ln.rstrip())
    speak = "\n".join(lines).strip()
    speak = re.sub(r"[*`_]{1,3}", "", speak)
    speak = re.sub(r"^#{1,6}\s+", "", speak, flags=re.M)
    speak = re.sub(r"\n{3,}", "\n\n", speak)
    return speak


def _parse_hermes_output(stdout: str, stderr: str) -> tuple[str, str | None]:
    """Quiet (-Q) mode: final answer on stdout, `session_id: …` on stderr."""
    hermes_id = _extract_session_id(stderr, stdout)
    speak = _clean_speak(stdout)
    if not speak:
        speak = _clean_speak(_strip_ansi(stdout or "") + "\n" + _strip_ansi(stderr or ""))
        if hermes_id and speak.endswith(hermes_id):
            speak = speak[: -len(hermes_id)].strip()
        speak = _clean_speak(speak)
    return speak, hermes_id


def is_casual_message(message: str) -> bool:
    """Public alias used by the agent router for the fast non-Hermes path."""
    return _is_casual(message)


def _is_casual(message: str) -> bool:
    intent = classify(message)
    if intent.kind != "chat":
        return False
    return not looks_like_work(message)


def _pending_models(session_id: str) -> list[PendingAction]:
    items = []
    for row in db.list_focused_pending(session_id) or db.list_pending(session_id):
        items.append(
            PendingAction(
                id=row["id"],
                kind=row["kind"],
                title=row["title"],
                summary=row["summary"],
                payload=row.get("payload") or {},
                agent_id=row.get("agent_id") or agent_for_kind(row["kind"]),
                tool_name=row.get("tool_name") or "",
            )
        )
    return items


def _activity_from_pending(pending: list[PendingAction]) -> list[ActivityEvent]:
    now = datetime.now().strftime("%H:%M:%S")
    events: list[ActivityEvent] = []
    for item in pending[:3]:
        code = item.agent_id or "ops"
        events.append(
            ActivityEvent(
                id=item.id,
                time=now,
                agent=agent_code(code),
                message=f"Awaiting clearance: {item.title}",
            )
        )
    return events


def _build_query(message: str, session_id: str, casual: bool, known: str | None) -> str:
    if casual:
        return (
            "[Jarvis: brief, candid personal assistant. One or two short sentences. "
            "No tools.]\n\n" + message
        )
    if not known:
        return (
            "[Jarvis mode: Operations Manager + personal assistant for a machining firm. "
            "You have a Jarvis MCP server. Prefer its tools (names look like "
            "mcp__jarvis__jarvis_draft_email, mcp__jarvis__jarvis_search_emails, "
            "mcp__jarvis__jarvis_read_shop_sheet, etc.). "
            f"Jarvis session id for HITL queues: {session_id}. "
            "External writes queue for human authorization — do not claim they were sent.]\n\n"
            + message
        )
    return message


def _instructions(casual: bool, session_id: str) -> str:
    if casual:
        return (
            "You are Jarvis: brief, candid personal assistant. "
            "Reply in one or two short sentences. Do not use tools."
        )
    return (
        "You are Jarvis: Operations Manager + personal assistant for a machining firm. "
        "Prefer Jarvis MCP tools (jarvis_draft_email, jarvis_search_emails, "
        "jarvis_read_shop_sheet, etc.). "
        f"HITL session id: {session_id}. "
        "External writes queue for human authorization — never claim they were sent."
    )


def _extract_responses_text(payload: dict[str, Any]) -> str:
    """Pull assistant text from OpenAI Responses API payload."""
    output = payload.get("output")
    chunks: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" or item.get("role") == "assistant":
                content = item.get("content")
                if isinstance(content, str):
                    chunks.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            text = part.get("text") or part.get("output_text")
                            if text:
                                chunks.append(str(text))
                        elif isinstance(part, str):
                            chunks.append(part)
            elif item.get("type") == "output_text" and item.get("text"):
                chunks.append(str(item["text"]))
    if chunks:
        return _clean_speak("\n".join(chunks))
    # Fallbacks some Hermes builds use
    for key in ("output_text", "response", "text"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return _clean_speak(val)
    choice = (payload.get("choices") or [None])[0]
    if isinstance(choice, dict):
        msg = choice.get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            return _clean_speak(str(msg["content"]))
    return ""


def _run_via_gateway(message: str, session_id: str, casual: bool) -> tuple[str, str, int]:
    """Warm API path. Returns (speak, session_label, elapsed_ms)."""
    base = hermes_gateway_url()
    title = hermes_session_title(session_id)
    headers = {
        "Authorization": f"Bearer {settings.hermes_api_key}",
        "Content-Type": "application/json",
        "X-Hermes-Session-Id": title,
        "X-Hermes-Session-Key": f"jarvis:{session_id}",
    }
    body: dict[str, Any] = {
        "model": "hermes-agent",
        "input": message,
        "instructions": _instructions(casual, session_id),
        "conversation": title,
        "store": True,
    }
    timeout = float(settings.hermes_timeout_sec)
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{base}/v1/responses", headers=headers, json=body)
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raise RuntimeError(
            f"Hermes timed out after {settings.hermes_timeout_sec:.0f}s ({elapsed_ms}ms)"
        ) from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if r.status_code >= 400:
        detail = (r.text or "")[:500]
        raise RuntimeError(f"Hermes gateway HTTP {r.status_code}: {detail}")
    payload = r.json()
    speak = _extract_responses_text(payload)
    hermes_id = str(payload.get("id") or title)
    if speak:
        return speak, hermes_id, elapsed_ms
    # Fallback: chat completions (stateless messages, still warm process)
    chat_body = {
        "model": "hermes-agent",
        "messages": [
            {"role": "system", "content": _instructions(casual, session_id)},
            {"role": "user", "content": message},
        ],
        "stream": False,
    }
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            r2 = client.post(f"{base}/v1/chat/completions", headers=headers, json=chat_body)
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raise RuntimeError(
            f"Hermes timed out after {settings.hermes_timeout_sec:.0f}s ({elapsed_ms}ms)"
        ) from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if r2.status_code >= 400:
        raise RuntimeError(f"Hermes gateway chat HTTP {r2.status_code}: {(r2.text or '')[:500]}")
    data = r2.json()
    speak = _extract_responses_text(data)
    return speak or "I am here.", title, elapsed_ms


def _run_via_cli(message: str, session_id: str, casual: bool) -> tuple[str, str | None, int]:
    """Cold CLI oneshot path (fallback). Returns (speak, hermes_id, elapsed_ms)."""
    if not hermes_cli_available():
        raise RuntimeError("Hermes CLI is not available")

    backend = str(Path(__file__).resolve().parents[2])
    env = {
        **os.environ,
        "JARVIS_SESSION_ID": session_id,
        "PYTHONPATH": backend + os.pathsep + env_pythonpath(backend),
    }
    if settings.hermes_home:
        env["HERMES_HOME"] = settings.hermes_home

    title = hermes_session_title(session_id)
    known = _load_hermes_session(session_id)
    query = _build_query(message, session_id, casual, known)

    cmd = [
        settings.hermes_bin,
        "chat",
        "-q",
        query,
        "--oneshot",
        "-Q",
        "--source",
        "tool",
    ]
    if known:
        cmd.extend(["--resume", known])
    else:
        cmd.extend(["--continue", title, "--create-if-missing"])

    if casual:
        cmd.extend(["--safe-mode", "--reasoning", "minimal", "-t", "clarify"])
    else:
        cmd.extend(["--accept-hooks", "--reasoning", "low"])

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=float(settings.hermes_timeout_sec),
            cwd=backend,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raise RuntimeError(
            f"Hermes timed out after {settings.hermes_timeout_sec:.0f}s ({elapsed_ms}ms)"
        ) from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    speak, hermes_id = _parse_hermes_output(proc.stdout or "", proc.stderr or "")
    if hermes_id:
        _save_hermes_session(session_id, hermes_id)
    if proc.returncode not in (0, None) and not speak:
        err = _strip_ansi((proc.stderr or proc.stdout or "Hermes failed")[-500:])
        raise RuntimeError(err)
    return speak or "I am here.", hermes_id, elapsed_ms


def run_hermes_turn(message: str, session_id: str = "default") -> ChatResponse:
    if not settings.hermes_enabled:
        raise RuntimeError("Hermes is not available")

    casual = _is_casual(message)
    title = hermes_session_title(session_id)
    transport = "cli"
    speak = ""
    hermes_id: str | None = None
    elapsed_ms = 0

    use_gateway = bool(settings.hermes_prefer_gateway and hermes_gateway_reachable())
    if use_gateway:
        # Warm path only — on timeout/error let the agent fall back to Gemini (no cold CLI).
        speak, hermes_id, elapsed_ms = _run_via_gateway(message, session_id, casual)
        transport = "gateway"
        if hermes_id:
            _save_hermes_session(session_id, hermes_id)
    else:
        if not hermes_cli_available():
            raise RuntimeError(
                "Hermes gateway is down and CLI is unavailable. "
                "Start with: hermes gateway run (API_SERVER_ENABLED=true)"
            )
        speak, hermes_id, elapsed_ms = _run_via_cli(message, session_id, casual)

    pending = _pending_models(session_id)
    if pending:
        db.set_focus_pending(session_id, pending[0].id)

    agent_states: dict[str, str] = {}
    for item in pending:
        aid = item.agent_id or agent_for_kind(item.kind)
        agent_states[aid] = "waiting"

    activity = _activity_from_pending(pending)
    if not activity:
        activity = [
            ActivityEvent(
                id=f"turn-{int(time.time())}",
                time=datetime.now().strftime("%H:%M:%S"),
                agent="SYS",
                message=(
                    f"{'Casual' if casual else 'Work'} · {transport} · "
                    f"{elapsed_ms}ms · session {hermes_id or title}"
                ),
            )
        ]

    scene = Scene(title="Jarvis", subtitle="Hermes", widgets=[])
    if pending:
        scene = Scene(
            title="Authorization required",
            subtitle=pending[0].title,
            widgets=[Widget(type="markdown", text=pending[0].summary)],
        )

    return ChatResponse(
        speak=speak,
        reply=speak,
        scene=scene,
        pending=pending,
        activity=activity,
        agents=[AgentStatus(**row) for row in agent_status_payload(agent_states)],
        offline=False,
    )


def env_pythonpath(backend: str) -> str:
    return os.environ.get("PYTHONPATH") or ""
