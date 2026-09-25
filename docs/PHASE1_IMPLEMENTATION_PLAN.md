# Phase 1: Quote Workflow Hardening — Implementation Plan

**Branch:** `overhaul` → work on `phase1-quote-hardening` branch
**Timeline:** 2 weeks
**Owner:** `jarvis-workflows` (backend), `jarvis-uiux` (frontend Engineering bench)
**Reference:** `docs/ROADMAP.md` Phase 1, `docs/SYSTEM_TRUTH.md` §4

---

## Executive Summary

Phase 1 makes the quote workflow production-ready. Current state: quote tools exist but have gaps — drawing lookup guesses, MHR demo seeds block sends, PDF/email send needs HITL wiring, Engineering bench proof strip is a preview only.

**Deliverable:** Real RFQ email → drawing → strategy → quote → PDF → Authorize → sent, with zero guessing and full audit trail.

---

## Current Architecture (What Exists)

### Backend Quote Flow (`backend/app/quote.py`)

```
build_quote() → creates xlsx artifact → stores rows in session memory
quote_to_pdf() → creates PDF artifact → stores path in session memory
verify_quote() → runs 14 checks (BLOCKER/WARN) → returns verdict + scene
queue_quote_send() → requests HITL approval → stores pending action
```

**Key Files:**
- `backend/app/quote.py` — core logic (build, pdf, verify, send)
- `backend/app/hermes/playbooks/quote/` — Hermes skill + markdown data files
- `backend/app/masterdata/mhr_lookup.py` — temporal MHR floor lookup
- `backend/app/masterdata/import_mhr_demo.py` — idempotent markdown→SQL import
- `backend/app/rfq.py` — RFQ intake, drawing conversation resolution

### Frontend Engineering Bench

```
OrchestratorShell → Pane (lens=bench) → QuoteSheet + DrawingStage
QuoteSheet tabs: Sheet | Strategy | Vision
ProofStrip: glyphs ✓/✗ per check, failed/total, "stop" badge
Authorize/Reject buttons (disabled when fixture or >2 BLOCKER failures)
```

**Key Files:**
- `frontend/src/components/bench/QuoteSheet.tsx` — main bench UI
- `frontend/src/components/bench/ProofStrip.tsx` — proof visualization
- `frontend/src/components/bench/DrawingStage.tsx` — drawing viewer
- `frontend/src/lib/pane/quoteContract.ts` — TypeScript types mirroring backend

### Data Flow

```
User: "quote this drawing"
    ↓
Hermes loads shop-quote skill → calls jarvis_quote_analyze_drawing / jarvis_quote_build
    ↓
build_quote() → xlsx artifact + session memory (last_quote_*)
    ↓
quote_to_pdf() → PDF artifact + session memory (last_quote_pdf*)
    ↓
verify_quote(stage="draft"|"send") → checks → verdict
    ↓
queue_quote_send() → pending_actions row (kind="quote_send")
    ↓
HITL: Authorize/Reject → POST /api/confirm → agent.resolve_pending
```

---

## Task Breakdown

### Q1.1 Drawing Lookup — Focus → Named Search → Save Attachment → Ask

**Status:** Partially exists in `rfq.py:_spawn_from_mail()` and `quote.py:analyze_drawing_vision()`
**Gap:** No unified "find drawing" tool; falls back to "which drawing?" string

**Implementation:**

1. **Create `jarvis_quote_find_drawing` tool** (`backend/app/quote.py`)
   ```python
   def find_drawing_for_quote(
       session_id: str,
       part_hint: str = "",
       drawing_path: str = "",
   ) -> dict[str, Any]:
       """
       Resolution order (stop at first hit):
       1. drawing_path provided → validate exists
       2. Focus on Engineering bench → conversation.focus.local_path
       3. Named search: local files (exports/, data/) + mail attachments by part_hint/filename
       4. Mail attachment save → save_attachments() → local path
       5. Zero hits → return {"ok": False, "need": "path", "candidates": [...]}
       """
   ```

2. **Register tool** in `backend/app/tools/registry.py` and Hermes MCP (`backend/app/hermes/mcp_server.py`)

3. **Update shop-quote playbook** (`backend/app/hermes/playbooks/quote/SKILL.md`) to call `find_drawing` first

