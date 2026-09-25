# Jarvis — System Truth (Single Source of Truth)

**Generated:** 2026-09-25  
**Status:** Consolidated from all living notes, architecture manifests, capability matrices, and as-built docs. This document replaces all prior work/ and docs/ files.

---

## 1. Product Identity & Architecture

### 1.1 What Jarvis Is

Jarvis is a **24/7 AI office assistant** for a precision machining company. It runs the office's computer grunt work continuously, orchestrates specialist agents, obeys HITL (Human-in-the-Loop) authorization, and progressively becomes fully local.

**Three-layer architecture:**
| Layer | Role | Technology |
|-------|------|------------|
| **Orchestrator (Jarvis)** | Conversation face, HUD/voice, HITL gates, connector ownership, task routing | Next.js 15 (frontend/), FastAPI (backend/app/) |
| **Primary Brain (Hermes)** | Intent understanding, planning, tool choice, draft content, research | Local gateway on :8642 |
| **Overflow/Specialist (Gemini)** | Vision/drawing analysis, heavy research, explicit delegation, fallback | API (cloud) |

**Hard constraints:**
- User always talks to "Jarvis" — Hermes is invisible infrastructure
- HUD stays Jarvis-branded
- **No external send/write without HITL Authorize**
- Tools own mail, calendar, files, and every number — model never invents prices, rates, dimensions, mail, or calendar facts
- Jobs are Hermes playbooks under `backend/app/hermes/playbooks/`, not new agents

### 1.2 Runtime Ports & Paths

| Service | Port/Path | Notes |
|---------|-----------|-------|
| HUD (Next.js) | `http://127.0.0.1:3000` | `frontend/` |
| API (FastAPI) | `http://127.0.0.1:8000` | `backend/app/` |
| Hermes Gateway | `http://127.0.0.1:8642` | Local agent |
| Voicebox TTS | `http://127.0.0.1:17493` | `POST /generate` only |
| Database | `<repo>/data/jarvis.db` | SQLite |
| Exports | `<repo>/exports/` | Only write location |
| Hermes Sessions | `<repo>/data/hermes_sessions.json` | File-based mapping |

### 1.3 Brain Routing (Locked)

| Path | Trigger | Model |
|------|---------|-------|
| **Casual chat** | Greeting, small talk, knowledge questions | Gemini-direct (fast, witty) |
| **Shop work** | Mail, calendar, quotes, drawings, RFQ | Hermes (gateway) |
| **Vision** | Drawing analysis (until local vision exists) | Gemini |
| **Fallback** | Hermes timeout (>30s) or unavailable | Ollama (local) → Gemini |

---

## 2. HUD Architecture (Locked)

### 2.1 Single Pane, Three Lenses

**One `OrchestratorShell`** — no per-workspace desk trees, no presence crossfade.

| Workspace (HudWorkspace) | Lens | Visual Presence |
|--------------------------|------|-----------------|
| `casual` | `converse` | Mint orb (`JarvisCore`) + Particles/LightRays |
| `monitor` | `watch` | Evil Eye (WebGL, ~55% internal res, 30fps, pauses off-screen) |
| `engineering` | `bench` | Drawing viewer (~55%) + quote/machining stack (~40%) |

**Rules:**
- Workspace (`casual|monitor|engineering`) is orthogonal to Turn FSM (`IDLE|LISTENING|THINKING|SPEAKING|AWAITING_HITL|EXECUTING`) — never collapse
- All panels always mounted in `<Pane>`; visibility via depth 0–3 (`DEPTH_VARIANTS`), never conditional render
- Lens changes: all voices start at t=0, settle ≤1.1s, interruptible
- `OrchestratorShell` does not subscribe to `paneStore.lens` (zero shell commits per lens change)

### 2.2 Turn FSM (Server is Truth)

| State | Meaning |
|-------|---------|
| `IDLE` | No turn in flight |
| `LISTENING` | Mic open |
| `THINKING` | Processing |
| `SPEAKING` | TTS playback |
| `AWAITING_HITL` | Pending action queued, waiting Authorize/Reject |
| `EXECUTING` | HITL approved, external effect in flight |
| `DONE` | Terminal success |
| `FAILED` / `ABANDONED` | Terminal error or expired HITL |

**Turn Ledger** (gated by `turn_ledger_enabled`, default **off**) — future work, not yet load-bearing.

### 2.3 Workspace Switching (Hybrid Auto + Pin)

