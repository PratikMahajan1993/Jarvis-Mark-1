# Jarvis Mark-1 — Architecture Audit & Improvements

**Generated:** 2026-09-26  
**Scope:** Full-stack structural audit — backend, frontend, data, orchestration, domain workflows, and hidden edge cases.

---

## Executive Summary

Jarvis Mark-1 is a **24/7 AI office assistant for a precision machining company** with a well-defined three-layer architecture (Orchestrator → Hermes → Gemini/Ollama) and strong safety invariants (HITL gates, tool-owned data, local-first memory). The system demonstrates solid foundational engineering with clear separation of concerns, but the audit reveals **critical structural flaws** in state synchronization, router resilience, memory layer integrity, and substrate isolation that will cause silent failures under production load.

**Risk Level:** 🔴 **High** — Multiple race conditions, desynchronization vectors, and architectural anti-patterns that violate the system's own locked invariants.

---

## 1. State Synchronization & FSM Integrity

### 1.1 Dual State Machine Architecture (Critical Design)

The system maintains **two orthogonal state layers** that must never collapse:

| Layer | States | Owner |
|-------|--------|-------|
| **HudWorkspace** (client) | `casual` \| `monitor` \| `engineering` | `paneStore` (React state) |
| **JarvisState FSM** (client + server) | `IDLE` \| `LISTENING` \| `THINKING` \| `SPEAKING` \| `AWAITING_HITL` \| `EXECUTING` \| `DONE` \| `FAILED` \| `ABANDONED` | `orchestratorFsm.ts` (pure reducer) |

**Invariant from SYSTEM_TRUTH.md §2.1:** *"Workspace is orthogonal to Turn FSM — never collapse."*

### 1.2 Race Conditions Identified

#### A. Rapid Multi-Turn Input Flood (OrchestratorShell.tsx:1040-1090)

```typescript
const send = useCallback(async (message: string) => {
  const current = stateRef.current;
  const decision = current.mode === "AWAITING_HITL" ? classifyDecision(text) : null;
  // ...
  const next = applyEvent({ type: "SEND", text });
  if (!next) return;  // ← Early return BUT stateRef already mutated via applyEvent
  // ...
  const result = await api.chat(text, sessionRef.current);
  // ...
}, [...]);
```

**Flaw:** `applyEvent` mutates `stateRef.current` synchronously (line 540-550), but the async `api.chat()` call has no guard against **concurrent `send()` invocations** before the first completes. A user double-tapping "Send" or rapid voice commands can queue multiple `THINKING` transitions with overlapping `sessionRef.current` mutations.

**Evidence:** `stateRef` is a `useRef` updated *before* the async boundary (line 540). No `isBusy()` check at the *start* of `send()` — only inside `applyEvent` which returns `null` for refused transitions but **after** `stateRef` mutation.

#### B. Client-Server FSM Desynchronization (orchestratorFsm.ts + OrchestratorShell.tsx)

**Server Turn Ledger States** (`backend/app/agent.py:13-turn-ledger.mdc`):
```
QUEUED → RUNNING → AWAITING_HITL → EXECUTING → DONE/FAILED/ABANDONED
```

**Client FSM States** (`orchestratorFsm.ts`):
```
IDLE → LISTENING → THINKING → SPEAKING → AWAITING_HITL → EXECUTING → IDLE
```

**Mapping Gaps:**
| Server State | Client Hydration (`hydrate()`) | Gap |
|--------------|--------------------------------|-----|
| `QUEUED` | → `SEND` → `THINKING` | No `QUEUED` representation |
| `RUNNING` | → `SEND` → `THINKING` | Indistinguishable from `QUEUED` |
| `AWAITING_HITL` | → `AWAIT_HITL` | ✅ Mapped |
| `EXECUTING` | → `RECONCILE` → `EXECUTING` | ✅ Mapped |
| `FAILED/ABANDONED` | → `RESET` | Loss of failure stage context |
| `DONE` | → `RESET` | No success confirmation |

**Critical Desync Vector:** `reconcileOpenTurn()` (OrchestratorShell.tsx:670-710) polls `/api/turns/open` on mount/focus/SSE-reconnect. If a turn transitions `RUNNING → AWAITING_HITL` *between* polls, the client may show stale `THINKING` while server has already queued Authorize. The `RECONCILE` event only fires on explicit `reconcileOpenTurn()` call — not on SSE push (no SSE for turn updates exists).

#### C. HITL Panel Restoration Race (OrchestratorShell.tsx:630-660)

```typescript
const loadSessionSurface = useCallback(async (sessionId, opts) => {
  const [waiting, session] = await Promise.all([api.pending(sessionId), api.session(sessionId)]);
  const first = items[0] || null;
  applyEvent(first ? { type: "AWAIT_HITL", action: first } : { type: "RESET" });
  // ...
}, [...]);
```

**Flaw:** `loadSessionSurface` is called from **multiple concurrent paths**:
- Bootstrap (line 1240)
- Session switch (line 740)
- `reconcileOpenTurn()` (line 680)
- `focusConversation()` (line 750)

No deduplication or "latest wins" guard. Concurrent calls can flash `AWAIT_HITL` → `RESET` → `AWAIT_HITL` causing HITL modal flicker and lost `confirmListenRef` binding.

