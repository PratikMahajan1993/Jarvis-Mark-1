# Codebase map (reconnaissance)

**Branch:** `overhaul` (HEAD `cdc7e77` — chore removing unused `HudShell`).  
**Scope:** Read-only audit of `/workspace` as implemented on this branch.  
**Uncertainty marker:** *Unknown — requires further investigation.*

---

## 1. Repository topology

| Path | Role |
| --- | --- |
| `frontend/` | Next.js 15 App Router HUD (`jarvis-hud`, port 3000) |
| `backend/app/` | FastAPI application package (`uvicorn app.main:app`, port 8000) |
| `backend/migrations/` | Versioned SQLite DDL (`0001`–`0018`) applied via `db.run_migrations()` |
| `backend/tests/` | Pytest suite (~63 `test_*.py` modules); session temp `data_dir` in `conftest.py` |
| `data/` | Runtime SQLite (`jarvis.db`), Hermes session map, OAuth tokens, LanceDB path under `data/memory/` (gitignored in normal use) |
| `exports/` | Allowed write root for generated artifacts (`settings.exports_dir`) |
| `work/` | Living product notes, capability matrix, manifest, perf artifacts |
| `docs/` | As-built (`CURRENT.md`), install, architecture-review (this folder) |
| `.cursor/` | Cloud/dev environment, Cursor rules, skills, roster agent prompts |
| `AGENTS.md` | Agent & skill map for Cursor workers |

---

## 2. Runtime entry points

### Backend

- **Module:** `backend/app/main.py` — `FastAPI(title="Jarvis Command Center")` with `lifespan` hook.
- **Startup (`startup()`):** `db.init_db()` → seed mail/calendar if not live → `resume_watches()` → `kick_snapshot()` → `maybe_kick_on_startup()` → optional memory schema → background Hermes MCP/playbook install → Voicebox/Hermes warm → `live_log` health snapshot.
- **Launch (repo):** `.cursor/environment.json` runs `.venv/bin/uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000`.
- **Config anchor:** `backend/app/config.py` — `Settings` loads `.env` at repo root and `backend/.env`; paths anchored to `REPO_ROOT` via `_anchor_to_repo_root()`.

### Frontend

- **Primary route:** `frontend/src/app/page.tsx` → dynamic `OrchestratorShell` (`ssr: false`).
- **Secondary routes:** `frontend/src/app/canvas/page.tsx` (`CanvasShell`); `frontend/src/app/lab/diarize/page.tsx` (lab UI).
- **API client:** `frontend/src/lib/api.ts` — `apiBase()` from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); mutating requests optionally send `Authorization: Bearer` when `NEXT_PUBLIC_JARVIS_API_TOKEN` is set (mirrors backend LAN token gate).

---

## 3. Backend module map (by concern)