| Rule | Behavior |
|------|----------|
| **Unpinned + ambient/empty desk** | Auto-switch to **Monitor** |
| **Pin on** | Locks auto-switch; explicit work (switcher, +New, RFQ, focusing job/drawing) still moves |
| **Talk-jump from Monitor** | Status questions → stay Monitor; Mail/chat → Casual; Drawing/quote/strategy → Engineering |
| **Reduced motion** | Instant snap, no staged delay |

### 2.4 Visual Specs (Locked)

**Monitor (Evil Eye):**
- `eyeColor="#FF6F37"`, `intensity={1.5}`, `pupilSize={0.6}`, `irisWidth={0.25}`, `glowIntensity={0.3}`, `scale={0.8}`, `noiseScale={1}`, `pupilFollow={1}`, `flameSpeed={1}`, `backgroundColor="#120F17"`
- Internal ~55% resolution / 30fps; CSS upscales
- Pauses when Monitor is not live workspace (tab hidden or other workspace)
- **No Aero Shards**, **no revolving orbs** — still sun-agent orbs below eye only

**Casual:**
- Mint accent `#7dffe0`
- Left Open notes (max 3 expanded), weather chip (shrink-0), suggested tasks, CommandBaton, tiny orchestra dots
- React Bits: `Particles`, `LightRays` on orb only (`ssr: false`)

**Engineering:**
- Drawing hero (~55% `DrawingViewer` + pdf.js), quote/machining stack (~40%)
- SpotlightCard / GlareHover accents
- **No WebGL** (no Eye, no Casual orb, no Shards)

---

## 3. HITL & Safety (Non-Negotiable)

### 3.1 What Requires Authorize (Per External Action)

- Outbound email (send, forward, reply)
- Calendar writes (create, update, delete)
- Sheets/Drive writes
- Quote send (`quote_send`)
- CNC program promote
- Broad memory wipe (namespace/forget-all)
- Browser consequential actions (login, form-submit)

### 3.2 What Is Auto-Allowed

- Local reads, indexing, downloads to local store
- Research/RAG, clarifying questions
- Gemini when user explicitly chose that path
- Read-only browse (HUD-visible)

### 3.3 Execution Envelope

- `pending_actions` flow: `pending → claimed → executed | failed | rejected`
- **Claim-once**: `UPDATE ... SET status='claimed' WHERE status='pending'` must affect **exactly one row**
- `POST /api/confirm` accepts **Idempotency-Key**; repeats return first response
- **External effects bracket**: Insert row with `state='intent'` + `request_hash` **before** outbound call; settle to `sent`/`failed`/`unknown`; boot reconciles `intent`/`unknown` → `needs_human` (never silent retry)
- **Copy discipline**: HUD/chat must not claim external act succeeded until execution records it

### 3.4 HITL UX

- Overlay modal: **Authorize / Reject** buttons (not "Shall I")
- Authorize card shows: total, currency, scope, rate sources, estimate flags, duplicate delivery check
- Duplicate Authorize after `claimed`/`executed` forbidden — surface outcome instead

---

## 4. Quote Workflow (Shop-Quote Playbook)

### 4.1 Playbook Structure

**Source:** `backend/app/hermes/playbooks/quote/` (skill name: `shop-quote`)  
**Install:** API startup `ensure_playbooks_installed()` copies to `{HERMES_HOME}/skills/shop/quote`

### 4.2 Quote Start — Many Doors, One Playbook

| Entry Point | Behavior |
|-------------|----------|
| RFQ email | Hermes loads shop-quote skill |
| Urgent walk-up | Same |
| Hard copy in office | Same |
| Old WhatsApp/email file | Same |
| **No drawing path** | **Do not call `reason_rfq`** — fallback: *"Which drawing — inbox attachment, file on desk, or photo?"* |

**Routing:** `is_quote_start()` → semantic router `tool_ops` / `DAT.03` → Hermes first. On Hermes error/timeout (default 30s), local fallback line only.

### 4.3 Quote Steps (Owner Order)

1. **Labour-only vs buy raw material** — default per customer; this order's mail or verbal word overrides; neither → ask
2. **If buy RM** — request supplier quote; note when it arrives
3. **Machining strategy** — operations, outsource, machines, special tooling (with team or alone)
4. **Machining cost** — from Machine Hour Rate (MHR)
5. **Assemble quotation** — special notes + delivery time → PDF → HITL send

### 4.4 Manufacturing Physics (Code Must Respect)

