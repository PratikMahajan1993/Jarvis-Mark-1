# Jarvis Mark-1 — Workflow Optimization Blueprint

**Generated:** 2026-09-26  
**Scope:** End-to-end domain workflow modernization — RFQ→Quote pipeline, HITL ergonomics, Engineering Desk integration, and discovered workflow gaps.

---

## Executive Summary

The current quote workflow (`backend/app/quote.py` + `hermes/playbooks/quote/`) is **functionally complete but operationally fragile**. It relies on sequential, synchronous tool calls with implicit state in session memory, no progressive validation, and HITL gates that create approval fatigue. This blueprint redesigns the workflow into a **progressive, resilient pipeline** with explicit state machines, parallelizable stages, and ergonomic safety boundaries.

---

## 1. End-to-End RFQ-to-Quote Pipeline Redesign

### 1.1 Current Pipeline (Sequential, Implicit State)

```
User: "Quote this drawing"
    │
    ▼
find_drawing_for_quote() → session memory: last_quote_drawing, last_quote_drawing_path
    │
    ▼
analyze_drawing_vision() → session memory: last_quote_vision_summary, last_part_revision_id
    │
    ▼
resolve_quote_scope() → session memory: last_quote_scope (labour/with_material)
    │
    ▼
request_rm_quote() → HITL Authorize → supplier email sent → session memory: last_quote_rm_*
    │
    ▼
record_rm_quote() → session memory: last_quote_rm_price, last_quote_rm_basis_date
    │
    ▼
add_quote_operation() × N → session memory: operations list
    │
    ▼
quote_build() → spreadsheet artifact → session memory: last_quote, last_quote_rows
    │
    ▼
quote_pdf() → PDF artifact → session memory: last_quote_pdf, last_quote_pdf_sha256
    │
    ▼
quote_verify(stage="draft") → checklist (WARNs only)
    │
    ▼
quote_verify(stage="send") → checklist (BLOCKERs stop)
    │
    ▼
queue_quote_send() → HITL Authorize → Gmail send
```

**Problems:**
- **Implicit session memory** as state carrier — no versioning, no rollback, fragile across sessions
- **No parallelization** — vision, RM quote, operations can run concurrently
- **Validation only at end** — `quote_verify` catches errors late; owner discovers missing MHR after building operations
- **HITL at wrong granularity** — Authorize per email send, not per logical milestone
- **No progress visibility** — HUD shows only current tool output, not pipeline stage

### 1.2 Progressive Pipeline Architecture (New)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QUOTE PIPELINE STATE MACHINE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DRAFT ──► DRAWING_RESOLVED ──► VISION_COMPLETE ──► SCOPE_LOCKED           │
│    │            │                  │                    │                  │
│    │            │                  │                    ▼                  │
│    │            │                  │            RM_QUOTE_PENDING           │
│    │            │                  │                    │                  │
│    │            │                  │                    ▼                  │
│    │            │                  │            OPERATIONS_DEFINED         │
│    │            │                  │                    │                  │
│    │            │                  │                    ▼                  │
│    │            │                  │            BUILD_COMPLETE             │
│    │            │                  │                    │                  │
│    │            │                  │                    ▼                  │
│    │            │                  │            PDF_GENERATED              │
│    │            │                  │                    │                  │
│    │            │                  │                    ▼                  │
│    │            │                  │            VERIFY_DRAFT_PASS          │
│    │            │                  │                    │                  │
│    └────────────┴──────────────────┴────────────────────► READY_TO_SEND    │
│                                                                             │
│  Each state: explicit data contract, validation gates, rollback targets    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Pipeline Stage Contracts

