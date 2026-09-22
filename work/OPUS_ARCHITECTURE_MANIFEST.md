# Jarvis Mark-1 — Opus Architecture Manifest

**Author:** Principal Systems Architect pass (2026-09-21) · **owner decisions locked 2026-09-22**
**Scope:** One-time architectural overhaul of Jarvis Mark-1 — resilience, agent guardrails, precision-machining features, master data, knowledge/recall, handoff protocol, blind spots.
**Status:** **DESIGN OF RECORD for the chunks in §5.6.** The seven executive decisions in §8 are locked by the owner (2026-09-22) and are binding on every chunk; the rest of this document is design that a chunk may refine but not contradict. Conversation locks live in `work/ARCHITECTURE_POINTS.md` / `work/APP_FEATURES.md` / `work/UI_UX_POINTS.md`; as-built truth lives in `docs/CURRENT.md`.
**Grounding:** every "today" claim below is read from this checkout, and the five defects in §6 were reproduced on this VM — see [`/opt/cursor/artifacts/blind_spot_evidence.log`](/opt/cursor/artifacts/blind_spot_evidence.log) and §6.0.

---

## How to read this document

| Reader | Read |
| ------ | ---- |
| Owner | §0 (including §0.1, the locked decisions and what each becomes), §3, §4B.1–4B.3, §6 (severity P0/P1), §8.8's three open defaults |
| Sub-agent dispatcher | §5 in full, then the chunk table §5.6 |
| Implementation worker | Only the sections its kickoff quotes. Workers never read this document for scope — the kickoff carries the excerpt |

**Document law:** this manifest is a *design source*, not a work queue. It does not authorize any edit. §5 defines how it becomes safe, small, reversible changes.

---

## 0. Executive summary

Jarvis today is a well-shaped **single-turn** system: one HTTP round trip, one global brain lock, one browser-resident state machine, and a quote workflow whose state is a session chat log. It works on a desk, with one operator, when nothing drops. It is one process crash, one double-click, or one 20-thousand-mail inbox away from either losing work silently or sending a wrong number to a customer.

Five findings set the priority order. All five were reproduced, not theorised:

1. A **25-off quotation at ₹0.00 passes all eight proof checks** and queues a "Authorize to send the quote PDF" card (§6.1). The proof asserts that prices are *numeric*, never that they are *sane*.
2. The **minimum-MHR floor is enforced only when the data happens to be present** — machine without rate, rate without machine, or a machine absent from the rate table all produce **no check at all** (§6.2). "Never underquote" is currently a best-effort.
3. **Two concurrent Authorize calls send the customer two emails** (§6.3), and a crash between "provider accepted" and "row marked approved" leaves the action re-authorizable. The HITL metric (`miss rate = 0`) cannot see either.
4. **Recall is a full table scan with hash-of-words vectors** — 162 ms at 4 000 docs, linear, inside the turn (§6.4). The stated goal is 100 days of Gmail, which is an order of magnitude more.
5. **The Hermes session map corrupts under concurrent writes** (§6.5), silently detaching a resumed job from its own thread history.

The overhaul is therefore ordered: **make wrong numbers impossible → make state recoverable → make knowledge durable → then add machining intelligence.** Features built on the current foundation would inherit a proof that cannot say no and a memory that cannot recall.

The five structural moves:

| # | Move | Replaces | Section |
| - | ---- | -------- | ------- |
| M1 | Server-authoritative **turn ledger** with leases, heartbeats, and a reaper | Browser-only FSM + synchronous `/api/chat` | §1 |
| M2 | **Claim-once HITL** with an external-effects intent log | Read-then-write `resolve_pending` | §1.5 |
| M3 | **Master data with mandatory price provenance** — a price line without a traceable source cannot be inserted | `memories` key/value quote state + a demo markdown rate table | §4 |
| M4 | **Three memory planes** — ledger (numbers), knowledge cards (confirmed facts per entity), corpus (citable chunks) | One `memory_docs` table searched linearly | §4B |
| M5 | **Tiered `.mdc` rule ecosystem** — a <200-word always-on core, everything else glob-scoped | ~1 570 words injected into every worker turn | §2 |

### 0.1 The seven locked decisions, and what each one becomes in code

Full statements in §8. Their mechanical consequences, because a decision that does not become a constraint is a preference:

| Lock | Becomes |
| ---- | ------- |
| **Cloud vision: default-deny per customer, 5 drawings per 10:00→10:00 cycle, owner override, and only the owner may spend a unit** | Three gates — a per-customer **consent** gate no override can bypass; a **trigger** gate, since automated ingest stops at the free local extract and marks the drawing `needs_vision` rather than charging the pool; and a **quota ledger** that claims a unit atomically before dispatch, counts a document once by sha256, asks before spending on a pack over four sheets, and raises a HITL card when the cycle is spent (§4B.4, §2.7, **V1/V1b/V2**) |
| **Keep the `demo` rate table; owner hand-edits it with real rates** | `source_kind='demo'` stays, but sendability moves from *storage* to *attestation*: a rate row still carrying its shipped seed value, or carrying no `attested_by`, is a **BLOCKER**; an owner-attested row prices real quotes (§4.3, §6.2, **S5**) |
| **Sole commercial authority — no second signature** | No approval tiers, no delegation model. `approved_by` stays as a single-owner audit stamp, and claim-once HITL (§1.5) becomes *more* important, not less: with one signer, a double-tap is the only thing that can forge a second approval (**Q2**) |
| **`toolwatch` v0 on the manual shop log; defer FOCAS/MTConnect** | No control-network integration and no `machine_telemetry` table in this overhaul. v0 needs a **capture surface** instead — a one-line spoken or HUD entry per insert change — or it has no data to learn from (§3.1, **M5**) |
| **Raw-material basis older than 30 days is a hard block** | A global `rm_basis_max_age_days = 30` BLOCKER, evaluated **again at the moment of send**, not only at verify — a quote proved on day 29 and authorized on day 31 must fail (§2.5, §4.4, **Q5**) |
| **Strip Honcho; 100 % local-first on LanceDB + SQLite** | One docstring and one module in code (`backend/app/memory/dual_write.py`), and a superseded strategy in `VISION_WORKBOOK.md` §2. It also promotes §6.4 from a defect to a blocker: LanceDB must become the **read** path, because it is now the committed vector store rather than an optional mirror (§4B.8, **K5/K8**) |
| **Jarvis never guesses a delivery date, but insists on having one** | No capacity model, no computed lead time, ever. The check is **stage-aware**: WARN at `stage='draft'` so pricing can be reviewed, BLOCKER at `stage='send'`. Jarvis asks during drafting and again on the Authorize card, which carries the field inline (§2.5, §3.5, **PG1**) |

Two of these reverse earlier positions in this document, deliberately: demo-sourced rates now *can* price a real quote once attested, and a missing delivery date now *does* block a send. §8 flags the second one against the owner's earlier interview answer.

---

## 1. Architectural & Logic Overhaul

### 1.1 Where the current design actually breaks

Read from the checkout, not inferred:

| Fact | Evidence |
| ---- | -------- |
| The turn FSM exists **only in the browser tab**. There is no server-side record that a turn is in flight | `frontend/src/lib/orchestratorFsm.ts` — `JarvisState` is React state; no turn table in `backend/app/db.py` |
| `/api/chat` is one synchronous request that computes the whole turn before responding | `backend/app/main.py` `api_chat` → `run_agent` |
| Every turn in the whole process takes one **global** lock | `backend/app/conversations.py` `_BRAIN = threading.Lock()`, taken by `agent.run_agent` |
| The HUD send path has **no timeout and no abort**; on any fetch rejection it dispatches `RESET` | `OrchestratorShell.tsx` `send()` — `catch` → `applyEvent({ type: "RESET" })` |
| Backend work already committed during a dropped turn (a queued Authorize, an artifact, a saved attachment) becomes **invisible** — there is no pending-action poll on the desk | no `setInterval`/poll for `api.pending` in `frontend/src/components/orchestrator/` |
| Restore shows the **last completed** surface only, deliberately mute | `backend/app/hud_state.py` `remember_hud` writes after success; `load_hud` returns `speak: ""` |
| Effective turn ceiling is minutes, not seconds: Hermes 30 s (`hermes_timeout_sec`), Gemini vision 180 s (`quote.analyze_drawing_vision`), Ollama 180 s, client ∞ | `backend/app/config.py`, `backend/app/quote.py`, `backend/app/agent.py` |
| SQLite runs with default journal, no `busy_timeout`, and is opened by **two processes** (API + the MCP stdio server) plus background threads | `backend/app/db.py` `connect()`; `backend/app/hermes/mcp_server.py` runs as its own process |

The failure modes that follow are not hypothetical:

- **Stranded THINKING.** Tab keeps the spinner until TCP gives up, because nothing bounds the wait and nothing else knows a turn exists.
- **Lost turn.** Browser reload or a dropped socket during a quote build: the sheet, the PDF, and the queued Authorize exist on disk; the desk shows an idle orb.
- **Head-of-line blocking.** One 35-second casual Hermes turn stalls the morning brief, the office refresh, and every other session, because they share `_BRAIN`.
- **Ghost authority.** A duplicate `POST /api/confirm` executes twice (§6.3).

### 1.2 Target pattern — server-authoritative turn ledger, client as projection

The invariant: **the server owns turn state; the browser renders a projection of it.** The strict FSM is kept exactly as it is — it is good, and its purity is what makes reconciliation cheap — but it gains one event (`RECONCILE`) and stops being the only copy of the truth.

```
POST /api/chat            -> writes turns row (QUEUED), returns {turn_id, state} in <100ms
worker (bounded pool)     -> RUNNING, heartbeat + stage every 5s, writes result
GET  /api/turns/{id}/events (SSE, Last-Event-ID) -> stage/result stream
GET  /api/turns/open?session_id=  -> reconciliation on mount / reconnect / tab focus
turn_reaper (background)  -> expired lease => FAILED(stage) — never leaves RUNNING
```

SSE, not WebSocket: the stream is one-way, survives proxies, and resumes with `Last-Event-ID`. Polling `GET /api/turns/{id}` every second is the documented fallback, so no HUD feature depends on SSE being available.

```sql
CREATE TABLE turns (
  id                TEXT PRIMARY KEY,           -- t-<uuid>
  session_id        TEXT NOT NULL,
  idempotency_key   TEXT NOT NULL UNIQUE,       -- client-generated; retries are free
  state             TEXT NOT NULL,              -- QUEUED|RUNNING|AWAITING_HITL|EXECUTING|DONE|FAILED|ABANDONED
  stage             TEXT NOT NULL DEFAULT '',   -- router|hermes|vision|tool:quote_build|...
  input             TEXT NOT NULL,
  route             TEXT NOT NULL DEFAULT '',   -- semantic_router verdict
  output_json       TEXT NOT NULL DEFAULT '',   -- ChatResponse payload when DONE
  pending_action_id TEXT,
  mission_id        TEXT,
  lease_owner       TEXT NOT NULL DEFAULT '',   -- worker id
  heartbeat_at      TEXT,
  lease_expires_at  TEXT,
  attempt           INTEGER NOT NULL DEFAULT 1,
  error             TEXT NOT NULL DEFAULT '',
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
CREATE INDEX turns_open ON turns(session_id, state);
CREATE INDEX turns_lease ON turns(state, lease_expires_at);
```

`idempotency_key` is the whole retry story: the HUD generates it per user action, so a resend after a network blip returns the *same* turn instead of starting a second one.

### 1.3 Turn state machine, and its mapping to `JarvisState`

```
         ┌─────────┐   claim    ┌─────────┐  reply w/ speech   ┌──────┐
 SEND ──▶│ QUEUED  │──────────▶ │ RUNNING │ ─────────────────▶ │ DONE │
         └─────────┘            └─────────┘                    └──────┘
                                  │     │ pending action queued
                    lease expired │     ▼
                                  │  ┌────────────────┐ approve  ┌───────────┐
                                  │  │ AWAITING_HITL  │────────▶ │ EXECUTING │──▶ DONE
                                  │  └────────────────┘  reject   └───────────┘
                                  ▼           │ no decision in N days
                              ┌────────┐      ▼
                              │ FAILED │  ┌───────────┐
                              └────────┘  │ ABANDONED │
                                          └───────────┘
```

| Server turn state | Client `JarvisState` | Notes |
| ----------------- | -------------------- | ----- |
| `QUEUED`, `RUNNING` | `THINKING{message, stage}` | `stage` is displayed; it is also what a reaper failure reports |
| `AWAITING_HITL` | `AWAITING_HITL{action,…}` | Unchanged panel semantics, including the two sub-booleans |
| `EXECUTING` | `EXECUTING{actionId}` | Now durable: survives reload |
| `DONE` with speech | `SPEAKING` → `IDLE` | On *reconnect* (not first delivery) restore text muted, as `load_hud` already does |
| `FAILED`, `ABANDONED` | `IDLE` + explicit failure line | "The brain dropped that at *vision*. Retry?" — never a silent reset |

The FSM stays a pure reducer. Add exactly one event and one selector; do not scatter server fields through the component:

```ts
| { type: "RECONCILE"; turn: ServerTurn | null }   // ledger snapshot -> mode
export function hydrate(turn: ServerTurn | null): JarvisEvent   // pure mapping, unit-testable
```

**Non-negotiable:** a client timeout is *not* a job cancellation. Aborting the fetch stops the tab from waiting; the turn keeps running and is picked up again from the ledger. Cancellation is a separate, explicit `POST /api/turns/{id}/cancel`.

### 1.4 Reconciliation matrix

Applied on mount, on tab focus, on SSE reconnect, and after every fetch failure:

| Client believes | Ledger says | Action |
| --------------- | ----------- | ------ |
| `THINKING` | `RUNNING` (fresh heartbeat) | Re-subscribe, keep spinner, show `stage` |
| `THINKING` | `RUNNING` (stale lease) | Wait for the reaper (≤15 s), then show the failure line with `stage` + Retry |
| `THINKING` | `DONE` | Render result, restore muted if the speech generation is stale (`voice.ts` late-clip rule) |
| `THINKING` | `AWAITING_HITL` | Open the HITL panel; do **not** auto-open the confirm mic (matches `loadSessionSurface` today) |
| `IDLE` | `AWAITING_HITL` | Open the panel — this is the lost-turn case that is invisible today |
| `AWAITING_HITL` | action `claimed`/`executed` | Close panel, show the outcome; never offer Authorize twice |
| `EXECUTING` | `DONE`/`FAILED` | Render terminal state |
| anything | no open turn | `RESET` + restore `hud_state` surface |

### 1.5 Exactly-once at the only place it matters: HITL execution

Grunt work is allowed to be at-least-once. **External effects must be at-most-once, and must be *provably* so.** The owner is the sole commercial signer (§8.3), which raises the stakes rather than lowering them: there is no second reviewer downstream, so a double-tap or a retried POST is the only way a second approval can exist at all. Three changes:

**(a) Atomic claim.** `pending_actions.status` becomes `pending → claimed → executed | failed | rejected`, and execution begins only if the claim wins:

```sql
UPDATE pending_actions
   SET status='claimed', claim_id=:claim, claimed_at=:now
 WHERE id=:id AND status='pending';
-- proceed only when rowcount == 1; otherwise reply "already handled"
```

This alone closes §6.3. `POST /api/confirm` also accepts an `Idempotency-Key` and returns the first response for a repeat.

**(b) Intent log before the call.** A provider call is bracketed by durable rows, so a crash is recoverable instead of ambiguous:

```sql
CREATE TABLE external_effects (
  id TEXT PRIMARY KEY, action_id TEXT NOT NULL, provider TEXT NOT NULL,   -- gmail|gcal|sheets|drive
  request_hash TEXT NOT NULL,        -- sha256(to|subject|body|attachment hashes)
  state TEXT NOT NULL,               -- intent|sent|failed|unknown
  provider_message_id TEXT, error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, settled_at TEXT
);
CREATE UNIQUE INDEX external_effects_dedupe ON external_effects(provider, request_hash);
```

Boot-time recovery: any `intent`/`unknown` row is reconciled against the provider (Gmail search by `request_hash` in a header, or the thread) before Jarvis will ever re-offer that action. If reconciliation is impossible, the action is parked in `needs_human` — **never retried silently**.

**(c) Blast-radius card gets a truth field.** `hitl_meta.blast_radius_for` already scores irreversibility; add "this will be the *first* delivery of this exact content" vs "an identical message was already accepted at HH:MM", computed from `external_effects`. That is the one HUD line that makes duplicate sends impossible to click through.

### 1.6 When Hermes (or the frontend) drops mid-task

**Hermes session durability.** Replace `data/hermes_sessions.json` (proven corruptible, §6.5) with a table, and make any remaining JSON writes `tempfile + os.replace` under a lock:

```sql
CREATE TABLE hermes_sessions (
  session_id TEXT PRIMARY KEY, hermes_thread TEXT NOT NULL,
  transport TEXT NOT NULL, updated_at TEXT NOT NULL
);
```

**Circuit breaker.** `hermes_available()` is a liveness probe; it does not protect against a gateway that accepts and stalls. Add a breaker in `backend/app/hermes/bridge.py`: 3 consecutive timeouts/5xx in 120 s → open for 60 s → half-open single probe. While open, work turns take the degraded path.

**Degraded mode must be honest and narrow.** Today a Hermes miss falls through to Gemini or legacy handling. That is right for chat and wrong for money. Degraded policy:

