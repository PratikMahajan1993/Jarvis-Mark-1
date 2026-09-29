# Jarvis — What Works Today (As-Built Snapshot)

**Updated:** 2026-09-30  
**Reference:** `docs/SYSTEM_TRUTH.md` (single source of truth), `docs/ROADMAP.md` (next steps)

## Product Shape

- **Jarvis** = 24/7 shop HUD + voice + HITL + connectors + local RAG/memory + office-day cards.
- **One Hermes brain** on `http://127.0.0.1:8642` (gateway). Gemini/Ollama = overflow, vision, semantic router, and fallback.
- **Orchestra codes** `RES.01` / `SEC.02` / `DAT.03` / `OPS.04` in `backend/app/agents.py` are **HUD labels**, not separate agents.
- **Speech** = Gemini TTS, voice Charon. Browser plays one WAV from `POST /api/tts` (`frontend/src/lib/voice.ts`). Out of calls on every speech model: the line stays on screen and Jarvis stays silent.
- **Agent map** = `AGENTS.md` + `.cursor/skills/` + `.cursor/rules/`.

## HUD

- **Scrolling desk:** `app/layout.tsx` → `JarvisRoot` owns the only WebGL canvas for the tab. `/` loads `Desk` (`core/desk/Desk.tsx`) with a vertical section stack (`SectionStack`: Monitor → Casual → Engineering; feature sections slot in by `order`). Lenis + snap live in `core/scroll/`; PageUp/PageDown and Alt+1–9 jump; Space types in fields (including the baton) and is the mic when not typing.
- **Workspace from section:** active scroll section derives HUD workspace (`casual|monitor|engineering`). Server chat and Hermes-run start may stamp `ui: {section, reason}`; the scroll director (`core/scroll/director.ts`) drops or defers automatic jumps when pinned, when a modal is open, or when the user was active recently. Engineering only yields to `explicit`.
- **Substrate:** one particle swarm on the root canvas (`frontend/src/substrate/`, worker `OffscreenCanvas`). Section formulas morph on scroll; FSM states move formula controls only. UI posts `postSubstrate` messages — never opens a second WebGL context.
- **Engineering:** drawing stage (pdf.js) and quote sheet when a note is focused; otherwise a stacked task deck (carousel). Baton text and engineering drafts autosave (`localStorage` + `PUT`/`POST /api/drafts/{key}`); programmatic leave awaits autosave (300 ms cap), wheel/snap fires once without freezing Lenis.
- **Talk-jump:** quote/drawing words from Monitor → Engineering; same words on Casual stay Casual. User scroll and pin win over soft hints.
- **HITL:** `HitlModal` — **Authorize / Reject / Later**. Parked chips live in `TaskDock`; TTL is `parkedAt`+30 min unless `expires_at`, then Authorize reopens with a needs-decision toast. On load/session switch, `loadSessionSurface` restores the first pending row for that session.
- **Perf gate:** `npm run perf` (`scripts/perf-gate.mjs`) — headless Chrome, `?perf=1`. Latest artifact: `work/perf/phase-6.json` (still workspace-switch oriented; not rewritten for the scroll desk).

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

- Scrolling desk HUD with Open notes (max 3 expanded), suggested tasks, weather card, Authorize blast-radius card.
- Monitor rail: weather (`features/weather`, shrink-0) above scrollable `SuggestedTasksPanel`.
- React Bits accents; mail board via SceneBoard inside SpotlightCard (`bodyClassName` scroll).
- Local-fast path for mail/calendar/briefing snapshot kinds.
- Hermes warm gateway bridge. Speech is Gemini TTS (Charon); prefetch warms `data/tts_cache/`.
- Turn log: auto-appended to `work/LIVE_TEST.md` + JSONL + `GET /api/turns/recent`.
- Local memory upsert/search/forget; quote path through verify + HITL send.

## Still Deepen with Real Office Use

- Live Google Sheet quotation workbook bind (local xlsx works).
- Continuous mail→attachment worker on production Gmail volume.
- Full Hermes browser computer-use end-to-end.
- Capability matrix: `work/CAPABILITY_TEST_MATRIX.md`.

## Scroll Overhaul

- Single vertical page: Monitor, Casual, Engineering (Lenis + snap, `core/scroll/`). Landing gates (`core/landing/`): substrate, fonts, desk, monitor/casual DOM, engineering chunk + DrawingViewer + pdf.js prefetch. Min 1.4 s (0.6 s on refresh), cap 4 s.
- Server section hints (`section_hint.py`) and scroll director. TaskDock parked approvals + engineering-tasks chip; deck quote-step chip and conversation-scoped parked badge.
- Drafts: baton flush on section change/`pagehide`; Engineering autosave on programmatic leave (awaited) and scroll-away (once); `pagehide` beacon as `text/plain` JSON; draft keys `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`, 64 KB cap.
- Voice: `voice.ts` posts analyser RMS `level` to the substrate. Space types in fields; mic when not typing; never scrolls.
- Feature platform scaffold: `app/core/features.py` (`publish` event-loop safe; jobs off), `/api/events` SSE, `frontend/src/sdk` (`Slot`, `defineFeature`, `defineCard`, `useSection`/`useTopic`/`useDraft`), `npm run new:feature`. Weather is the first feature (Monitor rail).
- Known gaps left open: snap `"lock"` vs contract “mandatory” (owner decision); HITL-to-chip shared-layout morph; card-to-stage morph; pdf.js deck thumbnails + IndexedDB cache; deck `deltaX` cycle; empty deck drop target; landing Hermes line + staggered chrome; 6 ms substrate sim budget (desk measure); full feature-platform SDK (loader, scheduler, OpenAPI commit, remaining hooks); perf-gate rewrite for the scroll desk; capability-matrix ids for the overhaul.

## Runtime Notes

- Start Hermes gateway. Speech uses the Gemini key already in `.env` (Charon). Voicebox is not part of the desk.
- Prefer API on `127.0.0.1:8000`. Frontend `:3000`.
- Data: `<repo>/data/`; exports: `<repo>/exports/`. Install: `docs/INSTALL.md`. Agents: `AGENTS.md`.