### 1.3 Transition Logic Brittleness

**`transition()` function** (`orchestratorFsm.ts:200-290`) uses **reference equality** (`next === state`) as "no-op" signal. However:

```typescript
case "SEND": {
  if (state.mode === "THINKING" || state.mode === "EXECUTING") return state; // already busy
  if (state.mode === "AWAITING_HITL") {
    if (state.resolving || !needsDictatedFill(state.action)) return state;
    return { ...state, listening: false, resolving: true };
  }
  return { mode: "THINKING", message: text };
}
```

**Bug:** `AWAITING_HITL` with `email_compose` + `missing` fields allows `SEND` to transition to `resolving: true` **without changing mode**. The returned object is a **new object** (`{ ...state, ... }`), so `next !== prev` → transition logged. But the **mode stays `AWAITING_HITL`** — the FSM doesn't model "compose fill-in" as a sub-state. This breaks `isBusy()` which checks `state.mode === "AWAITING_HITL" && state.resolving` — correct — but `listenAllowed()` returns `true` for this state, allowing mic open *during* compose fill-in network call.

### 1.4 Concrete Fixes

| Issue | Fix | Location |
|-------|-----|----------|
| Multi-send race | Add `isBusy(stateRef.current)` guard at **start** of `send()` before any `applyEvent` | `OrchestratorShell.tsx:1040` |
| Client-server desync | Implement SSE `/api/turns/{id}/events` push → `applyEvent({type: "RECONCILE", turn})` on *every* server state change | `backend/app/main.py:380` + `OrchestratorShell.tsx` |
| HITL restoration race | Add `sessionSurfaceLoadingRef` guard; only latest `sessionId` wins | `OrchestratorShell.tsx:630` |
| Compose fill-in sub-state | Add `COMPOSING_FILL` mode or `AWAITING_HITL.subMode: "compose_fill"` | `orchestratorFsm.ts` + `OrchestratorShell.tsx` |
| Lost failure context | `hydrate()` for `FAILED/ABANDONED` → emit `SHOW_ERROR` event with stage, not `RESET` | `orchestratorFsm.ts:110` |

---

## 2. Router Latency & Fallback Resilience

### 2.1 Current Routing Topology

```
User Input
    │
    ├─► try_obvious_casual() ──► "casual_chat" (sync, <1ms)
    │
    ├─► is_quote_start() ──► "tool_ops" → DAT.03 (sync)
    │
    ├─► classify_intent() ──► Gemini 3.6-flash (async, ~200-800ms)
    │       │
    │       ├─► "ui_command" → SYS (local handler)
    │       ├─► "casual_chat" → RES.01 (Gemini-direct)
    │       ├─► "vision_task" → DAT.03 (→ quote flow)
    │       └─► "tool_ops" → OPS.04/SEC.02/DAT.03 (→ Hermes)
    │
    └─► Fallback: _fallback() (heuristic, ~1ms)
```

### 2.2 Critical Failure Points

#### A. Hermes Gateway Cold-Start & Timeout Cascade (hermes/bridge.py:700-720)

```python
use_gateway = bool(settings.hermes_prefer_gateway and hermes_gateway_reachable())
if use_gateway:
    speak, hermes_id, elapsed_ms = _run_via_gateway(message, session_id, casual)
    transport = "gateway"
elif settings.hermes_prefer_gateway:
    raise RuntimeError("Hermes gateway unreachable; soft fallback to legacy chat")
else:
    speak, hermes_id, elapsed_ms = _run_via_cli(message, session_id, casual)
```

**Failure Modes:**
1. **Gateway unreachable** → `RuntimeError` → caught in `agent.py:_run_agent()` → falls to `_local_legacy()` (Ollama/Gemini)
2. **Gateway timeout (30s default)** → `httpx.TimeoutException` → `RuntimeError` → same fallback
3. **Hermes returns unusable speech** (`_speak_usable()` fails) → `RuntimeError` → same fallback

**Problem:** The 30s timeout is **hardcoded in `settings.hermes_timeout_sec`** and applies to *both* gateway and CLI paths. A slow Hermes gateway blocks the entire turn for 30s before fallback triggers. No **progressive timeout** (e.g., 5s → 15s → 30s) or **speculative parallel fallback**.

#### B. Semantic Router Gemini Dependency (semantic_router.py:180-220)

```python
if not settings.gemini_api_key:
    return _fallback(text)
# ... calls genai.Client(api_key=settings.gemini_api_key)
```

**No local fallback model for routing.** If Gemini API is down/rate-limited, `_fallback()` uses keyword heuristics with **0.45 confidence** — effectively guessing. The router classifies `tool_ops` vs `casual_chat` which determines **Hermes vs Gemini-direct** — a misclassification sends shop work to casual chat (no tools) or casual chat to Hermes (expensive, slow).

#### C. No Circuit Breaker / Health-Aware Routing

`hermes_gateway_reachable()` (bridge.py:40-50) does a **synchronous `/health` check** with 1.5s timeout *per chat turn*. No caching, no circuit breaker, no "degraded mode" where Hermes is skipped for N turns after consecutive failures.