4. **Frontend:** Add "Find Drawing" button on QuoteSheet header when no drawing loaded

**Acceptance:** Never guesses; ambiguous → lists candidates; no path → returns need="path"

---

### Q1.2 Labour vs RM Default per Customer + Override

**Status:** Scope logic exists in `build_quote()` and `verify_quote()` (lines 790-830)
**Gap:** No customer default lookup; no "ask" flow

**Implementation:**

1. **Add `customer_scope_default` table** (migration if `masterdata_enabled`) or extend `customers` table
   ```sql
   ALTER TABLE customers ADD COLUMN default_scope TEXT CHECK (default_scope IN ('labour','with_material'));
   ```

2. **Add `get_customer_scope_default(customer_id)`** in `backend/app/quote.py`
   - Returns `'labour'` | `'with_material'` | `None`

3. **Modify `build_quote()`** to auto-fill scope from customer default when not provided

4. **Add "ask" path:** When scope not provided AND no customer default → return `{"ok": False, "need": "scope", "message": "Labour-only or with material?"}`

5. **Frontend:** Scope selector in QuoteSheet header (Labour / With Material) with customer default pre-selected

**Acceptance:** Default from customer record; mail/verbal overrides; neither → ask

---

### Q1.3 Supplier RM Quote Tracking

**Status:** `rm_source`, `rm_source_note`, `rm_price` fields exist in `build_quote()` and memory
**Gap:** No workflow to request → receive → record supplier quote

**Implementation:**

1. **Add `supplier_rm_quotes` table** (migration 0019+)
   ```sql
   CREATE TABLE supplier_rm_quotes (
       id TEXT PRIMARY KEY,
       session_id TEXT,
       customer_id TEXT,
       material TEXT,
       supplier TEXT,
       quoted_price_minor INTEGER,
       currency TEXT DEFAULT 'INR',
       quote_date TEXT,          -- ISO date
       received_at TEXT,         -- ISO timestamp
       notes TEXT,               -- "historical avg 2024-Q1" or "supplier quote #123"
       is_estimate INTEGER DEFAULT 0,
       created_at TEXT
   );
   ```

2. **Add `jarvis_quote_request_rm_quote` tool** — creates tracking row, queues email to supplier (HITL)

3. **Add `jarvis_quote_record_rm_quote` tool** — records received quote, updates session memory

4. **Modify `verify_quote()`** to check `supplier_rm_quotes` table for received quotes; if only estimate exists → require `is_estimate=1` + non-empty `notes`

5. **Frontend:** RM quote tracker panel in QuoteSheet "Strategy" tab

**Acceptance:** Tracks request→receive; estimate allowed only from historical/market, labelled `is_estimate`

---

### Q1.4 Machining Strategy Editor

**Status:** QuoteSheet "Strategy" tab exists with `VarianceCard` + `ToolChangeField` placeholders
**Gap:** No drag-drop operations, outsource picker, machine selector, special tooling notes

**Implementation:**

**Backend:**
1. **Add `quote_operations` table** (migration)
   ```sql
   CREATE TABLE quote_operations (
       id TEXT PRIMARY KEY,
       session_id TEXT,
       seq INTEGER,
       operation TEXT,           -- "face", "rough turn", "finish bore", "heat treat"
       machine_type TEXT,        -- "Demo CNC vertical mill"
       outsource BOOLEAN DEFAULT 0,
       outsource_case TEXT,      -- "no_machine" | "customer_asked" | "capacity" | "not_in_house"
       outsource_vendor TEXT,
       outsource_price_minor INTEGER,
       special_tooling TEXT,
       setup_minor INTEGER,
       cycle_min REAL,
       notes TEXT
   );
   ```

2. **Add CRUD tools:** `jarvis_quote_add_operation`, `jarvis_quote_update_operation`, `jarvis_quote_delete_operation`, `jarvis_quote_reorder_operations`

3. **Modify `build_quote()`** to compute line items from operations (not just single machining_rate)

**Frontend (QuoteSheet Strategy tab):**
1. **Operation list** with drag-drop reorder (use `@dnd-kit/core`)
2. **Operation row:** Operation name | Machine dropdown | Outsource checkbox (+ case picker + vendor) | Setup min | Cycle min | Special tooling | Delete
3. **Add Operation** button → modal with operation templates (turning, milling, EDM, heat treat, plating, grinding)
4. **Outsource case picker:** radio buttons for 4 cases, vendor name + quote price when checked