| Stage | Input Contract | Output Contract | Validation Gate | Parallelizable |
|-------|----------------|-----------------|-----------------|----------------|
| `DRAWING_RESOLVED` | `part_hint?`, `drawing_path?` | `drawing: {path, sha256, identity}` | Identity cascade success; exactly 1 candidate | — |
| `VISION_COMPLETE` | `drawing.sha256`, `customer_id?` | `vision: {summary, candidates[], analysis_state}` | `analysis_state == "vision_done"`; consent+quota passed | ✅ (with drawing resolved) |
| `SCOPE_LOCKED` | `customer?`, `scope?` | `scope: "labour"\|"with_material", source` | Customer default or explicit; remembered | ✅ (with vision) |
| `RM_QUOTE_PENDING` | `material`, `supplier`, `supplier_email` | `rm_request: {id, status="requested"}` | HITL Authorize queued | ✅ (with scope locked) |
| `OPERATIONS_DEFINED` | `operations[]` | `ops: {id, machine_type, cycle_min, rate_source}[]` | Each op has machine + rate ≥ MHR floor | ✅ (with RM quote pending) |
| `BUILD_COMPLETE` | `part_name`, `vision`, `scope`, `rm`, `ops` | `quote_revision: {artifact_id, rows, totals}` | `quote_verify(stage="draft").stop == false` | — |
| `PDF_GENERATED` | `quote_revision` | `pdf: {artifact_id, sha256, path}` | PDF bound to revision; sha256 stored | — |
| `VERIFY_DRAFT_PASS` | `quote_revision`, `pdf.sha256` | `verify_result: {passed, warnings[]}` | Zero BLOCKERs; warnings surfaced | — |
| `READY_TO_SEND` | `to`, `subject`, `body`, `pdf` | `send_pending: {action_id, blast_radius}` | HITL Authorize; duplicate delivery check | — |

### 1.4 Pipeline Persistence Schema (New Tables)

```sql
-- backend/migrations/0028_quote_pipeline.sql
CREATE TABLE quote_pipelines (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN (
        'draft', 'drawing_resolved', 'vision_complete', 'scope_locked',
        'rm_quote_pending', 'operations_defined', 'build_complete',
        'pdf_generated', 'verify_draft_pass', 'ready_to_send', 'sent', 'abandoned'
    )),
    data_json TEXT NOT NULL,  -- Stage-specific payload
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(session_id, id)
);

CREATE TABLE quote_pipeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id TEXT NOT NULL REFERENCES quote_pipelines(id),
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    trigger TEXT NOT NULL,  -- 'tool', 'hitl', 'timeout', 'retry'
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_quote_pipeline_session ON quote_pipelines(session_id, stage);
```

### 1.5 Pipeline API (Replaces Ad-Hoc Endpoints)

```python
# backend/app/quote_pipeline.py (NEW)

class QuotePipeline:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.pipeline_id = self._get_or_create()
    
    def advance(self, target_stage: str, payload: dict) -> PipelineResult:
        """Atomic stage transition with validation."""
        current = self._load()
        if not self._can_transition(current.stage, target_stage):
            return PipelineResult(ok=False, error=f"Invalid transition {current.stage} → {target_stage}")
        
        validation = self._validate_stage(target_stage, payload)
        if not validation.passed:
            return PipelineResult(ok=False, errors=validation.errors)
        
        self._persist_stage(target_stage, payload)
        self._emit_event(current.stage, target_stage, "tool", payload)
        return PipelineResult(ok=True, stage=target_stage, data=payload)
    
    def _can_transition(self, from_stage: str, to_stage: str) -> bool:
        # Define DAG of valid transitions
        TRANSITIONS = {
            "draft": ["drawing_resolved", "abandoned"],
            "drawing_resolved": ["vision_complete", "scope_locked", "draft"],
            "vision_complete": ["scope_locked", "drawing_resolved"],
            "scope_locked": ["rm_quote_pending", "operations_defined", "vision_complete"],
            "rm_quote_pending": ["operations_defined", "scope_locked"],
            "operations_defined": ["build_complete", "rm_quote_pending"],
            "build_complete": ["pdf_generated", "operations_defined"],
            "pdf_generated": ["verify_draft_pass", "build_complete"],
            "verify_draft_pass": ["ready_to_send", "pdf_generated"],
            "ready_to_send": ["sent", "verify_draft_pass"],
            "sent": [],
            "abandoned": [],
        }
        return to_stage in TRANSITIONS.get(from_stage, [])
```

