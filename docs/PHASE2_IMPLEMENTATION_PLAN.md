# Phase 2: Memory & Knowledge Deepening — Implementation Plan

**Branch:** `overhaul` → work on `phase2-memory-knowledge` branch
**Timeline:** 2 weeks
**Owner:** `jarvis-workflows` (backend), `jarvis-uiux` (frontend UI for knowledge cards)
**Reference:** `docs/ROADMAP.md` Phase 2, `docs/SYSTEM_TRUTH.md` §6

---

## Executive Summary

Phase 2 makes drawing recall and shop-floor memory production-ready. Current state: identity cascade exists (`identity.py`), knowledge cards exist (`cards.py`), memory store exists (`store.py`). Gaps: no revision diff UI, no confirmed-only quotable enforcement in UI, no shop-floor projection, no freshness stamps, no ingest pipeline automation.

**Deliverable:** Second conversation about a drawing answers from the card (material, qty, scope, tolerances, routing, quoted history, unconfirmed gaps stated plainly). Shop-floor questions answer from `shop_state` projection with freshness stamps.

---

## Current Architecture (What Exists)

### Memory Store (`backend/app/memory/store.py`)
- SQLite `memory_docs` table + optional LanceDB
- Namespaces: `profile`, `people`, `jobs`, `session`, `corpus`
- `upsert(namespace, key, text, meta)` → stores text + vector
- `search(namespace, query, k)` → returns scored results

### Knowledge Cards (`backend/app/knowledge/cards.py`)
- `entity_cards` table: metadata + summary + fact counts
- `entity_facts` table: `field, value, unit, source_kind, source_ref, state` (confirmed/candidate/disputed)
- `read_card(entity_type, entity_id)` → returns confirmed facts + candidates + open questions
- `what_do_you_know()` → short answer from owner-confirmed facts only

### Drawing Identity (`backend/app/knowledge/identity.py`)
- Cascade: exact SHA256 → text fingerprint → (customer, drawing_no, revision) → new
- `resolve_drawing_identity()` returns `DrawingIdentityResult` with `kind`: exact/propose/revision_change/new
- `_diff_confirmed_facts()` compares confirmed facts between revisions

### Master Data Migrations (already applied)
- `part_revisions` table with `drawing_sha256`, `drawing_artifact_id` (fingerprint), `customer_id`, `drawing_no`, `revision`
- `components` table linking to customers
- `entity_cards`, `entity_facts` tables

---

## Task Breakdown

### M2.1 Drawing Identity: Hash → Fingerprint → (customer, drawing_no, revision)

**Status:** Core logic exists in `identity.py`. Gap: No UI for revision diff; no integration with quote workflow.

**Implementation:**

1. **Backend: `resolve_drawing_identity` tool** (`backend/app/knowledge/identity.py` → new tool in `quote.py` or `knowledge/identity.py`)
   ```python
   def resolve_drawing_identity_tool(
       session_id: str,
       drawing_sha256: str,
       fingerprint_text: str = "",
       customer_id: str = "",
       drawing_no: str = "",
       revision: str = "",
   ) -> dict[str, Any]:
       """Returns DrawingIdentityResult dict; revision_change includes changed_fields + details."""
   ```

2. **Register tool** in `tools/registry.py` and Hermes MCP

3. **Frontend: Revision Diff Banner** (`frontend/src/components/bench/RevisionDiffBanner.tsx` — NEW)
   - Shows when `kind === "revision_change"`
   - Lists changed fields with prior/current values
   - "This is a new revision — confirmed fields changed: material, tolerance, OD"
   - Owner can acknowledge or dismiss

4. **Integration:** Call `resolve_drawing_identity` in `find_drawing_for_quote` (Q1.1) → if revision_change → show banner on Engineering bench

**Acceptance:** Revision change = diff + warning; never silent reuse

---

### M2.2 Knowledge Cards: Owner-Confirmed Facts Only Quotable

**Status:** `cards.py` enforces `source_kind == "owner_confirmed"` for quotable facts. Gap: Vision suggestions stored as candidates; no value-level confirm UI.

**Implementation:**

1. **Backend: Vision → Candidate Flow**
   - Modify `analyze_drawing_vision` (`quote.py`) to upsert vision output as `candidate` facts on the drawing's entity card
   - `source_kind = "vision"`, `state = "candidate"`