**Acceptance:** Engineering bench: drag-drop ops, outsource picker, machine selector, special tooling notes

---

### Q1.5 MHR Table: Owner-Attested Rates Replace Demo Seeds

**Status:** `machine_hour_rates` table + `mhr-demo.md` + `mhr-demo-attestation.md` + `mhr_lookup.py`
**Gap:** No UI to attest rates; demo seeds still in DB

**Implementation:**

**Backend:**
1. **Add `jarvis_mhr_attest_rate` tool** — updates `attested_by`, `attested_at` on `machine_hour_rates` row
2. **Add `jarvis_mhr_list_rates` tool** — returns all rates with attestation status

**Frontend:**
1. **MHR Attestation Panel** in QuoteSheet "Strategy" tab (or separate Settings route)
3. **Table:** Machine Type | Demo Floor (INR/hr) | Attested By | Attested On | Status (✓ Attested / ○ Demo Seed / ⚠ Needs Attestation)
4. **Attest button** per row → modal: "Attest this rate?" → calls `jarvis_mhr_attest_rate`
5. **Show warning** in ProofStrip when rate is demo seed: "Demo MHR not attested — will block send"

**Acceptance:** `attested_by` + value ≠ seed = quotable; unattested = BLOCKER at send

---

### Q1.6 Outsource Pricing: Vendor Quote Required, Case Recorded

**Status:** `verify_quote()` checks for outsource price (lines 600-620 in quote.py)
**Gap:** No vendor quote tracking; no case recording

**Implementation:**

1. **Extend `quote_operations` table** (from Q1.4) with outsource fields — already covered

2. **Modify `verify_quote()`** to check:
   - If operation has `outsource=1` → `outsource_price_minor` required + `outsource_case` must be one of 4
   - If missing → BLOCKER check: "Outsource price/vendor missing for operation X"

3. **Frontend:** Outsource row in Strategy tab shows: Vendor | Quote Price | Case (dropdown) | Received checkbox

**Acceptance:** No guessed amounts; case recorded: no machine / customer asked / capacity / not in-house

---

### Q1.7 Quote PDF Generation (Formal Format, Bold Total, Attachment)

**Status:** `quote_to_pdf()` exists but produces plain text PDF
**Gap:** Professional format, bold total, proper sections

**Implementation:**

1. **Replace `quote_to_pdf()`** in `backend/app/quote.py` with reportlab-based professional template:
   - Header: Company name, "QUOTATION", quote number, date
   - Customer block: name, address, contact
   - Line items table: Item | Material | Qty | Unit Price | Total
   - **Total in bold, large font, INR currency**
   - Terms: Delivery, Payment, Validity
   - Footer: Authorized signatory line

2. **Use `quote-template.md`** from playbook files for section structure

3. **Email body template** in `queue_quote_send()`:
   ```
   Subject: Quotation — {part_name} — {quote_number}
   
   Dear {customer},
   
   Please find attached our quotation for **{part_name}**.
   
   **Total Quoted Cost: ₹{total_inr}**
   
   The detailed breakdown is in the attached PDF. Valid for 30 days.
   
   Regards,
   {sign_off}
   ```

**Acceptance:** PDF in exports; email body short formal with bold total; attachment included

---

### Q1.8 Quote Send Email (Authorize → Send via Gmail)

**Status:** `queue_quote_send()` creates pending action; `agent.resolve_pending` handles execution
**Gap:** HITL card needs blast-radius 5, duplicate delivery check; send execution not wired

**Implementation:**

1. **Enhance `queue_quote_send()`** payload:
   ```python
   payload = {
       "to": to,
       "subject": subject,
       "body": body,
       "attachment_paths": [pdf_path],
       "verify": verify_snapshot,
       "pdf_sha256": pdf_sha256,
       "blast_radius": 5,  # highest
       "duplicate_check": True,
   }
   ```

2. **Add duplicate delivery check** in `verify_quote()`:
   - Hash: `sha256(to + subject + pdf_sha256)`
   - Check `external_effects` table for same hash in last 30 days
   - If found → WARN on Authorize card: "Identical quote sent to {to} on {date}"