### 1.6 HUD Pipeline Visualization

```
Engineering Bench (BenchQuotePanel) — Progressive Disclosure:

┌─────────────────────────────────────────────────────────────────┐
│  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  DRAWING  ▸ VISION  ▸ SCOPE  ▸ RM QUOTE  ▸ OPERATIONS  ▸ BUILD  │
│  ✅        ✅        ✅       ⏳ PENDING     ⏸ WAITING    ⏸      │
└─────────────────────────────────────────────────────────────────┘

Each segment: click to expand/collapse, shows validation status, 
"Retry" button on failure, "Skip" only for optional stages (RM quote if labour-only).
```

---

## 2. Human-in-the-Loop (HITL) & Blast-Radius Ergonomics

### 2.1 Current HITL Surface (Over-Granular)

| Action Kind | Blast Radius | Current Trigger | Issue |
|-------------|--------------|-----------------|-------|
| `email_send` | 5 | Per email | Fatigue: 5 emails = 5 Authorizes |
| `email_compose` | 3 | Missing to/subject/body | Compose fill-in uses same HITL panel |
| `quote_send` | 5 | Per quote send | Duplicate delivery check only at Authorize |
| `calendar_create` | 4 | Per event | No batch "add all meetings" |
| `sheets_write` | 4 | Per cell update | OEE log = 1 Authorize per cell |
| `cnc_promote` | 5 | Per program | High blast radius, correct |
| `vision_quota_override` | 5 | Per document over cap | Correct but opaque |
| `memory_wipe` | 5 | Per namespace | Correct |
| `browser_action` | 5 | Per action | Not wired yet |

### 2.2 Blast-Radius Tiers (Proposed)

| Tier | Actions | Approval Pattern | UX |
|------|---------|------------------|----|
| **Tier 1: Micro** | Compose fill-in, single OEE cell, single calendar event | **Inline confirm** (toast + undo, no modal) | `CommandBaton` inline "Send?" / "Save?" |
| **Tier 2: Standard** | Email send, RM quote request, calendar batch, sheets batch | **Modal Authorize** with summary | Current `HitlModal` |
| **Tier 3: High** | Quote send, CNC promote, vision quota override, memory wipe | **Modal Authorize + Evidence Card** | `HitlModal` + `SpotlightCard` with provenance |
| **Tier 4: Critical** | Broad memory wipe, machine network transmit (never) | **Dual Authorize** (owner + witness) | Not implemented |

### 2.3 Consolidated Authorization Flow

```mermaid
sequenceDiagram
    participant User
    participant HUD
    participant API
    participant Hermes
    participant Gmail

    User->>HUD: "Send quote to customer@co.in"
    HUD->>API: POST /api/quote/pipeline/advance (stage=ready_to_send)
    API->>API: quote_verify(stage="send") → BLOCKERs?
    alt BLOCKERs exist
        API-->>HUD: 400 {errors: [...], stage: "verify_draft_pass"}
        HUD-->>User: Inline proof strip with red checks
    else Clean
        API->>API: Create pending_actions row (kind=quote_send, blast=3)
        API-->>HUD: 200 {pending_action_id, stage: "ready_to_send"}
        HUD->>User: Toast "Quote ready. Authorize to send?"
        User->>HUD: Click "Authorize"
        HUD->>API: POST /api/confirm (action_id, approved=true)
        API->>API: Claim → external_effects intent → Gmail send
        API-->>HUD: 200 {status: "sent", message_id}
        HUD-->>User: Toast "Sent ✓" + undo toast (5s)
```

### 2.4 HITL Ergonomic Improvements

