# Phase 4: Master Data & Schema (Complete) — Implementation Plan

**Branch:** `overhaul` → work on `phase4-master-data` branch
**Timeline:** 2 weeks
**Owner:** `jarvis-builder` (backend migrations + enablement), `jarvis-uiux` (Master Data UI), `jarvis-workflows` (temporal queries, aliases)
**Reference:** `docs/ROADMAP.md` Phase 4, `docs/SYSTEM_TRUTH.md` §5

---

## Executive Summary

Phase 4 makes master data the durable source for rates, machines, customers, vendors. Current state: migrations 0004-0007 exist but `masterdata_enabled=False` by default; markdown fallbacks (`mhr-demo.md`, `client-names.md`) are the production source. Gap: flag off, no UI for CRUD, temporal queries work but not exposed, aliases not managed.

**Deliverable:** `masterdata_enabled=True` in production; owner manages customers, machines, materials, suppliers, rates, MHR floors, outsource vendors via UI; temporal as-of queries power quote verification; aliases map to canonical IDs; supersede-not-delete enforced.

---

## Current Architecture (What Exists)

### Migrations Already Applied (0004-0007)
| Migration | Tables | Purpose |
|-----------|--------|---------|
| 0004_parties.sql | `customers`, `customer_aliases`, `customer_terms`, `materials`, `material_equivalents`, `suppliers`, `supplier_rm_quotes` | Parties, RM quotes |
| 0005_machines.sql | `machines`, `machine_hour_rates`, `machine_capabilities` | Machines, MHR floors, capabilities |
| 0006_routings.sql | `components`, `part_revisions`, `outsource_vendors`, `outsource_quotes`, `routings`, `routing_operations` | Components, routings, outsource |
| 0007_quotes.sql | Quote revision persistence | Quote master data |

### Master Data Modules (`backend/app/masterdata/`)
| Module | Purpose |
|--------|---------|
| `mhr_lookup.py` | Temporal as-of lookup for MHR floors |
| `import_mhr_demo.py` | Idempotent markdown→SQL import |
| `import_aliases.py` | Idempotent client-names.md→SQL import |
| `quotes.py` | Quote revision persistence |
| `lookup.py` | Customer name validation |

### Flag
- `masterdata_enabled: bool = False` in `config.py`
- When True: temporal MHR lookup, customer alias sync, quote revision persistence active
- When False: markdown fallbacks (`mhr-demo.md`, `client-names.md`)

### Current Fallbacks (Production Source)
| Data | Fallback Source |
|------|-----------------|
| MHR floors | `mhr-demo.md` + `mhr-demo-attestation.md` |
| Customer names | `client-names.md` |
| Materials | Not in fallback — only in master data |

---

## Task Breakdown

### D4.1 Enable `masterdata_enabled` Flag + Seed Real Data

**Status:** Flag exists, default False. Migrations applied. Gap: No real seed data; flag off.

**Implementation:**

1. **Create seed script** (`backend/app/masterdata/seed_master_data.py`)
   ```python
   def seed_master_data(conn: sqlite3.Connection) -> None:
       """Insert real shop data: machines, MHR floors, customers, materials, suppliers."""
       # Machines with real control models, axis travels, spindle limits
       # MHR floors with owner attestation
       # Customer records with default_scope, payment terms
       # Materials with grades, densities
       # Suppliers with lead times
   ```

