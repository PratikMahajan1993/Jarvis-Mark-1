# Jarvis — Roadmap (Next Steps & Priorities)

**Generated:** 2026-09-25  
**Status:** Active execution plan. Single source of truth for what to build next.  
**Reference:** `docs/SYSTEM_TRUTH.md` for locked architecture and rules.

---

## Phase 0: Foundation Verification (Current Sprint)

**Goal:** Confirm all locked decisions are implemented and tested. No new features.

| ID | Task | Owner | Acceptance | Status |
|----|------|-------|------------|--------|
| F0.1 | Verify HUD single-pane architecture | `jarvis-uiux` | One `OrchestratorShell`; three lenses; no conditional panel mounts; depth-only visibility | 🔄 |
| F0.2 | Verify Turn FSM + Workspace orthogonality | `jarvis-uiux` | FSM never stores workspace; workspace never collapses into turn state | 🔄 |
| F0.3 | Verify HITL claim-once + external effects bracket | `jarvis-workflows` | `pending_actions` flow correct; `request_hash` inserted before outbound; boot reconciliation works | 🔄 |
| F0.4 | Verify quote playbook gates (BLOCKER/WARN, stage-dependent) | `jarvis-workflows` | `quote_verify` blocks send on any BLOCKER; delivery WARN at draft/BLOCKER at send; PDF sha256 bound | 🔄 |
| F0.5 | Verify drawing vision two gates (consent + quota) | `jarvis-workflows` | Gate 1: default deny, customer terms only; Gate 2: 5/cycle, owner-only spend, claim-before-dispatch | 🔄 |
| F0.6 | Verify 100% local memory (Honcho stripped) | `jarvis-workflows` | No cloud memory calls; SQLite + LanceDB only; three planes never collapsed | 🔄 |
| F0.7 | Verify MHR floors + RM freshness blockers | `jarvis-workflows` | Missing/expired rate = BLOCKER; RM basis >30 days = BLOCKER at send; demo table attested only | 🔄 |
| F0.8 | Run full capability test matrix (A–O, skip retired) | Coordinator | All desk/cloud/offline tests pass; latency targets met | ⏳ |

**Exit Criteria (Foundation Done):**
1. Casual Hermes warm latency ≤5s
2. HITL miss rate = 0 (no external write without Authorize)
3. Office-day loop works: morning brief + one RFQ/quote path ending in Authorize-to-send

---

## Phase 1: Quote Workflow Hardening (Next 2 Weeks)

**Goal:** Make the quote workflow production-ready for real office use.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| Q1.1 | Drawing lookup: focus → named local search → save mail attach → ask | `jarvis-workflows` | Never guesses; never picks "last in DB"; ambiguous → asks | P0 |
| Q1.2 | Labour vs RM default per customer + override | `jarvis-workflows` | Default from customer record; mail/verbal overrides; neither → ask | P0 |
| Q1.3 | Supplier RM quote tracking (request → receive → note) | `jarvis-workflows` | Tracks arrival; estimate allowed only from historical transactions + market trend, labelled `is_estimate` | P1 |
| Q1.4 | Machining strategy editor (operations, outsource, machines, tooling) | `jarvis-uiux` + `jarvis-workflows` | Engineering bench: drag-drop ops, outsource picker, machine selector, special tooling notes | P1 |
| Q1.5 | MHR table: owner-attested rates replace demo seeds | `jarvis-workflows` | `attested_by` + value ≠ seed = quotable; unattested = BLOCKER | P0 |
| Q1.6 | Outsource pricing: vendor quote required, case recorded | `jarvis-workflows` | No guessed amounts; case: no machine / customer asked / capacity / not in-house | P1 |
| Q1.7 | Quote PDF generation (formal format, bold total, attachment) | `jarvis-workflows` | PDF in exports; email body short formal with bold total; attachment included | P0 |
| Q1.8 | Quote send email (Authorize → send via Gmail) | `jarvis-workflows` | HITL before send; blast-radius 5; duplicate delivery check on Authorize card | P0 |
| Q1.9 | Proof strip on Engineering bench mirrors `quote_verify` | `jarvis-uiux` | Real-time checklist; provenance glyphs ● ◉ ◐ ○; no guess numerals | P1 |

---

## Phase 2: Memory & Knowledge Deepening (Weeks 3-4)