| Improvement | Implementation | Impact |
|-------------|----------------|--------|
| **Inline Tier 1 confirms** | `CommandBaton` shows "Send to X?" with `Y`/`N` keys; no modal | -70% modal opens for compose fill-in |
| **Batch Authorize** | `pending_actions` supports `batch_id`; single Authorize for N same-kind actions | -80% Authorize clicks for OEE logging |
| **Evidence Card on Tier 3** | `HitlModal` renders `SpotlightCard` with provenance glyphs (● ◉ ◐ ○) | Zero "blind authorize" |
| **Duplicate Delivery Inline** | `quote_send` payload includes `duplicate_warning`; shown on Authorize card | Prevents accidental re-send |
| **Authorize Timeout Config** | `settings.hitl_timeout_min` (default 30min); expired → `needs_human` | No stale pending actions |
| **Undo Toast** | Post-execute toast with "Undo" → calls `POST /api/pending/{id}/undo` (compensating action) | Recovers from misclicks |

### 2.5 HITL State Machine (Per Action)

```
PENDING → [User opens HITL] → AWAITING_HITL
    │                              │
    │                              ├─► [Authorize] → CLAIMED → EXECUTING → EXECUTED
    │                              │                              │
    │                              │                              └─► [Provider error] → FAILED
    │                              │
    │                              └─► [Reject] → REJECTED
    │
    └─► [Timeout 30min] → EXPIRED → NEEDS_HUMAN (boot reconciliation)
```

---

## 3. Next-Gen Engineering Desk Integration

### 3.1 Current Engineering Desk (Fragmented)

- **Drawing Viewer** (`DrawingStage` + `DrawingViewer`): PDF.js, no annotation
- **Quote Sheet** (`QuoteSheet`): Static table, no inline editing
- **Operations Panel** (missing): `quote_ops` API exists but no UI
- **MHR Rates** (hidden): Only via `api_mhr_rates` endpoint
- **Proof Strip** (missing): `quote_verify` runs only on demand

### 3.2 Progressive Disclosure Desk Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ENGINEERING DESK (workspace="engineering", lens="bench")                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐  ┌────────────────────────────────────────────┐  │
│  │   DRAWING STAGE      │  │           QUOTE STACK                       │  │
│  │   (~55% width)       │  │           (~40% width)                      │  │
│  │                      │  │                                            │  │
│  │  [PDF.js Viewer]     │  │  ┌──────────────────────────────────────┐  │  │
│  │  - Pan/zoom          │  │  │ PIPELINE PROGRESS                     │  │  │
│  │  - Layer toggle      │  │  │ ████████░░░░ DRAWING ▸ VISION ▸ SCOPE  │  │  │
│  │  - Measurement tool  │  │  └──────────────────────────────────────┘  │  │
│  │  - Annotation layer  │  │                                            │  │
│  │                      │  │  ┌──────────────────────────────────────┐  │  │
│  │  [Thumbnail strip]   │  │  │ SCOPE & MATERIAL                      │  │  │
│  │  (multi-sheet PDF)   │  │  │ Labour / With Material [toggle]       │  │  │
│  │                      │  │  │ Material: [EN8______] ▼  Grade picker  │  │  │
│  │                      │  │  │ RM Source: [Supplier Quote ▼]  Basis:  │  │  │
│  │                      │  │  │ [2026-09-20]  [Refresh]                │  │  │
│  │                      │  │  └──────────────────────────────────────┘  │  │
│  └──────────────────────┘  │                                            │  │
│                            │  ┌──────────────────────────────────────┐  │  │
│                            │  │ OPERATIONS (drag-drop reorder)        │  │  │
│                            │  │ ┌──────────────────────────────────┐  │  │  │
│                            │  │ │ 1. Turning ▼  [CNC-1]  12.5 min   │  │  │  │
│                            │  │ │    Rate: ₹450/hr ● (floor ₹400)    │  │  │  │
│                            │  │ │    Setup: ₹500  Tooling: ₹200      │  │  │  │
│                            │  │ │    [Edit] [Delete] [↑] [↓]         │  │  │  │
│                            │  │ ├──────────────────────────────────┤  │  │  │
│                            │  │ │ 2. Milling  ▼  [VMC-3]  8.0 min   │  │  │  │
│                            │  │ │    Rate: ₹600/hr ◉ (attested)      │  │  │  │
│                            │  │ │    Outsource: ☐  Vendor: [____]   │  │  │  │
│                            │  │ │    [Edit] [Delete] [↑] [↓]         │  │  │  │
│                            │  │ └──────────────────────────────────┘  │  │  │
│                            │  │ [+ Add Operation] [Import Template]    │  │  │
│                            │  └──────────────────────────────────────┘  │  │
│                            │                                            │  │
│                            │  ┌──────────────────────────────────────┐  │  │
│                            │  │ PROOF STRIP (live quote_verify)       │  │  │
│                            │  │ ✅ Unit prices > 0                    │  │  │
│                            │  │ ✅ Qty × Rate matches                 │  │  │
│                            │  │ ✅ MHR floors met                     │  │  │
│                            │  │ ⚠ RM basis 28 days old                │  │  │
│                            │  │ ❌ Delivery time missing (BLOCKER)    │  │  │
│                            │  │ [Authorize to Send]  [Save Draft]     │  │  │
│                            │  └──────────────────────────────────────┘  │  │
│                            └────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Desk Component Architecture (New)