2. **Backend: Confirmation Tool** (`backend/app/knowledge/confirm.py` → new tool `confirm_drawing_fact`)
   ```python
   def confirm_drawing_fact(
       session_id: str,
       entity_type: str,  # "part_revision"
       entity_id: str,
       field: str,
       value: str,
       unit: str = "",
       source_ref: str = "",
   ) -> dict[str, Any]:
       """Owner confirms a candidate fact → state becomes 'confirmed', source_kind='owner_confirmed'."""
   ```

3. **Frontend: FactConfirmChips** (`frontend/src/components/orchestrator/engineering/FactConfirmChips.tsx` — EXISTS, enhance)
   - Shows candidate facts as chips: "Material: EN8 [vision]" → click to confirm/edit/reject
   - High-value fields (material, scope, qty, tolerance, heat treat) require explicit confirm
   - Once confirmed → moves to quotable facts list

4. **Enforce in `verify_quote`:** Already checks `price from unconfirmed drawing fact` → BLOCKER. Ensure candidate facts never pass as quotable.

**Acceptance:** Vision suggestion = candidate until confirmed; high-value fields need value-level confirm

---

### M2.3 Drawing Recall Path: Second Conversation Answers from Card

**Status:** `what_do_you_know()` returns confirmed facts. Gap: No "recall" tool for second conversation; no plain-language gaps summary.

**Decision:** **Option A — Deterministic Template** (locked 2026-09-26). Returns structured plain-language summary from confirmed facts only; zero latency, zero hallucination, consistent format.

**Implementation:**

1. **Backend: `recall_drawing_knowledge` tool** (`backend/app/knowledge/cards.py` → new tool)
   ```python
   def recall_drawing_knowledge(
       session_id: str,
       drawing_sha256: str = "",
       entity_id: str = "",
   ) -> dict[str, Any]:
       """
       Returns deterministic summary from confirmed facts only:
       - Drawing: {drawing_no} rev {revision}
       - Material: {material} (confirmed)
       - Qty: {qty} (confirmed)
       - Scope: {scope} (confirmed)
       - Tolerances: {tolerances} (confirmed/unconfirmed)
       - Routing: {routing} (confirmed)
       - Last quoted: {date} @ {amount} (confirmed)
       - Gaps: {unconfirmed_fields_list}
       """
   ```

2. **Frontend: Knowledge Summary Panel** (`frontend/src/components/bench/KnowledgeSummary.tsx` — NEW)
   - Shows on Engineering bench when drawing loaded
   - Sections: Confirmed Facts | Unconfirmed Gaps | Quote History
   - Deterministic format: "Drawing: PN-001 rev 2. Material: EN8 (confirmed). Qty: 50 (confirmed). Scope: with_material (confirmed). Tolerances: OD ±0.02mm (unconfirmed — gap). Routing: turning → heat treat → grinding (confirmed). Last quoted: 2026-08-15 @ ₹12,500 (confirmed). Gaps: bore diameter, heat treat spec."

3. **Integration:** Auto-call on drawing load if identity resolved (exact/propose)

**Acceptance:** Second conversation answers from card; material, qty, scope, tolerances, routing, quoted history, unconfirmed gaps stated plainly in deterministic format

---

### M2.4 Shop-Floor Memory: Event Log + `shop_state` Projection

**Status:** `shop/state.py` exists with event log pattern. Gap: No projection tables; no UI.

**Decision:** **Option B — Explicit tools called from chat** (locked 2026-09-26). Operator says "log downtime on M001" → tools write `shop_events`. No automated cron in this phase.

**Future Consideration:** Operator-accessible Google Sheets for shop-floor data. Operator updates sheet → Jarvis maintains offline copy in local DB → retains data from local DB. Deferred to later phase.

**Implementation:**