**Goal:** Drawing recall and shop-floor memory that actually work.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| M2.1 | Drawing identity: hash → fingerprint → (customer, drawing_no, revision) | `jarvis-workflows` | Revision change = diff + warning; never silent reuse | P0 |
| M2.2 | Knowledge cards: owner-confirmed facts only quotable | `jarvis-workflows` | Vision suggestion = candidate until confirmed; high-value fields need value-level confirm | P0 |
| M2.3 | Drawing recall path: second conversation answers from card | `jarvis-workflows` | Material, qty, scope, tolerances, routing, quoted history, unconfirmed gaps stated plainly | P0 |
| M2.4 | Shop-floor memory: event log + `shop_state` projection | `jarvis-workflows` | Machine status/load, downtime causes, scrap/OEE trends, stock/remnants, vendor turnaround | P1 |
| M2.5 | Freshness stamps on all knowledge | `jarvis-workflows` | Every card/projection has `updated_at`; stale = flagged not used | P1 |
| M2.6 | Retrieval pipeline latency budget | `jarvis-workflows` | <500ms for SQL; <1s for cards; <2s for corpus | P1 |
| M2.7 | Ingest: auto on mail/attachments/production/drawings + nightly + on-demand | `jarvis-workflows` | Off hot path; search never blocks on ingest | P1 |
| M2.8 | Embedding model id + dimension recorded per vector | `jarvis-workflows` | Mixed dims = invalid; hash fallback labelled | P1 |

---

## Phase 3: G-Code & Machining Features (Weeks 5-6)

**Goal:** Safe, verifiable CNC program generation.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| G3.1 | `program_verify` deterministic checks | `jarvis-workflows` | Fails closed on all 13 failure modes; names block number | P0 |
| G3.2 | Dialect emission (FANUC 0i-TF/31i, Mitsubishi M80/M800) | `jarvis-workflows` | Whitelist M-codes; explicit G20/G21; long-hand when unverified | P0 |
| G3.3 | Cycle-time simulation with calibration | `jarvis-workflows` | Per-axis rapid/accel, canned cycles, dwells, tool changes; correction factor + sample count | P1 |
| G3.4 | Bounded optimisation (air moves, approach/retract, pass depth, tool ordering) | `jarvis-workflows` | Never raises feed/speed, removes clearance, skips finish pass, loosens tolerance, merges routed ops | P1 |
| G3.5 | Exports to `<repo>/exports/nc/` + diff for owner | `jarvis-workflows` | DRAFT header; promotion versioned append-only; proven never overwritten | P0 |
| G3.6 | HITL promote Authorize (blast-radius high) | `jarvis-workflows` | Machine-ready only after Authorize | P0 |

---

## Phase 4: Master Data & Schema (Week 7)

**Status:** Implemented. `masterdata_enabled` defaults on. Master Data UI is `/masterdata`. Markdown `mhr-demo.md` and `client-names.md` are no longer read when the flag is on.

**Goal:** Durable source for rates, machines, customers, vendors.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| D4.1 | Enable `masterdata_enabled` flag | `jarvis-builder` | Migrations 0004-0007 active; temporal as-of lookups work | P0 |
| D4.2 | Customer/machine/vendor aliases → canonical ids | `jarvis-workflows` | Unresolved alias → ask; never guess from similarity | P1 |
| D4.3 | Temporal rates: `effective_from`/`effective_to` queries | `jarvis-workflows` | As-of quote date; missing row = BLOCKER | P0 |
| D4.4 | Supersede not delete on authoritative rows | `jarvis-workflows` | New row + end-date old; audit fields survive migrations | P1 |
| D4.5 | Migration 0019+ for any new schema needs | `jarvis-builder` | Forward-only; backfills in scripts; provenance preserved | P1 |

---

## Phase 5: Office-Day Spine Polish (Week 8)

**Goal:** Smooth daily workflow from morning brief to end-of-day.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| O5.1 | Morning brief: weather + overnight mail + calendar + night-shift production | `jarvis-uiux` + `jarvis-workflows` | Witty, concise, <10s; suggested task modals from RFQ/production | P1 |
| O5.2 | RFQ mail → local attachments → engineering review → quote in Sheets → PDF email | `jarvis-workflows` | End-to-end traceable; HITL at each external step | P1 |
| O5.3 | Production-log summary + optional 4pm downtime meeting | `jarvis-workflows` | Human-readable OEE; meeting created via calendar HITL | P2 |
| O5.4 | End-of-day report | `jarvis-workflows` | Useful daily summary | P2 |
| O5.5 | Remote: Telegram/email when away | `jarvis-workflows` | Basic command relay | P3 |
| O5.6 | Overnight attach download / night-shift ingest as script-only Hermes cron | `jarvis-workflows` | `no_agent=True`; not LLM poll | P2 |
| O5.7 | Orchestrator HUD drag-and-drop drawings | `jarvis-uiux` | Walk-up/hard-copy/WhatsApp files land as inbox files | P1 |

---

## Phase 6: Voice & TTS Reliability (Ongoing)

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| V6.1 | Single speak (no double-play) | `jarvis-voice` | One audio stream; no 15s replay | P0 |
| V6.2 | Voicebox cutover ≤1.4s | `jarvis-voice` | Browser TTS → Mark voice seamless | P0 |
| V6.3 | Late clip discarded after bridge owns line | `jarvis-voice` | No late blob played | P0 |
| V6.4 | TTS prefetch on chat out | `jarvis-voice` | `/api/tts` warms cache | P1 |
| V6.5 | Preferences voice toggle | `jarvis-uiux` | Disable voice → no TTS; HUD still updates text | P1 |
| V6.6 | HITL confirm mic opens after speak ends | `jarvis-voice` | Yes/No works | P1 |
| V6.7 | Compose dictation mic fills body without false authorize | `jarvis-voice` | Works | P1 |