| Rule | Enforcement |
|------|-------------|
| Machining cost = Σ(op time × MHR) + setup + tooling | Setup per batch (per-piece on 100-off overquotes, omitted on 1-off underquotes) |
| Cycle time from `cycletime` estimates or measured actuals | Never a guess; estimates carry confidence band + sample count |
| Material cost = nested blank mass/length × rate | Include saw kerf, facing allowance, grip remnant — **never finished-part mass** |
| Scope drives material | Labour-only = no RM line; with-material = always RM line |
| Outsource = priced line with vendor quote | Record case: no suitable machine / customer asked / capacity full / process not done in-house |
| Tolerance/finish drives process from table | Unreadable → ask |
| Units + currency with every number | Money = integer minor units |

### 4.5 MHR Floor & Freshness (Blockers)

- Floors in `machine_hour_rates` with `effective_from`/`effective_to`, read **as-of** quote date
- **Quoted rate ≥ floor** — above floor is owner's call; below = BLOCKER
- **Missing data = failure, not skip** — no machine, no rate, machine absent from table, expired rate → BLOCKER
- **RM basis > 30 days = BLOCKER** at send (supplier quote, invoice, or estimate alike)
- Outsource age = WARN only

### 4.6 Proof (`quote_verify`)

| Severity | Checks | Behavior |
|----------|--------|----------|
| **BLOCKER** | Zero/negative/absent unit price, total ≤ 0, qty×rate mismatch, missing rate source, missing/expired MHR, unattested/shipped-seed rate, RM basis >30 days, scope↔material contradiction, missing outsource price, unlabelled estimate, price from unconfirmed drawing fact, missing drawing revision, attachment hash mismatch, **empty delivery at `stage='send'`** | Any BLOCKER ⇒ `stop: true`; `quote_send` refuses to queue |
| **WARN** | Delivery field at `stage='draft'` | Warn at draft (pricing review must not be blocked), block at send |
| **Stage-dependent** | Delivery field | WARN at draft, BLOCKER at send — ask once while drafting, again on Authorize card (field carried inline) |

- Proof runs against stored `quote_revision`, not chat memory
- Verified PDF bound by sha256; `quote_send` re-hashes and refuses on drift
- >2 BLOCKER failures → `stop: true`
- Corrections go to playbook `notes.md` via `quote_playbook_note`, then broken step re-runs

### 4.7 Quote Send (HITL)

- `quote_send` queues Authorize card, **never** sets `sent: true`
- Authorize card shows: total, currency, scope, rate sources, estimate flags, duplicate delivery check
- **Delivery is never computed** — no capacity model, no lead-time arithmetic. Owner-typed or empty; blocks at Authorize.
- Customer/party fields from Master Data later

### 4.8 Never Underquote (Locked)

| Past Miss | Prevention |
|-----------|------------|
| Price corrected after send | Proof gates at send |
| Assumed material | RM line required for with-material; banned for labour-only |
| Forgotten outsource | Outsource priced line mandatory when applicable |
| Quoted material on labour-only | Scope↔material contradiction = BLOCKER |

---

## 5. Data & Schema (Locked)

### 5.1 Migration Discipline

- Schema changes → numbered SQL under `backend/migrations/` + row in `schema_migrations`
- **No ad-hoc `ALTER` in `init_db()`** — no patch blocks for production tables
- Forward-only: backfills in migration scripts, not request handlers

### 5.2 Types & Storage

| Type | Rule |
|------|------|
| **Money** | Integer minor units + ISO currency code on every monetary column; never float dollars |
| **Dimensions** | Numeric value + unit column (mm, in, kg, …); never bare floats |
| **Timestamps** | UTC ISO-8601 via `db.utc_now()`; render with `settings.tz`; naive `datetime.now()` banned in writes |

### 5.3 Provenance on Priced Data

- Every quotable/billable row carries `source_kind` + `source_ref` (or `rate_source_id`)
- **Demo/seed rows (`source_kind='demo'`) are stored but not sendable until attested**
- Attestation: `attested_by` set + value differs from shipped seed

### 5.4 Master Data Edits

- Temporal rates: always query **as-of** business date with `effective_from`/`effective_to`
- **No hard deletes** on authoritative rows — supersede with new row, end-date old
- Corrections append-only; audit fields (`created_at`, attestation) survive migrations

---

## 6. Memory & Knowledge (100% Local)

### 6.1 Three Planes — Never Collapsed