```
frontend/src/components/bench/
├── EngineeringDesk.tsx           # Root: orchestrates DrawingStage + QuoteStack
├── DrawingStage/
│   ├── DrawingViewer.tsx         # PDF.js + annotation layer (fabric.js)
│   ├── MeasurementTool.tsx       # Snap-to-geometry, dimension export
│   ├── AnnotationLayer.tsx       # Redlines, notes, linked to quote ops
│   └── ThumbnailStrip.tsx        # Multi-sheet navigation
├── QuoteStack/
│   ├── PipelineProgress.tsx      # Visual stage indicator (clickable)
│   ├── ScopeMaterialPanel.tsx    # Scope toggle, material picker, RM basis
│   ├── OperationsPanel.tsx       # Drag-drop list, inline edit, MHR inline check
│   ├── OperationEditor.tsx       # Modal: machine picker, cycle time, outsource
│   ├── ProofStrip.tsx            # Live quote_verify, provenance glyphs
│   └── SendAuthorizeCard.tsx     # Tier 3 HITL with evidence
├── hooks/
│   ├── useQuotePipeline.ts       # Pipeline state + advance() mutations
│   ├── useDrawingIdentity.ts     # Identity cascade, revision diff
│   └── useMHRFloors.ts           # Real-time MHR lookup + attestation status
└── types.ts                      # PipelineStage, Operation, ProofCheck, etc.
```

### 3.4 Desk ↔ FSM Integration (No Sprawling Routes)

**Principle:** Desk actions emit **pipeline events**, not arbitrary API calls. The `useQuotePipeline` hook owns all mutations.

```typescript
// frontend/src/lib/bench/useQuotePipeline.ts
interface PipelineAction {
  type: 'RESOLVE_DRAWING' | 'COMPLETE_VISION' | 'LOCK_SCOPE' | 
        'REQUEST_RM_QUOTE' | 'RECORD_RM_QUOTE' | 'ADD_OPERATION' |
        'UPDATE_OPERATION' | 'DELETE_OPERATION' | 'REORDER_OPERATIONS' |
        'BUILD_QUOTE' | 'GENERATE_PDF' | 'VERIFY_DRAFT' | 'AUTHORIZE_SEND';
  payload: any;
}

export function useQuotePipeline(sessionId: string) {
  const [pipeline, setPipeline] = useState<PipelineState>(initial);
  
  const dispatch = useCallback(async (action: PipelineAction) => {
    // 1. Optimistic UI update
    setPipeline(prev => applyOptimistic(prev, action));
    
    // 2. API call (single endpoint)
    const result = await api.quotePipelineAdvance(sessionId, action.type, action.payload);
    
    // 3. Reconcile
    if (result.ok) {
      setPipeline(prev => applyServerResult(prev, result));
      // 4. FSM notification (if HITL needed)
      if (result.hitl_required) {
        applyEvent({ type: 'AWAIT_HITL', action: result.pending_action });
      }
    } else {
      setPipeline(prev => rollbackOptimistic(prev, action));
      toast.error(result.error);
    }
  }, [sessionId]);
  
  return { pipeline, dispatch };
}
```

