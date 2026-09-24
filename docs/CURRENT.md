# Jarvis — what works today (2026-09-22)

Short as-built snapshot. Conversation record (intent, not full spec): `work/ARCHITECTURE_POINTS.md`, `work/APP_FEATURES.md`, `work/UI_UX_POINTS.md`. Vision: `work/VISION_WORKBOOK.md`.

## Product shape

- **Jarvis** = 24/7 shop HUD + voice + HITL + connectors + local RAG/memory + office-day cards.
- **One Hermes brain** on `http://127.0.0.1:8642` (gateway). Gemini/Ollama = overflow, vision, semantic router, and fallback.
- **Orchestra codes** `RES.01` / `SEC.02` / `DAT.03` / `OPS.04` in `backend/app/agents.py` are **HUD labels**, not separate agents.
- **Voicebox** = local TTS (`:17493`, `/generate` + cache); browser plays once (`frontend/src/lib/voice.ts`).
- **Agent map** = `AGENTS.md` + `.cursor/skills/` + `.cursor/rules/`.

## HUD

- **Single pane:** one `OrchestratorShell` hosts a always-mounted `Pane` (`frontend/src/components/pane/Pane.tsx`) — no per-workspace desk trees or presence crossfade. Intent still persists as **`casual` | `monitor` | `engineering`** in `hudWorkspace.ts`; the pane maps that once to lenses **Converse | Watch | Bench** (tabs + `paneStore`).
- **Substrate:** one `<canvas>` / one WebGL2 context in a worker (`frontend/src/substrate/`, `Substrate.tsx` + `createSubstrate.ts`). Lens changes tween shader weights (Eye / Orb / pilot light); contexts are not created or destroyed on switch. Idle **Watch** internal render scale is **0.55** (Evil Eye dpr baseline; adaptive quality steps down from there).
- **Bench (engineering):** drawing stage (`BenchStagePanel` / pdf.js viewer) and quote sheet (`BenchQuotePanel` / `QuoteSheet`) stay mounted at depth; lens only moves slot and depth.
- **Talk-jump:** `talkJumpWorkspace` returns `null` unless the current workspace is **monitor**. Quote/drawing words from Monitor can jump to Engineering; the same words on **Casual stay Casual** (no auto-jump).
- **HITL:** `HitlModal` — **Authorize / Reject** unchanged. On load and session switch, `loadSessionSurface` restores the first pending row for that session (calendar/mail/quote) on every workspace.
- **Perf gate:** from `frontend/`, `npm run perf` (`scripts/perf-gate.mjs`) — headless Chrome, `?perf=1`, 20 workspace switches. Latest desk run: `work/perf/phase-6.json`. The pre-pane baseline stays in `work/perf/baseline-overhaul.json`. Thresholds in `work/SONNET_UI_VISION.md` §2.7: on this desk run **rAF p95 8.5 ms** (pass), **10 long tasks, all over 50 ms**, mostly during initial load (gate fail), **1 WebGL context**, **5** `OrchestratorShell` profiler commits over the run.

## Sessions & data (`<repo>/data/`)

SQLite `jarvis.db`:

| Table | Role |
| ----- | ---- |
| `messages` | Chat turns per session |
| `conversations` | Open notes (max **3** expanded) |
| `memories` | Quote facts and artifacts per `session_id` |
| `pending_actions` | HITL queue |

Hermes thread map: `data/hermes_sessions.json` (separate from playbook files). Playbooks are **not** the chat log.

## Quote workflow (shop-quote)

- **Source playbook:** `backend/app/hermes/playbooks/quote/` (skill name **shop-quote**; `files/mhr-demo.md` is DEMO floors, not shop truth).
- **Install:** API startup `ensure_playbooks_installed()` in `hermes/bridge.py` copies to `{hermes home}/skills/shop/quote` (`HERMES_HOME` or `~/.hermes`).
- **Routing:** `is_quote_start()` in `intent.py` → semantic router `tool_ops` / `DAT.03`; must **not** hit `reason_rfq`. Hermes first (`agent.py` `_hermes_reply`). On Hermes error/timeout (`hermes_timeout_sec`, default **30s**), local fallback line only: *“Which drawing should I quote — an inbox attachment, a file on the desk, or a photo?”* — not Hermes speaking.
- **No drawing path:** do not call `reason_rfq` (that path queues holding mail + calendar deadline).
- **Tools (MCP + registry):** `jarvis_quote_analyze_drawing`, `jarvis_quote_build`, `jarvis_quote_pdf`, `jarvis_quote_verify`, `jarvis_quote_send`, `jarvis_quote_playbook_note`. Brain does not invent RM, MHR floor, or outsource prices.
- **Proof:** `quote_verify` can fail; **>2** failures → `stop: true` and `quote_send` refuses to queue. 1–2 failures may still queue Authorize. Delivery time does not block send.
- **Implementation:** `backend/app/quote.py`, `hermes/mcp_server.py`, tests in `backend/tests/test_quote_playbook.py`. Cursor skill: `.cursor/skills/jarvis-quote-playbook/SKILL.md`.

## Foundation gates (Aspect 14)

| Gate | Status |
| ---- | ------ |
| P0 Observability / HITL blast-radius + mission log + `/api/metrics` | Shipped |
| P1 Local memory / RAG (SQLite + LanceDB-when-available) + MCP memory tools | Shipped |
| P2 Hermes-first MCP expand + compose fill + **shop-quote playbook** + safety deny-list | Shipped |
| P3 Office-day spine (weather, suggested tasks, quote sheet/PDF/HITL send, vision helper) | Shipped |
| P4 Stretch browser evidence tools + docs | Shipped scaffolding |

## Working capabilities

- Orchestrator HUD with Open notes (max **3** expanded), suggested tasks, weather chip, Authorize blast-radius card.
- Right rail: **WeatherCard** (pinned) + scrollable **SuggestedTasksPanel**.
- React Bits accents; mail board via SceneBoard inside SpotlightCard (`bodyClassName` scroll).
- Local-fast path for mail/calendar/briefing snapshot kinds.
- Hermes warm gateway bridge; TTS prefetch + Voicebox cutover.
- Turn log: `work/LAST_TURNS.md` + `GET /api/turns/recent`.
- Local memory upsert/search/forget; quote path through verify + HITL send.

## Still deepen with real office use

- Live Google Sheet quotation workbook bind (local xlsx works).
- Continuous mail→attachment worker on production Gmail volume.
- Honcho → local cutover when local recall quality is proven.
- Full Hermes browser computer-use end-to-end.
- Capability matrix: `work/CAPABILITY_TEST_MATRIX.md`.

## Runtime notes

- Start Hermes gateway and Voicebox desktop app for Mark TTS.
- Prefer API on `127.0.0.1:8000`. Frontend `:3000`.
- Data: `<repo>/data/`; exports: `<repo>/exports/`. Install: `docs/INSTALL.md`. Agents: `AGENTS.md`.