3. **Ensure `agent.resolve_pending`** calls Gmail send for `kind="quote_send"` (check `backend/app/agent.py`)

4. **Frontend:** Authorize card shows blast-radius badge, duplicate warning if applicable

**Acceptance:** HITL before send; blast-radius 5; duplicate delivery check on Authorize card

---

### Q1.9 Proof Strip on Engineering Bench Mirrors `quote_verify`

**Status:** `ProofStrip.tsx` exists but only works with fixture data
**Gap:** Real-time checklist from live `verify_quote()`; provenance glyphs

**Implementation:**

**Backend:** Already returns full `QuoteVerifyResult` with checks array

**Frontend:**
1. **Update `QuoteSheet.tsx`** to call `verify_quote(session_id, stage)` on mount and after any row change
   - Add `useEffect` with debounce (500ms) on `doc.rows` changes
   - Store result in local state → pass to `ProofStrip`

2. **Enhance `ProofStrip.tsx`** with provenance glyphs:
   ```tsx
   const glyph = (prov: QuoteProvenance) => 
     prov === "tool" ? "●" : prov === "confirmed" ? "◉" : prov === "pending" ? "◐" : "○"
   
   // Show per-row in SheetRow.tsx
   ```

3. **Add `failingCheckIds`** to `QuoteFixtureDocument` for Authorize gating (already in types)

4. **Real-time updates:** When user edits a SheetRow → debounced re-verify → ProofStrip updates

**Acceptance:** Real-time checklist; provenance glyphs ● ◉ ◐ ○; no guess numerals

---

## Dependencies & Order

```
Week 1:
├── Q1.1 Drawing Lookup (unblocks everything)
├── Q1.2 Labour vs RM Default
├── Q1.5 MHR Attestation UI + Backend
└── Q1.7 PDF Generation (needs Q1.1 for drawing)

Week 2:
├── Q1.3 Supplier RM Quote Tracking (needs Q1.2 scope)
├── Q1.4 Machining Strategy Editor (needs Q1.5 MHR)
├── Q1.6 Outsource Pricing (needs Q1.4 operations)
├── Q1.8 Quote Send HITL (needs Q1.7 PDF)
└── Q1.9 Proof Strip Real-time (needs all above)
```

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/quote.py` → `find_drawing_for_quote()`, `request_rm_quote()`, `record_rm_quote()`, `attest_mhr_rate()`, `list_mhr_rates()` | New tools |
| `backend/app/tools/registry.py` | Register new tools |
| `backend/app/hermes/mcp_server.py` | Expose new tools to Hermes |
| `backend/migrations/0019_phase1_quote.sql` | New tables: `supplier_rm_quotes`, `quote_operations`, customer scope default |
| `backend/app/masterdata/quotes.py` | Extend with operations + RM quotes persistence |
| `frontend/src/components/bench/MHRAttestationPanel.tsx` | New UI component |
| `frontend/src/components/bench/OperationEditor.tsx` | New UI component |
| `frontend/src/components/bench/RMTracker.tsx` | New UI component |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/quote.py` | `build_quote()` uses operations; `verify_quote()` adds RM/outsource checks; `quote_to_pdf()` professional template; `queue_quote_send()` blast-radius + duplicate check |
| `backend/app/rfq.py` | Integrate `find_drawing_for_quote` |
| `backend/app/agent.py` | Ensure `quote_send` executes via Gmail |
| `frontend/src/components/bench/QuoteSheet.tsx` | Real-time verify, MHR panel, Strategy tab ops editor, RM tracker |
| `frontend/src/components/bench/ProofStrip.tsx` | Provenance glyphs |
| `frontend/src/components/bench/SheetRow.tsx` | Provenance glyph per row |
| `frontend/src/lib/pane/quoteContract.ts` | Add operations, RM quote types |

### Playbook Updates
| File | Changes |
|------|---------|
| `backend/app/hermes/playbooks/quote/SKILL.md` | Update toolbox + drawing lookup flow |
| `backend/app/hermes/playbooks/quote/files/mhr-demo-attestation.md` | Keep for demo path |
| `backend/app/hermes/playbooks/quote/notes.md` | Will auto-populate via `jarvis_quote_playbook_note` |

---

## Testing Checklist (Per ROADMAP Capability Matrix)