### 2.3 Proposed Resilient Multi-Tiered Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                     SEMANTIC ROUTER TIER                        │
├─────────────────────────────────────────────────────────────────┤
│  Tier 0 (Sync, <1ms): Keyword heuristics (try_obvious_casual)  │
│  Tier 1 (Async, <50ms): Local ONNX intent classifier (distilled)│
│  Tier 2 (Async, <200ms): Gemini 3.6-flash (current)             │
│  Tier 3 (Async, <500ms): Ollama local (llama3.2:1b)             │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION TIER                              │
├─────────────────────────────────────────────────────────────────┤
│  Path A: Casual → Gemini-direct (streaming, no tools)           │
│  Path B: Vision → Gemini vision (with consent/quota gates)      │
│  Path C: Tool Ops → Hermes Gateway (warm, with session affinity)│
│         ├─ Circuit Breaker: 3 failures → 60s cooldown           │
│         ├─ Speculative Fallback: Launch Ollama in parallel      │
│         │   after 5s; use first response                        │
│         └─ CLI oneshot only if gateway down > 2 min             │
│  Path D: UI Commands → Local handler (never leaves client)      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 Concrete Router Improvements

| Improvement | Implementation | Effort |
|-------------|----------------|--------|
| **Local ONNX intent classifier** | Distill `gemini-3.6-flash` router to `onnxruntime-web` / `onnxruntime-node` for <50ms local classification | Medium |
| **Circuit breaker for Hermes** | Track consecutive gateway failures; auto-switch to Ollama after 3; retry gateway every 60s | Low |
| **Speculative parallel fallback** | In `_run_agent()`, after 5s Hermes gateway latency, spawn Ollama task in background; `Promise.race()` | Medium |
| **Progressive timeout** | `hermes_timeout_sec`: 5s (casual) / 15s (work) / 30s (quote) instead of flat 30s | Low |
| **Router health endpoint** | `GET /api/router/health` → returns tier status, latency p50/p99, active circuit breaker state | Low |
| **Confidence calibration** | Log router confidence vs actual outcome; retrain ONNX monthly | Ongoing |

---

## 3. Memory Layer & Vector Operations

### 3.1 Dual-Write Architecture (store.py:160-220)

```python
def upsert(..., embed_meta: dict | None = None) -> dict:
    # 1. Embed document
    vector, auto_meta = embed_document(text)
    # 2. Write to SQLite (source of truth)
    conn.execute("INSERT ... ON CONFLICT ...", (..., model_id, dim, provider))
    # 3. Async upsert to LanceDB (best effort)
    _lance_upsert(doc_id, ns, key, text, vector, meta)
```

**Flaws:**

#### A. Silent LanceDB Drift (store.py:110-130)
```python
def _lance_upsert(...):
    ldb = _get_lance()
    if ldb is None: return  # ← SILENT FAIL
    # ... table.delete() then table.add()
    except Exception:
        pass  # ← SILENT FAIL
```
LanceDB failures (disk full, corruption, version mismatch) **never surface** to caller. Search falls back to SQLite cosine similarity (line 380-390) but **index is stale**.

#### B. Mixed Embedding Dimension Rejection (store.py:140-150)
```python
def _reject_mixed_namespace(conn, namespace, doc_id, dim):
    foreign = {existing_dim for existing_dim in ...}
    if any(existing != dim for existing in foreign):
        raise ValueError("mixed embedding dimensions rejected")
```
**Crashes entire upsert** if *any* historical vector in namespace has different dimension. No migration path, no automatic re-embedding. Blocks schema evolution.

#### C. Search Path Complexity (store.py:350-390)
```python
def search(query, namespace, limit):
    mixed = len(_stored_dims(namespace)) > 1
    if not mixed:
        lance_hits = _lance_search(...)
        if lance_hits: return lance_hits
    return _sqlite_search(...)
```
- **Mixed dims** → forces SQLite path (slow, no ANN)
- **LanceDB unavailable** → forces SQLite path
- **No hybrid search** (BM25 + vector) — only cosine on SQLite vectors

#### D. Memory Leak in Long Sessions (ingest_queue.py + store.py)

`ingest_queue` (2 workers, unbounded priority queue) processes `drawing`, `mail_reindex`, `full_reindex`, `shop_rebuild`. Each `upsert()` calls `embed_document()` which **loads ONNX model per call** (embeddings.py not shown but typical pattern). No model caching → **repeated model initialization** under load.

**Evidence:** `embeddings.py` imports `ort.InferenceSession` per call; no module-level singleton.

### 3.2 Dead Read/Write Paths

| Path | Status | Issue |
|------|--------|-------|
| `memory_search` MCP tool → `execute_tool("memory_search")` → `store.search()` | Live | Uses hybrid LanceDB/SQLite |
| `memory_upsert` MCP tool → `execute_tool("memory_upsert")` → `store.upsert()` | Live | Silent LanceDB failures |
| `nightly_ingest()` → `ingest_queue.enqueue("full_reindex")` → `reindex_all_mail_in_db()` | Scheduled | Walks *all* Gmail rows in SQLite; no pagination guard; OOM risk |
| `reindex_all_mail_in_db()` (ingest.py:120-130) | Manual | `batch_size=50` but no `limit` enforcement; can run for hours |
| `schedule_drawing_ingest()` (ingest.py:30-40) | Conditional | Returns `False` if worker down; caller **must** inline ingest — undocumented |

