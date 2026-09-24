---
name: jarvis-architecture
description: >
  Locked Jarvis architecture, tech stack, ports, and workflows. Use when changing
  HUD/API behavior, adding features, debugging mail/TTS/Hermes/conversations, or
  when unsure which module owns a concern. Protects the working desk model.
---

# Jarvis architecture

## Read first

- `docs/CURRENT.md` — what works today
- `AGENTS.md` — specialist roster
- For deep paths, see [reference.md](reference.md)

## Stack

- **HUD:** Next.js App Router, `OrchestratorShell.tsx` + strict FSM in `frontend/src/lib/orchestratorFsm.ts`
- **API:** FastAPI `backend/app/main.py` → agent/tools/conversations
- **Brain:** Hermes gateway `http://127.0.0.1:8642` preferred; Gemini/Ollama fallback
- **TTS:** Voicebox `http://127.0.0.1:17493` — Jarvis calls **`/generate`**, browser plays WAV from `/api/tts`
- **Memory:** SQLite under `data/memory/` is the source of truth. Search reads the local LanceDB mirror when it is available, and SQLite when it is not.

## Ownership

| Concern | Module |
| ------- | ------ |
| Chat / tools | `backend/app/agent.py`, `tools/registry.py` |
| Semantic router | `semantic_router.py` — Gemini flash intent + `target_agent`; UI commands via `handle_ui_command` |
| Intent / mail fast path | `intent.py`, `snapshot.py` — local mail/calendar/briefing skip Hermes when snapshot-ready |
| Quote playbook | `quote.py`, `hermes/playbooks/quote/`, `hermes/mcp_server.py`, `intent.is_quote_start`, Hermes timeout fallback in `agent.py` — see skill `jarvis-quote-playbook` |
| HUD workspaces | `frontend/.../hudWorkspace.ts` — talk-jump to Engineering **only from monitor** |
| Conversations desk | `conversations.py`, `db.py` (`MAX_EXPANDED = 3`) |
| Speak / prefetch | `voicebox.py`, `main.py` `/api/tts`, `frontend/src/lib/voice.ts` |
| Suggested tasks / weather | `office_day.py`, `SuggestedTasksPanel.tsx`, `WeatherCard.tsx` |
| HITL | `pending_actions` + `HitlModal` (Authorize/Reject); `loadSessionSurface` restores first pending on session load |
| Capability turn log | `turn_log.py` → `work/LAST_TURNS.md` + `/api/turns/recent` |

## Do not

- Call Voicebox `/speak` (double audio on machine + browser)
- Put board scroll on SpotlightCard outer wrapper
- Raise concurrent open notes above 3 without an explicit product decision
- Replace Orchestrator with HudShell as the primary desk
- Invent mail/calendar/shop numbers in the brain

## Verify

- API health: `GET http://127.0.0.1:8000/api/health`
- HUD: `http://127.0.0.1:3000`
- Offline tests: `python -m pytest -m "not live_service"` (see `backend/requirements-dev.txt`)
- Frontend: `npm run typecheck` and `npm run lint` in `frontend/`
- Prefer killing duplicate listeners on `:8000` before restart