| Turn class | Hermes down | Rule |
| ---------- | ----------- | ---- |
| Casual chat | Gemini direct | Already the lock (`ARCHITECTURE_POINTS` 2026-09-22) |
| Mail/calendar read | Local snapshot path | Already implemented (`_local_legacy`) |
| Quote / price / routing | **Tools only, no synthesis** | Jarvis may read master data and say what it has; it may not compose a price or a strategy. Existing line — "Which drawing should I quote…" — stays the honest fallback |
| Drawing vision | Queue as an async job | Never inline 180 s inside a turn (§1.8) |

**Frontend drop.** Covered by §1.4. The important consequence: a job resumed after a reload is the *same* turn (ledger id) and the same Hermes thread (durable map), so context is not silently reset.

**Stage-aware resume.** The reaper does not blindly retry. Retry policy is per stage, declared in code, because stages differ in idempotency:

| Stage | Retryable | Why |
| ----- | --------- | --- |
| `router`, `hermes`, `rag` | yes, automatic (max 2) | Read-only |
| `vision` | yes, but charges an API call → ask once | Costs money; cache by file hash (§4B.4) makes the retry free |
| `tool:quote_build`, `tool:quote_pdf` | yes — writes are keyed by `quote_revision_id` | Idempotent after §4 |
| `tool:*_send`, `confirm` | **never automatic** | §1.5 owns these |

### 1.7 Concurrency, storage, and the multi-process reality

| Change | Why |
| ------ | --- |
| Replace the global `_BRAIN` lock with **per-session locks + a bounded global semaphore** (default 3 concurrent brain turns, 1 per session) | A casual turn must not queue behind a night-shift ingest |
| Separate semaphore + low priority for background work (`snapshot`, `mail_sync`, `office_day`) | Interactive turns win by construction |
| `PRAGMA journal_mode=WAL; busy_timeout=5000; synchronous=NORMAL; foreign_keys=ON` in the single `db.connect()` chokepoint | The MCP server is a second **process** on the same file; without WAL this is a matter of time |
| **Schema versioning + forward-only migrations** (`schema_migrations` table, `backend/migrations/NNNN_*.sql`), retiring the ad-hoc `PRAGMA table_info` patch block in `init_db()` | §4 adds ~20 tables; the current pattern cannot express renames, constraints, or backfills |
| Nightly `VACUUM INTO` snapshot with retention, `PRAGMA integrity_check` on boot | One file currently holds quotes, mail, and memory with no backup (§6.18) |
| `data/` write path is always via `db.connect()`; no module writes its own JSON state file | `hermes_sessions.json` was the last one |

### 1.8 Latency budget and the timeout contract

The vision's targets (casual ≤5 s, simple tool ≤15 s, long jobs async) become an enforced contract, not an aspiration:

| Class | Client abort | Server budget | Over budget |
| ----- | ------------ | ------------- | ----------- |
| Casual (Gemini direct) | 8 s | 6 s | Fall to a short local line; log `budget_exceeded` |
| Tool turn (local snapshot / master data read) | 20 s | 15 s | Turn continues in ledger; HUD shows stage |
| Hermes work turn | 20 s (client stops waiting; job continues) | 30 s gateway | Breaker counts it; turn resolves via ledger |
| Vision / research / nesting / cycle-time sim | **no inline wait** | async job | Progress on HUD; optional spoken completion |

`analyze_drawing_vision`'s 180-second inline call is the clearest violation today: it can hold the global brain lock for three minutes. It becomes a job.

Per-stage latency is recorded in the ledger (`turns.stage` transitions), which also fixes the metric gap in §6.17 — today samples live in an in-process `deque(maxlen=200)` and vanish on restart.

### 1.9 Acceptance for Pillar 1

1. Kill the API mid-turn; the HUD reports the stage it died at within 15 s and offers Retry. No spinner outlives the reaper.
2. Reload during a quote build; the HUD re-attaches to the same turn and the same Hermes thread, and any queued Authorize appears.
3. Fire 5 concurrent `POST /api/confirm` for one action; exactly one external effect, four "already handled".
4. Kill the process between provider accept and status write (fault injection); on boot the action is `needs_human`, never re-offered.
5. Casual turn p50 unchanged or better with 3 background jobs running (no head-of-line blocking).
6. Matrix IDs to re-run: **A3, B1–B4, E-section, I-section**.
---

## 2. The Cursor Rule Ecosystem (`.mdc` files)

### 2.1 What the current set costs

Measured in this checkout (`wc -w`), injected into **every** worker turn regardless of the task:

| Always-on today | Words |
| --------------- | ----: |
| `AGENTS.md` | 599 |
| `.cursor/rules/jarvis-core.mdc` (`alwaysApply: true`) | 348 |
| `.cursor/rules/jarvis-capability-run.mdc` | 240 |
| `.cursor/rules/jarvis-subagent-dispatch.mdc` | 225 |
| `.cursor/rules/jarvis-living-notes.mdc` | 161 |
| **Total** | **1 573 (~2.1k tokens)** |

Two problems, neither of which is "too many words" in the abstract:

1. **Mis-targeting.** A worker fixing `WeatherCard.tsx` is told how to dispatch background agents and how to log capability observations. A worker writing `backend/tests` is told the Evil Eye's frame rate. Every irrelevant sentence is a chance to act on the wrong constraint.
2. **Duplication.** Stack, ports, HITL list, and data paths appear in `AGENTS.md`, `jarvis-core.mdc`, and the `jarvis-architecture` skill. Three copies drift; a worker that reads the stale one is not wrong, it was told wrong.

Target: **≤200 words always-on**, everything else earned by file scope or by task description.

### 2.2 The tiering law

| Tier | Mechanism | Budget | Contains |
| ---- | --------- | -----: | -------- |
| **T0 Core** | one file, `alwaysApply: true` | <200 words | Facts true of the whole repo that a wrong guess would break: ports, data paths, what owns numbers, what needs Authorize, what must never be committed |
| **T1 Scoped** | `globs:`, `alwaysApply: false` | ≤400 words each | Constraints for one area — loaded only when a matching file is in play |
| **T2 Description-routed** | `description:` only, no globs | ≤400 words | Cross-cutting procedures the agent should fetch when the *task* matches (dispatch, living notes, capability runs) |
| **T3 Skills** | `.cursor/skills/*/SKILL.md` | unbounded | Long procedures, examples, catalogues. Rules link to them; rules never inline them |

Frontmatter contract:

```yaml
---
description: <one line, written for a router: when should an agent pull this?>
globs: <comma-separated globs; omit for T2>
alwaysApply: <true only for 00-jarvis-core.mdc>
---
```

Law: `description` is a *routing* sentence ("use when…"), not a title. Omitting `globs` on a T1 rule silently makes it dead weight; setting `alwaysApply: true` anywhere but T0 is a review failure.

### 2.3 Proposed tree

```
.cursor/rules/
  00-jarvis-core.mdc                 alwaysApply  (<200 words)           §2.4
  backend/
    10-api-python.mdc                globs: backend/app/**/*.py
    11-hitl-safety.mdc               globs: backend/app/{agent,main}.py, backend/app/hermes/**, backend/app/tools/**
    12-data-schema.mdc               globs: backend/app/db.py, backend/app/schemas.py, backend/migrations/**, backend/app/masterdata/**
    13-turn-ledger.mdc               globs: backend/app/turns/**, backend/app/agent.py, backend/app/main.py
  frontend/
    20-hud-shell.mdc                 globs: frontend/src/components/orchestrator/**, frontend/src/lib/orchestratorFsm.ts
    21-react-bits.mdc                globs: frontend/**/*.{tsx,ts,css}      (exists today — keep, trim)
  domain/
    30-quote-playbook.mdc            globs: backend/app/quote.py, backend/app/hermes/playbooks/quote/**, backend/tests/test_quote_playbook.py   §2.5
    31-gcode-optimiser.mdc           globs: backend/app/cnc_suggest.py, backend/app/machining/**, backend/app/hermes/playbooks/gcode/**        §2.6
    32-master-data.mdc               globs: backend/app/masterdata/**, backend/migrations/**
    33-knowledge-rag.mdc             globs: backend/app/memory/**, backend/app/knowledge/**
    34-drawing-vision.mdc            globs: backend/app/quote.py, backend/app/vision/**       §2.7
  ops/
    40-tests.mdc                     globs: backend/tests/**, frontend/**/*.test.{ts,tsx}
    41-living-notes.mdc              T2 (description-routed)   — today's jarvis-living-notes.mdc
    42-dispatch.mdc                  T2 — today's jarvis-subagent-dispatch.mdc + jarvis-capability-run.mdc merged
```

Migration of what exists: `jarvis-core.mdc` splits into `00-jarvis-core.mdc` (T0) + `backend/11-hitl-safety.mdc` + `frontend/20-hud-shell.mdc`; `jarvis-react-bits.mdc` stays as `frontend/21-react-bits.mdc`; the two dispatch/capability rules merge into one T2; `AGENTS.md` shrinks to a map (roster + doc index + placement policy) and stops restating the stack.

### 2.4 `00-jarvis-core.mdc` — the entire always-on budget

```mdc
---
description: Jarvis repo-wide facts — stack, ports, data paths, who owns numbers, what needs Authorize
alwaysApply: true
---

# Jarvis core

- HUD: Next.js `frontend/` on :3000. API: FastAPI `backend/app/` on 127.0.0.1:8000.
- Brain: Hermes gateway :8642 for shop work; Gemini for casual and vision; Ollama last.
- TTS: Voicebox :17493, `POST /generate` only (never `/speak`).
- Data: `<repo>/data/jarvis.db`. Written files: `<repo>/exports/` only.
- One shell: `OrchestratorShell`. Turn state is a server ledger projected by
  `frontend/src/lib/orchestratorFsm.ts`. Workspaces (`casual|monitor|engineering`)
  are a separate layer and never collapse into turn state.
- Tools own mail, calendar, files, and every number. The model never invents a
  price, rate, dimension, mail, or calendar fact. No source → ask.
- Authorize (HITL) before any external or destructive act: send mail, calendar
  write, quote send, sheet write, CNC promote, broad memory wipe. Queue it; never
  claim it was done.
- Jobs are Hermes playbooks under `backend/app/hermes/playbooks/`, not new agents.
- Never commit `.env`, `data/`, `exports/`, tokens, or customer drawings.

Scoped rules in `.cursor/rules/` and skills in `.cursor/skills/` carry the detail.
Architecture: `docs/CURRENT.md` (as-built), `work/OPUS_ARCHITECTURE_MANIFEST.md` (target).
```

**189 words including frontmatter** (verified with `wc -w`).

### 2.5 `domain/30-quote-playbook.mdc` — manufacturing physics, MHR floors, HITL

```mdc
---
description: Hard rules for the shop-quote workflow — price provenance, MHR floors, proof severity, HITL send. Use when touching quote code, the quote playbook, or quote tests.
globs: backend/app/quote.py, backend/app/hermes/playbooks/quote/**, backend/app/masterdata/rates.py, backend/tests/test_quote_playbook.py
alwaysApply: false
---

# Quote workflow — non-negotiables

Underquoting is the failure the owner has actually suffered — a price corrected after
send, an assumed material, a forgotten outsource, material billed to a labour-only
customer. Fail closed.

## Provenance (no exceptions)

- Every money-bearing line carries `rate_source_id` → a `supplier_rm_quotes`,
  `machine_hour_rates`, `outsource_quotes`, or `owner_input` row. No source, no line.
- An estimate is labelled: `is_estimate = 1` plus a basis naming historical
  transactions or market trend. An unlabelled estimate is a bug.
- Sendability follows **attestation, not storage.** `source_kind='demo'` is a
  supported production source while the Master Data UI is deferred, but a rate row
  is quotable only when `attested_by` is set and its value differs from the shipped
  seed. An unattested row, or one still holding the shipped seed number, is a BLOCKER.
- The model never derives a price from prose, memory, or "similar jobs".

## Manufacturing physics the code must respect

- Machining cost = Σ(operation time × MHR) + setup + tooling. Setup is per batch: per
  piece on a 100-off overquotes, omitted on a 1-off underquotes.
- Cycle time comes from `cycletime` estimates or measured `routing_operations`
  actuals, never a guess; estimates carry a confidence band and sample count.
- Material cost = nested blank mass or length × rate, including saw kerf, facing
  allowance, and grip remnant. Never finished-part mass.
- Scope drives material: labour-only orders never carry a raw-material line;
  with-material orders always do. Default is per customer; this order's mail or
  the owner's word overrides it; neither present → ask.
- Outsource (heat treat, plating, grinding, no suitable machine, the customer asked,
  or capacity full) is a priced line with a vendor quote and a recorded case. Never
  a guessed amount.
- Tolerance and finish drive process from a table, not judgement; unreadable → ask.
- Units and currency travel with every number; money is integer minor units.

## MHR floor and freshness

- Floors live in `machine_hour_rates` with `effective_from/effective_to`, read
  **as of** the quote date, keyed by machine or machine type.
- Quoted rate ≥ floor. Above the floor is the owner's call; below is a BLOCKER.
- **Missing data is a failure, not a skip.** No machine, no rate, machine absent
  from the rate table, or expired rate row → BLOCKER. Never silently omit the check.
- Raw-material basis older than **30 days** is a BLOCKER (`rm_basis_max_age_days`) —
  supplier quote, invoice, or estimate alike, dated by its evidence and measured at
  **send**: proved day 29, authorized day 31 must fail. Outsource age is a WARN.

## Proof (`quote_verify`)

- Checks are classed: `BLOCKER` or `WARN`. Any BLOCKER ⇒ `stop: true`; counting
  failures is not a severity model.
- Severity is per **stage**: `verify_quote(stage='draft'|'send')`. A draft exists so
  the owner can review pricing, so it never fails on a field he fills at the end.
- BLOCKERs include: zero/negative/absent unit price, total ≤ 0, qty × rate
  mismatch, missing rate source, missing or expired MHR floor basis, unattested or
  shipped-seed rate value, raw-material basis older than 30 days, scope↔material
  contradiction, missing outsource price on an outsourced operation, unlabelled
  estimate, a price driven by an unconfirmed drawing fact, missing drawing revision,
  attachment hash mismatch, and an empty delivery field **at `stage='send'`**.
- Delivery is the one stage-dependent check: **WARN at draft, BLOCKER at send.** Ask
  once while drafting and again on the Authorize card, which carries the field inline.
- Proof runs against the stored `quote_revision`, not chat memory. The verified PDF
  is bound by sha256; `quote_send` re-hashes and refuses on drift.

## HITL

- `quote_send` queues an Authorize card and never sets `sent: true`.
- The Authorize card shows total, currency, scope, rate sources, estimate flags, and
  whether identical content was already delivered.
- **Delivery is never computed** — no capacity model, no vendor-lead-time sum, no
  inference from past jobs. Owner-typed or empty; never a suggestion.
- Corrections go to the playbook `notes.md` via `quote_playbook_note`, then the
  broken step re-runs. Fix the folder, not the chat.
```

### 2.6 `domain/31-gcode-optimiser.mdc` — program generation and optimisation

```mdc
---
description: Guardrails for G-code drafting, optimisation, and cycle-time simulation — control dialects, safety envelope, no machine transmission, HITL promote. Use when touching CNC program code.
globs: backend/app/cnc_suggest.py, backend/app/machining/**, backend/app/hermes/playbooks/gcode/**, backend/tests/test_cnc_suggest.py
alwaysApply: false
---

# G-code — draft, verify, never transmit

A wrong block crashes a spindle into a fixture. This module is allowed to be
useless (refuse) and is never allowed to be confidently wrong.

## Hard boundaries

- Jarvis **never transmits** a program to a control, DNC share, or machine network.
  Output is a file under `<repo>/exports/nc/` plus a diff for the owner.
- Every generated program is `DRAFT` and carries `(NOT PROVEN ON THE MACHINE)` in
  its header until an owner Authorize promotes it. Promotion is versioned and
  append-only; a proven program is never overwritten in place.
- Missing trusted geometry → refuse with the list of what is missing. Never
  interpolate a dimension, a stock size, or a datum.
- No program is generated for a machine with no `machines` row: dialect, control
  model, axis travels, rapid rates, spindle limits, and tooling come from master
  data, not from the model.

## Dialect discipline (FANUC / Mitsubishi)

- Emit only for the control recorded on the machine (`machines.control_make`,
  `control_model`, e.g. FANUC 0i-TF / 31i, Mitsubishi M80 / M800). Dialects differ
  in canned-cycle argument form, subprogram call and nesting, macro variable
  ranges, and retract behaviour — when the recorded control is absent or the
  construct is not verified for it, emit long-hand motion or refuse.
- Unit code is always explicit (`G20`/`G21`), never inherited. Plane, absolute
  mode, feed mode (`G94`/`G95`), and work offset are declared in the header.
- M-codes come from a per-control **whitelist**. A blocklist of a few G-codes
  (today's `_BANNED_WORDS`) is not a safety model and must not be treated as one.

## Deterministic verification before any promote (`program_verify`)

Fails closed on: unresolved modal state; motion outside `machines` travel limits;
rapid below the clearance plane or into stock; feed or speed outside the
tool/material envelope from master data; tool called without an offset;
unbalanced cycle start/cancel; missing safe retract before tool change or program
end; spindle direction or coolant contradictions; subprogram or macro call that
is not present; unit/scale mismatch versus the drawing; arc without a valid
centre/radius. Every failure names the block number.

## Optimisation is bounded

- Optimise only: air-move reduction, approach/retract distances, pass depth and
  step-over within the tool envelope, tool-change ordering, sequencing across
  setups, canned cycle selection where verified for the control.
- Never optimise by raising feed or speed above the tooling table, removing a
  clearance move, skipping a spring/finish pass, loosening a tolerance-driven
  step-over, or merging operations that the routing separates.
- Report savings as an estimate with its simulation basis, and store both estimate
  and later measured cycle time so the model of this machine improves.

## Cycle-time simulation

- Integrate motion with per-axis rapid rates, accel/decel and corner deceleration
  from `machines`, expanded canned cycles, dwells, tool changes, and load/unload
  from the routing. Naive length ÷ feed is not an estimate and must not be quoted.
- Calibrate against measured times per machine and material; report the
  correction factor and its sample count. Uncalibrated estimates are labelled and
  flow into the quote as `is_estimate`.
```