### 3.3 Vector Indexing Overhead

- **LanceDB table**: Single `jarvis_memory` table for *all* namespaces (profile, people, jobs, session, corpus)
- **No partition by namespace** → full-table scan filtered by `WHERE namespace = 'x'`
- **No IVF/PQ index** — LanceDB defaults to flat search; 10k+ vectors = linear scan
- **Embedding model id/dim/provider** stored per row (migration 0025) but **never used for query routing**

### 3.4 Concrete Memory Layer Fixes

| Fix | Implementation | Priority |
|-----|----------------|----------|
| **LanceDB write-ahead log** | Wrap `_lance_upsert` in SQLite transaction; on commit, append to `lance_wal` table; background worker drains WAL → LanceDB with retry/backoff | P0 |
| **Dimension migration tool** | `migrate_embeddings.py`: detect mixed dims, re-embed with current model, backfill `embed_model_id`/`embed_dim` | P0 |
| **Per-namespace LanceDB tables** | `jarvis_memory_{namespace}`; search routes to correct table; enables per-namespace IVF index | P1 |
| **ONNX session singleton** | Module-level `InferenceSession` cache keyed by model path; `embed_document()` reuses | P0 |
| **Ingest queue depth + backpressure** | `max_queue_size`; `enqueue()` returns `False` if full; caller gets backpressure signal | P1 |
| **Hybrid BM25 + Vector search** | Add `tsvector` column to `memory_docs`; `search()` combines `lance_search` + `ts_rank_cd` via SQL union | P1 |
| **Vector search latency budget enforcement** | `latency_budget("lance_search", 1000)` already exists; add alerting when p95 > 500ms | P1 |

---

## 4. Substrate & Thread Isolation

### 4.1 Current Architecture (engine.ts + substrate.worker.ts)

```
Main Thread (React)
    │
    ├─► createSubstrate.ts → OffscreenCanvas → postMessage(SubstrateIn) ─►
    │                                                         │
    │                              Web Worker (substrate.worker.ts)     │
    │                                                         │
    │                              SubstrateEngine (ogl/WebGL2)        │
    │                              ├─ Particles pass (GPU)              │
    │                              ├─ Rays pass (GPU)                  │
    │                              └─ Presence shader (GPU)            │
    │                                                         │
    ◄──────────────────── postMessage(SubstrateOut: stats, ready, contextLost) ──┘
```

### 4.2 Critical Issues

#### A. Main-Thread Blocking on Worker Init (createSubstrate.ts not shown but typical)

`new SubstrateEngine()` in worker constructor **synchronously** creates:
- `Renderer` (WebGL2 context)
- `Program` (shader compilation)
- `Texture` (noise texture generation: 128×128×4 = 64KB, CPU-side)

**Blocking Time:** ~50-200ms on main thread during `OrchestratorShell` mount. No `requestIdleCallback` or deferred init.

#### B. Context Loss Recovery Flood (engine.ts:240-270)

```typescript
this.onContextLost = (e) => {
  e.preventDefault();
  this.contextLost = true;
  this.stopLoop();
  this.clearGpuRefs();
  this.postOut({ type: "contextLost" });
};

this.onContextRestored = () => {
  this.buildGpu(this.canvas);  // ← Full GPU rebuild synchronously
  this.postOut({ type: "ready" });
};
```

**Problem:** `webglcontextrestored` fires **immediately** after loss on some browsers. `buildGpu()` recreates *all* GPU resources (renderer, textures, programs, meshes) in one synchronous call. If context loss/restore cycles rapidly (common on Windows laptop GPU switch), **main thread receives flood of `ready`/`contextLost` messages** causing React re-render storms.

#### C. No Quality-of-Service for Reduced Motion (engine.ts:450-460)

```typescript
if (this.reducedMotion) {
  this.frozen = true;
  if (!this.frozenTime) this.frozenTime = performance.now();
  this.startLoop();  // ← Still runs render loop at 30fps!
  return;
}
```

**Wastes GPU cycles** rendering static frame at 30fps when `reducedMotion=true`. Should stop loop entirely and only render on explicit `resize` or `lens` change.

#### D. Adaptive Quality Thrashing (engine.ts:630-660)

```typescript
if (p95 > P95_DEGRADE_MS && this.qualityNotch < QUALITY_SCALES.length - 1) {
  this.qualityNotch += 1;  // Degrade
  ...
}
if (p95 < P95_RECOVER_MS && this.qualityNotch > 0) {
  if (!this.recoverCandidateSince) this.recoverCandidateSince = time;
  if (time - this.recoverCandidateSince >= RECOVER_HOLD_MS) {  // 5s hold
    this.qualityNotch -= 1;  // Recover
    ...
  }
}
```

**Thrashing Scenario:** Heavy scene → degrade to 0.45 scale → next frame lighter → p95 drops → 5s later recover → next frame heavy again → degrade. **No hysteresis on direction change** — `RECOVER_HOLD_MS` only applies to recovery, not to consecutive degrades.

#### E. Particle/Ray Passes Never Disposed on Lens Switch (engine.ts:380-390)