1. **Migration 0022+**: Add `shop_events` + `shop_state` tables
   ```sql
   CREATE TABLE shop_events (
       id TEXT PRIMARY KEY,
       ts TEXT NOT NULL,           -- ISO timestamp
       kind TEXT NOT NULL,         -- "downtime" | "scrap" | "oee" | "stock" | "vendor"
       machine_id TEXT,
       machine_name TEXT,
       component_id TEXT,
       value REAL,
       unit TEXT,
       details TEXT,
       source TEXT,                -- "manual" (chat tool) | "sheet" (Google Sheets sync, future)
       created_at TEXT
   );

   CREATE TABLE shop_state (
       id TEXT PRIMARY KEY,        -- e.g., "machine:M001", "vendor:Acme", "component:BRKT-01"
       kind TEXT NOT NULL,
       data TEXT NOT NULL,         -- JSON projection
       updated_at TEXT NOT NULL
   );
   ```

2. **Backend: Projection Engine** (`backend/app/shop/state.py` → enhance)
   - `rebuild_shop_state()` — rebuilds `shop_state` from `shop_events`
   - Event handlers: `log_downtime()`, `log_scrap()`, `log_oee()`, `log_stock()`, `log_vendor_turnaround()`
   - Incremental updates on event insert

3. **Backend: Query Tools** (`backend/app/shop/state.py`)
   - `get_machine_status(machine_id)` → current status, load, last downtime
   - `get_vendor_turnaround(vendor)` → avg days, last delivery
   - `get_component_stock(component_id)` → on-hand, allocated, available
   - `get_oee_trend(days=30)` → trend data

4. **Frontend: Shop Floor Panel** (`frontend/src/components/bench/ShopFloorPanel.tsx` — NEW)
   - Tabs: Machines | Vendors | Stock | OEE
   - Freshness indicator: "Updated 2 min ago" / "Stale (>1hr)"

**Acceptance:** Machine status/load, downtime causes, scrap/OEE trends, stock/remnants, vendor turnaround

---

### M2.5 Freshness Stamps on All Knowledge

**Status:** `entity_cards.updated_at` exists. Gap: No staleness logic; no UI flag.

**Decision:** **Option A — Hard Block** (locked 2026-09-26). Stale card → excluded from `verify_quote`; quote proof fails with BLOCKER if stale data used. Owner must refresh before quote passes.

**Implementation:**

1. **Backend: Freshness Logic** (`backend/app/knowledge/cards.py`)
   ```python
   STALENESS_THRESHOLDS = {
       "machine_status": timedelta(hours=1),
       "vendor_turnaround": timedelta(days=7),
       "stock": timedelta(hours=4),
       "oee": timedelta(hours=2),
       "drawing_card": timedelta(days=30),
   }

   def is_stale(card: dict[str, Any], kind: str) -> bool:
       updated = parse_iso(card.get("updated_at"))
       threshold = STALENESS_THRESHOLDS.get(kind, timedelta(days=7))
       return datetime.now() - updated > threshold
   ```

2. **Frontend: Freshness Indicators**
   - `FreshnessBadge` component (green/yellow/red dot + tooltip "Updated 5 min ago")
   - Show on KnowledgeSummary, ShopFloorPanel, FactConfirmChips
   - Stale = red badge; excluded from quotable paths

3. **Integration:** `verify_quote` checks freshness of any knowledge card used for pricing — stale = BLOCKER

**Acceptance:** Every card/projection has `updated_at`; stale = excluded from quotable paths (quote proof BLOCKER)

---

### M2.6 Retrieval Pipeline Latency Budget

**Status:** `memory/store.py` search uses LanceDB or SQLite. Gap: No latency SLO enforcement.

**Implementation:**

1. **Backend: Latency Tracking** (`backend/app/memory/store.py`)
   ```python
   import time
   from contextlib import contextmanager

   @contextmanager
   def latency_budget(operation: str, budget_ms: int):
       start = time.perf_counter()
       yield
       elapsed = (time.perf_counter() - start) * 1000
       if elapsed > budget_ms:
           log.warning(f"{operation} exceeded budget: {elapsed:.0f}ms > {budget_ms}ms")
   ```

2. **Enforce in `search()` and `upsert()`:**
   - SQL lookup: <500ms
   - Card load: <1s
   - Corpus search: <2s
   - LanceDB vector search: <1s

3. **Frontend: Latency Display** (dev only)
   - Small badge on KnowledgeSummary: "SQL: 12ms, Card: 45ms, Corpus: 180ms"

**Acceptance:** <500ms SQL; <1s cards; <2s corpus

---