### 2.7 `domain/34-drawing-vision.mdc` — consent, quota, and the cache-first rule

```mdc
---
description: Gates on sending a customer drawing to a cloud vision model — per-customer consent, the 5-per-cycle quota, owner override, and the local-extract-first rule. Use when touching drawing analysis.
globs: backend/app/quote.py, backend/app/vision/**, backend/app/knowledge/**, backend/tests/test_vision_gate.py
alwaysApply: false
---

# Drawing vision — two gates, never one

A customer drawing is confidential contractual material, and its title block names
the customer and part. Cloud analysis also costs money per call. Both are bounded.

## Gate 1 — consent (cannot be overridden)

- Default is **deny**. A drawing goes to a cloud model only when its customer's
  `customer_terms.allow_cloud_vision = 1` and `nda = 0`, attested by the owner.
- Unknown or unresolved customer ⇒ deny and ask. Never infer consent from a past job,
  a sibling part, or a similar customer name.
- No quota override, urgency, or owner instruction grants consent inside a turn; the
  consent row is the only source. Changing it is a deliberate master-data edit.

## Gate 2 — quota (owner-overridable, once, per drawing)

- Cap: **5 drawings per cycle**, where a cycle runs 10:00 → 10:00 local time.
- One **document** (one sha256) is one unit, however many pages or calls it needs.
  Above `vision_page_threshold` (default 4) the tool asks first, after extracting a
  local sheet index, so a 40-sheet pack never silently spends the unit.
- **Only the owner spends a unit.** Automated mail ingest must never dispatch to a
  cloud model: it runs the free local extract, sets `analysis_state='needs_vision'`,
  and surfaces the drawing on the bench. The unit is charged when the owner opens
  that RFQ and asks for the analysis. A background job, a watch, a retry loop, or a
  Hermes tool call cannot charge a unit on its own.
- The counter is global across everything the owner initiates — bench-triggered
  analysis and manual UI upload draw on one pool.
- **Claim before dispatch.** Insert the usage row inside the same transaction that
  checks the count, keyed unique on `(cycle_start, file_sha256)`. Two concurrent
  ingests must not both see the fourth unit free.
- A re-analysis of a document already charged this cycle is free. A failed attempt
  does not charge, but three consecutive failures on one document stop and ask.
- Over cap ⇒ a HITL card naming the drawing, the customer, and the used/total count.
  Authorize grants **one** extra unit for that document and is logged. It never
  raises the cap and never bypasses Gate 1.

## Cache and local extract come first

- Identity cascade before anything else: an exact-hash or confirmed-fingerprint hit is
  answered from the knowledge card with **zero** calls. Vision runs only when the card
  is missing, the revision changed, the bytes changed, extraction failed, or the owner
  asks for a fresh look.
- Try the free local path first — PDF text, title block, dimension tokens — and send to
  the cloud only what that path could not resolve.
- Every dispatch writes `disclosure_log` (file hash, customer, provider, purpose, bytes,
  turn, cycle, authorized_by). A failure never ingests its error text as drawing content.
```

### 2.8 Remaining rules — charter and scope

Each is ≤400 words, glob-scoped, and states only what a wrong guess would break:

| File | Globs | Charter (one line) |
| ---- | ----- | ------------------ |
| `backend/10-api-python.mdc` | `backend/app/**/*.py` | Module ownership map, lazy-import convention, `settings` is the only config source, no new JSON state files, every external call has a timeout |
| `backend/11-hitl-safety.mdc` | `backend/app/{agent,main}.py`, `hermes/**`, `tools/**` | Claim-once execution, `external_effects` bracket, MCP tools queue and never send, safety deny-list, never claim an act was done |
| `backend/12-data-schema.mdc` | `db.py`, `schemas.py`, `migrations/**`, `masterdata/**` | Migrations only (no ad-hoc `ALTER` in `init_db`), money as integer minor units + currency, units on dimensions, UTC storage, `source_kind`/`source_ref` on every priced row |
| `backend/13-turn-ledger.mdc` | `turns/**`, `agent.py`, `main.py` | Turn states and their only legal transitions, leases and heartbeats, idempotency keys, client timeout ≠ cancellation |
| `frontend/20-hud-shell.mdc` | `components/orchestrator/**`, `lib/orchestratorFsm.ts` | FSM stays a pure reducer, server ledger is the source of turn truth, workspace layer is orthogonal, max 3 expanded notes, Authorize/Reject copy |
| `frontend/21-react-bits.mdc` | `frontend/**/*.{tsx,ts,css}` | Existing placement map and scroll/shrink rules; trim to the table plus the headless WebGL flag |
| `domain/32-master-data.mdc` | `masterdata/**`, `migrations/**` | Temporal rate lookups are always as-of, aliases never overwrite canonical rows, demo-sourced rows are unusable for send, no deletes (supersede) |
| `domain/33-knowledge-rag.mdc` | `memory/**`, `knowledge/**` | Cards answer "what do we know", SQL answers "what is the number", corpus answers "where is it written"; never ingest Jarvis' own prose or a failed vision stub; embedding model and dim recorded per row |
| `ops/40-tests.mdc` | `backend/tests/**`, `frontend/**/*.test.*` | `live_service` marker discipline, offline-first tests, one regression test per fixed defect, no network in unit tests |
| `ops/41-living-notes.mdc` | *(T2)* | Today's living-notes rule, unchanged |
| `ops/42-dispatch.mdc` | *(T2)* | Merged dispatch + capability-run procedure, `composer-2.5-fast` requirement, placement policy |

### 2.9 Rule hygiene (enforce in review)

1. **One fact, one home.** A port number, a path, or a HITL gate appears in exactly one rule. Everything else links.
2. **Rules state constraints; skills teach procedures.** If it has steps, it belongs in `.cursor/skills/`.
3. **No prose paragraphs.** Bullets and tables — a worker skims.
4. **Every rule is falsifiable.** "Be careful with prices" is not a rule; "no line without `rate_source_id`" is.
5. **Budget check in CI.** A tiny test asserts T0 <200 words, every T1 has `globs`, every T1/T2 ≤400 words, and no file outside T0 sets `alwaysApply: true`.
6. **Rules are not documentation.** When as-built changes, `docs/CURRENT.md` changes; a rule changes only when a *constraint* changes.
---

## 3. Advanced Precision Machining Features

### 3.0 The feature contract

Every feature below obeys the same five rules, because a machining shop is not a chat product:

1. **Numbers come from data, never from the brain.** A feature that cannot cite its input refuses and asks.
2. **Advisory by default.** No feature writes to a control, stops a machine, or sends anything. The highest authority a feature has is a HITL card.
3. **Insufficient history is a valid answer.** Below a declared sample threshold, output is "not enough history for this tool/material pair", not a confident number.
4. **Everything is versioned and dated.** Estimates are stored with their basis and later compared to actuals — that comparison is the product, not the estimate.
5. **Each feature ends in a number the quote can use.** Tool life → cost per part. Nesting → material cost per part. Feature recognition → routing. Cycle time → machining cost. Otherwise it is a dashboard, and a dashboard does not pay for itself.

### 3.1 `toolwatch` — tool wear, manual-log first

**Problem it solves:** insert failure mid-cut on a finished-to-size precision part is the expensive defect — scrapped material, lost cycle, sometimes a damaged fixture or a missed delivery. Inspection after the fact does not recover any of it.

> **Locked scope (§8.4):** **v0 only.** No control-network integration, no sensors, and no `machine_telemetry` table in this overhaul. T2/T3 intake and the v1/v2 models below are recorded for the future phase and are **out of scope for every chunk**.

**Intake, in the order it is actually achievable:**

| Tier | Source | Effort | Fidelity |
| ---- | ------ | ------ | -------- |
| T1 (start here) | Shop-log events the supervisor already records: piece counts per insert, insert-change reason, audible chatter, dimensional drift, scrap cause | none — extend `shop_log` | Enough for cumulative-life + drift models |
| T2 *(deferred)* | Control telemetry, read-only: FANUC FOCAS2 over Ethernet (spindle/servo load, feed override, alarms, part count), Mitsubishi EZSocket/MTConnect adapter | one adapter per control family | Load-trend prediction |
| T3 *(deferred)* | Retrofit sensors: triaxial accelerometer on the spindle housing / turret, thermocouple, current clamp — cheap, machine-agnostic, no control integration | per-machine hardware | Vibration band energy, thermal drift |

**Data model (in scope):** `tool_instances` (tool + insert grade + fitted_at + machine + position), `tool_life_events` (change, reason, pieces_made, measured wear), `toolwatch_predictions` (tool_instance, predicted_remaining_pieces, confidence, basis, model_version). `machine_telemetry` is **deferred** with T2/T3.

**The capture surface is the feature.** v0 learns only from what gets recorded, and a shop will not fill a form. So the deliverable is a one-breath entry — *"changed the insert on the turning cell, two forty pieces, edge chipped"* — parsed into a `tool_life_events` row from either speech or a single HUD field, with the machine inferred from the open job and confirmed in the reply. Without that, v0 is an empty table with a model attached.

**Model progression — earn the complexity:**

- **v0 (deterministic, ships first):** cumulative cutting time and piece count versus the historical median life for that (tool geometry, insert grade, material, operation) tuple. Alert at 80 % and 95 %. Needs nothing but the shop log, and already prevents the common "ran one batch too far".
- **v1 (trend, deferred):** on T2/T3 data, compare spindle load at *matched* conditions (same program, same feed/speed/DOC) across the batch; a rising slope in mean load and in peak-to-mean ratio is the classic wear signature. Alert on slope crossing a per-tuple threshold learned from past changes.
- **v2 (learned, deferred):** gradient-boosted classifier over windowed features — load slope, peak/mean, vibration RMS in tool-passing-frequency bands, temperature rise per minute, power spectrum kurtosis — labelled by `tool_life_events`. Train per material family, not globally; a shop does not have enough data for one global model but has plenty for "En1A on the turning cell".

**Guardrails:** nothing in this feature touches a control — v0 does not connect to one at all, and the deferred tiers stay read-only if they ever land. No auto-stop; output is a HUD card and, over a severity threshold, a HITL "hold the batch / change the insert" action. Predictions below the sample threshold say so. Every alert records the features that fired it so a false alarm is diagnosable.

**Quote link:** measured tool life → `tooling_cost_per_part` = insert cost ÷ pieces per edge × edges used. This is a cost line the shop is currently absorbing invisibly.

```
jarvis_toolwatch_status(machine_id="", tool_instance_id="")     -> life used, remaining, confidence, basis
jarvis_toolwatch_record_change(tool_instance_id, reason, pieces_made, measured_wear_mm="")
jarvis_toolwatch_alerts(since="")                               -> advisory alerts + HITL candidates
```

### 3.2 `stockcut` — raw-material yield and blank optimisation

**Problem it solves:** yield loss is silent. A 3 metre bar cut without planning leaves an unusable stub; a quote priced on finished mass under-recovers material cost on every piece.

**1D (bar, tube, extrusion) — the common case:**
Inputs: stock length options and their per-unit price from `supplier_rm_quotes`, saw kerf, facing allowance per cut face, minimum clamping/collet grip, part cut length (finished length + facing + parting allowance), quantity, and available remnants. Solver: first-fit-decreasing for an instant answer, then a small integer program (CBC/`pulp` or a bounded branch-and-bound) for the real nest; prefer consuming remnants before new bar.
Outputs: bars required by length, yield %, **remnant lengths written back to `remnant_stock`** so they become consumable stock rather than floor clutter, and material cost per piece for the quote.

**2D (plate, flat bar):** guillotine/skyline heuristic with grain direction and edge trim; report utilisation and offcut inventory. Good enough to quote; not a nesting-software replacement.

**3D:** out of scope — blank selection from a solid is master data (`part_revisions.blank_spec`), not a solver.

**Guardrails:** the optimiser decides *quantity*, never *price* — the rate is always a supplier quote or a labelled estimate. Weight uses `materials.density` (an owner-confirmed master row), never an assumed density for an unknown grade. Remnant reuse is proposed, and the owner confirms the remnant physically exists before a quote depends on it.

**ROI:** on a 40-off En1A job, the difference between naive cut planning and a nest is routinely one full bar. That is real money per order, every order.

```
jarvis_stockcut_plan(material_id, part_length_mm, qty, kerf_mm="", facing_mm="", grip_mm="", use_remnants=true)
   -> {bars:[{length,count,source:new|remnant}], yield_pct, remnants:[…], mass_per_piece_kg, cost_basis}
```

### 3.3 `featurescan` — feature recognition → operation routing