**API Endpoint (Single):**
```python
# backend/app/main.py
@app.post("/api/quote/pipeline/advance")
def api_quote_pipeline_advance(payload: PipelineAdvanceRequest) -> dict:
    pipeline = QuotePipeline(payload.session_id)
    result = pipeline.advance(payload.stage, payload.data)
    if result.hitl_required:
        return {"ok": True, "hitl_required": True, "pending_action": result.pending_action}
    return {"ok": result.ok, "stage": result.stage, "data": result.data, "errors": result.errors}
```

### 3.5 Desk State Persistence

- **Local-first**: All desk edits → `localStorage` (indexed by `pipeline_id`) → sync to pipeline table on `advance()`
- **Offline-capable**: Service worker caches drawing PDFs, quote revisions
- **Conflict resolution**: Last-write-wins per field; operational transform for operations list

---

## 4. Discovered Workflow Gaps

### 4.1 RFQ Intake → Quote Handoff Gap

**Current:** `rfq.py` creates RFQ record with `extract`, `similar_job_ids`, `deadline_iso`. But **no automatic transition** to quote pipeline. Owner must manually say "Quote this RFQ."

**Fix:** RFQ `status='extracted'` → auto-create `quote_pipeline` in `drawing_resolved` stage with `drawing` from RFQ attachments.

```python
# backend/app/rfq.py (add to intake())
if drawing_attachments:
    pipeline = QuotePipeline(session_id)
    pipeline.advance("drawing_resolved", {
        "drawing": {"path": att.path, "sha256": att.sha256},
        "rfq_id": rfq_id,
        "customer": customer_from_mail,
    })
```

### 4.2 Supplier RM Quote Tracking Gap

**Current:** `request_rm_quote()` creates `rm_quote_requests` row + HITL email. `record_rm_quote()` updates it. **No linkage** to quote pipeline — owner must manually copy price.

**Fix:** `rm_quote_requests.quote_pipeline_id` FK. When `record_rm_quote()` succeeds, auto-advance pipeline to `operations_defined` with `rm_price` populated.

### 4.3 Operation Template Gap

**Current:** `quote_add_operation()` requires all fields manually. **No templates** for common sequences (e.g., "Turn → Mill → Heat Treat → Grind").

**Fix:** `operation_templates` table (name, steps[]). Desk shows "Import Template" → pre-fills operations array.

### 4.4 Cycle Time Estimation Gap

**Current:** `cycle_min` entered manually. **No simulation** — owner guesses or uses tribal knowledge.

**Fix:** Integrate `cycletime` estimates (migration 0013) + `routing_operations` actuals. `OperationEditor` shows:
- "Estimated: 12.5 min (cycletime, n=15, ±15%)"
- "Measured: 14.2 min (last 3 runs on CNC-1)"
- Owner picks or overrides.

### 4.5 Drawing Revision Management Gap

**Current:** `resolve_drawing_identity()` returns `revision_change` with `changed_fields`. But **no workflow** to handle revision change mid-quote.

**Fix:** Pipeline stage `VISION_COMPLETE` stores `identity_kind`. If `revision_change`:
- Auto-create `pipeline_event` with `trigger='revision_change'`
- Desk shows "Revision changed from Rev A → Rev B. Fields changed: OD, Tolerance. [Update Quote] [Keep Original]"
- `Update Quote` → re-runs vision, preserves operations, flags affected ops.

### 4.6 MHR Attestation Workflow Gap

**Current:** `mhr_attest_rate()` sets `attested_by`, `attested_at`. **No review workflow** — owner must know which rates need attestation.

**Fix:** `MHRAttestationQueue` — periodic job finds rates where `attested_by='' AND shipped_seed_value_minor != min_mhr_minor`. Creates suggested task "Attest MHR for CNC-1 (floor ₹450, seed ₹400)". Desk shows attestation status inline on machine picker.