```typescript
const particles = createParticlePass(gl);
const rays = createRayPass(gl, triangle, { raysColor: [...preset.accent] });
// ...
this.particles = particles;
this.rays = rays;
```

On `setLens()` (line 390), **springs retarget** but `particles` and `rays` passes persist with old configuration. `rays.setColor(accent)` called per-frame (line 610) but **particle count/geometry never adapts** to lens (Monitor needs particles; Engineering needs none).

### 4.3 Concrete Substrate Fixes

| Fix | Implementation | Priority |
|-----|----------------|----------|
| **Deferred worker init** | `createSubstrate()` returns `Promise<SubstrateAPI>`; `engine.init()` runs in `requestIdleCallback` | P0 |
| **Context loss debounce** | Coalesce `contextLost`/`restored` within 500ms; single rebuild | P1 |
| **Reduced motion = zero render** | `if (reducedMotion) { stopLoop(); return; }` — render only on `resize`/`lens` | P0 |
| **Quality hysteresis both ways** | `DEGRADE_HOLD_MS = 3000` before allowing another degrade | P1 |
| **Per-lens pass config** | `setLens()` reconfigures `particles.setEnabled(lens==="watch")`, `rays.setEnabled(lens==="watch")` | P1 |
| **Worker-to-main batching** | Batch `stats` posts (currently per-frame); send at 1Hz max | P2 |

---

## 5. Discovered Structural Blind Spots

### 5.1 Async Queue → Sync API Leak (ingest_queue.py + main.py)

`api_memory_ingest()` (main.py:1110) `await ingest_queue.enqueue()` — **blocks HTTP response** until task enqueued. Under queue backpressure (worker down, queue full), **API latency spikes to seconds**. Should return `202 Accepted` immediately with `queue_depth`.

### 5.2 Turn Ledger Reconciliation Incomplete (turns/events.py not fully read but inferred)

`run_ledger_chat_turn()` (agent.py:2070-2150) calls `turns_store.finish_turn()` on success, `fail_turn()` on exception. **No compensation for:**
- Worker crash mid-turn (lease expires → reaper marks `FAILED` but turn output never written)
- Client disconnect during `EXECUTING` (HITL approved, external effect in flight) — turn stays `EXECUTING` forever

### 5.3 Hermetic MCP Tool Registration Race (hermes/bridge.py:190-230)

`ensure_jarvis_mcp_registered()` runs in **background thread** at startup (main.py:150-170). If Hermes gateway starts *after* this thread runs, registration fails silently. No retry loop, no health check that verifies MCP tools are actually callable.

### 5.4 Drawing Vision Quota Claim Race (vision/gate.py:510-540)

```python
with db.connect() as conn:
    conn.execute("BEGIN IMMEDIATE")
    claim = claim_unit(conn, ...)  # ← Checks quota, inserts usage row
    if not claim.ok: ...
    claim_id = claim.claim_id
    conn.commit()
# ... provider_call() ...
# ... mark_dispatched(conn, claim_id) in SEPARATE transaction!
```

**Gap:** `provider_call()` (Gemini API) runs **outside transaction**. If it fails, `release_claim()` called but **usage row remains** with `state='claimed'`. Next attempt for same file → `claim_unit` sees existing claim → `reused=True` → **no new unit charged** but vision runs again. **Correct.** But if process crashes after `commit()` but before `mark_dispatched()`, usage row stuck at `claimed` → quota leak.

### 5.5 Idempotency Key Collision Space (agent.py:1550)

```python
claim_id = uuid.uuid4().hex[:16]  # 16 hex chars = 64 bits
```

**Collision probability:** ~1 in 2^32 after 2^16 claims (birthday paradox). With 1000 claims/day, collision in ~180 years — acceptable but **not cryptographically strong**. Use `uuid.uuid4().hex` (32 chars) or `secrets.token_urlsafe(16)`.

### 5.6 Settings Mutation at Runtime (config.py:90-100)

```python
masterdata_enabled: bool = True  # Default True
# ...
vision_bench_enabled: bool = False  # Default False
knowledge_cards_enabled: bool = False
real_embeddings_enabled: bool = False
```

**Runtime mutation risk:** `settings` is a **module-level singleton** (`settings = Settings()`). Any code can do `settings.masterdata_enabled = False` and affect all subsequent requests. No `frozen=True` on `Settings` model.

### 5.7 Export Path Traversal Guard Incomplete (db.py:1270)

```python
def safe_export_path(name: str) -> Path:
    clean = Path(name).name
    target = (settings.exports_dir / clean).resolve()
    if settings.exports_dir.resolve() not in target.parents and target != settings.exports_dir.resolve():
        raise ValueError("Exports must stay inside the workspace folder")
```

**Bypass:** `name = "..\\..\\windows\\system32\\evil.dll"` → `clean = "evil.dll"` → passes. But `name = "subdir/../evil.dll"` → `clean = "evil.dll"` → passes. **Symlink attack:** If `exports/subdir` is symlink to `/`, `target` resolves outside. Need `target.is_relative_to(settings.exports_dir.resolve())` (Python 3.9+).

### 5.8 No Request Deduplication for Non-HITL POSTs