| Concern | Primary modules | Notes |
| --- | --- | --- |
| HTTP surface | `main.py` | ~40+ `/api/*` routes (health, chat, confirm, mail, calendar, RFQ, canvas, knowledge, vision bench, metrics, turns ledger, Google OAuth, TTS, etc.) |
| Chat orchestration | `agent.py`, `think.py`, `understand.py` | `run_agent()` → `_run_agent()`; `brain_lock(session_id)` in `conversations.py` |
| Intent (legacy/fast path) | `intent.py` | Regex/heuristic `Intent`, `Route`, `classify()`, `is_quote_start()`, `SAFETY_DENY_PHRASES` |
| Semantic router | `semantic_router.py` | Gemini structured `IntentClassification`; `handle_ui_command()`; used when turn ledger **off** |
| Brain fallback | `brain.py`, `gemini_client.py`, `ollama_client.py` | Provider `auto` → Gemini if key else Ollama |
| Hermes | `hermes/bridge.py`, `hermes/mcp_server.py`, `hermes/hitl.py` | Gateway `:8642`, session file `data/hermes_sessions.json`, playbook install to `{HERMES_HOME}/skills/shop/` |
| Tools | `tools/registry.py`, `tools/documents.py` | `execute_tool()`, `TOOL_SCHEMAS`, HITL via `request_human_approval()` |
| Quote / RFQ | `quote.py`, `rfq.py`, `quote_variance.py`, `quote_run_log.py` | Playbook source `hermes/playbooks/quote/` |
| Mail / calendar | `connectors/gmail.py`, `connectors/email.py`, `connectors/calendar.py`, `mail_sync.py`, `mail_compose.py`, `snapshot.py` | Local seed vs live Google; snapshot refresh threads |
| Conversations desk | `conversations.py`, `db.py` | Open notes, drawing/workflow sessions, `MAX_EXPANDED = 3` (enforced in DB layer — *verify call sites*) |
| HITL | `pending_actions` table, `resolve_pending()` in `agent.py`, `hermes/hitl.py` | Kinds mapped in `agents.py` `KIND_TO_AGENT` |
| Memory / RAG | `memory/store.py`, `memory/mirror.py`, `memory/embeddings.py`, `rag/search.py`, `rag/ingest.py`, `rag/eval.py` | SQLite `memory_docs`; optional LanceDB upsert; separate `rag_*` tables (migration `0010_rag.sql`) |
| Master data | `masterdata/*` | Gated by `settings.masterdata_enabled` (default **false**) |
| Vision / knowledge | `vision/*`, `knowledge/*` | Gated by `vision_bench_enabled`, `knowledge_cards_enabled` (default **false**) |
| Shop floor | `shop/state.py`, `shop_log.py`, `toolwatch.py`, `cycletime.py`, `stockcut.py` | Event/projection patterns in tests |
| Turn ledger | `turns/accept.py`, `turns/store.py`, `turns/worker.py`, `turns/events.py`, `turns/reaper.py` | Gated by `turn_ledger_enabled` (default **false**) |
| Observability | `metrics.py`, `live_log.py`, `turn_log.py`, `quote_run_log.py` | Mission steps, JSONL live log, `work/LAST_TURNS.md` |
| Office day UI data | `office_day.py`, `briefing.py` | Suggested tasks, weather tool hooks |
| Voice | `voicebox.py`, `conversation_voice.py`, `casual_voice.py` | Voicebox `POST /generate`; prefetch on chat out |
| Jobs (demo) | `jobs.py` | Seeded demo job in `init_db()` |
| Canvas | `db.py` canvas tables + `main.py` canvas routes | Separate from Orchestrator shell |
| Auth (API) | `main.py` middleware | Mutating non-localhost requests require bearer token unless on allowlist |
| Google OAuth | `connectors/google_auth.py` | Token at `data/google_token.json`; callback `/api/google/callback` |

### Orchestra labels (not separate agents)

`backend/app/agents.py` — fixed map `research|sec|data|ops` → `RES.01`…`OPS.04`; `agent_status_payload()` for `/api/agents`.

---

## 4. Data layer

### SQLite (`settings.db_path` → `<repo>/data/jarvis.db`)

Migrations applied in order (`backend/app/db.py`):

| Version | File | Adds (summary) |
| --- | --- | --- |
| 0001 | `0001_baseline.sql` | Core chat, pending, mail, calendar, conversations, canvas, audit, mission_steps, hud_state, watches, … |
| 0002 | `0002_turns.sql` | `turns` ledger table |
| 0003 | `0003_external_effects.sql` | External effect tracking |
| 0004–0007 | parties, machines, routings, quotes | Master-data / quote revision scaffolding |
| 0008 | `0008_turn_events.sql` | Turn SSE event stream storage |
| 0009–0011 | entity_cards, rag, shop_state | Knowledge + RAG + shop projection |
| 0012–0018 | quote_variance, cycletime, remnant_stock, feature_rules, toolwatch, nc_programs, metrics | Engineering / ops extensions |

**Preferences:** single row `preferences.id = 1` JSON blob (`schemas.Preferences`).

**Hermes mapping:** `data/hermes_sessions.json` (not in migrations) — Jarvis `session_id` → Hermes thread id; quote titles under `quote:{session_id}` keys (`hermes/bridge.py`).

### Filesystem