### M2.7 Ingest: Auto on Mail/Attachments/Production/Drawings + Nightly + On-Demand

**Status:** `memory/ingest.py` exists. Gap: No auto-ingest triggers; no nightly cron; no on-demand API.

**Decision:** **Option B — Lightweight Async Queue (`asyncio.Queue`)** (locked 2026-09-26). Dedicated queue with worker, retry, backoff, priority; isolated from main background tasks.

**Implementation:**

1. **Ingest Queue** (`backend/app/memory/ingest_queue.py` — NEW)
   ```python
   import asyncio
   from dataclasses import dataclass
   from enum import Enum
   from typing import Any, Callable
   import logging

   log = logging.getLogger(__name__)

   class IngestPriority(Enum):
       HIGH = 0    # drawing save, mail attachment
       NORMAL = 1  # mail sync, production log
       LOW = 2     # nightly reindex, full reindex

   @dataclass
   class IngestTask:
       kind: str                    # "mail_attachment" | "drawing" | "production" | "reindex"
       payload: dict[str, Any]
       priority: IngestPriority = IngestPriority.NORMAL
       retries: int = 0
       max_retries: int = 3

   class IngestQueue:
       def __init__(self, max_workers: int = 2):
           self.queue: asyncio.PriorityQueue[tuple[int, IngestTask]] = asyncio.PriorityQueue()
           self.max_workers = max_workers
           self.workers: list[asyncio.Task] = []
           self.handlers: dict[str, Callable] = {}
           self.running = False

       def register_handler(self, kind: str, handler: Callable, max_retries: int = 3):
           self.handlers[kind] = handler

       async def enqueue(self, task: IngestTask):
           await self.queue.put((task.priority.value, task))

       async def start(self):
           self.running = True
           for _ in range(self.max_workers):
               self.workers.append(asyncio.create_task(self._worker()))

       async def stop(self):
           self.running = False
           for w in self.workers:
               w.cancel()
           await asyncio.gather(*self.workers, return_exceptions=True)

       async def _worker(self):
           while self.running:
               try:
                   _, task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
               except asyncio.TimeoutError:
                   continue
               await self._execute(task)

       async def _execute(self, task: IngestTask):
           handler = self.handlers.get(task.kind)
           if not handler:
               log.warning(f"No handler for ingest kind: {task.kind}")
               return
           try:
               await handler(task.payload)
           except Exception as e:
               log.warning(f"Ingest {task.kind} failed: {e}")
               if task.retries < task.max_retries:
                   task.retries += 1
                   await asyncio.sleep(2 ** task.retries)  # exponential backoff
                   await self.enqueue(task)
               else:
                   log.error(f"Ingest {task.kind} failed after {task.max_retries} retries: {e}")

   # Global instance
   ingest_queue = IngestQueue(max_workers=2)
   ```

2. **Auto Triggers** (in existing handlers):
   - Mail sync → `ingest_queue.enqueue(IngestTask(kind="mail_attachment", payload={...}, priority=IngestPriority.HIGH))`
   - Drawing save → `ingest_queue.enqueue(IngestTask(kind="drawing", payload={...}, priority=IngestPriority.HIGH))`
   - Production log write → `ingest_queue.enqueue(IngestTask(kind="production", payload={...}, priority=IngestPriority.NORMAL))`

3. **Nightly Cron** (separate script, not queue)
   ```python
   async def nightly_ingest():
       await ingest_queue.enqueue(IngestTask(kind="mail_reindex", payload={}, priority=IngestPriority.LOW))
       await ingest_queue.enqueue(IngestTask(kind="full_reindex", payload={}, priority=IngestPriority.LOW))
       await ingest_queue.enqueue(IngestTask(kind="shop_rebuild", payload={}, priority=IngestPriority.LOW))
   ```

4. **On-Demand API** (`backend/app/main.py` → new routes)
   - `POST /api/memory/ingest` — trigger specific ingest via queue
   - `POST /api/memory/reindex` — full reindex via queue