2. **Seed data** (from owner's actual shop):
   - **Machines:** 3-5 real machines with control_make/model, axis travels, rapid rates, spindle limits
   - **MHR floors:** Owner-attested rates per machine type (not demo seeds)
   - **Customers:** Real customer names, GSTIN, default_scope (labour/with_material), payment terms
   - **Materials:** Real grades (EN8, EN24, 18CrNiMo7-6, etc.) with densities
   - **Suppliers:** Real vendor names, lead days

3. **Enable flag** in `.env` → `MASTERDATA_ENABLED=true`

4. **Verify:** `mhr_lookup.machine_hour_rate_as_of()` returns real rates; `lookup.customer_name_is_known()` works

**Acceptance:** `masterdata_enabled=True` in production; temporal as-of lookups work; real data seeded

---

### D4.2 Customer/Machine/Vendor Aliases → Canonical IDs

**Status:** `customer_aliases` table exists; `import_aliases.py` syncs from markdown. Gap: No UI to manage aliases; unresolved alias = ask but no tool to add alias.

**Implementation:**

1. **Backend: Alias Management Tools** (`backend/app/masterdata/aliases.py` — NEW)
   ```python
   def add_customer_alias(conn, customer_id, alias, source="manual") -> dict
   def remove_customer_alias(conn, alias) -> dict
   def list_customer_aliases(conn, customer_id) -> list
   def resolve_customer_alias(conn, alias) -> str | None  # returns canonical customer_id
   ```
   Same pattern for machines (`machine_aliases` — new table) and vendors (`vendor_aliases` — new table)

2. **Migration 0024+**: Add `machine_aliases`, `vendor_aliases` tables
   ```sql
   CREATE TABLE machine_aliases (
     machine_id TEXT NOT NULL REFERENCES machines(id),
     alias TEXT NOT NULL,
     source TEXT NOT NULL,
     PRIMARY KEY (alias)
   );
   CREATE TABLE vendor_aliases (
     vendor_id TEXT NOT NULL REFERENCES suppliers(id),
     alias TEXT NOT NULL,
     source TEXT NOT NULL,
     PRIMARY KEY (alias)
   );
   ```

3. **Frontend: Alias Manager** (`frontend/src/components/masterdata/AliasManager.tsx` — NEW)
   - Table: Alias | Canonical Name | Source | Actions (Remove)
   - "Add Alias" modal: type alias → autocomplete to canonical → save
   - Unresolved alias in chat → suggests "Did you mean X?" with "Add as alias" button

4. **Integration:** `resolve_drawing_identity` uses aliases for customer matching

**Acceptance:** Unresolved alias → ask; never guess from similarity; UI to manage aliases

---

### D4.3 Temporal Rates: As-Of Queries

**Status:** `mhr_lookup.machine_hour_rate_as_of()` exists and works. Gap: Not exposed for RM quotes, outsource quotes, supplier quotes; no UI for temporal management.

**Implementation:**

1. **Backend: Extend Temporal Lookups** (`backend/app/masterdata/lookup.py` — enhance)
   ```python
   def supplier_rm_quote_as_of(conn, material_id, as_of) -> dict | None
   def outsource_quote_as_of(conn, process, as_of) -> dict | None
   def machine_capability_as_of(conn, machine_id, process, as_of) -> dict | None
   ```

2. **Integration in `verify_quote`:**
   - RM quote basis date → `supplier_rm_quote_as_of(material_id, quote_date)`
   - Outsource quote → `outsource_quote_as_of(process, quote_date)`
   - MHR floor → already uses `machine_hour_rate_as_of()`

3. **Frontend: Temporal Rate Editor** (`frontend/src/components/masterdata/TemporalRateEditor.tsx` — NEW)
   - Table: Effective From | Effective To | Rate | Attested By | Attested At
   - "Add Rate" modal: effective_from, effective_to, rate, currency
   - Visual timeline showing rate history
   - "Current rate" badge on active row

4. **MHR Attestation Panel:** Already exists (Phase 1) — enhance to show temporal history

**Acceptance:** As-of quote date queries work; missing row = BLOCKER; UI for temporal management

---

### D4.4 Supersede Not Delete on Authoritative Rows

**Status:** Pattern documented in `SYSTEM_TRUTH.md` §5.4. Gap: No enforcement in code; no UI guidance.

**Implementation:**

1. **Backend: Supersede Helpers** (`backend/app/masterdata/lifecycle.py` — NEW)
   ```python
   def supersede_customer(conn, old_id, new_customer_data) -> str  # returns new_id
   def supersede_machine(conn, old_id, new_machine_data) -> str
   def supersede_material(conn, old_id, new_material_data) -> str
   def supersede_supplier(conn, old_id, new_supplier_data) -> str
   def supersede_rate(conn, table, old_id, new_rate_data, effective_from) -> str
   ```
   - Inserts new row with `effective_from = today`
   - Sets `effective_to = today` on old row
   - Preserves `created_at`, `attested_by`, `attested_at`, provenance

2. **Frontend: "Replace" Action** (not Delete)
   - In all Master Data tables: "Replace" button instead of "Delete"
   - "Replace" opens modal pre-filled with current values → owner edits → saves as new version
   - Old row marked "Superseded" with strikethrough in table

3. **Audit Trail:** `audit` table logs all supersedes with `action: "supersede"`

**Acceptance:** No hard deletes; supersede with new row + end-date old; audit fields survive

---

### D4.5 Master Data UI (Complete CRUD)

**Status:** No UI exists. Gap: Owner cannot manage customers, machines, materials, suppliers, rates via UI.

**Implementation:**

**Frontend: Master Data Settings Page** (`frontend/src/app/masterdata/page.tsx` — NEW)
```
Tabs: Customers | Machines | Materials | Suppliers | MHR Floors | Outsource Vendors
```

| Tab | Entity | Fields | Temporal | Special |
|-----|--------|--------|----------|---------|
| Customers | `customers` + `customer_terms` | name, GSTIN, currency, status, default_scope, payment_terms, nda, vision_consent | No | Alias manager link |
| Machines | `machines` + `machine_hour_rates` | name, type, control_make/model, axes, travels, rapid, spindle, bar_cap, chuck | MHR rates | Capabilities link |
| Materials | `materials` + `material_equivalents` | grade, family, standard, density, machinability, hardness, form | No | Equivalents |
| Suppliers | `suppliers` + `supplier_rm_quotes` | name, contact, lead_days | RM quotes | Outsource vendors link |
| MHR Floors | `machine_hour_rates` | machine_type, min_mhr, target_mhr, currency, effective_from/to, attested | Yes | Attestation status |
| Outsource Vendors | `outsource_vendors` + `outsource_quotes` | name, processes, lead_days | Outsource quotes | Process coverage |

**Per-Tab Components:**
- **Table** with pagination, sort, filter
- **Add/Edit Modal** with validation
- **Temporal Editor** for rate tables (effective_from/to)
- **Alias Manager** link for customers/machines/vendors
- **Replace** action (not Delete) for authoritative rows

**Backend: CRUD API** (`backend/app/masterdata/routes.py` — NEW)
- REST endpoints: `GET/POST /api/masterdata/{entity}`, `GET/PATCH/DELETE /api/masterdata/{entity}/{id}`
- PATCH = supersede (not update-in-place) for rates
- Validation: temporal overlaps, required fields, referential integrity

**Integration with Quote Workflow:**
- `build_quote` dropdown for machines → from `machines` table
- `build_quote` material dropdown → from `materials` table
- Customer autocomplete → from `customers` + `customer_aliases`

---

### D4.6 Migration 0019+ for Schema Evolution

**Status:** Current at 0021. Gap: Future migrations need standards.

**Implementation:**

1. **Migration Standards Doc** (`docs/MIGRATION_STANDARDS.md` — NEW)
   - Forward-only: no down migrations
   - Backfills in migration script, not request handlers
   - Provenance columns preserved (`source_kind`, `source_ref`, `attested_by`, `attested_at`, `shipped_seed_value_minor`)
   - Idempotent: check existence before insert
   - Temporal: `effective_from`/`effective_to` on rate tables

2. **Template** (`backend/migrations/TEMPLATE.sql` — NEW)
   ```sql
   -- Description: what this migration does
   -- Dependencies: migration numbers
   BEGIN IMMEDIATE;
   -- idempotent inserts/updates
   COMMIT;
   ```

3. **CI Check:** `test_migration_standards.py` validates new migrations follow template

---

## Dependencies & Order

```
Week 1:
├── D4.1 Enable flag + seed real data (unblocks everything)
├── D4.2 Alias tables + migration 0024 (unblocks D4.2 UI)
├── D4.5 Master Data UI skeleton + Customers tab (first entity)
└── D4.3 Temporal lookups already work — verify integration

Week 2:
├── D4.5 Remaining tabs: Machines, Materials, Suppliers, MHR Floors, Outsource Vendors
├── D4.4 Supersede logic + "Replace" UI pattern
├── D4.6 Migration standards + CI check
└── Integration: Quote workflow dropdowns → master data tables
```

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/masterdata/seed_master_data.py` | Seed real shop data |
| `backend/app/masterdata/aliases.py` | Alias management tools |
| `backend/app/masterdata/lifecycle.py` | Supersede helpers |
| `backend/app/masterdata/routes.py` | REST API for Master Data |
| `backend/app/masterdata/lookup.py` — enhance | Temporal lookups for RM/outsource |
| `backend/migrations/0024_aliases.sql` | `machine_aliases`, `vendor_aliases` |
| `frontend/src/app/masterdata/page.tsx` | Master Data Settings page (tabs) |
| `frontend/src/components/masterdata/AliasManager.tsx` | Alias CRUD UI |
| `frontend/src/components/masterdata/TemporalRateEditor.tsx` | Temporal rate timeline |
| `frontend/src/components/masterdata/CustomerTable.tsx` | Customers CRUD |
| `frontend/src/components/masterdata/MachineTable.tsx` | Machines CRUD + MHR |
| `frontend/src/components/masterdata/MaterialTable.tsx` | Materials CRUD |
| `frontend/src/components/masterdata/SupplierTable.tsx` | Suppliers CRUD |
| `frontend/src/components/masterdata/MHRFloorTable.tsx` | MHR Floors CRUD |
| `frontend/src/components/masterdata/OutsourceVendorTable.tsx` | Outsource Vendors CRUD |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/config.py` | `masterdata_enabled` default → `True` |
| `backend/app/quote.py` | Dropdowns from master data tables; temporal RM/outsource lookups |
| `backend/app/main.py` | Register masterdata routes |
| `backend/app/tools/registry.py` | Register alias, seed, supersede tools |
| `backend/app/hermes/mcp_server.py` | Expose masterdata tools |
| `backend/app/masterdata/import_mhr_demo.py` | Deprecate (markdown fallback removed) |
| `backend/app/masterdata/import_aliases.py` | Deprecate (markdown fallback removed) |
| `frontend/src/lib/api.ts` | Add masterdata API client methods |

### Test Files (New)
| File | Purpose |
|------|---------|
| `backend/tests/test_masterdata_seed.py` | Seed script inserts correct data |
| `backend/tests/test_masterdata_aliases.py` | Alias CRUD + resolution |
| `backend/tests/test_masterdata_temporal.py` | As-of queries for MHR, RM, outsource |
| `backend/tests/test_masterdata_supersede.py` | Supersede preserves audit fields |
| `backend/tests/test_masterdata_ui.py` | Frontend component tests |

---

## Testing Checklist (Per ROADMAP Capability Matrix)

| ID | Test | Phase 4 Coverage |
|----|------|------------------|
| G1 | Inbound drawing RFQ detect | ✅ (existing) |
| G2 | Vision on drawing | ✅ (existing) |
| G3 | Quote build (sheet) | ✅ (dropdowns from master data) |
| G5 | Quote send (HITL) | ✅ (existing) |
| G6 | Full dry-run loop | ✅ (end-to-end with real data) |
| G9 | Quote proof (`quote_verify`) | ✅ (temporal RM/outsource lookups) |
| G10 | Shop-quote playbook load | ✅ (real MHR floors) |

---

## Acceptance Criteria (Definition of Done)

1. **D4.1:** `masterdata_enabled=True` in production; real machine data seeded; MHR floors from SQL not markdown
2. **D4.2:** Alias manager UI works; unresolved alias → ask; never guess from similarity
3. **D4.3:** Temporal queries for MHR, RM, outsource work; missing row = BLOCKER; UI shows timeline
3. **D4.4:** "Replace" not "Delete"; supersede preserves `created_at`, `attested_by`, provenance
4. **D4.5:** Complete CRUD UI for all 6 entities; quote workflow uses master data dropdowns
5. **D4.6:** Migration template + CI check; forward-only; provenance preserved

---

## Handoff Notes for Implementation Agent

1. **Start with D4.1** — seed script + enable flag. This unblocks everything else.
3. **Use existing patterns** — `mhr_lookup.py` for temporal queries, `import_mhr_demo.py` for idempotent imports
3. **Frontend state** — Master Data page is a new route (`/masterdata`), not part of the bench
4. **Temporal queries** — reuse `machine_hour_rate_as_of()` pattern for RM/outsource
5. **Supersede** — always insert new row + end-date old; never UPDATE-in-place on authoritative rows
6. **Deprecate markdown fallbacks** — once flag is on, `mhr-demo.md` and `client-names.md` are obsolete

---

## Quick Start Commands

```bash
# Backend
cd backend && python -c "from app.masterdata.seed_master_data import seed_master_data; from app.db import connect; seed_master_data(connect())"
cd backend && python -m pytest tests/test_masterdata_seed.py tests/test_masterdata_aliases.py -v

# Frontend
cd frontend && npm run typecheck && npm run lint

# Migrations
cd backend && python -c "from app.db import run_migrations; run_migrations()"
```

---

## Clarifying Questions

### Q1: Seed Data Source
Where does the real seed data come from?
- **Option A:** Owner provides CSV/JSON — we write a one-time import script
- **Option B:** Owner enters manually via UI after D4.5 — seed script just creates empty tables
- **Option C:** Mix — seed script creates structure; owner fills via UI

### Q2: Machine Capabilities UI
Should `machine_capabilities` (process tolerance/finish floors) be in the Machines tab or a separate "Capabilities" tab?
- **Option A:** In Machines tab — inline editor per machine
- **Option B:** Separate tab — cleaner, more space

### Q3: Material Equivalents
Should `material_equivalents` be managed in Materials tab or separate?
- **Option A:** In Materials tab — "Add Equivalent" button per material
- **Option B:** Separate — cross-reference table

### Q4: Outsource Vendor Processes
`outsource_vendors.processes` is TEXT (comma-separated). Should this be a junction table for proper relational queries?
- **Option A:** Keep as TEXT — simpler, processes are few
- **Option B:** Junction table `outsource_vendor_processes` — proper relational, enables "find vendors for process X"