- `exports/` — tool-generated PDFs, drawings, documents (`EXPORTS_DIR`).
- `data/canvas/` — canvas file uploads (default under `data_dir`).
- `data/memory/lancedb/` — optional LanceDB URI when import succeeds (`memory/store.py`).

---

## 5. HTTP API boundaries (grouped)

Full list lives in `backend/app/main.py`. Grouped service boundaries:

| Boundary | Representative routes | Handler layer |
| --- | --- | --- |
| Liveness | `GET /api/health`, `/api/voicebox/status` | `brain.health()`, Hermes/Voicebox probes |
| Chat / HITL | `POST /api/chat`, `/api/confirm`, `/api/pending`, `/api/pending/{id}/update` | `agent.run_agent`, `resolve_pending`; chat branches on `turn_ledger_enabled` |
| Turn ledger | `GET /api/turns/open`, `/api/turns/{id}`, `/api/turns/{id}/events` (SSE) | `turns/*` |
| Session / HUD restore | `GET /api/session`, `POST` hud remember via chat side effects | `hud_state.py`, `remember_hud()` |
| Mail | `/api/mail/sync`, attachments save/reply | `mail_sync`, `mail_attachments`, tools |
| Google | `/api/google/status`, `/auth`, `/callback` | `google_auth` |
| Office | `/api/briefing`, `/api/glance`, `/api/suggested-tasks`, `/api/office/refresh` | `briefing`, `office_day` |
| Quote / variance | `/api/quote-variance/erosion`, RFQ routes | `quote_variance`, `rfq` |
| Knowledge / vision | `/api/knowledge/*`, `/api/vision/bench`, masterdata vision consent | Feature-flagged modules |
| Metrics / audit | `/api/metrics`, `/api/missions`, `/api/audit`, `/api/live-log` | `metrics`, `db.audit` |
| TTS | `POST /api/tts` | `voicebox` proxy/cache |
| Canvas | `/api/canvas/boards`, `/api/canvas/files` | `db` + file storage |
| Conversations | `/api/conversations*` | `conversations.py` |

**CORS:** `settings.origin_list` + regex for localhost/127.0.0.1.

**Caching:** Voicebox TTS prefetch (`voicebox.prefetch_tts` on chat response); brain health TTL 60s (`brain.py`); snapshot staleness 900s (`snapshot.py`). No HTTP reverse-proxy cache documented in-repo.

**Errors:** FastAPI `HTTPException`; chat paths often return speak lines + `offline` flag in `ChatResponse` rather than HTTP errors for model failures.

---

## 6. Frontend architecture

### Shell

- **`OrchestratorShell.tsx`** — single desk: voice FSM (`orchestratorFsm.ts`), workspace (`hudWorkspace.ts`), API wiring, modals, pane panel slots, conversation rail, HITL, Google connect, preferences.
- **`Pane.tsx`** — always-mounted lens shell: substrate WebGL worker, panel layout from `LENS_LAYOUT`, `CommandBaton`, workspace sync via `LensTabs` / `useSyncWorkspaceLens`.
- **Workspace → lens:** `lensForWorkspace()` in `frontend/src/lib/pane/lenses.ts` — `monitor→watch`, `casual→converse`, `engineering→bench`.

### Client state ownership

| State | Owner | Persistence |
| --- | --- | --- |
| Turn FSM (`JarvisState`) | `jarvisReducer` in `OrchestratorShell` | Ephemeral; reconciled from `/api/turns/open` when ledger enabled |
| HUD workspace | React state + `localStorage` keys `jarvis.hudWorkspace`, `jarvis.hudWorkspacePinned` | `hudWorkspace.ts` |
| Pane lens / overlay | Module singleton `paneStore.ts` | Ephemeral (lens gesture + settle watchdog) |
| Active conversation | React + `FOCUS_STORAGE_KEY` | `localStorage` `jarvis.activeConversationId` |
| Scene / pending / agents | React from API responses | Server: `hud_state`, `pending_actions`, `messages` |
| Substrate WebGL | `frontend/src/substrate/*` worker | Worker-local; driven by pane conductor |

### Key libraries