5. **Integration** (`backend/app/main.py` startup)
   ```python
   from app.memory.ingest_queue import ingest_queue

   @app.on_event("startup")
   async def startup_ingest_queue():
       ingest_queue.register_handler("mail_attachment", ingest_mail_attachments)
       ingest_queue.register_handler("drawing", ingest_drawing_summary)
       ingest_queue.register_handler("production", ingest_production_event)
       ingest_queue.register_handler("mail_reindex", reindex_mail)
       ingest_queue.register_handler("full_reindex", reindex_all)
       ingest_queue.register_handler("shop_rebuild", rebuild_shop_state)
       await ingest_queue.start()
   ```

**Acceptance:** Off hot path; search never blocks on ingest; priority lanes; retry with exponential backoff; observability via queue depth

---

### M2.8 Embedding Model ID + Dimension Recorded Per Vector

**Status:** `store.py` stores vector as JSON but no model metadata. Gap: Mixed dims possible; hash fallback not labelled.

**Implementation:**

1. **Migration 0023+**: Add columns to `memory_docs`
   ```sql
   ALTER TABLE memory_docs ADD COLUMN embed_model_id TEXT;
   ALTER TABLE memory_docs ADD COLUMN embed_dim INTEGER;
   ALTER TABLE memory_docs ADD COLUMN embed_provider TEXT;  -- "hash" | "onnx" | "openai" | "local"
   ```

2. **Backend: Record on Upsert** (`store.py`)
   ```python
   def upsert(..., embed_meta: dict | None = None):
       model_id = embed_meta.get("model_id") or settings.embed_model_id
       dim = embed_meta.get("dim") or len(vector)
       provider = embed_meta.get("provider") or "hash"
       # store in new columns
   ```

3. **Validation:** On search, if mixed dims detected → log error, fallback to hash

4. **Hash Fallback:** Explicitly label `provider="hash"` in meta

**Acceptance:** Mixed dims = invalid; hash fallback labelled

---

## Dependencies & Order

```
Week 1:
├── M2.1 Drawing Identity + Revision Diff UI (unblocks M2.3)
├── M2.2 Knowledge Cards: Candidate → Confirm flow (unblocks M2.3)
├── M2.5 Freshness Stamps (foundation for M2.3, M2.4)
└── M2.8 Embedding Metadata (migration first)

Week 2:
├── M2.3 Drawing Recall Path (uses M2.1, M2.2)
├── M2.4 Shop-Floor Memory (independent, parallelizable)
├── M2.6 Latency Budget (observability)
└── M2.7 Ingest Pipeline (depends on M2.1-M2.4 data)
```

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/knowledge/identity.py` → `resolve_drawing_identity_tool` | Tool for identity resolution |
| `backend/app/knowledge/confirm.py` → `confirm_drawing_fact` | Tool for fact confirmation |
| `backend/app/knowledge/cards.py` → `recall_drawing_knowledge` | Tool for recall summary |
| `backend/app/shop/state.py` — enhance projection + query tools | Shop floor memory |
| `backend/migrations/0022_shop_memory.sql` | `shop_events` + `shop_state` |
| `backend/migrations/0023_embed_metadata.sql` | Embedding model columns |
| `frontend/src/components/bench/RevisionDiffBanner.tsx` | NEW: revision change banner |
| `frontend/src/components/bench/KnowledgeSummary.tsx` | NEW: drawing recall panel |
| `frontend/src/components/bench/ShopFloorPanel.tsx` | NEW: shop floor tabs |
| `frontend/src/components/bench/FreshnessBadge.tsx` | NEW: stale indicator |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/quote.py` | Integrate `resolve_drawing_identity` in `find_drawing_for_quote` |
| `backend/app/quote.py` | `analyze_drawing_vision` → upsert candidates |
| `backend/app/knowledge/confirm.py` | Enhance `confirm_fact` for drawing fields |
| `backend/app/memory/store.py` | Latency tracking, embed metadata |
| `backend/app/knowledge/cards.py` | Freshness logic, recall tool |
| `backend/app/shop/state.py` | Projection engine + query tools |
| `backend/app/tools/registry.py` | Register new tools |
| `backend/app/hermes/mcp_server.py` | Expose new tools |
| `frontend/src/components/bench/QuoteSheet.tsx` | Add KnowledgeSummary, ShopFloorPanel tabs |
| `frontend/src/components/orchestrator/engineering/FactConfirmChips.tsx` | Value-level confirm for high-value fields |