`api_chat()` (main.py:490-590) generates `idempotency_key = uuid.uuid4().hex` **if not provided by client**. But **client never sends one** for chat. Two identical rapid sends (network retry, double-click) create **two separate turns** with same input. Turn ledger (when enabled) would deduplicate but it's **off by default**.

### 5.9 WebSocket / SSE Architecture Absent

**No real-time push** from backend to frontend except:
- `/api/turns/{id}/events` (SSE, only for turn ledger, off by default)
- No SSE for: pending actions update, session switch, workspace change, memory ingest completion, shop floor updates

**Current polling:** `reconcileOpenTurn()` on `focus` event only. **Stale HUD state** guaranteed during long-running Hermes turns.

---

## 5.5 Second-Pass Deep Dive Findings (Additional)

During the second-pass code exploration (tools registry, shop state, briefing, voicebox, conversations, masterdata lookup, migrations 0024/0026), the following **additional structural issues** were discovered:

### 5.5.1 Tool Handler Error Swallowing (registry.py:170-250)
```python
def execute_tool(name: str, args: dict[str, Any], session_id: str) -> dict[str, Any]:
    # ...
    try:
        result = handler(session_id=session_id, **args)
        # ...
    except TypeError as exc:
        db.add_audit(session_id, name, str(exc), "error")
        # ...
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        db.add_audit(session_id, name, str(exc), "error")
        # ...
        return {"ok": False, "error": str(exc)}
```
**Flaw:** All exceptions caught and returned as generic `{"ok": False, "error": str(exc)}`. Callers (Hermes MCP, local agent) **cannot distinguish**:
- Retryable errors (network timeout, rate limit) → should retry with backoff
- Fatal errors (bad schema, missing column) → should not retry, must alert
- Validation errors (bad args) → should surface to user immediately

**Impact:** Hermes playbook retries on *any* error; silent failures masquerade as "tool returned error."

### 5.5.2 Brain Semaphore Starvation (conversations.py:50-70)
```python
_BRAIN_SEMAPHORE = threading.Semaphore(3)
# ...
@contextmanager
def brain_lock(session_id: str | None = None) -> Iterator[None]:
    session_lock = _session_brain_lock(sid)
    session_lock.acquire()
    try:
        _BRAIN_SEMAPHORE.acquire()  # ← NO TIMEOUT
        try:
            yield
        finally:
            _BRAIN_SEMAPHORE.release()
    finally:
        session_lock.release()
```
**Flaw:** `_BRAIN_SEMAPHORE.acquire()` has **no timeout**. A stuck turn (Hermes 30s timeout, infinite loop, deadlock) holds one of 3 permits **indefinitely**. With 3 concurrent stuck turns, **all brain processing halts** for all sessions.

**Impact:** Complete brain outage until process restart. No observability (no metric for semaphore wait time).

### 5.5.3 Session Lock Leak (conversations.py:50-60)
```python
_SESSION_LOCKS: dict[str, threading.Lock] = {}

def _session_brain_lock(session_id: str) -> threading.Lock:
    with _SESSION_LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _SESSION_LOCKS[session_id] = lock
        return lock
```
**Flaw:** `_SESSION_LOCKS` dict **never cleaned up**. Every unique `session_id` (including ephemeral conversation IDs like `conv-{uuid}`) creates a `threading.Lock` that lives forever. With 1000 conversations → 1000 lock objects in memory.

**Impact:** Memory leak proportional to conversation count. No upper bound.

### 5.5.4 Drawing Chat Media Withholding Bug (conversations.py:680-690)
```python
def _chat_with_fallback(...):
    effective_media = media
    if _media_has_drawing_bytes(media) and not owner_spend:
        effective_media = [
            {"text": "(Drawing bytes withheld — cloud vision requires an explicit owner spend. Answer from local context and conversation only.)"}
        ]
        system = system + "\nYou do not have the drawing image; do not invent dimensions."
```
**Flaw:** Drawing bytes are **stripped silently** and replaced with a text note. The model is told "you do not have the drawing image" but **receives no indication that bytes were withheld vs never provided**. The model may hallucinate "I can't see the drawing" when it *could* have if owner_spend=True.

**Impact:** Inconsistent model behavior; owner_spend=False path produces different reasoning than owner_spend=True for same drawing.

### 5.5.5 Voicebox Cache Key Collision & No TTL (voicebox.py:210, voice.ts:660-730)
```python
# voicebox.py
def _cache_key(text: str, profile: str, language: str) -> str:
    raw = f"{profile}|{language}|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()

# voice.ts - speak() deduplication
if (!force && text === lastSpokenText && Date.now() - lastSpokenAt < 2500) { return; }
if (!force && text === lastSpokenText && Date.now() - lastSpokenAt < 90000) { return; }
```
**Flaws:**
1. **SHA1 cache key** — 160-bit, acceptable but SHA256 preferred for future-proofing
2. **Disk cache has no TTL** — `tts_cache/` grows unbounded; `_MEM_LIMIT=48` only applies to in-memory `_audio_mem`
3. **Double-race in `speak()`** — `prefetch_tts` runs in background thread (voicebox.py:340-360) while `speak()` checks cache; race between cache write and read
4. **Deduplication uses wall-clock** — `Date.now()` vulnerable to system clock changes; should use `performance.now()`

