# Jarvis architecture reference

## Ports

| Service | URL |
| ------- | --- |
| HUD | http://127.0.0.1:3000 |
| API | http://127.0.0.1:8000 |
| Hermes gateway | http://127.0.0.1:8642 |
| Voicebox | http://127.0.0.1:17493 |

Bind API with `--host 127.0.0.1` when possible. A second process on `0.0.0.0:8000` causes confusing dual listeners.

## TTS bridge (frontend)

File: `frontend/src/lib/voice.ts`

1. `speak(text)` starts `/api/tts` fetch and a 160ms browser-TTS bridge.
2. If Voicebox blob arrives before ~1.4s after bridge start → cancel browser, play Mark.
3. If later → **do not play** Voicebox; browser already owns the line (cache still warms).
4. Never play inside fetch before the late-cutover check (causes ~15s double speak).

Backend: `prefetch_tts` on chat/confirm; disk cache under `<repo>/data/tts_cache/`.

## Semantic router

File: `backend/app/semantic_router.py`

1. `/api/chat` classifies each utterance (`ui_command`, `casual_chat`, `vision_task`, `tool_ops`).
2. UI commands resolve locally via `handle_ui_command` → `ChatResponse.ui_action` (hide/show dock, minimize/expand notes).
3. Other intents stamp `target_agent` + orchestra highlight on `ChatResponse.agents`.
4. `tool_ops` prefers Hermes in `agent.py`; falls back to local snapshot / legacy on error.

## Mail / snapshot fast path

Kinds in `SNAPSHOT_KINDS` (briefing, mail_search, mail_read, calendar_list) use local DB/tools when ready instead of waiting on Hermes. Empty attachment-only mail must still speak a useful line (not “Mail is on the board.” alone).

## Desk model

- Ambient session = everyday desk (default workspace **monitor** when unpinned)
- **Workspaces:** `casual` | `monitor` | `engineering` — orthogonal to turn FSM (`orchestratorFsm.ts`)
- **Talk-jump:** `talkJumpWorkspace(text, current)` — returns `null` unless `current === "monitor"`; engineering hints jump to Engineering; same quote/drawing words on Casual do **not** jump
- Discussions / jobs = named conversations in Open notes
- Suggested RFQ “engineering” opens/resumes a job workflow note
- Weather is **outside** the scrollable tasks list (`WeatherCard` + `shrink-0`)
- **HITL restore:** `OrchestratorShell.loadSessionSurface` fetches `pending_actions` and opens `HitlModal` for the first row (any workspace)

## Quote playbook (shop-quote)

| Piece | Location |
| ----- | -------- |
| Repo source | `backend/app/hermes/playbooks/quote/` (`SKILL.md` name **shop-quote**) |
| Hermes install | `{hermes home}/skills/shop/quote` via `ensure_playbooks_installed()` in `hermes/bridge.py` on API startup |
| Tool impl | `backend/app/quote.py` + `tools/registry.py` + `hermes/mcp_server.py` (`jarvis_quote_*`) |
| Start detection | `intent.is_quote_start` → router `tool_ops` / `DAT.03`; blocks `reason_rfq` for quote starts |
| Hermes path | `agent.py` `_hermes_reply` first; timeout/error → fixed local drawing-path question (30s default) |
| Sessions | Quote facts in `memories` per `session_id`; Hermes map in `data/hermes_sessions.json` |

Deep workflow: skill **`jarvis-quote-playbook`**.

## React Bits inventory

See skill `jarvis-react-bits` / `catalog.md`.

## Capability tests

`work/CAPABILITY_TEST_MATRIX.md` — run order and log template. The coordinator delegates specialists on observations.