---

## Phase 7: Turn Ledger (Future — Gated)

**Status:** `turn_ledger_enabled` default **off** — future work, not yet load-bearing.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| T7.1 | Server turn ledger states + transitions legal | `jarvis-builder` | QUEUED→RUNNING→AWAITING_HITL→EXECUTING→DONE/FAILED; illegal transitions rejected | P3 |
| T7.2 | Leases + heartbeats + reaper | `jarvis-builder` | Stale lease → reaper marks failure with stage preserved; ≤15s HUD visibility | P3 |
| T7.3 | Idempotency keys on confirm + turn-creating POSTs | `jarvis-builder` | Duplicates return original outcome | P3 |
| T7.4 | Client fetch timeout ≠ cancellation | `jarvis-builder` | Turn runs until explicit `POST /api/turns/{id}/cancel` | P3 |
| T7.5 | HUD FSM reconciliation (RECONCILE/hydrate) | `jarvis-uiux` | On mount, focus, SSE reconnect, fetch failures; lost AWAITING_HITL reopens panel | P3 |

---

## Phase 8: Canvas & Artifacts (Deferred)

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| C8.1 | `/canvas` route remains separate (not fourth lens) | `jarvis-uiux` | Board CRUD, file upload, artifact display work | P3 |
| C8.2 | SceneBoard / Engineering stack displays tool artifacts | `jarvis-uiux` | Artifact widgets render correctly | P2 |

---

## Cross-Cutting Technical Debt

| ID | Area | Task | Priority |
|----|------|------|----------|
| X1 | SQLite config | WAL mode, busy timeout, foreign keys ON for multi-process | P1 |
| X2 | `live_service` marker | Register in `conftest.py`; `pytest -m "not live_service"` must pass | P1 |
| X3 | Rule budget enforcement | `test_rule_budget.py` enforces word caps + frontmatter | P1 |
| X4 | Observability | `/api/metrics` p50/p95; `/api/missions` prompt/tool/result; `work/LAST_TURNS.md` updated | P1 |
| X5 | Data path resolution | API uses `<repo>/data` not CWD-relative paths | P0 |
| X6 | API token gate | Mutating non-localhost requests require bearer token | P1 |

---

## Agent Dispatch Priority

| Priority | Agent | Typical Work |
|----------|-------|--------------|
| P0 | `jarvis-workflows` | Quote, HITL, mail, calendar, memory, vision gates, master data |
| P0 | `jarvis-builder` | Migrations, restarts, live verification, SQLite config |
| P1 | `jarvis-uiux` | HUD panes, lenses, bench, React Bits, morph, canvas |
| P1 | `jarvis-voice` | Voicebox, TTS, speak bridge, double-play |
| P2 | Coordinator | Capability test dispatch, observation routing |

---

## Current Blockers (2026-09-25)

| Blocker | Impact | Resolution |
|---------|--------|------------|
| Hermes gateway timeout (30s) on quote starts | Fallback triggers, delays quote | Investigate Hermes health; consider longer timeout or better warmup |
| `live_service` marker not registered | CI/offline tests may hit live services | Add marker to `conftest.py` |
| Turn ledger off by default | FSM reconciliation paths untested | Enable in test env; verify reconcile logic |
| Master data UI deferred | Rate attestation manual | Build minimal attestation UI or script |

---

## Success Metrics (From Vision Workbook §14)

| Metric | Target | Current |
|--------|--------|---------|
| Casual Hermes warm latency | ≤5s | ~5-10s (needs measurement) |
| HITL miss rate | 0 | Unknown — needs audit |
| Office-day loop (brief + RFQ→Authorize) | Works end-to-end | Partial — quote path works, brief needs polish |
| **Stretch:** Local RAG useful on real shop question | Yes | No |
| **Stretch:** One novel browser task with evidence | Yes | No |

---

## Decision Log (Roadmap Changes)

| Date | Change | Reason |
|------|--------|--------|
| 2026-09-25 | Roadmap created from consolidated SYSTEM_TRUTH | Single source of truth established; all prior docs superseded |

---

**Next Review:** After Phase 0 verification complete (target: 2026-09-28).  
**Coordination:** Use `jarvis-observation-dispatch` skill when reporting live observations during testing.  
**Capability Tests:** Run per `work/CAPABILITY_TEST_MATRIX.md` order (I3 → E1/P1 → P7-P9 → P10-P12 → P13/E2/E16/E17 → P14 → P2/P3 → P4/P5/P6 → P15/E11/B2-B3 → E8-E10/E14-E15 → A1-A3/A8-A10/A14 → K1-K3/K6 → C3-C5/C8 → D1-D2 → E3-E7/A7 → F1/F5 → G2-G6/L1-L2 → H1-H4 → N1-N2 → O* after G6).