### Test Files (New)
| File | Purpose |
|------|---------|
| `backend/tests/test_drawing_identity.py` | Identity cascade + revision diff |
| `backend/tests/test_knowledge_cards.py` | Candidate → confirm → quotable |
| `backend/tests/test_drawing_recall.py` | Recall summary + gaps |
| `backend/tests/test_shop_floor_memory.py` | Events → projection → queries |
| `backend/tests/test_freshness.py` | Staleness detection |
| `backend/tests/test_ingest_pipeline.py` | Auto + nightly + on-demand |

---

## Testing Checklist (Per ROADMAP Capability Matrix)

| ID | Test | Phase 2 Coverage |
|----|------|------------------|
| H1 | Remember preference | ✅ (memory store) |
| H2 | Recall | ✅ (recall_drawing_knowledge) |
| H3 | Forget/wipe | ✅ (existing) |
| H4 | RAG on shop/mail fact | ✅ (corpus search) |
| H5 | Dual-write | ✅ (existing) |
| H6 | Mail reindex | ✅ (ingest pipeline) |
| L1 | Open drawing conversation | ✅ (existing) |
| L2 | Drawing chat | ✅ (knowledge cards) |
| L5 | Quote analyze drawing tool | ✅ (candidate flow) |

---

## Acceptance Criteria (Definition of Done)

1. **M2.1:** Revision change shows diff banner with changed fields; never silent reuse
2. **M2.2:** Vision output = candidate; high-value fields need explicit confirm; unconfirmed blocks quote proof
3. **M2.3:** Second conversation answers from card; gaps stated plainly
4. **M2.4:** ShopFloorPanel shows machines/vendors/stock/OEE with freshness
5. **M2.5:** Stale cards flagged; not used in quotable paths
6. **M2.6:** Latency budgets logged; <500ms SQL, <1s cards, <2s corpus
7. **M2.7:** Auto-ingest on mail/drawing/production; nightly cron; on-demand API
8. **M2.8:** Embedding model/dim/provider recorded; mixed dims rejected

---

## Handoff Notes for Implementation Agent

1. **Start with M2.1 + M2.8 migrations** — they're foundational and independent
2. **Use existing patterns** — `memory/store.py` for upsert/search, `knowledge/cards.py` for card logic
3. **Frontend state** — `paneStore` for bench; add KnowledgeSummary to QuoteSheet tabs
4. **Shop floor projection** — rebuild from events on demand; incremental on event insert
5. **Freshness** — compute on read; don't add background staleness jobs yet
5. **Types** — `quoteContract.ts` may need extensions for KnowledgeSummary/ShopFloorPanel data

---

## Quick Start Commands

```bash
# Backend
cd backend && python -m pytest tests/test_drawing_identity.py tests/test_knowledge_cards.py -v

# Frontend
cd frontend && npm run typecheck && npm run lint

# Migrations (run with masterdata_enabled=True)
cd backend && python -c "from app.db import run_migrations; run_migrations()"
```

---

## Clarifying Questions

### Q1: M2.4 Shop-Floor Memory — Event Source
Should `shop_events` be written by a dedicated Hermes cron (`no_agent=True`), or by explicit tools called from chat?
- **Option A:** Dedicated Hermes cron (`no_agent=True`) — automatic, matches 'overnight ingest as script-only'
- **Option B:** Explicit tools — operator logs downtime/scrap via chat

### Q2: M2.3 Drawing Recall — Summary Generation
Should the recall summary be generated by a local LLM (Ollama) summarizing the card, or a deterministic template from confirmed facts?
- **Option A:** Deterministic template — no LLM, plain language from confirmed facts only
- **Option B:** Local LLM summary — more natural language, but adds latency

### Q3: M2.7 Ingest Pipeline — Queue Mechanism
Use existing background task system in `main.py`, or add a lightweight async queue (e.g., `asyncio.Queue`)?
- **Option A:** Existing background tasks in `main.py` — simpler, no new deps
- **Option B:** Asyncio queue — more control, retry/backoff built-in

### Q4: M2.5 Freshness — Staleness Enforcement
Should stale cards be hard-blocked from quotable paths, or soft-warned (UI flag only)?
- **Option A:** Hard block — stale = not quotable, matches 'stale = flagged not used'
- **Option B:** Soft warn — UI flag only, owner can override