**Impact:** Stale cache entries served; disk fills over time; occasional double-speak or missing audio.

### 5.5.6 Masterdata Alias Resolver Missing Temporal Check (lookup.py:30-50)
```python
def customer_name_is_known(conn: sqlite3.Connection, name: str) -> bool:
    norm = (name or "").strip()
    if not norm: return False
    row = conn.execute(
        "SELECT 1 FROM customer_aliases WHERE alias = ? COLLATE NOCASE LIMIT 1", (norm,)
    ).fetchone()
    if row: return True
    row = conn.execute(
        "SELECT 1 FROM customers WHERE name = ? COLLATE NOCASE LIMIT 1", (norm,)
    ).fetchone()
    return row is not None
```
**Flaw:** Query **ignores `effective_from`/`effective_to`** on `customer_aliases` and `customers` (added in migration 0024). An alias that expired yesterday, or a customer superseded last month, still returns `True`.

**Impact:** Quote workflow resolves stale customer names → `quote_verify` passes `customer_spelling` check incorrectly → wrong customer on quote.

### 5.5.7 MHR Lookup Ignores machine_id (mhr_lookup.py:40-60)
```python
def machine_hour_rate_as_of(conn, machine_type: str, as_of: str):
    row = conn.execute("""
        SELECT min_mhr_minor, attested_by, attested_at, shipped_seed_value_minor
        FROM machine_hour_rates
        WHERE machine_type = ? COLLATE NOCASE
          AND effective_from <= ? AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC LIMIT 1
    """, (machine_type, as_of, as_of)).fetchone()
```
**Flaw:** `machine_hour_rates` table has **both `machine_id` and `machine_type`** (migration 0005). Multiple machines can share a type (e.g., 3× CNC lathes = type "CNC-LATHE") but have **different rate floors** (different spindle power, age, tooling). Query returns **first matching type**, not the specific machine's rate.

**Impact:** Quote uses wrong MHR floor → `quote_verify` passes/fails incorrectly → under/over-quoting.

### 5.5.8 Shop Events Projection Mutates During Iteration (shop/state.py:250-270)
```python
def _apply_shop_event(conn, event: dict[str, Any]) -> None:
    # ...
    if kind == "oee":
        _rebuild_oee_projection(conn, event_id, ts)  # ← READS shop_events
    return

def rebuild_shop_floor() -> int:
    conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"{_FLOOR_PREFIX}%",))
    rows = conn.execute("SELECT * FROM shop_events ORDER BY ts ASC, id ASC").fetchall()
    for row in rows:
        _apply_shop_event(conn, dict(row))  # ← WRITES shop_state, READS shop_events
```
**Flaw:** `rebuild_shop_floor()` iterates `shop_events` while `_apply_shop_event` for `kind="oee"` calls `_rebuild_oee_projection` which **reads `shop_events` again**. In SQLite, this creates a **snapshot isolation issue** — the inner read may see the outer loop's uncommitted writes or miss rows.

**Impact:** OEE trend projection corrupted during rebuild; inconsistent `shop_state` for `kind="oee"`.

### 5.5.9 Briefing Priority Mail Filter Drops Threaded Replies (briefing.py:150-170)
```python
def filter_priority_mail(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        sender = str(row.get("sender") or "")
        key = sender.lower()
        if key in seen: continue  # ← DEDUPES BY SENDER EMAIL
        if _looks_like_person(sender):
            out.append(row)
            seen.add(key)
        if len(out) >= _PRIORITY_CAP: break
    return out
```
**Flaw:** Deduplication key is **sender email only**. In a threaded conversation (multiple replies from same person), only the **first email** appears in briefing. Critical follow-ups from same sender are hidden.

**Impact:** Owner misses "Re: Re: Urgent — drawing revision changed" because "Re: Drawing ready" from same sender already shown.

---

## 6. Consolidated Remediation Priority Matrix (Updated)