### 4.7 Quote Variance Tracking Gap

**Current:** `quote_variance.rank_margin_erosion()` exists (migration 0012) but **no closed loop** — variance not fed back to MHR floors or cycle estimates.

**Fix:** After job completion, `log_actual_cycle_time()` compares `actual` vs `quoted`. If variance > 20%:
- Auto-create `quote_playbook_note` with "CNC-1 turning 12.5min quoted → 15.8min actual (+26%)"
- Suggest MHR floor adjustment or cycle time calibration.

### 4.8 Error Recovery Weaknesses

| Scenario | Current Behavior | Gap | Fix |
|----------|------------------|-----|-----|
| Vision fails (3 retries) | `analysis_state='needs_vision'`; owner must click "Analyse" | No auto-retry with backoff; no fallback to local extract | Exponential backoff retry (1m, 5m, 30m); local extract always runs first |
| Hermes timeout mid-quote | Turn fails; owner restarts from chat | No pipeline checkpoint | Pipeline persists at each stage; `recover_pipeline()` resumes from last stage |
| MHR floor missing mid-quote | `quote_verify` BLOCKER at send | Discovered late | `OperationsPanel` shows MHR status inline (green/yellow/red) per machine |
| Duplicate quote send | `duplicate_delivery_warning` only at Authorize | Not prevented earlier | `READY_TO_SEND` stage checks duplicate; blocks advance if identical PDF sent <30 days |
| Drawing revision change after PDF | PDF sha256 drift → `quote_verify` BLOCKER at send | Caught late | `VISION_COMPLETE` stage detects revision change; forces re-verify before `BUILD_COMPLETE` |

---

## 5. Tool-Calling Handoff Lapses

### 5.1 Hermes MCP → Local Tool Boundary

**Current:** Hermes calls `jarvis_quote_*` MCP tools → `execute_tool()` → local Python functions. **No streaming/progress** — Hermes waits for full result.

**Problem:** Long operations (vision 30s, PDF generation 5s) block Hermes conversation. No intermediate "Working..." updates.

**Fix:** MCP tools return `{"status": "started", "poll_url": "/api/quote/pipeline/status/{id}"}`. Hermes polls or uses SSE. Local tool runs async via `ingest_queue` or background task.

### 5.2 Semantic Router → Hermes Handoff

**Current:** `semantic_router.classify_intent()` → `tool_ops` → `agent.py` → `run_hermes_turn()`. **No context passing** — Hermes re-classifies intent.

**Fix:** Router passes `classification.intent` + `confidence` + `target_agent` as `X-Jarvis-Route` header. Hermes uses as prior.

### 5.3 Vision → Knowledge Card Handoff

**Current:** `dispatch_drawing_vision()` → `record_vision_candidates()` → `entity_facts` with `state='candidate'`. **No automatic card refresh** — `read_card()` must be called separately.

**Fix:** `record_vision_candidates()` emits event → `knowledge/cards.py` auto-refreshes card counts → HUD `knowledge_card_api_payload` reflects new candidates instantly.

---

## 6. Implementation Roadmap (Phased)

### Phase 1: Pipeline Foundation (Week 1-2)
| Task | Owner | Deliverable |
|------|-------|-------------|
| Create `quote_pipelines` schema + migration | `jarvis-builder` | Migration 0028 applied |
| Implement `QuotePipeline` class + `advance()` | `jarvis-workflows` | `backend/app/quote_pipeline.py` |
| Single `/api/quote/pipeline/advance` endpoint | `jarvis-workflows` | Replaces 8 quote endpoints |
| Pipeline events table + audit trail | `jarvis-workflows` | Full traceability |

### Phase 2: Desk Integration (Week 3-4)
| Task | Owner | Deliverable |
|------|-------|-------------|
| `EngineeringDesk` root component | `jarvis-uiux` | `frontend/src/components/bench/EngineeringDesk.tsx` |
| `PipelineProgress` visual component | `jarvis-uiux` | Clickable stage indicator |
| `OperationsPanel` with drag-drop | `jarvis-uiux` | Inline MHR floor checks |
| `ProofStrip` live component | `jarvis-uiux` | Provenance glyphs, real-time verify |