| ID | Test | Phase 1 Coverage |
|----|------|------------------|
| G1 | Inbound drawing RFQ detect | ✓ (rfq.py) |
| G2 | Vision on drawing | ✓ (analyze_drawing_vision) |
| G3 | Quote build (sheet) | ✓ (build_quote + operations) |
| G4 | Quote PDF | ✓ (professional template) |
| G5 | Quote send (HITL) | ✓ (blast-radius + duplicate check) |
| G6 | Full dry-run loop | ✓ (end-to-end) |
| G9 | Quote proof (`quote_verify`) | ✓ (real-time on bench) |
| G10 | Shop-quote playbook load | ✓ (updated SKILL.md) |
| P14 | Engineering bench | ✓ (QuoteSheet + DrawingStage) |
| P15 | HITL on every workspace | ✓ (Authorize/Reject) |

---

## Acceptance Criteria (Definition of Done)

1. **Drawing Lookup:** `find_drawing` tool returns correct path or asks; never guesses
2. **Scope Default:** Customer record provides default; override works; missing → asks
3. **RM Tracking:** Request → receive → record flow works; estimates labelled
4. **Strategy Editor:** Drag-drop ops, outsource picker, machine selector, tooling notes
5. **MHR Attestation:** Owner can attest rates; unattested blocks send; demo seeds flagged
6. **Outsource:** Vendor quote required; case recorded; no guessed amounts
7. **PDF:** Professional format, bold total, proper sections
8. **Send:** HITL Authorize with blast-radius 5; duplicate warning; Gmail send executes
9. **Proof Strip:** Real-time, provenance glyphs, Authorize gated by >2 BLOCKER

---

## Handoff Notes for Implementation Agent

1. **Start with Q1.1** — it unblocks the entire workflow. The `find_drawing_for_quote` tool should be a standalone function in `quote.py` that the Hermes skill calls first.

2. **Use existing patterns** — `build_quote`, `verify_quote`, `queue_quote_send` are the model. New tools follow same signature: `session_id` + kwargs → `dict[str, Any]`.

3. **Frontend state** — `paneStore` is the source of truth for bench. Use `usePane` selector. Real-time verify: debounced effect on `doc.rows` changes.

4. **Migrations** — Only run if `masterdata_enabled=True`. Use `backend/app/masterdata/import_mhr_demo.py` as pattern for idempotent imports.

5. **Playbook notes** — `jarvis_quote_playbook_note` appends to `notes.md`. Use this for corrections during testing.

6. **Hermes timeout** — Current 30s is a blocker. Consider adding a warmup endpoint or increasing timeout in `config.py` for quote tools specifically.

7. **Types** — `quoteContract.ts` is the contract. Keep backend `verify_quote` return shape in sync.

---

## Quick Start Commands

```bash
# Backend
cd backend && python -m pytest tests/test_quote_playbook.py -v

# Frontend
cd frontend && npm run typecheck && npm run lint

# Full test
cd frontend && npm run perf  # headless Chrome perf gate
```

---

## Questions for Clarification (Before Implementation)

### Q1: Machining Strategy Editor (Q1.4) Persistence
Should the Machining Strategy Editor persist operations to a new `quote_operations` table, or keep them in session memory like current line_items?
- **Option A:** New SQL table (quote_operations) — durable, queryable, supports future master data
- **Option B:** Session memory only — simpler, matches current pattern

### Q2: MHR Attestation (Q1.5) UI Location
For MHR Attestation, should the UI be a standalone Settings page or embedded in QuoteSheet Strategy tab?
- **Option A:** Standalone Settings page (Master Data section) — cleaner separation
- **Option B:** Embedded in QuoteSheet Strategy tab — contextual while quoting

### Q3: Supplier RM Quote Tracking (Q1.3) Email
Should requesting a supplier quote send an actual email (HITL), or just create a tracking record?
- **Option A:** Actual email via Gmail (HITL) — real workflow
- **Option B:** Tracking record only — email sent manually outside Jarvis

### Q4: PDF Template (Q1.7) Source
Use the existing `quote-template.md` from playbook files, or build a new reportlab template from scratch?
- **Option A:** Parse quote-template.md sections → reportlab — keeps playbook as source of truth
- **Option B:** Hardcode reportlab template — faster, less parsing