| Question Type | Store | Rule |
|---------------|-------|------|
| "What is the number?" | SQL master data / ledger | Authoritative; cite row id |
| "What do we know about X?" | Entity cards / confirmed facts | **Only owner-confirmed facts are quotable** |
| "Where is it written?" | Corpus chunks (BM25 + vector) | Citations only — **never** source of a number |

**Routing:** number → SQL; know-about → card; where-written → retrieval; absent → **ASK**, never interpolate

### 6.2 Storage

- **Ledger mirror, entity cards, vectors**: SQLite + LanceDB under `<repo>/data/memory/`
- **No cloud memory service** — no hosted vector DBs, no sync to third-party memory APIs
- **Honcho stripped entirely** (locked 2026-09-22)

### 6.3 Drawing Identity & Recall

- Identity cascade: exact hash → confirmed fingerprint → `(customer, drawing_no, revision)`
- Revision change = diff + warning, never silent reuse
- Vision re-runs only when: card missing, revision changed, bytes changed, extraction failed, or owner asks
- Shop-floor memory = event log + rebuildable `shop_state` projection with freshness stamp

### 6.4 Ingest Bans

- **Do not ingest**: Jarvis' own chat prose, tool error strings, failed vision stubs
- Vision error text ≠ substitute for extracted drawing facts

### 6.5 Embeddings

- Record **embedding model id + dimension** per vector row; mixed dims = invalid
- Hash-of-words fallback must be labelled — not silently equivalent to ONNX

### 6.6 Writes

- Ingest off hot request path (outbox/async where implemented)
- Search reads must not block on unbounded ingest

---

## 7. Drawing Vision (Two Gates, Never One)

### 7.1 Gate 1 — Consent (Cannot Be Overridden)

- Default: **deny**
- Cloud vision only when: `customer_terms.allow_cloud_vision = 1` AND `nda = 0`, attested by owner
- Unknown/unresolved customer ⇒ deny and ask
- **Never infer consent** from past job, sibling part, similar name
- No quota override, urgency, or owner instruction grants consent inside a turn
- Changing consent = deliberate master-data edit

### 7.2 Gate 2 — Quota (Owner-Overridable, Once, Per Drawing)

- Cap: **5 documents per cycle** (cycle = 10:00 → 10:00 local time)
- One document (one sha256) = one unit, regardless of pages/calls
- Above `vision_page_threshold` (default 4): tool asks first after local sheet index
- **Only owner spends a unit** — automated mail ingest: free local extract → `analysis_state='needs_vision'` → surfaces on bench; unit charged when owner opens RFQ
- Counter global across bench-triggered + manual UI upload
- **Claim before dispatch**: usage row inserted in same transaction checking count, unique on `(cycle_start, file_sha256)`
- Re-analysis of already-charged document = free
- Failed attempt = no charge; 3 consecutive failures on one document → stop and ask
- Over cap ⇒ HITL card naming drawing, customer, used/total count; Authorize grants **one** extra unit for that document (logged); never raises cap, never bypasses Gate 1

### 7.3 Cache & Local Extract First

- Identity cascade before anything: exact-hash or confirmed-fingerprint hit → knowledge card (zero calls)
- Vision runs only when: card missing, revision changed, bytes changed, extraction failed, or owner asks
- Free local path first (PDF text, title block, dimension tokens) → cloud only for unresolved
- Every dispatch writes `disclosure_log` (file hash, customer, provider, purpose, bytes, turn, cycle, authorized_by)
- Failure never ingests error text as drawing content

---

## 8. G-Code (Draft, Verify, Never Transmit)

### 8.1 Hard Boundaries

- **Jarvis never transmits** to control, DNC, or machine network
- Output = file under `<repo>/exports/nc/` + diff for owner
- Every program = `DRAFT` + `(NOT PROVEN ON THE MACHINE)` header until owner Authorize promotes
- Promotion = versioned, append-only; proven program never overwritten in place
- Missing trusted geometry → refuse with missing list; never interpolate dimension, stock size, or datum
- No program for machine without `machines` row (dialect, control model, axis travels, rapid rates, spindle limits, tooling from master data)

### 8.2 Dialect Discipline (FANUC / Mitsubishi)

- Emit only for recorded control (`machines.control_make`, `control_model`)
- Dialects differ in: canned-cycle args, subprogram call/nesting, macro variable ranges, retract behaviour
- When control absent or construct unverified → emit long-hand motion or refuse
- Unit code always explicit (`G20`/`G21`); plane, absolute mode, feed mode (`G94`/`G95`), work offset declared in header
- M-codes from per-control **whitelist**; blocklist of few G-codes is not a safety model