- `frontend/src/lib/voice.ts` — browser STT/TTS bridge, Voicebox cutover timing.
- `frontend/src/lib/liveLog.ts` — HUD-side capability logging to API.
- `frontend/src/lib/types.ts` — shared TS types mirroring `schemas.py` shapes (partial).

---

## 7. Integrations

| Integration | Config | Code entry |
| --- | --- | --- |
| Hermes gateway | `HERMES_GATEWAY_URL`, `HERMES_API_KEY`, `HERMES_ENABLED` | `hermes/bridge.py` — gateway health requires API key in `_gateway_reachable` |
| Voicebox | `VOICEBOX_URL`, profile `Mark` | `voicebox.py`, `/api/tts` |
| Gemini | `GEMINI_API_KEY`, models in settings | `gemini_client.py`, router, casual chat, vision |
| Ollama | `OLLAMA_HOST`, `OLLAMA_MODEL` | `ollama_client.py` |
| Google Gmail/Calendar/Drive/Sheets | OAuth client env, `data/google_token.json` | `connectors/*`, `google_auth.py` |
| Web search | Tavily, Brave, Google CSE keys | `connectors/search.py` |
| MCP (Hermes) | `hermes/mcp_server.py` registers Jarvis tools | Background thread on startup when Hermes enabled |

---

## 8. Background work / events

| Mechanism | Trigger | Module |
| --- | --- | --- |
| Mail/calendar snapshot refresh | Startup + periodic loop + “fresh” utterances | `snapshot.py` |
| Mail bulk sync | `/api/mail/sync`, startup kick | `mail_sync.py` |
| Gmail watches | `resume_watches()` on startup | `watch.py` |
| Hermes MCP registration | Daemon thread post-startup | `main.startup` → `bridge.ensure_jarvis_mcp_registered` |
| Turn worker | `schedule_turn()` when ledger accepts chat | `turns/worker.py` asyncio thread |
| Turn reaper | Lifespan when `turn_ledger_enabled` | `turns/reaper.py` |
| Turn SSE | Client `EventSource` on `/api/turns/{id}/events` | `turns/events.py` |

---

## 9. Domain logic hotspots

- **Mail compose fast path:** `intent` mail_draft + `mail_compose.start_email_compose()` — bypasses Hermes (`agent.py`).
- **Snapshot-local reads:** `mail_read`, `mail_search`, `calendar_list`, `briefing` via `_run_agent_legacy()` when snapshot ready (`agent.py`, `snapshot.py`).
- **Quote start:** `is_quote_start()` → Hermes path; on failure fixed fallback string in `agent.py` (not Hermes-generated).
- **RFQ without drawing:** `reason_rfq` tool path — *separate from quote playbook* (see `intent.py`, `rfq.py`, tests).
- **Proof gates:** `quote_verify`, send refusal — `quote.py`, tests `test_quote_proof_gates.py`, `test_quote_playbook.py`.
- **Brain lock:** per-session mutex for concurrent chat (`conversations.brain_lock`).

---

## 10. Tests, build, deployment

### Tests

- **Runner:** `python -m pytest` from `backend/` with `backend/tests/conftest.py` redirecting `data_dir`/`exports_dir` to temp.
- **Marker:** `api_service` — needs live API on :8000 (`conftest.py`).
- **Skill convention:** `pytest -m "not live_service"` referenced in `jarvis-architecture` skill — *marker registration for `live_service` not found in `conftest.py`; Unknown — requires further investigation.*
- **Frontend:** `npm run typecheck`, `lint`, `perf` (headless Chrome gate in `frontend/scripts/perf-gate.mjs`).

### Build / install

- `.cursor/install.sh` — venv, `requirements.txt` + `requirements-dev.txt`, `npm install`, copies `.env.example` → `.env` if missing.
- **Documented desk ports:** HUD `:3000`, API `127.0.0.1:8000` preferred in rules; cloud terminal binds `0.0.0.0:8000`.

### Observability (as implemented)

