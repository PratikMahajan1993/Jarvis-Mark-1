# Jarvis â€” Roadmap (Next Steps & Priorities)

**Generated:** 2026-09-25  
**Updated:** 2026-09-30  
**Status:** Active execution plan. Single source of truth for what to build next.  
**Reference:** `docs/SYSTEM_TRUTH.md` for locked architecture and rules.

---

## Phase 0: Foundation Verification (Current Sprint)

**Goal:** Confirm all locked decisions are implemented and tested. No new features.

| ID | Task | Owner | Acceptance | Status |
|----|------|-------|------------|--------|
| F0.1 | Verify scroll-desk HUD | Coordinator | `JarvisRoot` + `Desk`; Monitor â†’ Casual â†’ Engineering; one WebGL context; workspace from the active section | Shell is in the tree; full pass is F0.8 |
| F0.2 | Verify Turn FSM + Workspace orthogonality | Coordinator | FSM never stores workspace; workspace never collapses into turn state | ðŸ”„ |
| F0.3 | Verify HITL claim-once + external effects bracket | Coordinator | `pending_actions` flow correct; `request_hash` inserted before outbound; boot reconciliation works | ðŸ”„ |
| F0.4 | Verify quote playbook gates (BLOCKER/WARN, stage-dependent) | Coordinator | `quote_verify` blocks send on any BLOCKER; delivery WARN at draft/BLOCKER at send; PDF sha256 bound | ðŸ”„ |
| F0.5 | Verify drawing vision two gates (consent + quota) | Coordinator | Gate 1: default deny, customer terms only; Gate 2: 5/cycle, owner-only spend, claim-before-dispatch | ðŸ”„ |
| F0.6 | Verify 100% local memory (Honcho stripped) | Coordinator | No cloud memory calls; SQLite + LanceDB only; three planes never collapsed | ðŸ”„ |
| F0.7 | Verify MHR floors + RM freshness blockers | Coordinator | Missing/expired rate = BLOCKER; RM basis >30 days = BLOCKER at send; demo table attested only | ðŸ”„ |
| F0.8 | Run full capability test matrix (Aâ€“O and S, skip retired) | Coordinator | All desk/cloud/offline tests pass; latency targets met | â³ |

**Exit Criteria (Foundation Done):**
1. Casual Hermes warm latency â‰¤5s
2. HITL miss rate = 0 (no external write without Authorize)
3. Office-day loop works: morning brief + one RFQ/quote path ending in Authorize-to-send

---

## Phase 1: Quote Workflow Hardening (Next 2 Weeks)

**Goal:** Make the quote workflow production-ready for real office use.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| Q1.1 | Drawing lookup: focus â†’ named local search â†’ save mail attach â†’ ask | Coordinator | Never guesses; never picks "last in DB"; ambiguous â†’ asks | P0 |
| Q1.2 | Labour vs RM default per customer + override | Coordinator | Default from customer record; mail/verbal overrides; neither â†’ ask | P0 |
| Q1.3 | Supplier RM quote tracking (request â†’ receive â†’ note) | Coordinator | Tracks arrival; estimate allowed only from historical transactions + market trend, labelled `is_estimate` | P1 |
| Q1.4 | Machining strategy editor (operations, outsource, machines, tooling) | Coordinator + Coordinator | Engineering bench: drag-drop ops, outsource picker, machine selector, special tooling notes | P1 |
| Q1.5 | MHR table: owner-attested rates replace demo seeds | Coordinator | `attested_by` + value â‰  seed = quotable; unattested = BLOCKER | P0 |
| Q1.6 | Outsource pricing: vendor quote required, case recorded | Coordinator | No guessed amounts; case: no machine / customer asked / capacity / not in-house | P1 |
| Q1.7 | Quote PDF generation (formal format, bold total, attachment) | Coordinator | PDF in exports; email body short formal with bold total; attachment included | P0 |
| Q1.8 | Quote send email (Authorize â†’ send via Gmail) | Coordinator | HITL before send; blast-radius 5; duplicate delivery check on Authorize card | P0 |
| Q1.9 | Proof strip on Engineering bench mirrors `quote_verify` | Coordinator | Real-time checklist; provenance glyphs â— â—‰ â— â—‹; no guess numerals | P1 |

---

## Phase 2: Memory & Knowledge Deepening (Weeks 3-4)