### 8.3 Deterministic Verification (`program_verify`)

Fails closed on: unresolved modal state; motion outside travels; rapid below clearance or into stock; feed/speed outside tool/material envelope; tool without offset; unbalanced cycle start/cancel; missing safe retract before tool change/end; spindle/coolant contradictions; subprogram/macro call not present; unit/scale mismatch vs drawing; arc without valid centre/radius. Every failure names block number.

### 8.4 Optimisation Bounded

**Allowed:** air-move reduction, approach/retract distances, pass depth/step-over within tool envelope, tool-change ordering, sequencing across setups, canned cycle selection (verified for control)  
**Never:** raise feed/speed above tooling table, remove clearance move, skip spring/finish pass, loosen tolerance-driven step-over, merge operations routing separates  
**Report:** savings as estimate with simulation basis; store both estimate and later measured cycle time

### 8.5 Cycle-Time Simulation

- Integrate motion with per-axis rapid rates, accel/decel, corner deceleration from `machines`, expanded canned cycles, dwells, tool changes, load/unload from routing
- Naive length ÷ feed = not an estimate
- Calibrate against measured times per machine/material; report correction factor + sample count
- Uncalibrated estimates = labelled, flow into quote as `is_estimate`

---

## 9. Cloud Vision Spend (Locked 2026-09-22)

- **Default deny** per customer (NDA drawings never leave)
- **Only owner action spends a unit** — automated ingest stops at free local extract + `needs_vision` flag
- **Authorised customers**: shared cap of **5 documents per 10:00→10:00 cycle**
- 6th document → asks for override (worth 1 document)
- Pack >4 sheets → asks before spending
- Override never grants consent
- Known drawings → answer from saved card (zero calls)

---

## 10. Rate Data (Locked 2026-09-22)

- `source_kind='demo'` table = production source while Master Data UI deferred
- Owner fills with real shop rates
- **Sendability hinges on attestation, not storage**
- Rate quotable only once `attested_by` set + value ≠ shipped seed
- Missing machine, missing rate, unlisted machine → **blocks send** (not skip)

---

## 11. Tool Wear (Locked 2026-09-22)

- `toolwatch` v0: manual shop log only — one spoken/typed line per insert change
- **No FOCAS/MTConnect, no sensors, no `machine_telemetry` in this phase**

---

## 12. Capability Test Matrix (Active)

| Section | Focus | Tags |
|---------|-------|------|
| A | Conversation, brain & semantic router | desk/offline |
| B | HITL & safety | desk/cloud/offline |
| C | Mail | desk/offline |
| D | Calendar & briefing | desk/cloud |
| E | Orchestrator HUD & FSM | cloud |
| P | HUD workspaces, morph & skins | cloud (P16/P17 retired) |
| F | Shop / sheets / CNC / docs | desk/offline |
| G | RFQ → quote → send | desk/offline |
| H | Memory & RAG | desk/offline |
| I | Metrics, health & ops | desk/cloud/offline |
| J | Desk, conversations & UI commands | desk/cloud |
| K | Voice & TTS | desk/cloud |
| L | Drawing, vision & viewer | desk/offline |
| M | Canvas & artifacts | desk/offline |
| N | Connectors & preferences | desk/offline |
| O | Stretch (later) | — |

**Test method:** One use case at a time → pass/fail + latency → dispatch fix → continue  
**Prerequisite:** `OrchestratorShell` at :3000, two state layers never collapsed  
**Run log:** Auto-appended by API to `work/LIVE_TEST.md` + JSONL (distinct from human verdict log)

---

## 13. Agent Roster & Skills

| Agent | Owns | Needs Desk Machine? |
|-------|------|---------------------|
| `jarvis-uiux` | Layout, React Bits, weather/tasks panels, visual polish | No (cloud-verifiable rendering/layout/scroll/card-state) |
| `jarvis-voice` | Voicebox, `/api/tts`, speak bridge, double-play, latency | Yes — Voicebox on :17493 |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools | Yes for live mail/Hermes; no for logic + `backend/tests` |
| `jarvis-builder` | General agreed implementation / restarts / verify | Only for restarts and live verification |

**UI/UX Rule:** Always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents  
**Placement Policy:** Cloud workers can build/serve HUD and drive headless Chrome (`--enable-unsafe-swiftshader` for WebGL); what they cannot reach: Hermes, Voicebox, real Google OAuth, GPU-representative Ollama, physical mic/speaker

---

## 14. Key Files Reference