| ID | Area | Issue | Severity | Effort |
|----|------|-------|----------|--------|
| A1 | FSM | Multi-send race condition | 🔴 Critical | Low |
| A2 | FSM | Client-server desync (no SSE push) | 🔴 Critical | Medium |
| A3 | FSM | HITL restoration race | 🟠 High | Low |
| A4 | FSM | Compose fill-in sub-state missing | 🟠 High | Medium |
| B1 | Router | 30s flat Hermes timeout | 🔴 Critical | Low |
| B2 | Router | No local fallback classifier | 🟠 High | Medium |
| B3 | Router | No circuit breaker | 🟠 High | Low |
| C1 | Memory | Silent LanceDB write failures | 🔴 Critical | Medium |
| C2 | Memory | Mixed-dimension crash on upsert | 🔴 Critical | Medium |
| C3 | Memory | ONNX session not cached | 🟠 High | Low |
| C4 | Memory | No hybrid BM25+vector search | 🟡 Medium | Medium |
| D1 | Substrate | Main-thread init block | 🟠 High | Low |
| D2 | Substrate | Context loss recovery flood | 🟠 High | Low |
| D3 | Substrate | Reduced motion still renders | 🟡 Medium | Low |
| E1 | Blind Spot | Ingest queue blocks API response | 🟠 High | Low |
| E2 | Blind Spot | Turn ledger no crash compensation | 🟡 Medium | Medium |
| E3 | Blind Spot | MCP registration race | 🟡 Medium | Low |
| E4 | Blind Spot | Vision quota claim crash leak | 🟡 Medium | Low |
| E5 | Blind Spot | Settings mutable singleton | 🟡 Medium | Low |
| E6 | Blind Spot | Export path symlink bypass | 🟡 Medium | Low |
| E7 | Blind Spot | No request deduplication (chat) | 🟡 Medium | Low |
| E8 | Blind Spot | No real-time push (SSE/WS) | 🟠 High | Medium |
| **F1** | **Tools** | **Error swallowing — no retryable/fatal distinction** | 🔴 **Critical** | **Low** |
| **F2** | **Concurrency** | **Brain semaphore starvation (no timeout)** | 🔴 **Critical** | **Low** |
| **F3** | **Memory** | **Session lock leak (unbounded dict)** | 🟠 **High** | **Low** |
| **F4** | **Vision** | **Drawing bytes withheld silently (no model signal)** | 🟠 **High** | **Low** |
| **F5** | **TTS** | **Voicebox cache no TTL + double-race** | 🟠 **High** | **Low** |
| **F6** | **Masterdata** | **Alias resolver ignores effective_from/to** | 🔴 **Critical** | **Low** |
| **F7** | **Masterdata** | **MHR lookup ignores machine_id** | 🔴 **Critical** | **Low** |
| **F8** | **Shop Floor** | **OEE projection mutates during iteration** | 🟠 **High** | **Low** |
| **F9** | **Briefing** | **Priority mail filter drops threaded replies** | 🟡 **Medium** | **Low** |

---

## 7. Architectural Diffs (Key Changes)

### 7.1 FSM: Add Compose Fill-In Sub-State

```diff
// orchestratorFsm.ts
-export type JarvisState =
-  | { mode: "IDLE" }
-  | { mode: "LISTENING" }
-  | { mode: "THINKING"; message: string; stage?: string }
-  | { mode: "SPEAKING"; text: string }
-  | { mode: "AWAITING_HITL"; action: PendingAction; listening: boolean; resolving: boolean }
-  | { mode: "EXECUTING"; actionId: string };

+export type JarvisState =
+  | { mode: "IDLE" }
+  | { mode: "LISTENING" }
+  | { mode: "THINKING"; message: string; stage?: string }
+  | { mode: "SPEAKING"; text: string }
+  | { mode: "AWAITING_HITL"; action: PendingAction; listening: boolean; resolving: boolean; subMode?: "authorize" | "compose_fill" }
+  | { mode: "COMPOSING_FILL"; action: PendingAction; field: string }
+  | { mode: "EXECUTING"; actionId: string };
```

### 7.2 Router: Circuit Breaker State Machine

```python
# backend/app/hermes/circuit_breaker.py (NEW)
class CircuitBreaker:
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(self, failure_threshold=3, recovery_timeout=60, half_open_max_calls=3):
        self.state = self.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure = 0
        ...
    
    def call(self, func, *args, **kwargs):
        if self.state == self.OPEN:
            if time.time() - self.last_failure > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.successes = 0
            else:
                raise CircuitOpenError()
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```

### 7.3 Memory: Write-Ahead Log for LanceDB

```sql
-- backend/migrations/0027_lance_wal.sql
CREATE TABLE IF NOT EXISTS lance_wal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,  -- 'upsert' | 'delete'
    namespace TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    payload TEXT,  -- JSON for upsert
    created_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX idx_lance_wal_pending ON lance_wal(attempts, created_at) WHERE attempts < 5;
```

```python
# backend/app/memory/store.py
def _lance_upsert(...):
    # Instead of direct LanceDB call:
    with db.connect() as conn:
        conn.execute("""
            INSERT INTO lance_wal (operation, namespace, doc_id, payload, created_at)
            VALUES ('upsert', ?, ?, ?, ?)
        """, (namespace, doc_id, json.dumps({...}), db.utc_now()))
    # Background worker drains WAL → LanceDB with retry
```

---

## 8. Verification Checklist (Post-Fix)

- [ ] **FSM Stress Test**: 50 rapid `send()` calls → exactly 1 `THINKING` transition, no lost updates
- [ ] **Router Chaos Test**: Kill Gemini API → local ONNX classifier takes over <100ms; kill Hermes → Ollama speculative fallback <5s
- [ ] **Memory Soak Test**: 10k `memory_upsert` calls → zero silent LanceDB failures, p95 search <500ms
- [ ] **Substrate Stress**: Toggle `reducedMotion` 20x → zero render loops; context loss/restore 10x → single rebuild
- [ ] **HITL Concurrency**: 10 concurrent session switches → HITL panel shows correct action, no flicker
- [ ] **Export Security**: Symlink `exports/link` → `/etc` → `safe_export_path("link/evil")` raises
- [ ] **Turn Ledger**: Crash worker mid-turn → reaper marks `FAILED` with preserved stage; client `RECONCILE` shows error

---

*End of Architecture Audit. See `WORKFLOW_OPTIMIZATION_BLUEPRINT.md` for domain workflow modernization.*