- `GET /api/metrics` — latency samples, mission aggregates (`metrics.py`).
- `POST /api/live-log` + `GET /api/live-log/recent` — capability test stream (`live_log.py` → `data/live_test.jsonl`, `work/LIVE_TEST.md`).
- Chat turn trail: `turn_log.record_turn` → `work/LAST_TURNS.md` (when ledger off path runs).
- Quote route tracing: `quote_run_log.py`.
- DB `audit`, `mission_steps` tables.

---

## 11. End-to-end data flows

### A. Chat turn (turn ledger **disabled** — default)

```text
HUD OrchestratorShell.send()
  → POST /api/chat { message, session_id }
  → semantic_router.classify_intent (or try_obvious_casual)
  → handle_ui_command OR agent.run_agent(message, route)
       → brain_lock
       → pending yes/no via classify_decision OR Hermes run_hermes_turn OR legacy tools/Gemini
  → ChatResponse JSON (speak, scene, pending, agents)
  → remember_hud; turn_log; live_log; optional prefetch_tts
  → HUD applyResponse: voice speak, scene boards, AWAIT_HITL if pending
```

### B. Chat turn (turn ledger **enabled**)

```text
POST /api/chat
  → accept_chat_turn → QUEUED row in turns
  → schedule_turn → run_ledger_chat_turn (agent.run_ledger_chat_turn)
  → HTTP returns { turn_id, state } only
HUD TurnStageLine
  → EventSource /api/turns/{id}/events (fallback poll GET /api/turns/{id})
  → onComplete → applyResponse
OrchestratorShell mount
  → reconcileOpenTurn GET /api/turns/open
  → orchestratorFsm RECONCILE / hydrate
```

*Default env leaves ledger off while HUD contains full ledger UI paths — see investigation doc.*

### C. HITL confirm

```text
HitlModal Authorize/Reject OR spoken classifyDecision
  → POST /api/confirm { action_id, approved, session_id }
  → agent.resolve_pending
  → tool execution or queue rejection
  → updated pending list + speak line
```

### D. Hermes quote playbook (happy path sketch)

```text
Utterance classified tool_ops / is_quote_start
  → run_hermes_turn (bridge) with MCP tools jarvis_quote_* (mcp_server.py)
  → Playbook skill shop-quote (installed from backend/app/hermes/playbooks/quote/)
  → Tools hit quote.py + masterdata + verify gates
  → quote_send queues pending_actions → HitlModal
```

*Exact Hermes tool loop inside gateway — Unknown — requires further investigation (external process).*

### E. Mail snapshot read

```text
Utterance → intent mail_read/mail_search + snapshot ready
  → _run_agent_legacy → execute_tool → connectors/email or gmail
  → Scene widgets for SceneBoard / SpotlightCard in shell
```

---

## 12. Configuration flags (feature gates)

From `backend/app/config.py` (defaults matter for desk behavior):

| Setting | Default | Effect |
| --- | --- | --- |
| `turn_ledger_enabled` | `False` | Sync chat vs accept-then-work |
| `masterdata_enabled` | `False` | SQL master data vs markdown fallbacks |
| `vision_bench_enabled` | `False` | Engineering vision queue API |
| `knowledge_cards_enabled` | `False` | Entity card API |
| `real_embeddings_enabled` | `False` | ONNX embedder vs hash vectors |
| `hermes_enabled` | `True` | Hermes routing attempts |
| `voicebox_enabled` | `True` | TTS server preference |

---

## 13. Overhaul branch notes (from `work/ARCHITECTURE_POINTS.md`)

- Single `OrchestratorShell`; `HudShell` removed (commit at HEAD).
- Pane/substrate overhaul: one WebGL context, lens morph (`Pane`, `substrate/`).
- Product locks documented in living notes and `work/OPUS_ARCHITECTURE_MANIFEST.md` — implementation spread across quote, vision, masterdata modules with many flags default-off.

---

## 14. Cross-references

- As-built summary: `docs/CURRENT.md`
- Agent map: `AGENTS.md`
- Capability tests: `work/CAPABILITY_TEST_MATRIX.md`
- UI performance artifacts: `work/perf/phase-6.json`, `frontend/scripts/perf-gate.mjs`