| File | Role |
|------|------|
| `docs/CURRENT.md` | As-built snapshot (what works on desk today) |
| `docs/SYSTEM_TRUTH.md` | **This file** — single source of truth |
| `docs/ROADMAP.md` | Next steps & priorities |
| `AGENTS.md` | Agent & skill map |
| `.cursor/rules/00-jarvis-core.mdc` | Always-on core rules |
| `.cursor/rules/backend/*.mdc` | Backend module rules |
| `.cursor/rules/domain/*.mdc` | Domain workflow rules (quote, gcode, vision, master data, knowledge) |
| `.cursor/rules/frontend/*.mdc` | HUD shell, React Bits, UI/UX |
| `.cursor/rules/ops/*.mdc` | Tests, living notes, dispatch |
| `work/CAPABILITY_TEST_MATRIX.md` | Capability test IDs and log |
| `backend/app/hermes/playbooks/quote/` | Shop-quote playbook source |
| `backend/app/quote.py` | Quote implementation |
| `frontend/src/lib/orchestratorFsm.ts` | Pure FSM reducer |
| `frontend/src/components/orchestrator/OrchestratorShell.tsx` | Primary shell |

---

## 15. Locked Decisions Log

| Date | Decision | Reference |
|------|----------|-----------|
| 2026-09-14 | Thin Jarvis shell; Hermes primary brain; Gemini overflow | Vision Workbook §1 |
| 2026-09-14 | HITL per external action; auto-allow local prep | Vision Workbook §8 |
| 2026-09-14 | Dual-write memory (Honcho cloud + local) | Vision Workbook §2 |
| 2026-09-14 | Hermes-first intelligence; tiny deny-list only | Vision Workbook §7 |
| 2026-09-14 | Soft Hermes-invented teams; parallel jobs | Vision Workbook §6 |
| 2026-09-14 | Latency targets; 30s soft Gemini fallback | Vision Workbook §3 |
| 2026-09-14 | Gemini overflow triggers; vision-first for drawings | Vision Workbook §9 |
| 2026-09-14 | Hermes browser first; controlled profile; keychain secrets | Vision Workbook §10 |
| 2026-09-14 | OSS leverage; AGPL OK personally | Vision Workbook §11 |
| 2026-09-14 | Voice-first, keyboard-equal; office-day HUD | Vision Workbook §12 |
| 2026-09-14 | Local-first, single-user, controllable retention | Vision Workbook §13 |
| 2026-09-14 | Foundation metrics: latency + HITL=0 + office-day loop | Vision Workbook §14 |
| 2026-09-16 | Three HUD workspaces (Casual/Monitor/Engineering) | ARCHITECTURE_POINTS §2026-09-16 |
| 2026-09-16 | Staged morph; Aero Shards off Monitor | ARCHITECTURE_POINTS §2026-09-16 |
| 2026-09-17 | Evil Eye GPU budget (reduced res + 30fps) | ARCHITECTURE_POINTS §2026-09-17 |
| 2026-09-17 | Hermes playbook loop (quote first) | ARCHITECTURE_POINTS §2026-09-17 |
| 2026-09-17 | Quote start many ways; no extra intent AI | ARCHITECTURE_POINTS §2026-09-17 |
| 2026-09-21 | Knowledge planes: drawing remembered, not reprocessed | ARCHITECTURE_POINTS §2026-09-21 |
| 2026-09-22 | Seven executive decisions locked (cloud vision, rates, sign-off, telemetry, RM freshness, memory, delivery) | ARCHITECTURE_POINTS §2026-09-22 |
| 2026-09-22 | Casual chat = Gemini-direct | ARCHITECTURE_POINTS §2026-09-22 |
| 2026-09-22 | One Hermes chat per quote; wipe transcript store | ARCHITECTURE_POINTS §2026-09-24 |
| 2026-09-23 | Overhaul workers local (not cloud) | ARCHITECTURE_POINTS §2026-09-23 |
| 2026-09-23 | Single pane, no staged morph | UI_UX_POINTS §2026-09-23 |

---

**End of System Truth.**  
All prior work/ documentation, OPUS_ARCHITECTURE_MANIFEST.md, VISION_WORKBOOK.md, FOUNDATION_BUILD_PLAN.md, ARCHITECTURE_POINTS.md, UI_UX_POINTS.md, APP_FEATURES.md, SONNET_UI_VISION.md, CAPABILITY_TEST_RUN_*, QUOTE_RUN.md, and architecture-review/ folder are superseded by this document and `docs/ROADMAP.md`.