**Goal:** Drawing recall and shop-floor memory that actually work.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| M2.1 | Drawing identity: hash â†’ fingerprint â†’ (customer, drawing_no, revision) | Coordinator | Revision change = diff + warning; never silent reuse | P0 |
| M2.2 | Knowledge cards: owner-confirmed facts only quotable | Coordinator | Vision suggestion = candidate until confirmed; high-value fields need value-level confirm | P0 |
| M2.3 | Drawing recall path: second conversation answers from card | Coordinator | Material, qty, scope, tolerances, routing, quoted history, unconfirmed gaps stated plainly | P0 |
| M2.4 | Shop-floor memory: event log + `shop_state` projection | Coordinator | Machine status/load, downtime causes, scrap/OEE trends, stock/remnants, vendor turnaround | P1 |
| M2.5 | Freshness stamps on all knowledge | Coordinator | Every card/projection has `updated_at`; stale = flagged not used | P1 |
| M2.6 | Retrieval pipeline latency budget | Coordinator | <500ms for SQL; <1s for cards; <2s for corpus | P1 |
| M2.7 | Ingest: auto on mail/attachments/production/drawings + nightly + on-demand | Coordinator | Off hot path; search never blocks on ingest | P1 |
| M2.8 | Embedding model id + dimension recorded per vector | Coordinator | Mixed dims = invalid; hash fallback labelled | P1 |

---

## Phase 3: G-Code & Machining Features (Weeks 5-6)

**Goal:** Safe, verifiable CNC program generation.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| G3.1 | `program_verify` deterministic checks | Coordinator | Fails closed on all 13 failure modes; names block number | P0 |
| G3.2 | Dialect emission (FANUC 0i-TF/31i, Mitsubishi M80/M800) | Coordinator | Whitelist M-codes; explicit G20/G21; long-hand when unverified | P0 |
| G3.3 | Cycle-time simulation with calibration | Coordinator | Per-axis rapid/accel, canned cycles, dwells, tool changes; correction factor + sample count | P1 |
| G3.4 | Bounded optimisation (air moves, approach/retract, pass depth, tool ordering) | Coordinator | Never raises feed/speed, removes clearance, skips finish pass, loosens tolerance, merges routed ops | P1 |
| G3.5 | Exports to `<repo>/exports/nc/` + diff for owner | Coordinator | DRAFT header; promotion versioned append-only; proven never overwritten | P0 |
| G3.6 | HITL promote Authorize (blast-radius high) | Coordinator | Machine-ready only after Authorize | P0 |

---

## Phase 4: Master Data & Schema (Week 7)

**Status:** Implemented. `masterdata_enabled` defaults on. Master Data UI is `/masterdata`. Markdown `mhr-demo.md` and `client-names.md` are no longer read when the flag is on.

**Goal:** Durable source for rates, machines, customers, vendors.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| D4.1 | Enable `masterdata_enabled` flag | Coordinator | Migrations 0004-0007 active; temporal as-of lookups work | P0 |
| D4.2 | Customer/machine/vendor aliases â†’ canonical ids | Coordinator | Unresolved alias â†’ ask; never guess from similarity | P1 |
| D4.3 | Temporal rates: `effective_from`/`effective_to` queries | Coordinator | As-of quote date; missing row = BLOCKER | P0 |
| D4.4 | Supersede not delete on authoritative rows | Coordinator | New row + end-date old; audit fields survive migrations | P1 |
| D4.5 | Migration 0019+ for any new schema needs | Coordinator | Forward-only; backfills in scripts; provenance preserved | P1 |

---

## Phase 5: Office-Day Spine Polish (Week 8)

**Goal:** Smooth daily workflow from morning brief to end-of-day.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| O5.1 | Morning brief: weather + overnight mail + calendar + night-shift production | Coordinator + Coordinator | Witty, concise, <10s; suggested task modals from RFQ/production | P1 |
| O5.2 | RFQ mail â†’ local attachments â†’ engineering review â†’ quote in Sheets â†’ PDF email | Coordinator | End-to-end traceable; HITL at each external step | P1 |
| O5.3 | Production-log summary + optional 4pm downtime meeting | Coordinator | Human-readable OEE; meeting created via calendar HITL | P2 |
| O5.4 | End-of-day report | Coordinator | Useful daily summary | P2 |
| O5.5 | Remote: Telegram/email when away | Coordinator | Basic command relay | P3 |
| O5.6 | Overnight attach download / night-shift ingest as script-only Hermes cron | Coordinator | `no_agent=True`; not LLM poll | P2 |
| O5.7 | Desk drag-and-drop drawings | Coordinator | Walk-up/hard-copy/WhatsApp files land as inbox files on the Engineering deck | P1 |

---

## Phase 6: Voice & TTS Reliability (Ongoing)

