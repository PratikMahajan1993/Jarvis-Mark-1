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
- **Talk-jump:** `section_hint.py` stamps `ui: {section, reason}`. Quote start and drawing/RFQ/CNC words route to Engineering from Monitor and from Casual. Mail and chat words route to Casual. A short status question stays put. `applyServerHint` (`core/desk/controller.ts`) ignores a non-explicit hint while Engineering is showing. Pin, an open modal, and user activity in the last 1.2 s drop or defer the scroll.
- **HITL:** `HitlModal` — **Authorize / Reject / Later**. Later parks a chip in `TaskDock` (shared `layoutId` with the modal). TTL is `parkedAt`+30 min unless `expires_at`, then Authorize reopens with a needs-decision toast. On load/session switch, `loadSessionSurface` in `core/desk/controller.ts` restores the first pending row for that session.
- **Perf gate:** `npm run perf` (`frontend/scripts/perf-gate.mjs`) — headless Chrome, `?perf=1`, cycles section nav. Writes `work/perf/baseline-overhaul.json`.

## Sessions & Data (`<repo>/data/`)

SQLite `jarvis.db`:

| Table | Role |
|-------|------|
| `messages` | Chat turns per session |
| `conversations` | Open notes (max **3** expanded) |
| `memories` | Quote facts and artifacts per `session_id` |
| `pending_actions` | HITL queue |
| `drafts` | Baton and engineering draft bodies (`PUT`/`POST /api/drafts/{key}`) |

Hermes thread map: `data/hermes_sessions.json` (separate from playbook files). Playbooks are **not** the chat log.

## Quote Workflow (Shop-Quote)

- **Source playbook:** `backend/app/hermes/playbooks/quote/` (skill: `shop-quote`; `files/mhr-demo.md` = DEMO floors). With `masterdata_enabled` (default on), live floors are `machine_hour_rates`, not that markdown file. Editor: `/masterdata`.
- **Install:** API startup `ensure_playbooks_installed()` copies to `{HERMES_HOME}/skills/shop/quote`
- **Routing:** `is_quote_start()` → semantic router `tool_ops` / `DAT.03`; must **not** hit `reason_rfq`. Hermes first. On Hermes error/timeout (30s default), local fallback: *"Which drawing — inbox attachment, file on desk, or photo?"*
- **No drawing path:** do not call `reason_rfq` (queues holding mail + calendar deadline).
- **Tools (MCP + registry):** `jarvis_quote_analyze_drawing`, `jarvis_quote_build`, `jarvis_quote_pdf`, `jarvis_quote_verify`, `jarvis_quote_send`, `jarvis_quote_playbook_note`. Brain does not invent RM, MHR floor, or outsource prices.
- **Proof:** `quote_verify` — any BLOCKER sets `stop: true` and `quote_send` refuses to queue. A WARN does not stop a draft. Empty delivery is WARN at `stage='draft'` and BLOCKER at `stage='send'`. Counting failures is not the severity model.
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
- Master data on by default (`masterdata_enabled`). Editor at `/masterdata` (Customers, Products, Machines, Materials, Suppliers, MHR floors, Outsource vendors, Shop logs). A product is name, number, customer, unit, and a stock-monitored flag. A demo/seed rate is stored and is not sendable until `attested_by` is set and the value differs from the shipped seed. Once any non-demo customer is active, startup does not insert Deepak, Rajesh, Priya Mehta, or Apex Components again.
- Replacing a master-data row with a different name leaves the closed row’s name as it was. Replacing it and keeping the same name stores that label in `recorded_name` (or `recorded_grade` / `recorded_product_number`). Lists show the recorded label. The unique key on the closed row may still carry a `[superseded …]` suffix so the new row can keep the name.
- Shop logs are read-only. Bind them on `/masterdata` → Shop logs (account, spreadsheet link, exact tab, header names for date, machine, job, qty, downtime). The shop Google token is `data/google_token.json`. A second staff account is `data/google_token_staff.json`, connected from Preferences → **Connect another Google account**. Jarvis copies the named tab locally. Current state is rows whose date column is today. Empty cells stay missing. Two sheets that disagree are both reported. The morning brief refreshes them. The Monitor card is `features/sheet-listen`. `TELEGRAM_OWNER_USER_IDS` gates rate attestation from Telegram only.

## Still Deepen with Real Office Use

- Live Google Sheet quotation workbook bind (local xlsx works).
- Continuous mail→attachment worker on production Gmail volume.
- Full Hermes browser computer-use end-to-end.
- Capability matrix: `work/CAPABILITY_TEST_MATRIX.md`.

## Contract Delta (vs X# / P#)

The HUD section above is the running desk. Contracts stay in `docs/overhaul/`. This list is the only as-built gap list.

Shipped detail that the HUD bullets do not repeat:

- Landing gates (`core/landing/`): substrate, fonts, desk, Monitor DOM, Casual DOM, engineering chunk + DrawingViewer + pdf.js prefetch. Min 1.4 s (0.6 s on same-tab refresh), cap 4 s. The status line can say “Checking Hermes”; Hermes never blocks exit. Chrome fades in staggered 80 ms (`Desk.tsx`, `CHROME_STAGGER_S`).
- Drafts: baton flush on section change and `pagehide`; Engineering autosave on programmatic leave (awaited, 300 ms cap) and once on scroll-away; `pagehide` beacon is `text/plain` JSON; draft keys `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`, 64 KB cap.
- Voice: `voice.ts` posts analyser RMS `level` to the substrate. Space types in fields, including the baton; the mic runs when not typing; Space never scrolls.
- Deck: pdf.js page-1 thumbnails cached in IndexedDB (`pdfThumbCache.ts`); empty deck is a drop target; card-to-stage and HITL-to-chip use shared `layoutId`. Arrow keys and a horizontal trackpad swipe cycle the deck (`deckWheel.ts`). A vertical or diagonal swipe still scrolls the page.
- Feature platform: `backend/app/core/features.py` (event-loop-safe `publish`, `GET /api/features`, `GET /api/events`). SDK hooks are the exports in `frontend/src/sdk/index.ts`, including `useJarvisSend`, `useOrb`, and `useFeatureQuery`. OpenAPI types are committed at `frontend/src/lib/api/schema.gen.ts`. `npm run new:feature` writes the feature and registers `frontend/src/features/index.ts` and `backend/app/features/__init__.py`. Weather is the first feature (`frontend/src/features/weather`); its backend module is `features_weather.py`, not `backend/app/features/weather/`.
- Substrate degrader keys off worker `simMs` (bloom first, then a slower sim).
- Landing first frame is server HTML (`LandingFirstFrame` in `app/page.tsx`): “Waking substrate” and a hairline, painted before the desk bundle runs. The client overlay removes that node when it mounts.
- Capability matrix section **S** covers landing, snap, dock, and deck (`work/CAPABILITY_TEST_MATRIX.md`).

Still open:

- Lenis snap type is `"lock"` (`core/scroll/engine.ts`: one gesture, one section). Contract X2 says “mandatory”. Do not change the type until the owner picks; both are recorded on purpose.
- Feature job runner (`backend/app/core/scheduler.py`) is not started from API lifespan. Jobs stay off until a feature registers one and startup calls `start`.

## Runtime Notes

- Start Hermes gateway. Speech uses the Gemini key already in `.env` (Charon). Voicebox is not part of the desk.
- Prefer API on `127.0.0.1:8000`. Frontend `:3000`.
- Data: `<repo>/data/`; exports: `<repo>/exports/`. Install: `docs/INSTALL.md`. Agents: `AGENTS.md`.