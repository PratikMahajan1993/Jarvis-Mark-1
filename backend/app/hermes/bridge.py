"""Bridge: Jarvis chat turns → Hermes (warm API gateway, CLI oneshot fallback)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .. import db
from ..agents import agent_code, agent_for_kind, agent_status_payload
from ..config import settings
from ..intent import classify, looks_like_work
from ..schemas import ActivityEvent, AgentStatus, ChatResponse, PendingAction, Scene, Widget
from .circuit_breaker import gateway_circuit
from .runs import HermesRunStopped, consume_hermes_run

# Tool-ops and quotes keep settings.hermes_timeout_sec (30s). Casual gateway calls do not.
CASUAL_GATEWAY_TIMEOUT_SEC = 12.0

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_SESSION_FILE = "hermes_sessions.json"
_SESSION_ID_RE = re.compile(r"(?im)^\s*session_id:\s*(\S+)\s*$")
_RESUME_RE = re.compile(r"hermes\s+--resume\s+(\S+)")


def hermes_cli_available() -> bool:
    return bool(shutil.which(settings.hermes_bin) or Path(settings.hermes_bin).exists())


def hermes_gateway_url() -> str:
    return (settings.hermes_gateway_url or "").rstrip("/")


def hermes_gateway_reachable(timeout: float = 1.5) -> bool:
    """True when the warm API server answers /health.

    An open circuit skips this probe and reports unreachable so the caller
    uses the existing Hermes-miss path. No parallel fallback is started here.
    """
    base = hermes_gateway_url()
    if not base or not settings.hermes_api_key:
        return False
    if not gateway_circuit.before_health_probe():
        return False
    ok = False
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{base}/health")
            ok = r.status_code == 200
    except Exception:
        ok = False
    finally:
        gateway_circuit.after_health_probe(ok)
    return ok


def hermes_available() -> bool:
    if not settings.hermes_enabled:
        return False
    if settings.hermes_prefer_gateway:
        # Gateway preferred: skip cold CLI when down — agent soft-falls to Gemini/legacy.
        return hermes_gateway_reachable()
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


def _quote_conversation_key(session_id: str) -> str:
    return f"quote:{session_id}"


def _load_sessions_data() -> dict[str, Any]:
    path = _sessions_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_sessions_data(data: dict[str, Any]) -> None:
    path = _sessions_path()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_quote_conversation_title(session_id: str) -> str | None:
    value = _load_sessions_data().get(_quote_conversation_key(session_id))
    return str(value) if value else None


def _save_quote_conversation_title(session_id: str, title: str) -> None:
    data = _load_sessions_data()
    data[_quote_conversation_key(session_id)] = title
    _write_sessions_data(data)


def _new_quote_conversation_title() -> str:
    return f"jarvis-quote-{uuid.uuid4().hex[:12]}"


_NON_QUOTE_CONVERSATION_KINDS = frozenset(
    {"shop_read", "shop_write", "shop_bind", "shop_create", "briefing"}
)


def _turn_uses_default_hermes_conversation(message: str) -> bool:
    kind = classify(message).kind
    if kind.startswith("mail_"):
        return True
    if kind.startswith("calendar_"):
        return True
    return kind in _NON_QUOTE_CONVERSATION_KINDS


def hermes_conversation_title(message: str, session_id: str) -> str:
    """Hermes gateway conversation + X-Hermes-Session-Id for this turn."""
    from ..intent import is_quote_start

    if is_quote_start(message):
        title = _new_quote_conversation_title()
        _save_quote_conversation_title(session_id, title)
        return title
    saved = _load_quote_conversation_title(session_id)
    if saved and not _turn_uses_default_hermes_conversation(message):
        return saved
    return hermes_session_title(session_id)


def hermes_session_title(session_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", (session_id or "default").strip()) or "default"
    return f"jarvis-{safe}"


def _hermes_skills_home() -> Path:
    if settings.hermes_home:
        return Path(settings.hermes_home).expanduser()
    return Path.home() / ".hermes"


def ensure_playbooks_installed() -> bool:
    """Copy repo quote playbook into Hermes skills dir (idempotent). No CLI required."""
    source = Path(__file__).resolve().parent / "playbooks" / "quote"
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        return False
    dest = _hermes_skills_home() / "skills" / "shop" / "quote"
    dest.mkdir(parents=True, exist_ok=True)

    def _copy_tree(src: Path, dst: Path) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                _copy_tree(item, target)
            else:
                shutil.copy2(item, target)

    for name in ("SKILL.md", "notes.md"):
        shutil.copy2(source / name, dest / name)
    for sub in ("files", "examples"):
        sub_src = source / sub
        if sub_src.is_dir():
            _copy_tree(sub_src, dest / sub)
    return True


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


def _speak_usable(speak: str, *, casual: bool) -> bool:
    """Reject empty / tool-dump / truncated junk so agent can fall back to Gemini."""
    text = (speak or "").strip()
    if len(text) < 2:
        return False
    low = text.lower()
    if low.startswith(("traceback", "exception:", "error:", "http 4", "http 5")):
        return False
    # Tiny pipe-table fragments like "Theater|...|" are never valid HUD speech
    if text.count("|") >= 2 and len(text) < 48:
        return False
    if casual and len(text) > 600:
        return False
    return True


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
                irreversibility=int(row.get("irreversibility") or 2),
                consequence=str(row.get("consequence") or ""),
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
        from ..casual_voice import CASUAL_PERSONA

        return (
            "[Jarvis: dry, sharp, wickedly witty aide. One crisp aside then the answer. "
            f"{CASUAL_PERSONA} No tools.]\n\n" + message
        )
    if not known:
        return (
            "[Jarvis mode: Operations Manager + personal assistant for a machining firm. "
            "You have a Jarvis MCP server. Prefer its tools (names look like "
            "mcp__jarvis__jarvis_draft_email, mcp__jarvis__jarvis_search_emails, "
            "mcp__jarvis__jarvis_read_shop_sheet, etc.). "
            f"Jarvis session id for HITL queues: {session_id}. "
            "Batch multi-step quote and shop tool calls with execute_code. "
            "External writes queue for human authorization — do not claim they were sent.]\n\n"
            + message
        )
    return message


def _instructions(casual: bool, session_id: str, message: str = "") -> str:
    if casual:
        from ..casual_voice import CASUAL_PERSONA

        return (
            "You are Jarvis: dry, sharp, wickedly witty British aide. "
            f"{CASUAL_PERSONA} "
            "Bare greetings use the same lines as social_fallback in casual_voice. "
            "Reply in one or two short spoken sentences unless they ask to expand. Do not use tools."
        )
    base = (
        "You are Jarvis: Operations Manager + personal assistant for a machining firm. "
        "Prefer Jarvis MCP tools (jarvis_draft_email, jarvis_search_emails, "
        "jarvis_read_shop_sheet, etc.). "
        f"HITL session id: {session_id}. "
        "Multi-step quote or shop work: batch the tool calls with execute_code "
        "in one step instead of a separate model turn per call. "
        "External writes (mail send, calendar write, quote send, sheet write) "
        "still go through Jarvis tools and only queue Authorize. Never claim they were sent. "
        "Do not call reason_rfq unless a drawing path, mail id, or drawing conversation id is already known. "
        "If it is not, ask which drawing — inbox attachment, file on the desk, or photo."
    )
    if message:
        from ..intent import is_quote_start

        if is_quote_start(message):
            base += (
                " Quote start: load skill shop-quote (skill_view). "
                "If there is no local drawing path yet, ask which drawing and where it lives "
                "(inbox, file on the desk, photo). Do not call reason_rfq or analyze until a path exists."
            )
    return base


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


_WARM_LOCK = threading.Lock()
_WARM_AT: dict[str, float] = {}
_WARM_STATUS: dict[str, str] = {}
WARM_TTL_SEC = 180.0


def hermes_warm_status(session_id: str = "default") -> dict[str, Any]:
    """Expose warm state for HUD bootstrap / capability tests."""
    key = (session_id or "default").strip() or "default"
    last = _WARM_AT.get(key)
    return {
        "ok": True,
        "session_id": key,
        "enabled": settings.hermes_enabled,
        "gateway": hermes_gateway_reachable(timeout=1.5),
        "status": _WARM_STATUS.get(key, "idle"),
        "last_warm_at": last,
        "fresh": bool(last and (time.monotonic() - last) < WARM_TTL_SEC),
    }


def warm_hermes(session_id: str = "default", *, force: bool = False) -> dict[str, Any]:
    """Prime the Hermes gateway for a Jarvis session (HUD open / API startup).

    Confirms /health. Live turns use the Runs API, not a blocking chat ping.
    """
    key = (session_id or "default").strip() or "default"
    if not settings.hermes_enabled or not settings.hermes_prefer_gateway:
        return {**hermes_warm_status(key), "started": False, "reason": "hermes_disabled"}

    now = time.monotonic()
    with _WARM_LOCK:
        if not force and key in _WARM_AT and (now - _WARM_AT[key]) < WARM_TTL_SEC:
            return {**hermes_warm_status(key), "started": False, "reason": "fresh"}
        if _WARM_STATUS.get(key) == "running":
            return {**hermes_warm_status(key), "started": False, "reason": "running"}
        _WARM_STATUS[key] = "running"

    def _run() -> None:
        try:
            if not hermes_gateway_reachable(timeout=2.0):
                _WARM_STATUS[key] = "unreachable"
                return
            _WARM_AT[key] = time.monotonic()
            _WARM_STATUS[key] = "ready"
        except Exception:
            _WARM_STATUS[key] = "error"

    threading.Thread(target=_run, name=f"jarvis-hermes-warm-{key}", daemon=True).start()
    return {**hermes_warm_status(key), "started": True}


def _hermes_session_key(title: str) -> str:
    return f"hermes:{title}"


def _load_conversation_hermes_id(title: str, session_id: str) -> str | None:
    """Hermes session id for this conversation, from data/hermes_sessions.json."""
    data = _load_sessions_data()
    stored = data.get(_hermes_session_key(title))
    if not stored and title == hermes_session_title(session_id):
        stored = data.get(session_id)
    return str(stored) if stored else None


def _store_conversation_hermes_id(title: str, hermes_session: str) -> None:
    if not title or not hermes_session:
        return
    data = _load_sessions_data()
    data[_hermes_session_key(title)] = hermes_session
    _write_sessions_data(data)


def _run_via_gateway(message: str, session_id: str, casual: bool) -> tuple[str, str, int]:
    """Runs API path. Returns (speak, hermes_session_id, elapsed_ms).

    Sends only the new sentence. Hermes loads its own transcript from the
    session id stored in hermes_sessions.json.
    """
    base = hermes_gateway_url()
    title = hermes_session_title(session_id) if casual else hermes_conversation_title(message, session_id)
    stored = _load_conversation_hermes_id(title, session_id)
    timeout = float(settings.hermes_timeout_sec)
    if casual:
        timeout = min(timeout, CASUAL_GATEWAY_TIMEOUT_SEC)
    try:
        speak, hermes_session, elapsed_ms, _events = consume_hermes_run(
            base_url=base,
            message=message,
            session_id=stored,
            instructions=_instructions(casual, session_id, message),
            casual=casual,
            timeout=timeout,
        )
    except HermesRunStopped:
        raise
    except Exception:
        gateway_circuit.record_failure()
        raise
    if hermes_session:
        _store_conversation_hermes_id(title, hermes_session)
    cleaned = _clean_speak(speak)
    if not cleaned:
        raise RuntimeError("Hermes returned no speakable text")
    return cleaned, hermes_session or title, elapsed_ms


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


def run_hermes_turn(message: str, session_id: str = "default", *, casual: bool | None = None) -> ChatResponse:
    if not settings.hermes_enabled:
        raise RuntimeError("Hermes is not available")

    if casual is None:
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
    elif settings.hermes_prefer_gateway:
        raise RuntimeError(
            "Hermes gateway is unreachable; soft fallback to legacy chat "
            "(start with: hermes gateway run, API_SERVER_ENABLED=true)"
        )
    else:
        if not hermes_cli_available():
            raise RuntimeError(
                "Hermes CLI is unavailable. "
                "Start with: hermes gateway run (API_SERVER_ENABLED=true)"
            )
        speak, hermes_id, elapsed_ms = _run_via_cli(message, session_id, casual)

    from ..metrics import new_mission_id, record_hermes_latency, record_mission_step

    if not _speak_usable(speak, casual=casual):
        if transport == "gateway":
            gateway_circuit.record_failure()
        record_hermes_latency(
            session_id=session_id,
            transport=transport,
            casual=casual,
            latency_ms=elapsed_ms,
            ok=False,
        )
        raise RuntimeError("Hermes returned empty or unusable speech")

    if transport == "gateway":
        gateway_circuit.record_success()

    mission_id = new_mission_id()
    record_hermes_latency(
        session_id=session_id,
        transport=transport,
        casual=casual,
        latency_ms=elapsed_ms,
        ok=True,
    )
    record_mission_step(
        session_id=session_id,
        mission_id=mission_id,
        step=0,
        role="prompt",
        detail=message[:800],
        latency_ms=None,
        status="ok",
    )
    record_mission_step(
        session_id=session_id,
        mission_id=mission_id,
        step=1,
        role="hermes",
        detail=(speak or "")[:800],
        latency_ms=elapsed_ms,
        status="ok",
    )

    warm_key = (session_id or "default").strip() or "default"
    _WARM_AT[warm_key] = time.monotonic()
    _WARM_STATUS[warm_key] = "ready"

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

    # Speak-only Hermes turns: VoiceLine carries the reply — no empty decorative board.
    scene = Scene(title="", widgets=[])
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