Desk speech is Gemini TTS, voice Charon (`gemini_tts.py`). Lite, then 3.8 Flash, then 2.5 Flash only when both are out of calls. If every speech model is exhausted, the reply stays on screen and Jarvis stays silent. No browser `speechSynthesis`. No Voicebox.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| V6.1 | Single speak (no double-play) | Coordinator | One WAV from `/api/tts`; no second clip | P0 |
| V6.2 | Charon on the lite model | Coordinator | Spoken line matches the HUD text | P0 |
| V6.3 | Quota exhaustion stays silent | Coordinator | Text remains; no other voice | P0 |
| V6.4 | TTS prefetch on chat out | Coordinator | `/api/tts` warms cache | P1 |
| V6.5 | Preferences voice toggle | Coordinator | Disable voice â†’ no TTS; HUD still updates text | P1 |
| V6.6 | HITL confirm mic opens after speak ends | Coordinator | Yes/No works | P1 |
| V6.7 | Compose dictation mic fills body without false authorize | Coordinator | Works | P1 |

---

## Phase 7: Turn Ledger (Future â€” Gated)

**Status:** `turn_ledger_enabled` default **off** â€” future work, not yet load-bearing.

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| T7.1 | Server turn ledger states + transitions legal | Coordinator | QUEUEDâ†’RUNNINGâ†’AWAITING_HITLâ†’EXECUTINGâ†’DONE/FAILED; illegal transitions rejected | P3 |
| T7.2 | Leases + heartbeats + reaper | Coordinator | Stale lease â†’ reaper marks failure with stage preserved; â‰¤15s HUD visibility | P3 |
| T7.3 | Idempotency keys on confirm + turn-creating POSTs | Coordinator | Duplicates return original outcome | P3 |
| T7.4 | Client fetch timeout â‰  cancellation | Coordinator | Turn runs until explicit `POST /api/turns/{id}/cancel` | P3 |
| T7.5 | HUD FSM reconciliation (RECONCILE/hydrate) | Coordinator | On mount, focus, SSE reconnect, fetch failures; lost AWAITING_HITL reopens panel | P3 |

---

## Phase 8: Canvas & Artifacts (Deferred)

| ID | Task | Owner | Acceptance | Priority |
|----|------|-------|------------|----------|
| C8.1 | `/canvas` route remains separate (not a fourth desk section) | Coordinator | Board CRUD, file upload, artifact display work | P3 |
| C8.2 | SceneBoard / Engineering stack displays tool artifacts | Coordinator | Artifact widgets render correctly | P2 |

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

## Future feature ideas

Voice-native shift handover, drawing-revision diff lens, supplier negotiation coach, and similar uncommitted ideas are catalogued in `work/FEATURE_SUGGESTIONS.md` when that file is active. None of them are scheduled; if one graduates, add it to the numbered phases above with an owner, an acceptance check, and a priority.

## Current Blockers

| Blocker | Impact | Resolution |
|---------|--------|------------|
| Hermes gateway timeout (30s) on quote starts | Fallback line fires and the quote waits | Recorded 2026-09-25. Not re-measured in the 2026-09-30 docs pass. Check Hermes health before raising the timeout |
| Capability matrix not run end-to-end on the scroll desk | F0.8 still open | Run `work/CAPABILITY_TEST_MATRIX.md` (include section S) |

Resolved since 2026-09-25: `live_service` is registered (`backend/conftest.py`, `pytest.ini`). Master Data UI is `/masterdata` and `masterdata_enabled` defaults on. Turn ledger stays off on purpose (Phase 7).

---

## Success Metrics (From Vision Workbook Â§14)

| Metric | Target | Current |
|--------|--------|---------|
| Casual Hermes warm latency | â‰¤5s | ~5-10s (needs measurement) |
| HITL miss rate | 0 | Unknown â€” needs audit |
| Office-day loop (brief + RFQâ†’Authorize) | Works end-to-end | Partial â€” quote path works, brief needs polish |
| **Stretch:** Local RAG useful on real shop question | Yes | No |
| **Stretch:** One novel browser task with evidence | Yes | No |

---

## Decision Log (Roadmap Changes)

| Date | Change | Reason |
|------|--------|--------|
| 2026-09-25 | Roadmap created from consolidated SYSTEM_TRUTH | Single source of truth established; all prior docs superseded |
| 2026-09-30 | F0.1 acceptance rewritten for the scroll desk. `live_service` and Master Data UI removed from blockers | Those items are in the tree; the matrix run is still open |

---

**Next review:** After an F0.8 capability-matrix pass on the scroll desk.  
**Coordination:** The coordinator fixes observations directly. A Cursor subagent runs only if the user names one.  
**Capability tests:** `work/CAPABILITY_TEST_MATRIX.md` (sections Aâ€“O and S). Suggested order is in that file.