### Phase 3: HITL Ergonomics (Week 5)
| Task | Owner | Deliverable |
|------|-------|-------------|
| Tier 1 inline confirms (CommandBaton) | `jarvis-uiux` | Zero-modal compose fill-in |
| Batch Authorize for same-kind actions | `jarvis-workflows` | `pending_actions.batch_id` |
| Evidence Card on Tier 3 HITL | `jarvis-uiux` | `HitlModal` + `SpotlightCard` |
| Authorize timeout + boot reconciliation | `jarvis-builder` | `hitl_timeout_min` setting |

### Phase 4: Gap Closure (Week 6-7)
| Task | Owner | Deliverable |
|------|-------|-------------|
| RFQ → Pipeline auto-handoff | `jarvis-workflows` | `rfq.py` creates pipeline |
| RM Quote → Pipeline linkage | `jarvis-workflows` | `rm_quote_requests.quote_pipeline_id` |
| Operation Templates CRUD | `jarvis-workflows` + `jarvis-uiux` | Template library in desk |
| Revision Change Workflow | `jarvis-workflows` | Desk handles `revision_change` |
| MHR Attestation Queue | `jarvis-workflows` | Suggested task generation |
| Variance Feedback Loop | `jarvis-workflows` | Post-job cycle comparison |

### Phase 5: Observability & Polish (Week 8)
| Task | Owner | Deliverable |
|------|-------|-------------|
| Pipeline metrics (`/api/metrics/quote`) | `jarvis-builder` | Stage latency, failure rates, HITL turnaround |
| Desk keyboard shortcuts | `jarvis-uiux` | Power-user efficiency |
| Offline desk (SW cache) | `jarvis-uiux` | Works without network |
| Migration guide for existing quotes | `jarvis-workflows` | Backfill script |

---

## 7. Success Metrics (Post-Implementation)

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Quote creation time (drawing → Authorize) | ~25 min | <8 min | Pipeline stage timestamps |
| HITL Authorize clicks per quote | 3-5 | 1 (Tier 3 only) | `pending_actions` count |
| Quote revision cycles (rework) | 2.3 | <1.2 | `quote_pipeline_events` with `trigger='retry'` |
| Vision quota overrides/month | Unknown | <2 | `vision_quota_usage` with `state='override'` |
| MHR attestation coverage | ~40% | 100% | `machine_hour_rates.attested_by != ''` |
| Pipeline recovery success | 0% (manual) | 95% | `quote_pipelines` resumed from checkpoint |
| Desk task completion rate | Unknown | >90% | `suggested_tasks` status=completed |

---

## 8. Backward Compatibility Strategy

- **Legacy endpoints** (`/api/quote/*`) remain but delegate to `QuotePipeline.advance()`
- **Session memory keys** (`last_quote_*`) still written for Hermes playbook compatibility
- **Hermes playbook** (`shop-quote`) updated to use pipeline stages via MCP tool `jarvis_quote_pipeline_advance`
- **Feature flag** `quote_pipeline_enabled` (default on) for gradual rollout

---

## 9. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipeline state corruption | Medium | High | SQLite transactions + event sourcing; `quote_pipeline_events` is source of truth |
| Desk performance (large drawings) | High | Medium | PDF.js worker; progressive rendering; tile-based zoom |
| HITL fatigue regression | Low | High | Tier 1 inline confirms measurable; telemetry on modal opens |
| Migration data loss | Low | Critical | Backfill script validates each legacy quote → pipeline; dry-run mode |
| Hermes playbook breakage | Medium | Medium | Playbook uses new MCP tool; old tools deprecated with shim |

---

*End of Workflow Optimization Blueprint. This document should be treated as a living specification — update via `jarvis-observation-dispatch` as implementation progresses.*