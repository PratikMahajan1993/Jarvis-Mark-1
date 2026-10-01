---
name: jarvis-architecture
description: >
  Locked Jarvis architecture, tech stack, ports, and workflows. Use when changing
  HUD/API behavior, adding features, debugging mail/TTS/Hermes/conversations, or
  when unsure which module owns a concern. Protects the working desk model.
---

# Jarvis architecture

## Read first

- `docs/SYSTEM_TRUTH.md` — what is true today and what is locked
- `docs/ROADMAP.md` — what is next

## Stack

- **HUD:** Next.js App Router. `app/layout.tsx` → `JarvisRoot`; `/` → `Desk` (`frontend/src/core/desk/Desk.tsx`). Turn FSM is the pure reducer in `frontend/src/lib/orchestratorFsm.ts`.
- **API:** FastAPI `backend/app/main.py` → agent/tools/conversations.
- **Brain:** Hermes gateway `http://127.0.0.1:8642` preferred; Gemini/Ollama fallback.
- **TTS:** Gemini TTS, male voice Charon. Lite, then 3.8 Flash, then 2.5 Flash. Browser plays WAV from `/api/tts`. Quota exhaustion stays silent.
- **Memory:** SQLite under `data/memory/` is the source of truth. Search reads the local LanceDB mirror when available, SQLite otherwise.

## Ownership map

| Concern | Module |
| ------- | ------ |
| Chat / tools | `backend/app/agent.py`, `tools/registry.py` |
| Semantic router | `core/router.py` (ONNX first), `semantic_router.py` (Gemini + keywords); UI commands via `handle_ui_command` |
| Intent / mail fast path | `intent.py`, `snapshot.py` |
| Quote playbook | `quote.py`, `hermes/playbooks/quote/`, `hermes/mcp_server.py`, `intent.is_quote_start`, `_hermes_reply` in `agent.py` |
| HUD sections | `section_hint.py` stamps `ui.section`; `applyServerHint` in `core/desk/controller.ts` scrolls |
| Conversations desk | `conversations.py`, `db.py` (`MAX_EXPANDED = 3`) |
| Speak / prefetch | `gemini_tts.py`, `main.py` `/api/tts`, `frontend/src/lib/voice.ts` |
| Suggested tasks / weather | `office_day.py`, `SuggestedTasksPanel.tsx`, `WeatherCard.tsx` |
| HITL | `pending_actions` + `HitlModal`; `loadSessionSurface` restores first pending |
| Capability turn log | `turn_log.py` → `work/LAST_TURNS.md` + `/api/turns/recent` |

## Do not

- Speak through Voicebox or `speechSynthesis`. Desk speech is Gemini TTS only.
- Put board scroll on `SpotlightCard`'s outer wrapper (use `bodyClassName`).
- Raise concurrent open notes above 3.
- Reintroduce `OrchestratorShell` or `HudShell`, or open a second WebGL context.
- Invent mail/calendar/shop numbers in the brain.

## Verify

- API health: `GET http://127.0.0.1:8000/api/health`
- HUD: `http://127.0.0.1:3000`
- Offline tests: `python -m pytest -m "not live_service"` (see `backend/requirements-dev.txt`)
- Frontend: `npm run typecheck` and `npm run lint` in `frontend/`
- Prefer killing duplicate listeners on `:8000` before restart.