**Problem it solves:** the routing is where quoting accuracy is decided, and today it is re-invented from scratch per RFQ, from memory, under time pressure. Forgotten operations (the owner's own list includes a forgotten outsource) are underquotes.

**Two paths, honestly separated:**

| Path | Input | Method | Trust |
| ---- | ----- | ------ | ----- |
| **Geometry-true** | STEP / IGES / native CAD | OpenCascade (`pythonocc`) or `build123d`: face classification (planar, cylindrical, conical, toroidal), hole detection by axis clustering + diameter runs, pocket/slot from concave loop nesting, boss/step detection, thread from cylindrical face + pitch annotation, wall-thickness and corner-radius extraction | High — geometry is deterministic |
| **Drawing-derived** | PDF / photo (today's reality) | Vision extract + title-block and dimension/GD&T text parsing → *candidate* features | **Proposed only.** Never auto-promoted to a routing |

**Feature → operation templates** (a table in master data, `feature_process_rules`, not model judgement):

| Recognised feature | Proposed operations |
| ------------------ | ------------------- |
| Prismatic pocket | Rough mill (step-over/DOC from tool envelope) → semi-finish → finish; corner radius check against smallest available tool |
| Hole ⌀ < 12 mm, free tolerance | Centre drill → drill |
| Hole with H7/H8 | Drill → bore or ream; add gauge inspection |
| Bore ⌀ > 25 mm with H6 or Ra < 0.4 | Bore → hone, or grinding (usually outsource) |
| Thread | Tap (size-dependent) or single-point / thread mill; add gauge |
| Face with flatness < 0.01 mm | Grinding — outsource trigger "process not in-house" |
| Hardness or case-depth note | Heat treat outsource + post-HT finishing operations + distortion allowance |
| Plating/coating note | Plating outsource; add masking and pre-plate size compensation |
| Turned part with L/D > 8 | Steady/tailstock support, reduced DOC, possible between-centres operation |

Output is a **routing draft**: ordered operations, machine candidates filtered by `machine_capabilities` (envelope, tolerance floor, control), setup count with datum reasoning, per-op cycle-time estimate from §3.4, and an explicit list of features it could not classify. The owner accepts it into `routings` (a HITL-ish confirm; no external effect, so no Authorize gate) and the accepted version becomes reusable master data for repeat orders — the second time this part is quoted, this step is a lookup.

**Guardrails:** tolerance- and finish-driven process selection is table-driven; unreadable tolerances become questions, never assumptions. A 2D-derived feature set is labelled `source_kind='drawing_derived'` and a quote built on it carries that label. Nothing here decides an outsource *price*.

### 3.4 `cycletime` — two engines, one calibration loop

**Problem it solves:** machining cost = time × rate. The rate is governed (§4). The time is currently a guess, which makes the rate floor meaningless.

**Engine A — parametric, per operation:** from feature geometry, tool, and material:
`t_cut = L_total / (f_z · z · n)` for milling, `t = L / (f · n)` for turning, plus air moves, approach/retract, tool changes, dwells, and per-setup load/unload from master data. Cheap, works at RFQ time before any program exists. Uses `tool_material_params` (a master table of feed/speed envelopes), never model-invented feeds.

**Engine B — G-code backplot:** parse blocks, carry modal state, expand canned cycles, integrate motion **with machine dynamics** — per-axis rapid rates, accel/decel, corner deceleration and look-ahead behaviour, feed mode (`G94`/`G95`), overrides, dwell. This is where naive length ÷ feed is wrong by 30–40 % on parts with many short moves: the machine never reaches programmed feed.

**Calibration is the actual feature:** store estimate and measured time per (machine, material, operation class); maintain a correction factor with its sample count; report it. A quote that uses an uncalibrated estimate says so, and the **quote-to-actual variance ledger** (§3.5) closes the loop that currently allows the same underquote to repeat.

**Guardrails:** every estimate carries method (`parametric|backplot`), confidence band, and calibration sample count. Backplot never validates safety — that is `program_verify` (§2.6). Simulation is an async job, never an inline turn (§1.8).

```
jarvis_cycletime_estimate(routing_id="", program_path="", machine_id="")
   -> per-op times, setup, total, method, confidence, calibration_n
jarvis_cycletime_record_actual(routing_operation_id, measured_min, pieces, operator_note="")
```

### 3.5 Secondary features with real ROI

| Feature | What it does | Why it pays |
| ------- | ------------ | ----------- |
| **Quote-to-actual variance ledger** | Joins `quote_lines` to production actuals: quoted vs real cycle time, material, outsource, scrap. Ranks parts by margin erosion | The single highest-value feature in this document: it is the only mechanism that *learns* from an underquote instead of repeating it |
| **RM price aging + index** | Tracks supplier quote validity; refuses a send whose material basis is older than a configured window; trend line per material for labelled estimates | Steel moves. A 60-day-old rate is a silent loss |
| ~~Capacity-aware promise dates~~ | **Removed by lock (§8.7).** Jarvis does not compute or suggest a delivery date under any circumstances. What replaces it: a WIP/load *view* the owner reads before typing his own date, and "capacity full" stays an owner-stated outsource reason rather than a computed one | — |
| **Outsource turnaround tracker** | Actual vendor lead times per process/vendor vs quoted | Heat-treat slip is a delivery slip; this is where it is detectable early |
| **Inspection / first-article gate** | Ingests CMM or gauge reports, binds them to `part_revisions`, blocks despatch claims without a first-article pass | Precision customers audit this; it is also the cheapest scrap filter |
| **Setup-sheet generator** | Fixture, datum, tool list, offsets, and inspection points per routing operation, from accepted routings | Kills the "which tool in which pocket" tribal knowledge tax |
| **Repeat-order fast path** | Same part + revision + customer → previous routing, cycle times, and rates as-of today, with a diff of what changed | Turns a two-hour requote into a five-minute confirm — the clearest daily time win |

### 3.6 Build order

| Order | Feature | Depends on | Payback |
| ----- | ------- | ---------- | ------- |
| 1 | Quote-to-actual variance ledger | §4 schema | Immediate, and it aims everything else |
| 2 | `cycletime` Engine A + calibration | §4 schema, routings | Makes MHR floors meaningful |
| 3 | `stockcut` 1D + remnant stock | `materials`, `supplier_rm_quotes` | Per-order material recovery |
| 4 | `featurescan` geometry-true (STEP) + `feature_process_rules` | Routing tables | Removes forgotten operations |
| 5 | `toolwatch` v0 (shop-log only) | `shop_log` extension | Prevents the expensive batch |
| 6 | Repeat-order fast path | 1–4 accumulate the data | Compounding time win |
| 7 | `cycletime` Engine B (backplot) | `machines` dynamics data | Accuracy on short-move parts |
| — | ~~`toolwatch` v1/v2~~, ~~capacity-aware dates~~ | Deferred / removed by §8.4 and §8.7 | Out of scope for this overhaul |
---

## 4. Master Data & Schema Design

### 4.1 Five laws

1. **Provenance is structural, not cultural.** `quote_lines.rate_source_id` is `NOT NULL` with a foreign key. A price line with no traceable source *cannot be inserted*. This is the schema-level version of "the brain never invents numbers" — today that rule lives in prompts and a markdown file; after this it lives in the database.
   **Attestation, not storage, decides sendability (§8.2).** The owner is keeping the `demo` rate table and filling it with real shop numbers, so "demo" can no longer mean "unusable". Every rate row carries `attested_by` / `attested_at` and the fingerprint of the value it shipped with: unattested, or still equal to the shipped seed, blocks a send; attested prices real work, whatever its `source_kind`.
2. **Rates are temporal.** Every rate carries `effective_from` / `effective_to`, and every lookup is **as-of** a date. A quote sent in March must still re-prove itself in December with March's floor.
3. **Sent things are immutable.** A quote revision, once sent, is frozen; a change is a new revision. The PDF is hashed and archived.
4. **Money is integer minor units plus a currency code.** No floats, ever. Today `unit_price` is a float or an empty string in a spreadsheet row.
5. **Units travel with quantities.** `value` + `unit` on every dimension and every quantity (`pc`, `kg`, `hr`, `mm`, `in`). Mixed units are how precision shops scrap parts.

### 4.2 Entity map

```
customers ──< customer_contacts                      materials ──< material_equivalents
    │   └──< customer_terms (default scope, currency, NDA, cloud-vision consent)
    │                                                suppliers ──< supplier_rm_quotes >── materials
    ├──< components ──< part_revisions ──< drawing_facts        (confirmed facts, §4B)
    │                        │      └──< part_features          (featurescan output)
    │                        └──< routings ──< routing_operations >── machines / outsource_vendors
    │                                                   │
    └──< quotes ──< quote_revisions ──< quote_lines ────┘ (rate_source_id → any rate row)
                          ├──< quote_proofs   (checklist + PDF sha256 + verdict)
                          └──< quote_events   (sent / viewed / won / lost + reason)

machines ──< machine_hour_rates          machines ──< machine_capabilities
    └──< production_logs >── downtime_reasons   tools ──< tool_instances ──< tool_life_events
                                                  remnant_stock >── materials
customer_terms ──< vision_quota_usage >── disclosure_log      (machine_telemetry: deferred, §8.4)

outsource_vendors ──< outsource_processes ──< outsource_quotes
pending_actions ──< external_effects     turns (§1.2)     rag_documents ──< rag_chunks (§4B)
```

### 4.3 Core DDL (SQLite dialect, Postgres-portable)

Trimmed to the load-bearing columns; `created_at`/`updated_at`/`created_by` are on every table.

```sql
-- ─── Parties ────────────────────────────────────────────────────────────────
CREATE TABLE customers (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, gstin TEXT,
  currency TEXT NOT NULL DEFAULT 'INR', status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE customer_aliases (            -- replaces files/client-names.md
  customer_id TEXT NOT NULL REFERENCES customers(id), alias TEXT NOT NULL,
  source TEXT NOT NULL, PRIMARY KEY (alias)
);
CREATE TABLE customer_terms (
  customer_id TEXT PRIMARY KEY REFERENCES customers(id),
  default_scope TEXT NOT NULL CHECK (default_scope IN ('labour','with_material','ask')),
  payment_terms_days INTEGER, delivery_basis TEXT,
  nda INTEGER NOT NULL DEFAULT 0,             -- drawings never leave the machine
  allow_cloud_vision INTEGER NOT NULL DEFAULT 0,   -- default deny (§8.1); owner-attested
  vision_consent_by TEXT, vision_consent_at TEXT,
  quote_validity_days INTEGER NOT NULL DEFAULT 30  -- validity of OUR outgoing quote
);                                                 -- inbound RM basis age is global: 30 days

-- ─── Materials & raw-material pricing ───────────────────────────────────────
CREATE TABLE materials (
  id TEXT PRIMARY KEY, grade TEXT NOT NULL UNIQUE,          -- 'En1A', '18CrNiMo7-6', 'SS304'
  family TEXT NOT NULL,                                     -- free-cutting steel, case-hardening, stainless…
  standard TEXT, density_kg_m3 REAL, machinability_index REAL,
  hardness_spec TEXT, form TEXT NOT NULL,                   -- bar|tube|plate|forging|casting
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE material_equivalents (         -- En1A ~ AISI 12L14: owner-confirmed only
  material_id TEXT NOT NULL REFERENCES materials(id), equivalent_grade TEXT NOT NULL,
  standard TEXT, confirmed_by TEXT NOT NULL, PRIMARY KEY (material_id, equivalent_grade)
);
CREATE TABLE suppliers (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, contact TEXT, lead_days INTEGER
);
CREATE TABLE supplier_rm_quotes (
  id TEXT PRIMARY KEY,
  supplier_id TEXT NOT NULL REFERENCES suppliers(id),
  material_id TEXT NOT NULL REFERENCES materials(id),
  size_spec TEXT NOT NULL,                    -- 'Ø25 bright bar', 'Ø50x3000 tube'
  unit_basis TEXT NOT NULL CHECK (unit_basis IN ('per_kg','per_bar','per_piece','per_metre')),
  price_minor INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'INR',
  min_qty REAL, qty_break TEXT,
  effective_from TEXT NOT NULL, effective_to TEXT,
  basis_date TEXT NOT NULL,                   -- when the price was actually quoted/invoiced;
                                              -- age > 30 days blocks a send (§8.5)
  source_kind TEXT NOT NULL CHECK (source_kind IN ('supplier_quote','invoice','owner_input','estimate','demo')),
  source_ref TEXT NOT NULL DEFAULT '',        -- mail id / artifact id / doc hash
  is_estimate INTEGER NOT NULL DEFAULT 0, estimate_basis TEXT NOT NULL DEFAULT '',
  attested_by TEXT NOT NULL DEFAULT '', attested_at TEXT,
  shipped_seed_value_minor INTEGER            -- set on seeded rows; equal value ⇒ still fictional
);
CREATE INDEX rm_quotes_lookup ON supplier_rm_quotes(material_id, effective_from, effective_to);

-- ─── Machines, rates, capability ────────────────────────────────────────────
CREATE TABLE machines (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, machine_type TEXT NOT NULL,   -- 'CNC turning centre', 'VMC'
  control_make TEXT NOT NULL, control_model TEXT NOT NULL,               -- FANUC / 0i-TF ; Mitsubishi / M80
  axes INTEGER, travel_x REAL, travel_y REAL, travel_z REAL,
  max_rpm INTEGER, spindle_kw REAL, bar_capacity_mm REAL, chuck_mm REAL,
  rapid_x REAL, rapid_y REAL, rapid_z REAL, accel_g REAL,                -- cycletime Engine B
  accuracy_class TEXT, status TEXT NOT NULL DEFAULT 'running'
);
CREATE TABLE machine_hour_rates (
  id TEXT PRIMARY KEY,
  machine_id TEXT REFERENCES machines(id), machine_type TEXT,  -- one of the two is set
  min_mhr_minor INTEGER NOT NULL, target_mhr_minor INTEGER,
  currency TEXT NOT NULL DEFAULT 'INR',
  effective_from TEXT NOT NULL, effective_to TEXT,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('owner_input','costing_sheet','demo')),
  source_ref TEXT NOT NULL DEFAULT '',
  attested_by TEXT NOT NULL DEFAULT '', attested_at TEXT,   -- unattested ⇒ BLOCKER (§8.2)
  shipped_seed_value_minor INTEGER,                         -- still the shipped demo number ⇒ BLOCKER
  CHECK (machine_id IS NOT NULL OR machine_type IS NOT NULL)
);
CREATE TABLE machine_capabilities (          -- drives in-house vs outsource
  machine_id TEXT NOT NULL REFERENCES machines(id), process TEXT NOT NULL,
  tolerance_floor_mm REAL, finish_floor_ra REAL,
  max_part_x REAL, max_part_y REAL, max_part_z REAL, max_part_kg REAL,
  PRIMARY KEY (machine_id, process)
);

-- ─── Components, routings ───────────────────────────────────────────────────
CREATE TABLE components (
  id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
  customer_part_no TEXT, our_part_no TEXT, name TEXT NOT NULL,
  UNIQUE (customer_id, customer_part_no)
);
CREATE TABLE part_revisions (
  id TEXT PRIMARY KEY, component_id TEXT NOT NULL REFERENCES components(id),
  revision TEXT NOT NULL, drawing_no TEXT,
  drawing_artifact_id TEXT, drawing_sha256 TEXT,        -- identity for §4B recall
  material_id TEXT REFERENCES materials(id),
  blank_spec TEXT, finished_mass_kg REAL, units TEXT NOT NULL DEFAULT 'mm',
  analysis_state TEXT NOT NULL DEFAULT 'none',          -- none|needs_vision|vision_done|
                                                        -- owner_confirmed|failed
  superseded_by TEXT REFERENCES part_revisions(id),
  UNIQUE (component_id, revision)
);
CREATE TABLE routings (
  id TEXT PRIMARY KEY, part_revision_id TEXT NOT NULL REFERENCES part_revisions(id),
  version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft',  -- draft|accepted|superseded
  source_kind TEXT NOT NULL,        -- featurescan_geometry|featurescan_drawing|owner|copied_from:<id>
  accepted_by TEXT, accepted_at TEXT, UNIQUE (part_revision_id, version)
);
CREATE TABLE routing_operations (
  id TEXT PRIMARY KEY, routing_id TEXT NOT NULL REFERENCES routings(id),
  seq INTEGER NOT NULL, operation TEXT NOT NULL,                 -- turning|milling|drilling|tapping|grinding|HT|plating
  machine_id TEXT REFERENCES machines(id),
  outsource_vendor_id TEXT REFERENCES outsource_vendors(id),
  outsource_case TEXT,          -- no_machine|customer_asked|capacity|not_in_house
  setup_min REAL, cycle_min_est REAL, cycle_min_actual REAL,
  est_method TEXT, est_confidence REAL, est_calibration_n INTEGER,
  tooling TEXT, fixture TEXT, program_ref TEXT, inspection TEXT,
  CHECK (machine_id IS NOT NULL OR outsource_vendor_id IS NOT NULL),
  UNIQUE (routing_id, seq)
);

-- ─── Outsource ──────────────────────────────────────────────────────────────
CREATE TABLE outsource_vendors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, processes TEXT NOT NULL, lead_days INTEGER
);
CREATE TABLE outsource_quotes (
  id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES outsource_vendors(id),
  process TEXT NOT NULL, spec TEXT NOT NULL,        -- 'case depth 0.6-0.9, HRc 58-62'
  unit_basis TEXT NOT NULL CHECK (unit_basis IN ('per_kg','per_piece','per_batch')),
  price_minor INTEGER NOT NULL, min_lot_minor INTEGER, currency TEXT NOT NULL DEFAULT 'INR',
  lead_days INTEGER, effective_from TEXT NOT NULL, effective_to TEXT,
  source_kind TEXT NOT NULL, source_ref TEXT NOT NULL DEFAULT ''
);

-- ─── Quotes ─────────────────────────────────────────────────────────────────
CREATE TABLE quotes (
  id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
  rfq_ref TEXT, mail_id TEXT, conversation_id TEXT,
  status TEXT NOT NULL DEFAULT 'open'          -- open|sent|won|lost|withdrawn
);
CREATE TABLE quote_revisions (
  id TEXT PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES quotes(id),
  revision INTEGER NOT NULL, part_revision_id TEXT REFERENCES part_revisions(id),
  routing_id TEXT REFERENCES routings(id),
  scope TEXT NOT NULL CHECK (scope IN ('labour','with_material')),
  scope_source TEXT NOT NULL,                  -- customer_default|mail:<id>|verbal:<turn_id>
  qty INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'INR',
  total_minor INTEGER NOT NULL DEFAULT 0, margin_pct REAL,
  delivery_days INTEGER,                       -- owner-typed only; NULL blocks authorize (§8.7)
  delivery_entered_by TEXT, delivery_entered_at TEXT,
  notes TEXT,
  frozen INTEGER NOT NULL DEFAULT 0,           -- set at send; immutable thereafter
  pdf_artifact_id TEXT, pdf_sha256 TEXT,
  UNIQUE (quote_id, revision)
);
CREATE TABLE quote_lines (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  seq INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('material','machining','outsource','tooling','inspection','freight','other')),
  description TEXT NOT NULL,
  qty REAL NOT NULL, qty_unit TEXT NOT NULL,            -- pc|kg|hr|batch
  rate_minor INTEGER NOT NULL, amount_minor INTEGER NOT NULL,
  machine_id TEXT REFERENCES machines(id), time_min REAL,
  rate_source_kind TEXT NOT NULL,                       -- supplier_rm_quote|machine_hour_rate|outsource_quote|owner_input
  rate_source_id TEXT NOT NULL,                         -- ← the provenance law (§4.1.1)
  is_estimate INTEGER NOT NULL DEFAULT 0, estimate_basis TEXT NOT NULL DEFAULT '',
  CHECK (rate_minor >= 0 AND qty > 0),
  UNIQUE (quote_revision_id, seq)
);
CREATE TABLE quote_proofs (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  verdict TEXT NOT NULL,                     -- pass|warn|block
  blockers INTEGER NOT NULL DEFAULT 0, warnings INTEGER NOT NULL DEFAULT 0,
  checklist_json TEXT NOT NULL, pdf_sha256 TEXT, created_at TEXT NOT NULL
);
CREATE TABLE quote_events (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  event TEXT NOT NULL,                       -- queued|authorized|sent|customer_replied|won|lost
  detail TEXT, external_effect_id TEXT REFERENCES external_effects(id), created_at TEXT NOT NULL
);

-- ─── Cloud-vision consent, quota, and disclosure (§8.1) ─────────────────────
CREATE TABLE vision_quota_usage (
  id TEXT PRIMARY KEY,
  cycle_start TEXT NOT NULL,                  -- 10:00 local boundary, computed not stored ad hoc
  file_sha256 TEXT NOT NULL,
  customer_id TEXT REFERENCES customers(id),
  spent_by TEXT NOT NULL CHECK (spent_by IN ('owner_bench','owner_upload','owner_override')),
  arrival TEXT NOT NULL,                      -- mail_ingest|ui_upload|walk_in: how it arrived,
                                              -- never who spent the unit (§8.1: only the owner does)
  pages INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL CHECK (state IN ('claimed','dispatched','failed','override')),
  turn_id TEXT, override_action_id TEXT REFERENCES pending_actions(id),
  created_at TEXT NOT NULL
);
-- the claim: one document charges one unit per cycle, whatever its page or retry count
CREATE UNIQUE INDEX vision_quota_unit ON vision_quota_usage(cycle_start, file_sha256);

CREATE TABLE disclosure_log (                 -- what left this machine, and on whose authority
  id TEXT PRIMARY KEY, file_sha256 TEXT NOT NULL, customer_id TEXT,
  provider TEXT NOT NULL, purpose TEXT NOT NULL, bytes INTEGER NOT NULL,
  turn_id TEXT, cycle_start TEXT, authorized_by TEXT NOT NULL, created_at TEXT NOT NULL
);

-- ─── Shop floor ─────────────────────────────────────────────────────────────
CREATE TABLE production_logs (
  id TEXT PRIMARY KEY, shift TEXT NOT NULL, log_date TEXT NOT NULL,
  machine_id TEXT REFERENCES machines(id), part_revision_id TEXT REFERENCES part_revisions(id),
  qty_ok INTEGER NOT NULL DEFAULT 0, qty_rework INTEGER NOT NULL DEFAULT 0,
  qty_scrap INTEGER NOT NULL DEFAULT 0, scrap_cause TEXT,
  run_min REAL, downtime_min REAL, downtime_reason TEXT REFERENCES downtime_reasons(code),
  oee_pct REAL, source_ref TEXT NOT NULL DEFAULT '',     -- sheet row / mail id; never invented
  operator TEXT
);
CREATE TABLE downtime_reasons (code TEXT PRIMARY KEY, label TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE remnant_stock (
  id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(id),
  size_spec TEXT NOT NULL, length_mm REAL, mass_kg REAL,
  location TEXT, from_job TEXT, confirmed_by TEXT, status TEXT NOT NULL DEFAULT 'available'
);
```

### 4.4 Cross-cutting conventions

| Concern | Rule |
| ------- | ---- |
| Money | `*_minor INTEGER` + `currency`. Never float, never a bare number in a sheet cell |
| Quantity | `qty REAL` + `qty_unit` from a fixed vocabulary |
| Dimensions | Stored in mm with an explicit `units` on the part revision; inch drawings converted at ingest with the original preserved |
| Time | Store UTC ISO-8601 via `db.utc_now()`; render in `settings.tz`. `datetime.now()` (naive) is banned — it exists today in `quote.append_playbook_note` |
| Provenance | `source_kind` + `source_ref` + `approved_by` on every priced or quotable row |
| Temporal lookups | Always as-of: `WHERE effective_from <= :as_of AND (effective_to IS NULL OR effective_to > :as_of)` |
| Deletion | No hard deletes on master data — supersede (`superseded_by`, `effective_to`) |
| Rate attestation | `source_kind='demo'` is a valid production source (§8.2). Sendability needs `attested_by` set **and** a value differing from `shipped_seed_value_minor`. The HUD names the basis and its attestation date |
| RM freshness | `basis_date` age > **30 days** is a BLOCKER, checked again at send (§8.5). Outsource-quote age is a WARN pending an owner ruling |
| Delivery | `delivery_days` is owner-typed or NULL — never computed, never inferred. NULL blocks authorize (§8.7) |
| Cloud disclosure | No drawing leaves the machine without a consent row and a claimed quota unit; every dispatch writes `disclosure_log` (§8.1) |
| Identity | Every externally-sourced document gets a sha256; drawings additionally get a text fingerprint (§4B.2) |

### 4.5 Migration from the demo tables

| Today | Becomes | How |
| ----- | ------- | --- |
| `jobs` (demo seed: Ace Designers / 18CrNiMo7-6) | `components` + `part_revisions` + `routings` | Script, one-time; keep `jobs` read-only for one release behind a `masterdata_enabled` flag |
| `rfqs` | `quotes` + `quote_revisions` | Map `extract` JSON into `part_revisions` + `drawing_facts` candidates |
| `memories` keys `last_quote_*` | `quote_revisions` + `quote_lines` | **Must die.** See §6.7: quote state in a per-session 50-row window is the worst data-model flaw in the current system |
| `files/mhr-demo.md` | `machine_hour_rates` rows with `source_kind='demo'` | **Stays the owner's edit surface** while the Master Data UI is deferred (§8.2). The file gains `attested_by` / `attested_on` / `effective_from` columns; the importer is idempotent, fails closed on a malformed row, records `shipped_seed_value_minor` for seeded values, and writes nothing the owner has not attested |
| `files/client-names.md` | `customers` + `customer_aliases` | Proof check becomes a real lookup instead of a substring match |
| `emails`, `calendar_events`, `inbox_files` | unchanged | They are connector caches; only `rag_documents` links are added |
| `pending_actions` | + `status='claimed'`, `claim_id`, `external_effects` | §1.5 |

Rollout discipline: every new table lands behind a flag, with **dual-read** (master data first, fall back to the legacy path) for one release, a backfill script, and a reconcile report. No cut-over without the reconcile report being clean.
---

## 4B. Knowledge, Memory & Recall — the RAG architecture that makes Jarvis smart

> Owner's requirement (2026-09-21): *"When Jarvis is talking to me about an engineering drawing for the first time, it will save all of the confirmed information in the RAG database. When and if I talk about the same drawing again, it should reference the RAG database rather than processing the drawing again. Jarvis should also have a functioning memory of the shop floor and other relevant information which will help it answer questions about known things a lot faster."*

That requirement is not a vector-database feature. A vector index finds *similar text*; it cannot tell you that Rev C superseded Rev B, that the material was confirmed by you and the tolerance was only guessed by a vision model, or that the ⌀25 H7 bore is authoritative. Recall that is *smart* needs three separate planes with different truth rules.

### 4B.1 Three planes, never collapsed

All three planes are **100 % local** (§8.6): SQLite for the ledger and the durable mirror, LanceDB for vectors, nothing in a cloud memory service.

| Plane | Store | Answers | Truth rule |
| ----- | ----- | ------- | ---------- |
| **Ledger** | SQL master data (§4) | "What is the number?" — rates, quantities, dates, totals | Authoritative. Numbers in an answer are *always* read from here |
| **Knowledge** | `entity_cards` + `entity_facts` (per drawing, part, customer, machine, vendor, tool) | "What do we know about this thing?" — distilled, confirmed, provenanced facts | Only `owner_confirmed` facts are quotable; candidates are visibly candidates |
| **Corpus** | `rag_documents` + `rag_chunks` (hybrid BM25 + vector) | "Where is it written?" — mail bodies, drawing text, vision transcripts, production reports, standards, playbook notes | Citations only. Never the source of a number |

The routing rule an agent must follow, and which `domain/33-knowledge-rag.mdc` enforces:

```
number asked for      -> ledger lookup (SQL)             ; cite row id
"what do we know"     -> entity card                     ; cite fact ids + provenance
"where did we see it" -> corpus retrieval                ; cite doc + chunk
not present anywhere  -> ASK. Never interpolate.
```

Today all three roles are served by one table (`memory_docs`) searched by a linear cosine scan over hash-of-words vectors (§6.4), which is why recall is both slow and shallow.

### 4B.2 The drawing identity problem (this is what makes "don't process it again" work)

The same drawing arrives as a mail attachment, a WhatsApp photo, a re-scanned PDF, and a walk-in hard copy. Byte equality alone will miss three of those four; fuzzy matching alone will confuse Rev B with Rev C — the expensive mistake. Resolution is a **cascade with a human stop**:

| Step | Key | Result |
| ---- | --- | ------ |
| 1 | `sha256(file bytes)` → `part_revisions.drawing_sha256`, `rag_documents.sha256` | Exact hit: instant recall, zero processing |
| 2 | **Text fingerprint** — normalised title-block tokens + sorted dimension-token multiset, hashed (`simhash`/minhash over extracted PDF text or OCR) | Near-duplicate hit (re-scan, re-export, photo of the same sheet) → **propose** the match, show both, owner confirms |
| 3 | `(customer_id, drawing_no, revision)` from the title block | Logical hit → confirm it is the same sheet |
| 4 | `(customer_id, drawing_no)` with a *different* revision | **Revision-change branch**: load the old card, diff what changed, warn if a prior quote used the old revision |
| 5 | nothing matches | New `part_revision`; first-time path (vision allowed) |

Revision discipline is the guardrail: a card belongs to a `part_revision`, never to a "drawing name". Rev C arriving after a Rev B quote produces a spoken line the shop actually needs — *"Rev C landed. Three dimensions and the case-depth note changed since the quote we sent on the 14th."* Geometry facts are per revision; **commercial** facts (scope, price basis, qty) are per revision **and** customer, because the same part quoted to two customers is two commercial truths.

### 4B.3 Knowledge schema

```sql
CREATE TABLE entity_cards (
  id TEXT PRIMARY KEY,                       -- card:<type>:<entity_id>
  entity_type TEXT NOT NULL,                 -- part_revision|component|customer|machine|vendor|tool|material|job
  entity_id TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',          -- regenerated digest, embedded for semantic hits
  summary_embedding_id TEXT,
  fact_count INTEGER NOT NULL DEFAULT 0,
  confirmed_count INTEGER NOT NULL DEFAULT 0,
  open_questions TEXT NOT NULL DEFAULT '[]', -- what Jarvis still needs — spoken, not hidden
  updated_at TEXT NOT NULL,
  UNIQUE (entity_type, entity_id)
);

CREATE TABLE entity_facts (
  id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL REFERENCES entity_cards(id),
  field TEXT NOT NULL,                       -- material | od_mm | bore_h7_mm | tolerance_flatness_mm | qty | scope | heat_treat_spec …
  value TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '',
  numeric_value REAL,                        -- populated when parseable, for range queries
  source_kind TEXT NOT NULL CHECK (source_kind IN
    ('owner_confirmed','customer_mail','title_block','vision_suggestion','measured','computed','jarvis_inference')),
  source_ref TEXT NOT NULL DEFAULT '',       -- mail id | artifact id | turn id | chunk id
  confidence REAL NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'candidate'    -- candidate|confirmed|rejected|superseded
    CHECK (state IN ('candidate','confirmed','rejected','superseded')),
  confirmed_by TEXT, confirmed_at TEXT,
  confirmed_from TEXT,                       -- 'vision_suggestion' when the owner accepted a suggestion
  superseded_by TEXT REFERENCES entity_facts(id),
  expires_at TEXT,                           -- candidates expire; confirmed facts do not
  created_at TEXT NOT NULL
);
CREATE INDEX entity_facts_card ON entity_facts(card_id, state, field);

CREATE TABLE rag_documents (
  id TEXT PRIMARY KEY, uri TEXT NOT NULL, sha256 TEXT NOT NULL,
  doc_kind TEXT NOT NULL,                    -- mail|drawing|vision_transcript|production_report|quote|standard|playbook_note|spec_sheet
  namespace TEXT NOT NULL,                   -- drawings|quotes|production|people|standards|session|playbook|profile
  authored_by TEXT NOT NULL DEFAULT 'external',   -- external|owner|jarvis  (jarvis prose is never fact-retrievable)
  entity_type TEXT, entity_id TEXT,          -- link into the ledger
  effective_date TEXT, retention TEXT NOT NULL DEFAULT 'keep',   -- keep|ttl:<days>
  indexed_at TEXT, UNIQUE (sha256, namespace)
);

CREATE TABLE rag_chunks (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES rag_documents(id),
  ordinal INTEGER NOT NULL, section TEXT NOT NULL DEFAULT '',   -- title_block|notes|dimensions|body|per_machine_row…
  text TEXT NOT NULL, text_sha256 TEXT NOT NULL,
  token_count INTEGER NOT NULL DEFAULT 0,
  embedding_model TEXT NOT NULL, embedding_dim INTEGER NOT NULL, vector BLOB,
  indexed_at TEXT, UNIQUE (document_id, ordinal)
);
CREATE VIRTUAL TABLE rag_fts USING fts5(text, content='rag_chunks', content_rowid='rowid');

CREATE TABLE rag_index_state (               -- outbox + lag metric; ingest never blocks a turn
  id INTEGER PRIMARY KEY CHECK (id = 1),
  pending INTEGER NOT NULL DEFAULT 0, embedded INTEGER NOT NULL DEFAULT 0,
  model TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '', updated_at TEXT
);

CREATE TABLE shop_state (                    -- materialised projection, rebuildable from events
  key TEXT PRIMARY KEY,                      -- machine:VMC-02 | material:En1A | vendor:HT-Pune | shift:last
  payload TEXT NOT NULL,                     -- JSON snapshot
  as_of TEXT NOT NULL, derived_from TEXT NOT NULL   -- 'production_logs<=2026-09-21T06:00Z'
);
```

`embedding_model` and `embedding_dim` on every chunk is the column that makes a future embedding upgrade survivable — today a model change would silently mix vector spaces (§6.4).

### 4B.4 First conversation about a drawing → durable knowledge

```
 drop / mail attachment
        │
        ▼
 [1] identity cascade (§4B.2) ── exact or confirmed hit ──▶ jump to §4B.5 (recall path, no vision)
        │ new revision
        ▼
 [2] cheap deterministic extract: PDF text, title block, dimension tokens, notes list
        │        (free, local, always runs; also becomes corpus chunks)
        ▼
 [3] cloud vision ONLY when the owner asks, and only past both gates (§8.1).
        │        automated ingest never reaches here: it stops at [2], sets
        │        analysis_state='needs_vision', and waits on the bench.
        │        gate 0 trigger  - owner opened this RFQ and asked; no job, watch, retry
        │                          or tool call may spend a unit on its own
        │        gate 1 consent  - customer_terms.allow_cloud_vision=1 AND nda=0, owner-attested;
        │                          unknown customer = deny and ask; no override grants consent
        │        gate 2 quota    - <5 documents charged this 10:00->10:00 cycle; unit claimed
        │                          atomically by (cycle_start, file_sha256) before dispatch;
        │                          over cap = HITL card, Authorize grants ONE unit for that file
        │        every dispatch writes disclosure_log; a failure ingests nothing (§6.14)
        ▼
 [4] candidate facts  → entity_facts(state='candidate', source_kind='vision_suggestion'|'title_block')
        │
        ▼
 [5] the conversation itself: owner says "material is En1A, 25 off, labour only, no grinding"
        │   extractor proposes candidates with the exact transcript quote as source_ref
        ▼
 [6] CONFIRM CHIPS on the Engineering bench: field · value · where it came from · [✓] [edit] [✗]
        │   one tap = entity_facts(state='confirmed', confirmed_by=owner, confirmed_at=now)
        ▼
 [7] card summary regenerated + embedded; corpus chunks written; vision transcript stored
        │   (transcript is a citation, not a fact)
        ▼
 [8] quotable set = confirmed facts only.  Unconfirmed → the card's open_questions, spoken aloud.
```

**The quota is affordable because nothing spends it by accident.** Five documents per cycle would be tight if every conversation re-analysed a drawing, and it is not: step 1 answers repeat drawings for free, step 2 resolves title blocks and dimension text locally for free, and step 3 is reached only when the owner opens a genuinely new sheet that the local extract could not read. Overnight RFQs queue as `needs_vision` rather than charging the pool (§8.1), so the budget the owner sees at 10:00 is the budget he gets. The HUD carries the used/total count and the reset time.

Why the confirm step exists rather than "just save what was said": a quote priced on a vision guess is exactly the failure the owner has already paid for. `entity_facts.state` makes the difference machine-checkable — `quote_verify` (§2.5) can refuse a price whose driving fact is a candidate.

**Confirmation must be explicit for high-value fields.** For `material`, `scope`, `qty`, and any tolerance or heat-treat spec, the chip echoes the value and requires a value-level confirm — a blanket "yes fine" never launders a vision suggestion into `owner_confirmed`. When it *is* accepted from a suggestion, `confirmed_from='vision_suggestion'` records that, so an audit can find every quote that stands on one.

### 4B.5 Second conversation about the same drawing — the recall path

```
"Let's pick up the KOSO spacer"
  │
  ├─ entity pin: conversation focus already carries part_revision_id (conversations.focus)
  ├─ card read:  SELECT … FROM entity_facts WHERE card_id=? AND state='confirmed'     (~2 ms)
  ├─ ledger read: last quote revision, rates as-of today, routing, open questions      (~5 ms)
  └─ corpus: skipped unless the question is "where/what did they say"
  │
  ▼
"En1A, 25 off, labour only. Ø25 H7 bore, flatness 0.01 so the face goes out for grinding.
 We quoted Rev B at ₹41,500 on the 14th — not sent yet. Still missing the case-depth
 spec you were going to check. Want the same routing repriced at today's rates?"
```

Properties that matter:

- **Zero vision calls, zero re-processing.** Vision re-runs only when: no card, revision changed, file bytes changed, extraction previously failed, or the owner says "look at it again".
- **Latency is a lookup, not a search.** Card + ledger is single-digit milliseconds against a vector search that is already 162 ms at 4 000 docs and grows linearly.
- **It says what it does not know.** `open_questions` is part of the card, so recall never bluffs.
- **It is auditable.** Every sentence above traces to a fact id or a ledger row.

### 4B.6 Shop-floor memory

Same pattern, different entities. The shop floor is an **event log plus a rebuildable projection**, never a model's recollection:

| Layer | Content |
| ----- | ------- |
| Events (truth) | `production_logs`, `downtime_reasons`, `tool_life_events`, `machine_telemetry`, `outsource_quotes`/actual turnaround, `remnant_stock` movements |
| Projection | `shop_state` rows per machine, material, vendor, and shift: status, current job, last downtime and cause, 7/30-day OEE trend, scrap rate, queue/WIP, tooling on hand, remnants available, vendor lead-time actuals — each with `as_of` and `derived_from` |
| Digest | A short generated narrative per machine and one shop-wide, regenerated on change, stored as a `rag_document` (`namespace='production'`, `authored_by='jarvis'`, **excluded from fact retrieval**) and embedded so questions like *"which machine keeps dying on night shift?"* hit one high-signal document instead of scanning thousands of rows |

Answer policy: numeric or aggregate questions → SQL over events (fast, exact, citable to `source_ref`); narrative or "why" questions → digest + citations; every answer carries a freshness stamp (*"as of the 06:00 night-shift log"*). This preserves the existing lock — Jarvis never invents an OEE number (`shop_excel.py` already refuses) — while making "known things" instant.

Other cards worth having on day one, because they are asked daily: **customer** (default scope, payment behaviour, who signs, NDA flag, quote win rate), **vendor** (processes, real lead times, price validity), **machine** (control, capability, current load), **material** (grades on hand, remnants, latest rate and its age), **people** (roles, shifts — extends the existing `familiarity.py`).

### 4B.7 Retrieval pipeline and latency budget

```
Stage 0  PIN        conversation focus + named entities     → entity ids            ~1 ms
Stage 1  CARDS      confirmed facts + ledger rows for pins  → authoritative context ~5 ms
Stage 2  RECALL     only if the question needs documents:
                      BM25 (rag_fts)  ∪  vector ANN (LanceDB/sqlite-vec)
                      fused by Reciprocal Rank Fusion, filtered by namespace/entity/date
                      top ~40 → lexical/cross-encoder rerank → top 6–8              ≤150 ms @100k chunks
Stage 3  PACK       budgeted: cards → digest → chunks(with citations) → "unknowns"  ~10 ms
Stage 4  ANSWER     numbers from cards/ledger only, each with an id; else ASK
```

**Hybrid is not optional in this domain.** Part numbers, drawing numbers, PO numbers, and grade codes (`SPL-4092-B`, `En1A`, `18CrNiMo7-6`) are exact-match tokens that dense vectors handle badly; prose ("that job where the bore kept going oversize") is where vectors win. BM25 ∪ vector with RRF gets both, and FTS5 is already available in SQLite.

Caching: per-turn memo; per-card cache invalidated on fact write; embedding cache keyed by `text_sha256` (re-indexing the same mail costs nothing). Budget: **RAG adds ≤0.25 s to a turn**, and the common case (a pinned drawing or machine) costs ~10 ms because it never reaches Stage 2.

### 4B.8 Ingest, chunking, embeddings

- **Structure-aware chunking**, not fixed windows: mail → header + paragraph groups; drawing → title block / notes list / dimension table / vision transcript sections; production report → per-machine rows; quote → per section; playbook note → per line. 200–400 tokens, ~15 % overlap, each chunk carrying entity links, `section`, and `effective_date`.
- **Ingest is an outbox worker**, never inline in a turn: write `rag_documents`/`rag_chunks` rows first, embed asynchronously, track `rag_index_state.pending` as a HUD-visible lag metric. Today a 100-day Gmail sync embeds inline on the sync thread (`mail_sync.py` → `reindex_all_mail_in_db`), which is both slow and unobservable.
- **Idempotent** by `(document_id, ordinal, text_sha256)`; re-ingesting a mail is free.
- **Real embeddings.** Replace the hash-of-words embedder (`backend/app/memory/embeddings.py`) with a local ONNX model — `bge-small-en-v1.5` or `e5-small-v2` (384-dim, so the existing column shape survives), warmed in-process, batched. Keep the hash embedder as a declared fallback (`embedding_model='hash-v1'`) so offline dev works, flagged as low-recall.
- **Model migration without downtime:** a new model writes rows with its own `embedding_model`; reads stay on the complete space until the re-embed backlog drains, then flip. Never mix spaces in one search.
- **Vector index:** LanceDB is now the committed store, not an experiment (§8.6), so it becomes the **read** path with an ANN index — today it is written on every upsert and never queried (§6.4), which is cost without recall. SQLite stays the durable mirror; the outbox guarantees convergence, a nightly reconcile compares counts and hashes, and the silent `except Exception: pass` mirror (§6.6) is replaced by a divergence metric.
- **Never ingest as fact:** Jarvis' own prose, failed-vision stubs (today `analyze_drawing_vision` writes *"Vision unavailable…"* into the corpus — §6.14), or unconfirmed candidate facts. `authored_by='jarvis'` documents are retrievable for continuity but excluded from fact answers, which is the guard against a model citing its own earlier guess.

### 4B.9 Retention, forgetting, privacy

| Namespace | Retention | Notes |
| --------- | --------- | ----- |
| `profile`, `people` | keep | Superseded, never silently overwritten |
| `drawings`, `quotes`, `production`, `standards` | keep | Commercial and engineering record |
| candidate `entity_facts` | TTL 14 days | Expire rather than leak into a price |
| `session` chatter | TTL 30 days | Matches the vision's rolling-session decision |
| Voice transcripts | TTL 7 days unless saved | Existing privacy lock |
| `disclosure_log` | keep forever | The record of what left this machine; never pruned, never wiped by a memory `forget` |
| `vision_quota_usage` | keep 1 year | Spend history and override audit; a `forget` must not reset a cycle counter |
| NDA customers | local only | `customer_terms.nda=1` ⇒ no cloud vision, no external summarisation; enforced at the tool boundary, logged in `disclosure_log` (§6.12) |

First-class owner controls (already promised in the vision, now implementable): *"what do you know about this drawing / this customer / me"* → card dump with provenance; *"forget this"* → by entity, fact, or namespace, with Authorize on a broad wipe.

### 4B.10 Evaluation — recall quality must be measured, not believed

A 50-question gold set drawn from real shop questions, versioned in `work/RAG_EVAL.md`, with a harness in `backend/tests/test_rag_eval.py` (offline):

| Metric | Target |
| ------ | -----: |
| Card hit on a known drawing (no vision call) | 100 % |
| Vision calls on a re-opened drawing | 0 |
| recall@8 on document questions | ≥0.9 |
| **Wrong-number rate** (a number in an answer not traceable to a card/ledger row) | **0** |
| Second-conversation first-token latency | <1 s |
| Numeric shop question answered from events with a freshness stamp | 100 % |

### 4B.11 Acceptance for Pillar 4B

1. Same drawing arrives twice (identical bytes, then a re-scan): first is processed, second is recognised — the re-scan is *proposed* as the same sheet and confirmed by the owner. Zero vision calls on the second.
2. A drawing conversation ends with confirm chips; only confirmed facts appear in the next conversation's opening line, and the unconfirmed ones are spoken as open questions.
3. Rev C of a quoted drawing triggers a change summary naming the changed fields and the affected quote revision.
4. "What's the state of the turning cell?" answers from `shop_state` with an `as_of` stamp in <1 s, citing the log rows.
5. A price whose driving fact is still a `candidate` is refused by `quote_verify` with that fact named.
6. Matrix section **H** extended with H-cards (H6 drawing recall, H7 shop-state recall, H8 wrong-number rate).
---

## 5. Agent Handoff Protocol

### 5.1 What this document is to the dispatcher

This manifest is a **design source**. It is not a backlog, and a worker must never be handed the whole file. The dispatcher's job is to turn sections into chunks that each satisfy five properties:

1. **One concern.** A chunk never touches both the FSM and the schema, or both rules and runtime code.
2. **PR-sized.** Reviewable in one sitting; if the diff would exceed ~400 lines of non-generated code, split it.
3. **Reversible.** Either behind a flag or a pure addition. Every chunk states its rollback in one sentence.
4. **Provable.** Names the test file it adds to or creates, plus the capability-matrix ID to re-run.
5. **Self-contained.** The kickoff quotes the manifest excerpts verbatim — workers cannot see the coordinator's chat, and must not re-derive the design.

### 5.2 Reading and chunking law

- **Quote, don't reference.** "Follow §4.3" is useless to a worker; paste the DDL block. Each chunk in §5.6 names the exact sections to inline.
- **A worker never redesigns.** If the excerpt is ambiguous or contradicts the repo, the worker stops and returns `GAPS`. Inventing a resolution is the one unforgivable behaviour, because this document's whole purpose is to keep manufacturing logic out of model judgement.
- **No chunk may weaken a gate.** Removing or bypassing a HITL gate, a proof check, or a provenance constraint is out of scope for every worker, always, even if it makes a test pass.
- **Contract before refactor.** Before any chunk that moves runtime behaviour, a golden-contract test pins the current `/api/chat` and `/api/confirm` response shapes. That test is chunk **T0** and blocks the rest of the T series.
- **Flags, not branches.** New paths ship dark: `turn_ledger_enabled`, `masterdata_enabled`, `knowledge_cards_enabled`, `real_embeddings_enabled` in settings/preferences, default off, dual-read for one release.
- **Never in a commit:** `.env`, `data/`, `exports/`, `google_token.json`, customer drawings, or a live rate table.

### 5.3 Dependency order (the safety ladder)

```
wave 1 (no dependencies; dispatch together, merge before wave 2)
  PG1─ proof gates, ONE worker over verify_quote: severity classes, zero/total/qty×rate,
       missing-MHR-is-a-failure, undated RM basis, stage-aware delivery check
  V1 ─ vision gate: deny-all default, ingest never spends, 5-per-cycle ledger, override
  K8 ─ strip Honcho; local-first declared
  R1 ─ rule tree split (T0 <200 words)
  S0 ─ migration runner + WAL / busy_timeout / FK pragmas
  T0 ─ golden contract tests

wave 2   Q2 claim-once HITL + external_effects · Q3 PDF hash binding · T1 turn ledger
         V1b needs-vision queue + spend action on the bench · S1 parties/materials/RM
         S2 machines + temporal MHR
wave 3   S3 routings · S4 quote revisions · S5 attested rate import · V2 per-customer consent
         Q5b 30-day comparison · T2–T5 SSE, reaper, reconciliation, concurrency
wave 4   K1–K7 knowledge cards, identity cascade, hybrid retrieval, real embeddings, shop state
wave 5   M1–M6 machining features · O1–O2 metrics, backup · P1 network posture
```

The ordering is deliberate. **Wave 1 is everything that stops a wrong or costly act and needs nothing built first**: the proof cannot currently refuse ₹0.00, a delivery date can be left blank, an undated material basis is invisible, and any drawing can be shipped to Gemini without a gate or a spend cap. Rules (R1) ride along because they are free and make every later worker smarter. Features (M) come last, because a feature built on today's quote-state model inherits §6.7.

**One worker per file, not one worker per rule.** Every gate above lands in `verify_quote`, so they ship as a single chunk (**PG1**) rather than three parallel workers colliding in one function. Parallelism inside a wave is only safe across disjoint file sets — check that before dispatching, not after.

**V1 before V2 on purpose:** consent lives on `customer_terms`, which does not exist until S1. Until it does, the safe interim is not "allow and remember" but **deny every customer** and let the owner authorize per drawing — the quota ledger and the override card are useful on day one, and S1 only relaxes the gate for customers the owner has attested.

### 5.4 Chunk anatomy (the dispatcher's template)

```
Chunk:        <ID> — <title>
Agent:        jarvis-uiux | jarvis-voice | jarvis-workflows | jarvis-builder
Model:        composer-2.5-fast        (required; never inherit)
Placement:    cloud | desk   (desk only for Hermes :8642, Voicebox :17493, real Google OAuth,
                              GPU-representative Ollama, or physical mic/speaker)
Depends on:   <chunk ids that must be merged first>

Goal:         <one sentence, outcome-shaped>
Context the worker cannot see: <paste the manifest excerpt(s) verbatim>
Files in scope: <explicit paths; everything else is out of scope>
Non-goals:    <the adjacent thing it must NOT touch>
Acceptance:   <observable: test name, API shape, HUD state, log line>
Verification: <command(s) to run: pytest -m "not live_service" …, npm run typecheck>
Rollback:     <one sentence>
Return:       DONE / FILES / TRY / GAPS
```

Two standing clauses in every kickoff: *"Do not expand scope"* and *"If this manifest excerpt is ambiguous, return GAPS instead of choosing."*

### 5.5 Verification ladder

| Rung | What | Who |
| ---- | ---- | --- |
| 1 | Unit test for the changed unit (`backend/tests/…`, offline) | Worker |
| 2 | Contract test: `/api/chat`, `/api/confirm`, `/api/pending` shapes unchanged | Worker |
| 3 | `pytest -m "not live_service"` green + `npm run typecheck` + `npm run lint` | Worker |
| 4 | Capability-matrix ID re-run (headless HUD where cloud-verifiable) | Worker (cloud) or owner (desk) |
| 5 | Live desk check for anything touching Hermes, Voicebox, OAuth, mic | Owner |

A chunk that cannot state its rung-4 ID is not ready to dispatch.

### 5.6 Chunk table

| ID | Title | Agent | Place | Depends | Manifest excerpt to paste | Acceptance |
| -- | ----- | ----- | ----- | ------- | ------------------------- | ---------- |
| **PG1** | **Proof gates — one worker, one pass over `verify_quote`.** Severity classes (BLOCKER/WARN, any BLOCKER stops); zero / negative / absent price, total ≤ 0, qty × rate mismatch; missing-MHR-is-a-failure; raw-material basis must carry a date; stage-aware delivery check (WARN at draft, BLOCKER at send) | workflows | cloud | — | §2.5, §6.1, §6.2, §6.9, §8.5, §8.7 | New tests: ₹0.00 line ⇒ `verdict='block'`; machine-without-rate ⇒ block; undated RM basis ⇒ block; no delivery ⇒ `stage='draft'` warns and `stage='send'` blocks; no code path computes a date; `test_quote_playbook.py` green |
| **Q2** | Claim-once HITL + `external_effects` + Idempotency-Key | workflows | cloud | S0 | §1.5, §6.3 | 5 concurrent confirms ⇒ 1 effect, 4 "already handled"; fault-injection test leaves `needs_human` |
| **Q3** | Bind proof to PDF sha256; refuse on drift at send | workflows | cloud | PG1 | §2.5, §6.8 | Mutating the PDF after verify blocks the send |
| **Q5b** | 30-day RM staleness comparison, re-evaluated at send | workflows | cloud | PG1, S1 | §2.5, §4.4, §6.30 | Test: basis 31 days old ⇒ block; verified day 29 / authorized day 31 ⇒ block |
| **V1** | Cloud-vision gate: deny-all default, owner-only spend (ingest stops at the local extract and sets `needs_vision`), `vision_quota_usage` ledger with atomic claim, 5-per-cycle cap on a 10:00 boundary, page threshold of 4, HITL override for one document, `disclosure_log` | workflows | cloud | — | §2.7, §4.3, §4B.4, §8.1 | Tests: mail ingest of a new drawing ⇒ zero dispatches and `analysis_state='needs_vision'`; 6th owner-opened document ⇒ HITL card, no dispatch; concurrent claims ⇒ one unit; retry of a charged file ⇒ free; failure ⇒ no charge and no corpus write; 6-sheet pack ⇒ asks with a local sheet index; provider stubbed |
| **V1b** | Bench affordance for the queue: `needs_vision` list, an explicit "analyse this drawing (spends 1 of 5)" action, and the used/total + reset-time counter | uiux | cloud | V1 | §2.7, §6.28, §8.1 | Headless check: the queue renders, the action names its cost, the counter reflects the ledger. No spend path exists that does not pass through an owner action |
| **V2** | Per-customer consent rows + owner attestation UI path; NDA hard-deny | workflows | cloud | V1, S1 | §2.7, §4.3 | Unknown customer denies and asks; `nda=1` cannot be overridden |
| **K8** | Strip Honcho: remove the module's cloud framing, rename `dual_write` → `memory.mirror`, mark `VISION_WORKBOOK` §2 superseded, assert local-first in the rule set | builder | cloud | — | §6.6, §8.6 | `rg -i honcho` returns nothing in `backend/`; memory doc states local-first |
| **R1** | Split rules into the §2.3 tree; write the always-on core plus the three domain rules (quote, g-code, drawing-vision); CI budget test | builder | cloud | — | §2.2–§2.9 | Core rule <200 words; every scoped rule has `globs`; no rule but the core sets `alwaysApply: true`; scoped rules ≤700 words |
| **R2** | Trim `AGENTS.md` to a map; delete duplicated stack/HITL prose | builder | cloud | R1 | §2.1, §2.9 | One home per fact; no contradictions with `docs/CURRENT.md` |
| **S0** | Migration runner, `schema_migrations`, WAL + `busy_timeout` + FK pragmas | builder | cloud | — | §1.7, §4.4 | Fresh DB and existing DB both migrate; concurrent write test passes |
| **S1** | Parties + materials + suppliers + RM quotes (+ alias backfill from `client-names.md`) | workflows | cloud | S0 | §4.3, §4.5 | Customer-spelling proof check reads `customer_aliases` |
| **S2** | Machines, `machine_hour_rates` (temporal, as-of), capabilities; import `mhr-demo.md` as `source_kind='demo'` | workflows | cloud | S0 | §4.1, §4.3 | As-of lookup test; missing or expired floor blocks send (attestation lands in S5) |
| **S3** | Components, part revisions, routings, routing operations, outsource tables | workflows | cloud | S1, S2 | §4.3 | Round-trip test; `jobs` dual-read behind flag |
| **S4** | Quotes / revisions / lines / proofs / events; migrate `memories`-based quote state | workflows | cloud | S1–S3, PG1 | §4.3, §4.5, §6.7 | Two quotes in one session no longer collide; >50 memory writes no longer lose facts |
| **S5** | Attested rates: `attested_by` / `attested_at` / `shipped_seed_value_minor`, idempotent importer for the owner-edited `files/mhr-demo.md`, fail-closed on malformed rows | workflows | cloud | S2 | §4.1, §4.5, §6.2, §8.2 | Unattested or shipped-seed value ⇒ BLOCKER; an owner-attested row prices a real quote; a bad row fails the import instead of landing silently |
| **T0** | Golden contract tests for chat/confirm/pending/session | builder | cloud | — | §5.2 | Snapshot tests pass before and after T1–T4 |
| **T1** | `turns` table + accept-then-work `/api/chat` + idempotency key | builder | cloud | S0, T0 | §1.2, §1.3 | POST returns `{turn_id}` <100 ms; result readable from ledger |
| **T2** | SSE stream + polling fallback + `stage` heartbeats | builder | cloud | T1 | §1.2, §1.8 | Stage visible in HUD; reconnect resumes with `Last-Event-ID` |
| **T3** | Reaper + stage-aware retry policy + honest failure line | builder | cloud | T1 | §1.6, §1.9 | Killed worker ⇒ FAILED within 15 s naming the stage |
| **T4** | HUD `RECONCILE` event + `hydrate()` + reconciliation matrix | uiux | cloud | T1–T3 | §1.3, §1.4 | Reload during a turn re-attaches; lost queued Authorize appears |
| **T5** | Per-session locks + bounded semaphore; vision/nesting/backplot become async jobs | builder | cloud | T1 | §1.7, §1.8 | Casual p50 unchanged with 3 background jobs |
| **K1** | `entity_cards` / `entity_facts` + card read API + "what do you know" | workflows | cloud | S0, S3 | §4B.1, §4B.3, §4B.5 | Card read <10 ms; only confirmed facts quotable |
| **K2** | Drawing identity cascade (sha256 → fingerprint → logical → revision diff) | workflows | cloud | K1 | §4B.2, §4B.4 | Re-scan proposed as same sheet; Rev C produces a change summary; zero vision calls on a known drawing |
| **K3** | Confirm-chip extraction pipeline + Engineering bench chips | uiux + workflows (split) | cloud | K1 | §4B.4 | Candidate facts expire; high-value fields need value-level confirm |
| **K4** | Hybrid retrieval: FTS5 + ANN + RRF + rerank, outbox ingest, structure-aware chunking | builder | cloud | S0 | §4B.7, §4B.8 | recall@8 ≥0.9 on the gold set; ingest off the request path |
| **K5** | Real local embeddings (ONNX 384-dim) + per-row model/dim + dual-space migration | builder | cloud | K4 | §4B.8, §6.4 | Search ≤150 ms @100 k chunks; hash embedder flagged fallback |
| **K6** | `shop_state` projection + digests + freshness stamps | workflows | cloud | S3 | §4B.6 | Numeric answers cite log rows; narrative answers cite the digest |
| **K7** | RAG eval harness + gold set | builder | cloud | K4 | §4B.10 | Wrong-number rate 0 in CI |
| **M1** | Quote-to-actual variance ledger + HUD card | workflows | cloud | S4 | §3.5, §3.6 | Variance per quote line; ranked margin erosion |
| **M2** | `cycletime` Engine A + calibration store | builder | cloud | S3 | §3.4 | Estimates carry method/confidence/`n`; uncalibrated labelled |
| **M3** | `stockcut` 1D + `remnant_stock` | builder | cloud | S1 | §3.2 | Yield and remnants written back; cost per piece feeds the quote |
| **M4** | `featurescan` STEP path + `feature_process_rules` + routing draft | builder | cloud | S3 | §3.3 | Routing draft from a STEP file; unclassified features listed |
| **M5** | `toolwatch` v0 on shop-log events **plus the one-line capture path** (speech or single HUD field → `tool_life_events`) | workflows | cloud | S2 | §3.1, §8.4 | 80/95 % life alerts; "insufficient history" below threshold; an insert change can be recorded in one utterance. No control integration in scope |
| **M6** | `program_verify` + versioned program store + promote gate | builder | cloud | S2 | §2.6, §6.13 | Envelope/feed/rapid violations fail closed with block numbers |
| **O1** | Durable metrics: per-stage latency, proof-block rate, duplicate-effect count, index lag | builder | cloud | T1 | §1.8, §6.17 | Survives restart; `/api/metrics` exposes the new series |
| **O2** | Nightly `VACUUM INTO` backup, boot `integrity_check`, sent-quote archive | builder | cloud | S0 | §6.18 | Restore drill documented and run once |
| **P1** | Loopback bind by default + local token on mutating endpoints + CORS tightening | builder | desk | — | §6.19 | LAN client cannot POST `/api/confirm` |

Desk-only work is deliberately rare: only **P1** (needs the real network posture) and the live rungs of §5.5. Everything else is cloud-verifiable, per the placement policy in `AGENTS.md`.

### 5.7 Living-notes discipline during the overhaul

The coordinator (not the workers) keeps the conversation record current: a dated **Log** bullet per owner decision in `work/ARCHITECTURE_POINTS.md`, `work/APP_FEATURES.md`, or `work/UI_UX_POINTS.md`; `docs/CURRENT.md` is updated only when a chunk actually ships. This manifest is neither — it is the target, and it is superseded section by section as chunks land. When a section is fully implemented, mark it `SHIPPED → docs/CURRENT.md §x` rather than deleting it, so the reasoning survives.
---

## 6. Critical Blind Spots & Omissions

### 6.0 Method

Five of these were **reproduced on this VM** against the real modules, not reasoned about. Harness output: [`/opt/cursor/artifacts/blind_spot_evidence.log`](/opt/cursor/artifacts/blind_spot_evidence.log). The rest are read directly from the checkout with the file cited. Severity:

| Tier | Meaning |
| ---- | ------- |
| **P0** | Can send a wrong number, a duplicate, or a customer's drawing where it must not go |
| **P1** | Loses work, corrupts state, or blocks the shop |
| **P2** | Breaks at real scale or gives quietly wrong answers |
| **P3** | Governance, recoverability, and audit |

---

### P0 — money, authority, and disclosure

#### 6.1 The quote proof cannot tell ₹0.00 from a price *(reproduced)*

`quote.verify_quote` checks that `unit_price` **parses as a number**, then passes. A 25-off line at `0` clears it:

```
passed = True   failed_count = 0   stop = False
  [PASS] unit_prices: All 1 row(s) have numeric unit prices
quote_send ok=True queued=True    speak: "Authorize to send the quote PDF."
```

There is no total assertion, no `qty × rate` recomputation, no currency, no sanity band against historical ₹/kg or ₹/hr, and no check that an outsourced operation carries a price. "Never underquote" is the owner's hardest rule (`APP_FEATURES.md`, interview Q8) and the proof cannot enforce its most extreme violation.
**Fix:** §2.5 BLOCKER list; positive total; arithmetic recomputation from `quote_lines`; outlier band from history with the band named in the check evidence. → **PG1**

#### 6.2 The MHR floor is checked only when the data happens to be there *(reproduced)*

```
machine + rate below demo floor    -> FAIL (good)
machine recorded, rate omitted     -> check absent (silently skipped)
rate recorded, machine omitted     -> check absent (silently skipped)
machine not in the demo table      -> check absent (silently skipped)
```

Three of the four shapes of "we underquoted the machine time" produce **no check at all**, because `verify_quote` only compares when `machine and mhr_rate is not None` and only against machine types listed in `files/mhr-demo.md`. The real shop has machines that will never appear in a demo markdown table.
**Fix:** invert the default — absent machine, absent rate, unlisted machine, or expired rate row is a BLOCKER; floors move to `machine_hour_rates` with as-of lookup. Per §8.2 the `demo` table stays in production, so the send gate is **attestation**, not storage: unattested, or still equal to the shipped seed value, blocks. → **PG1**, **S2**, **S5**

#### 6.3 Two Authorizes send two emails *(reproduced)*

```
replies    = ['Sent to deepak@koso.example.', 'Sent to deepak@koso.example.']
mails sent = 2   (expected 1)
```

`agent.resolve_pending` reads `status`, performs the provider call, then writes `status='approved'` — no transaction, no claim, and `/api/confirm` is not even behind the `brain_lock` that `/api/chat` takes. Two clicks, a retried POST, or a mobile double-tap sends twice. The same read-then-write ordering means a crash between "Gmail accepted" and the status write leaves the action `pending` — re-authorizable, indistinguishable from never-sent. And the foundation metric ("HITL miss rate = 0", `VISION_WORKBOOK` §14) measures *unauthorized* sends, so it cannot see any of this.
**Fix:** §1.5 atomic claim + `external_effects` intent log + Idempotency-Key + boot reconciliation into `needs_human`; add `duplicate_external_effect_count` to the metric contract. → **Q2**, **O1**

#### 6.4 Recall is a linear scan over hash-of-words vectors *(reproduced)*

```
   200 docs -> search   8 ms
  1000 docs -> search  41 ms
  4000 docs -> search 160 ms        (linear, inside the turn)
ingest per doc WITH the LanceDB mirror : 10.8 ms
ingest per doc WITHOUT the mirror      :  5.1 ms
```

`backend/app/memory/store.py::search` loads **every row**, JSON-decodes a 384-float vector per row, and computes cosine in Python. `backend/app/memory/embeddings.py` is a signed hash of bag-of-words — so "bright bar" will not match "rod stock", and recall is lexical while being advertised as semantic. The stated goal is 100 days of Gmail (tens of thousands of documents) plus drawings and production reports: seconds per turn, and shallow.
Worse: **LanceDB is written and never read.** `search()` has no Lance path at all, yet `_lance_upsert` runs on every document and doubles ingest cost — the vector store the architecture is named after is pure write amplification today (`get_summary()` still reports `engine: lancedb+sqlite`, which is how this went unnoticed).
Three independent defects, all P0 because the owner's top-two foundation priorities are memory and latency.
**Fix:** §4B.7–4B.8 — hybrid FTS5 + ANN with RRF, real ONNX embeddings, structure-aware chunks, outbox ingest, per-row model/dim. → **K4**, **K5**

#### 6.5 The Hermes session map corrupts under concurrency *(reproduced)*

```
40 concurrent job mappings written -> file holds 6 (lost 34)
# a second run of the same harness left the file as invalid JSON:
#   Extra data: line 3 column 4
```

`backend/app/hermes/bridge._save_hermes_session` is read-JSON → mutate → `write_text`, unsynchronised, and `_load_hermes_session` swallows `JSONDecodeError` and returns `None`. A corrupt or lost mapping means a resumed quote job **silently starts a fresh Hermes thread** — the job loses its own history mid-workflow, which reads to the owner as "Jarvis forgot what we just decided".
**Fix:** `hermes_sessions` table with atomic upsert; no module writes its own JSON state file. → **S0**

#### 6.6 "Dual-write memory" is a name, not a mechanism

`backend/app/memory/dual_write.py` is titled *"Best-effort dual-write into local memory while Honcho remains live"* and does exactly one local `upsert`. There is **no Honcho client anywhere in the backend** (one match in the whole tree — that docstring), and it is called from exactly one place (`backend/app/tools/registry.py`, preference writes). Meanwhile the LanceDB mirror in `store._lance_upsert` swallows every exception (`except Exception: pass`), is never read back (§6.4), and has no reconciliation and no divergence metric.
So the strategy of record — "dual-write now, cut over from Honcho later" (`VISION_WORKBOOK` §2) — describes a system that does not exist: Hermes' own memory is opaque to Jarvis, Jarvis' store is local-only, and nothing reconciles them. That is not necessarily wrong as an end state, but the plan should stop pretending a migration is in progress.
**Locked (§8.6):** Honcho is stripped and the architecture is 100 % local-first on LanceDB + SQLite. In this repo that is small — one module and its docstring (`rg -i honcho backend/` matches exactly one line) plus 19 stale lines in `VISION_WORKBOOK.md`. Two consequences worth naming: the LanceDB write-only defect (§6.4) is promoted from waste to a blocker, because Lance is now the committed read path rather than an optional mirror; and the repo cannot prove the *Hermes* side is local — the gateway's own memory provider lives in `~/.hermes`, off this checkout, so that verification is a desk task, not a chunk.
**Fix:** rename `dual_write` → `memory.mirror`, drop the cloud framing, mark the workbook decision superseded, single writer + outbox + nightly reconcile + index-lag metric. → **K8**, **K4**, **O1**

#### 6.7 Quote state lives in a 50-row session chat log

Quote facts are `memories` rows (`last_quote_rows`, `last_quote_scope`, `last_quote_machining_rate`, …) read by `quote._latest_memory`, which scans `db.list_memories(session_id, limit=50)`. Consequences, all silent:

- **Cross-contamination.** Keys are per session, not per quote. Quoting part B in the same conversation overwrites A's scope, machine, and rate — and `verify_quote` then proves the *mixture*.
- **Silent truncation.** `build_quote` writes ~10 memory rows per build; after ~5 builds the drawing name, customer, or scope the proof depends on has fallen out of the 50-row window, and the corresponding check flips to "missing" or, worse, reads an older quote's value.
- **No revisions, no audit, no re-proof.** A sent quote cannot be reconstructed.

This is the most dangerous data-model flaw in the current system, because it silently *changes numbers* rather than failing.
**Fix:** §4.3 `quote_revisions` + `quote_lines`; session memory holds a pointer only. → **S4**

#### 6.8 Verify and send agree on a path, not on bytes

`registry._quote_send` re-runs `verify_quote` (good) but the queued payload carries `attachment_paths` — a filesystem path. Between queue and Authorize the PDF can be regenerated or edited; the Authorize card then shows a proof describing different bytes than Gmail attaches. Nothing binds the two.
**Fix:** hash at verify, re-hash at send, refuse on mismatch; store `pdf_sha256` on the revision and the proof. → **Q3**

#### 6.9 `stop` is arithmetic, not severity

`stop = failed > 2`. Two catastrophic failures (no price + wrong customer) queue the send; three cosmetic ones block it. Severity is not a count.
**Fix:** BLOCKER/WARN classes, any BLOCKER stops. → **PG1**

#### 6.10 Drawings reach a cloud model with no disclosure gate

`quote.analyze_drawing_vision` base64s any local path straight to Gemini whenever the tool is called. The privacy lock says raw drawings stay local "unless the user explicitly delegates that file" (`VISION_WORKBOOK` §5/§13), but there is no per-file consent, no per-customer NDA flag, no disclosure record, and no redaction. For a jobbing shop, customer drawings are contractual confidential material — and the title block carries the customer's name and part number.
**Locked (§8.1):** default-deny per customer, a hard cap of five documents per 10:00→10:00 cycle across every source, and an owner override for an urgent sixth. Mechanism in §2.7 and §4B.4: consent and quota are *independent* gates, the quota unit is claimed atomically before dispatch and keyed on the file hash so retries and multi-page packs cannot double-charge, and every dispatch writes `disclosure_log`.
**Fix:** → **V1** (deny-all + ledger + override, no dependencies), **V2** (per-customer consent once `customer_terms` exists)

---

### P1 — lost work, blocked shop

#### 6.11 Head-of-line blocking on one global lock

Every turn takes `conversations._BRAIN`. One 35-second Hermes casual turn stalls the morning brief, `office_day` refresh, and every other session. Combined with a 180-second inline vision call and no client timeout, the practical worst case is a multi-minute freeze of the whole desk.
**Fix:** §1.7 per-session locks + bounded semaphore; vision/backplot/nesting become async jobs. → **T5**

#### 6.12 SQLite is configured for a single-process toy

Default journal mode, no `busy_timeout`, no `foreign_keys`, and **two processes** on one file (the API plus `backend/app/hermes/mcp_server.py` over stdio) with several background threads (`mail_sync`, `snapshot`, warm, watches). `database is locked` is a matter of load, and it will surface as a failed tool call mid-quote.
**Fix:** WAL + `busy_timeout=5000` + FK pragmas at the single `connect()` chokepoint. → **S0**

#### 6.13 G-code safety rests on a six-code blocklist

`cnc_suggest` refuses missing geometry (genuinely good) and blocks a handful of G-codes via `_BANNED_WORDS`. But nothing checks the program against the **machine**: no travel-limit check, no rapid-into-stock check, no feed/speed envelope, no tool-offset presence, no control-dialect match, no required retract before tool change. A blocklist cannot make a program safe; only a whitelist plus a deterministic verifier can. And `cnc_promote` is HITL but promotion is not versioned, so a proven program can be overwritten.
**Fix:** §2.6 `program_verify` + per-control M-code whitelist + versioned program store + never transmit to a control. → **M6**

#### 6.14 A failed vision call poisons the corpus

On exception, `analyze_drawing_vision` returns `ok: False` **and still** ingests `"Vision unavailable (…) File X queued for manual dimensional review"` into the RAG corpus and writes `last_quote_drawing*` memories. Downstream, the quote path believes a drawing was analysed, and a later RAG answer can cite the failure text as if it were drawing content.
**Fix:** never ingest failure text; `part_revisions.analysis_state='failed'`; corpus writes only on success. → **K2**

#### 6.15 Schema evolution by ad-hoc `ALTER`

`init_db()` patches columns with `PRAGMA table_info` checks and no version record. It cannot express a rename, a constraint, a backfill, or a rollback — and §4 adds ~20 tables with foreign keys.
**Fix:** `schema_migrations` + forward-only SQL files. → **S0**

#### 6.16 One-way playbook sync silently discards desk edits

`ensure_playbooks_installed()` copies the repo playbook over `~/.hermes/skills/shop/quote` **on every API start**, while `quote.append_playbook_note` writes to the *repo* copy. Net effect: notes survive (good), but anything the owner edits in the installed copy — the one they would naturally open while Hermes is running — is destroyed at the next restart with no warning.
**Fix:** treat the home copy as a build artifact; log the overwrite; detect drift (hash compare) and warn instead of silently clobbering; ship a `jarvis playbook sync` direction flag. → **R2**

---

### P2 — quietly wrong at scale

#### 6.17 Metrics are in-process and business-blind

`metrics._latency_samples` is a `deque(maxlen=200)` in memory — gone on restart, and only 200 samples wide. Nothing measures the things that decide whether this system is working: proof-block rate, duplicate external effects, quoted-vs-actual variance, abandoned turns, index lag, vision-call count per drawing.
**Fix:** durable per-stage metrics from the turn ledger + the business series. → **O1**

#### 6.18 No backup, no integrity check, single point of loss

One SQLite file holds quotes, mail, memory, and HITL history; `exports/` holds the only copy of sent PDFs; there is no backup job, no `integrity_check`, no restore drill. A corrupt page loses the shop's quote history — which is also its commercial record.
**Fix:** nightly `VACUUM INTO` with retention, boot integrity check, append-only archive of sent quote PDFs + payload, one rehearsed restore. → **O2**

#### 6.19 The desk API is unauthenticated on the LAN

`settings.jarvis_host` defaults to `0.0.0.0`, and CORS allows `https?://(localhost|127\.0\.0\.1|(\d{1,3}\.){3}\d{1,3})(:\d+)?` — any LAN IP. No endpoint requires a credential, including `POST /api/confirm`. Anyone on the shop network (or a guest phone on the same Wi-Fi) can authorise an outbound quote email. The core rule says "prefer 127.0.0.1", but the default and the CORS regex say otherwise, and defaults are what run.
**Fix:** bind loopback by default; local bearer token for mutating endpoints; explicit opt-in for LAN with an allowlist. → **P1**

#### 6.20 Time, units, and currency are inconsistent

`db.utc_now()` coexists with naive `datetime.now()` (`quote.append_playbook_note`, activity timestamps); `tz` is `Asia/Kolkata` but no display-layer conversion is enforced; money has no currency field and lands in a spreadsheet cell as a float or an empty string; `cnc_suggest` **infers** inch-vs-mm by sniffing tokens. On a shop floor, a units mix-up is a scrap event, and an inch/mm inference is not a safety-grade decision.
**Fix:** §4.4 conventions; units on every dimension with the original preserved; currency on every money field; UTC storage everywhere; units asserted in the quote proof. → **S0**, **S4**, **PG1**

#### 6.21 No dedupe on mail → RFQ intake

`reindex_all_mail_in_db` dedupes corpus rows by `mail:{id}` (fine), but RFQ/job intake has no natural key: a re-synced thread, a forward, or a re-sent RFQ can create a second RFQ and a second suggested-task card. The bulk 100-day sync also embeds inline on the sync thread with no backpressure.
**Fix:** natural key `(customer_id, drawing_no, revision, thread_id)` on `quotes`; ingest via the outbox. → **S4**, **K4**

#### 6.22 Confirmation laundering (a risk the new design must not create)

Once §4B exists, the new hazard is a vision guess that becomes truth because the owner said "yes, fine" to a summary. Designed out from the start: value-level confirmation for `material`, `scope`, `qty`, tolerances, and heat-treat specs; `entity_facts.confirmed_from='vision_suggestion'` recorded so an audit can list every quote standing on one; candidate facts expire rather than lingering. → **K3**

#### 6.23 Self-citation / corpus collapse

Jarvis' own summaries, digests, and drafts are text. If they are indexed as corpus alongside external documents, later answers cite Jarvis' earlier guesses as evidence, and confidence rises while accuracy does not. `rag_documents.authored_by` exists precisely to exclude them from fact retrieval while keeping them for continuity. → **K4**

---

### P3 — governance and the things nobody notices until they matter

#### 6.24 "Capacity full" is an outsource trigger with no capacity model

The locked outsource rule includes "the shop is at capacity" (`APP_FEATURES` interview Q6), and quotes carry delivery days — but there is no load model, no shift calendar, and no WIP view.
**Resolved by lock (§8.7), in the strict direction:** Jarvis never computes a date and never suggests one, so the absence of a capacity model is no longer a correctness risk — it is simply out of scope. "Capacity full" stays an owner-stated outsource reason recorded as `outsource_case='capacity'`, and the delivery field is the owner's typed number or nothing. → **PG1**

#### 6.25 Single-operator authority — now a deliberate choice, with one consequence to engineer

**Locked (§8.3):** the owner is the sole commercial signer; no approval tiers, no delegation. That removes a workflow but not a risk, and the risk moves rather than disappearing:

- With one signer, **a duplicate click is the only possible forged approval** — so Q2 (claim-once) is the whole integrity story for commercial authority, not a nicety.
- Nothing may ship a quote while the owner is unreachable, which means a queued Authorize must never expire quietly. `ABANDONED` (§1.2) must not apply to `quote_send`: those age into a visible, sorted queue with a spoken reminder, never into a silent drop.
- `approved_by` stays in the schema as a single-owner audit stamp. Keep it even though there is one name: a quote sent last quarter must still say who authorised it.

#### 6.26 No revision of the *customer's* documents

A customer can revise an RFQ, a PO, or a specification after a quote is sent. There is no mechanism to detect that the inbound document changed and that an outstanding quote is now stale.
**Fix:** hash inbound documents (already in §4B), alert when a new revision of a quoted document arrives. → **K2**

#### 6.27 Playbook proof cannot be tested against real shop truth

`files/mhr-demo.md` is explicitly fictional, and `client-names.md` is a placeholder. The proof therefore passes in development for reasons that will not hold in production, and the first real quote is the first real test.
**Resolved by lock (§8.2):** the owner will fill the demo table with real shop rates, so the proof will finally run against real numbers — but only if the code can tell an attested rate from the shipped fiction, which is what `attested_by` + `shipped_seed_value_minor` exist for. `files/client-names.md` still needs the same treatment: a placeholder customer list makes the spelling check pass for the wrong reason. → **S5**, **S1**, matrix **G-section** case "a real part, a real rate, a real proof"

---

### New edges created by the locked decisions

Each lock closes a hazard and opens a smaller one. These are the smaller ones, and they are cheaper to engineer now than to discover in a quoting morning.

#### 6.28 An overnight mail ingest could have spent the whole vision budget before 10 AM

The cap is global and the cycle boundary is 10:00, so a night of inbound RFQs could have charged all five units before the owner sat down — the cost landing on him, at the worst moment, for work he did not initiate.

**Closed by lock (§8.1):** automated ingest no longer spends at all. It runs the free local extract, marks the drawing `analysis_state='needs_vision'`, and surfaces it on the Engineering bench; the unit is charged when the owner opens that RFQ and asks. Better than a reserve quota, because the spend now coincides with the moment the analysis has value — a drawing card is worthless until the owner confirms its facts anyway.

What the code must enforce: **only an owner-initiated open can charge a unit.** A watch, a retry loop, a background job, a Hermes tool call, or a mail re-sync must not, which is why `vision_quota_usage.spent_by` is constrained to owner-initiated values while `arrival` records how the drawing came in. The HUD carries used/total and the reset time. → **V1**, **V1b**

#### 6.29 A document is one unit, but a 40-page pack is not one drawing

Charging per `sha256` is what makes retries and page loops safe (§2.7). It also means a customer who sends a 40-sheet assembly pack gets the same unit as a single part sheet, and the per-page calls inside it cost real money.
**Approved (§8.1):** `vision_page_threshold`, default 4. Above it the tool extracts a sheet index locally, shows it, and asks which sheet matters before spending the unit. → **V1**

#### 6.30 A hard 30-day block with no override needs a fast way to refresh the basis

§8.5 is deliberately absolute, and the second-order effect is a shop that cannot send. A quote proved on day 29, queued for Authorize, and approved on day 31 must fail at send (§2.5) — correct, and infuriating unless refreshing the basis is a two-minute path. There is no override by design, so the escape hatch has to be *speed*, not permission.
**Fix:** warn at day 25 on any open quote whose RM basis is ageing; make "request a fresh supplier rate" a one-action path from the blocked send, with the RFQ mail pre-drafted; on a new rate, re-price and re-prove the same revision rather than rebuilding the quote. Also: an estimate's `basis_date` is the date of the *evidence* behind it, not the day Jarvis wrote it — dating an estimate "today" would silently defeat the rule. → **Q5b**

#### 6.31 A markdown rate file has no history, but the schema promises as-of lookups

The owner's edit surface is a file (§8.2), and editing a line in place destroys the previous floor. Law 2 in §4.1 says a quote sent in March must still re-prove itself in December with March's floor — impossible if the import overwrites.
**Fix:** the importer never updates in place. A changed value closes the current row (`effective_to = now`) and appends a new one with `effective_from = now` and the new attestation, so the file is a *view* of the latest rates while the DB keeps the timeline. Corollary: the file needs a `attested_on` column, and the importer must refuse a row whose date moves backwards. → **S5**

---

## 7. What "done" looks like

| Gate | Test |
| ---- | ---- |
| G-A | No quote can be queued for send without every line carrying a traceable rate source, a positive total, and a floor basis |
| G-B | Five concurrent Authorizes produce exactly one external effect; a mid-send crash parks the action for a human |
| G-C | Killing the API mid-turn produces a stage-named failure within 15 s; a reload re-attaches to the same turn and the same Hermes thread |
| G-D | Re-opening a known drawing costs zero vision calls and answers from confirmed facts in <1 s, naming what is still unconfirmed |
| G-E | "What's the state of the turning cell?" answers from events with a freshness stamp and citations |
| G-F | Wrong-number rate on the RAG gold set is 0, and recall@8 ≥0.9 at 100 k chunks with search ≤150 ms |
| G-G | T0 rule is <200 words; no non-T0 rule sets `alwaysApply`; every T1 rule has globs; CI enforces it |
| G-H | A quoted job's actual cycle time, material, and outsource cost land back against the quote line that predicted them |
| G-I | An overnight mail ingest dispatches nothing and queues the drawing as `needs_vision`; the sixth drawing the owner opens raises an override card naming customer, drawing, and used/total. Concurrent claims charge one unit; a retry of a charged document charges nothing; a failure charges nothing and ingests nothing; a pack over four sheets asks first |
| G-J | A quote with an empty delivery field drafts and prices normally with a warning, cannot be authorized, and no code path anywhere computes or suggests a date |
| G-K | A raw-material basis 31 days old blocks the send even when the proof passed on day 29 |
| G-L | An unattested rate row, or one still equal to its shipped seed value, blocks the send; an owner-attested row prices a real quote and the HUD names its attestation date |
| G-M | `rg -i honcho backend/` returns nothing, and every memory read and write is local (SQLite + LanceDB) |

---

## 8. Locked executive decisions (2026-09-22)

The owner reviewed the proposal and locked the following. These are **binding on every chunk**; a worker may not soften, widen, or "improve" them, and a chunk whose acceptance conflicts with one of them is wrong by definition.

### 8.1 Cloud vision — default deny, five documents per cycle, owner override

Default-deny per customer to protect NDA IP. For authorized customers, automated Gemini Vision analysis is capped at **5 drawings per 24-hour cycle running 10:00 → 10:00**. The quota is global: automated email ingests and the owner's own manual UI uploads draw on the same pool. Exceeding it pauses and requests an explicit manual override.

**Refined 2026-09-22:** automated email ingest uses the free local text extraction only and flags the drawing `needs_vision`; a vision unit is consumed later, when the owner explicitly opens that RFQ at his desk. The multi-page threshold check is approved.

Engineering reading: three gates (§2.7). Consent is a master-data fact and no override touches it. The trigger gate means no background path — ingest, watch, retry, or tool call — can charge a unit; `vision_quota_usage.spent_by` is constrained to owner-initiated values, with `arrival` recording provenance separately. Quota is a ledger with an atomic claim keyed on `(cycle_start, file_sha256)`, so one document is one unit regardless of pages or retries; above four sheets the tool extracts a local sheet index and asks first; an override grants exactly one unit for one named document. → **V1**, **V1b**, **V2**; §6.28 is closed by this refinement and §6.29 is the page rule.

### 8.2 Rate data — keep the `demo` infrastructure, filled with real numbers

Retain `source_kind='demo'`. The owner will manually update the seed values with actual shop rates so real quoting can proceed while the Master Data UI stays deferred.

Engineering reading: "demo" stops meaning "unusable", so the send gate moves from storage to **attestation** — `attested_by` plus a value differing from `shipped_seed_value_minor`. The markdown file remains the edit surface, the importer never overwrites in place (§6.31), and the temporal columns keep as-of proof honest. → **S5**, **S2**, **PG1**.

### 8.3 Commercial authority — the owner alone, no second signature

No multi-tier approval workflow.

Engineering reading: no tiers, no delegation, `approved_by` kept as an audit stamp. Claim-once HITL carries the whole integrity story, and a queued quote Authorize must never expire silently (§6.25). → **Q2**.

### 8.4 Telemetry — `toolwatch` v0 on the manual shop log

Lock v0. Defer FOCAS/MTConnect and any direct hardware network integration to a future phase.

Engineering reading: no `machine_telemetry` table, no adapters, no sensors in this overhaul. v0's real deliverable is the **capture path** — one spoken or typed line per insert change — because a model with an empty table predicts nothing (§3.1). → **M5**.

### 8.5 Estimate staleness — a 30-day hard block

A raw-material price basis older than 30 days blocks the quote send. Strict.

Engineering reading: global `rm_basis_max_age_days = 30`, evaluated at send and not only at verify, applying to supplier quotes, invoices, and labelled estimates alike, with an estimate dated by its evidence rather than by the day it was written. No override exists, so the escape hatch is a fast basis-refresh path (§6.30). → **PG1**, **Q5b**.

### 8.6 Memory — strip Honcho, 100 % local-first

Remove Honcho from the codebase entirely. Memory and knowledge run local on LanceDB + SQLite.

Engineering reading: small in code (one module, one docstring) and larger in docs — `VISION_WORKBOOK.md` §2 is superseded and marked as such. Two consequences: LanceDB must become the read path rather than a write-only mirror (§6.4), and the Hermes gateway's own memory provider must be verified on the desk, since it lives outside this checkout (§6.6). → **K8**, **K5**.

### 8.7 Delivery promises — never guessed, never computed

Jarvis must not guess or calculate a delivery date. The lead-time field stays empty and a strict flag requires the owner's manual input before a quote can be authorized.

**Confirmed 2026-09-22:** Jarvis insists on a delivery time, but a missing date must not block creation of the quote draft. Blocking the final "Authorize to send" stage is correct; drafting must proceed so the owner can review the pricing first.

Engineering reading: no capacity model, no vendor-lead-time arithmetic, no inference from past jobs — the capacity-aware-dates feature is removed from §3.5 outright. The proof takes a stage: `verify_quote(stage='draft')` emits a WARN for the empty field, `stage='send'` makes it a BLOCKER, and the Authorize card carries the input inline so the number is typed at the moment of authorising. Jarvis asks once while drafting and never proposes a value. This reconciles interview Q7 — "delivery time does not hold the quote", which governs the draft — with the new rule, which governs the send. → **PG1**.

### 8.8 Still open — flagged, not decided

Three left, each a default rather than a design, and none blocking any wave:

1. **Outsource-quote staleness.** The 30-day rule is locked for raw material. Heat-treat and plating prices drift too; currently a WARN. Raise to BLOCKER?
2. **MHR attestation ageing.** A rate attested 18 months ago is stale in a different way. Currently a WARN at 180 days, never a block.
3. **`files/client-names.md`.** Real customer list, or keep the placeholder and accept that the spelling check passes for the wrong reason (§6.27)?

Resolved 2026-09-22: automated ingest does not spend vision units (§8.1), the page threshold is approved at 4 (§6.29), the delivery check is stage-aware (§8.7), and the three proof gates ship as one chunk (§5.6 **PG1**).

## 9. Evidence appendix

Reproduction harness output (full): [`/opt/cursor/artifacts/blind_spot_evidence.log`](/opt/cursor/artifacts/blind_spot_evidence.log)

| Claim | Section | Verdict |
| ----- | ------- | ------- |
| ₹0.00 × 25 off passes all 8 proof checks and queues Authorize | §6.1 | Reproduced |
| MHR floor check absent in 3 of 4 missing-data shapes | §6.2 | Reproduced |
| Two concurrent Authorizes ⇒ 2 emails, status `approved` | §6.3 | Reproduced |
| `memory.search` 8 ms → 41 ms → 160 ms at 200 → 1 000 → 4 000 docs | §6.4 | Reproduced |
| LanceDB mirror doubles ingest cost (10.8 vs 5.1 ms/doc) and is never read by `search()` | §6.4 | Reproduced |
| `hermes_sessions.json` keeps 6 of 40 concurrent mappings; invalid JSON on a second run | §6.5 | Reproduced |
| No Honcho client in the backend; `dual_write` is one local upsert | §6.6 | Read from source |
| Quote state read from `list_memories(limit=50)` | §6.7 | Read from source |
| `jarvis_host='0.0.0.0'` + LAN-wide CORS regex, no auth on `/api/confirm` | §6.19 | Read from source |
| `build_quote()` has no delivery field, no date on the RM basis, and no attestation — an undated estimate with a missing delivery date passes the proof | §8.2, §8.5, §8.7 | Reproduced (claim 6) |

*End of manifest. The seven decisions in §8 are locked and binding, with §8.1 and §8.7 refined on 2026-09-22; §8.8 lists three defaults still open, none of which block any wave.*
