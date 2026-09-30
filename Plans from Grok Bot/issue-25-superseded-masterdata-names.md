# Plan: #25 Superseded master-data rows keep original names

**Repo:** PratikMahajan1993/Jarvis-Mark-1  
**Issue:** https://github.com/PratikMahajan1993/Jarvis-Mark-1/issues/25  
**Priority:** High  
**Status:** Plan only — no implementation until accepted

## Goal
When a customer / supplier / material / outsource vendor / product is superseded on `/masterdata`, the closed row keeps the shop’s original display name (or product number). The new active row can still take a clean unique name. History under the current row stays readable.

## Constraints
- Do not hard-delete authoritative rows (supersede + end-date).
- Do not invent prices, GSTIN, or rates.
- Do not change quote proof, HITL, scroll desk, or substrate.
- Active names (and active product numbers) must remain unique.

## Current behavior
In `backend/app/masterdata/lifecycle.py`, supersede paths free UNIQUE constraints by rewriting the old row:
- customers / suppliers / materials / outsource_vendors: `name` → `{old} [superseded {id}]`
- products: `product_number` → `{old} [superseded {id}]`

`frontend/src/components/masterdata/shared.tsx` `groupWithHistory` already chains history via `superseded_by`. Display does not need a new grouping model once names stay intact.

## Proposed approach
1. **Schema:** Confirm uniqueness (table UNIQUE vs index). Replace whole-table uniqueness with a **partial unique index on active rows only** (match schema conventions in `docs/MIGRATION_STANDARDS.md` / `.cursor/rules/backend/12-data-schema.mdc` — e.g. `WHERE status = 'active'` or `WHERE effective_to IS NULL`). Cover name-unique entities and product_number.
2. **Lifecycle:** Remove the pre-insert name/number rewrite in the relevant `supersede_*` functions. Keep insert + `_end_date` + audit only.
3. **Data repair (optional, decide before coding):** One-time migration to strip ` [superseded …]` suffixes from already-mangled closed rows where the stripped value does not collide with another active unique key.
4. **UI:** Verify `/masterdata` history rows show original names; no change expected to `groupWithHistory` unless something assumes the suffix.
5. **Tests / smoke:** Supersede customer to a new name → old name unchanged, new active unique, history nested under current. Repeat for supplier / material / product_number if touched.

## Out of scope
Quote proof, HITL, desk, substrate, rate supersede paths (those do not rewrite display names the same way).

## Open question
Repair existing mangled rows in the same change, or only stop rewrite going forward?

## Done when
Plan accepted; implementation is a separate step (local edits by owner).
