# Jarvis — What Works Today (As-Built Snapshot)

**Updated:** 2026-09-25  
**Reference:** `docs/SYSTEM_TRUTH.md` (single source of truth), `docs/ROADMAP.md` (next steps)

## Product Shape

- **Jarvis** = 24/7 shop HUD + voice + HITL + connectors + local RAG/memory + office-day cards.
- **One Hermes brain** on `http://127.0.0.1:8642` (gateway). Gemini/Ollama = overflow, vision, semantic router, and fallback.
- **Orchestra codes** `RES.01` / `SEC.02` / `DAT.03` / `OPS.04` in `backend/app/agents.py` are **HUD labels**, not separate agents.
- **Voicebox** = local TTS (`:17493`, `/generate` + cache); browser plays once (`frontend/src/lib/voice.ts`).
- **Agent map** = `AGENTS.md` + `.cursor/skills/` + `.cursor/rules/`.

## HUD

- **Single pane:** one `OrchestratorShell` hosts always-mounted `Pane` (`frontend/src/components/pane/Pane.tsx`) — no per-workspace desk trees or presence crossfade. Workspace (`casual|monitor|engineering`) maps 1:1 to lenses (`converse|watch|bench`) via `paneStore`.
- **Substrate:** one `<canvas>` / one WebGL2 context in a worker (`frontend/src/substrate/`). Lens changes tween shader weights (Eye / Orb / pilot light); contexts not created/destroyed on switch. Idle **Watch** internal render scale **0.55** (Evil Eye dpr baseline).
- **Bench (engineering):** drawing stage (`BenchStagePanel` / pdf.js viewer) and quote sheet (`BenchQuotePanel` / `QuoteSheet`) stay mounted at depth; lens only moves slot and depth.
- **Talk-jump:** `talkJumpWorkspace` returns `null` unless current workspace is **monitor**. Quote/drawing words from Monitor → Engineering; same words on Casual stay Casual.
- **HITL:** `HitlModal` — **Authorize / Reject**. On load/session switch, `loadSessionSurface` restores first pending row for that session on every workspace.
- **Perf gate:** `npm run perf` (`scripts/perf-gate.mjs`) — headless Chrome, `?perf=1`, 20 workspace switches. Latest: `work/perf/phase-6.json`.

## Sessions & Data (`<repo>/data/`)

SQLite `jarvis.db`:

| Table | Role |
|-------|------|
| `messages` | Chat turns per session |
| `conversations` | Open notes (max **3** expanded) |
| `memories` | Quote facts and artifacts per `session_id` |
| `pending_actions` | HITL queue |

Hermes thread map: `data/hermes_sessions.json` (separate from playbook files). Playbooks are **not** the chat log.

## Quote Workflow (Shop-Quote)

- **Source playbook:** `backend/app/hermes/playbooks/quote/` (skill: `shop-quote`; `files/mhr-demo.md` = DEMO floors)
- **Install:** API startup `ensure_playbooks_installed()` copies to `{HERMES_HOME}/skills/shop/quote`
- **Routing:** `is_quote_start()` → semantic router `tool_ops` / `DAT.03`; must **not** hit `reason_rfq`. Hermes first. On Hermes error/timeout (30s default), local fallback: *"Which drawing — inbox attachment, file on desk, or photo?"*
- **No drawing path:** do not call `reason_rfq` (queues holding mail + calendar deadline).
- **Tools (MCP + registry):** `jarvis_quote_analyze_drawing`, `jarvis_quote_build`, `jarvis_quote_pdf`, `jarvis_quote_verify`, `jarvis_quote_send`, `jarvis_quote_playbook_note`. Brain does not invent RM, MHR floor, or outsource prices.
- **Proof:** `quote_verify` — >2 failures → `stop: true`, `quote_send` refuses. 1–2 failures may still queue Authorize. Delivery time does not block send (but blocks at Authorize per `stage='send'`).
- **Implementation:** `backend/app/quote.py`, `hermes/mcp_server.py`, tests in `backend/tests/test_quote_playbook.py`.

## Foundation Gates

| Gate | Status |
|------|--------|
| P0 Observability / HITL blast-radius + mission log + `/api/metrics` | Shipped |
| P1 Local memory / RAG (SQLite + LanceDB) + MCP memory tools | Shipped |
| P2 Hermes-first MCP expand + compose fill + shop-quote playbook + safety deny-list | Shipped |
| P3 Office-day spine (weather, suggested tasks, quote sheet/PDF/HITL send, vision helper) | Shipped |
| P4 Stretch browser evidence tools + docs | Shipped scaffolding |

## Working Capabilities

- Orchestrator HUD with Open notes (max 3 expanded), suggested tasks, weather chip, Authorize blast-radius card.
- Right rail: `WeatherCard` (`shrink-0`) + scrollable `SuggestedTasksPanel`.
- React Bits accents; mail board via SceneBoard inside SpotlightCard (`bodyClassName` scroll).
- Local-fast path for mail/calendar/briefing snapshot kinds.
- Hermes warm gateway bridge; TTS prefetch + Voicebox cutover.
- Turn log: auto-appended to `work/LIVE_TEST.md` + JSONL + `GET /api/turns/recent`.
- Local memory upsert/search/forget; quote path through verify + HITL send.

## Still Deepen with Real Office Use

- Live Google Sheet quotation workbook bind (local xlsx works).
- Continuous mail→attachment worker on production Gmail volume.
- Full Hermes browser computer-use end-to-end.
- Capability matrix: `work/CAPABILITY_TEST_MATRIX.md`.

## Runtime Notes

- Start Hermes gateway and Voicebox desktop app for Mark TTS.
- Prefer API on `127.0.0.1:8000`. Frontend `:3000`.
- Data: `<repo>/data/`; exports: `<repo>/exports/`. Install: `docs/INSTALL.md`. Agents: `AGENTS.md`.