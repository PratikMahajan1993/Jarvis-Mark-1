# Implementation Plan: Jarvis Architectural & Logic Fixes
## For: Grok 4.7 implementation agent
## Goal: Fix all confirmed defects from Sonnet + adversarial review while preserving stability
## Safety principle: Zero-breaking changes; product decisions required before risky modifications

---

## ⚡ PHASE 1: Immediate High-Risk/Low-effort Fixes (Run Now)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `.cursor/skills/jarvis-quote-playbook/SKILL.md` | Fix "stop: true when >2 failures" → "any BLOCKER stops; WARN never stops" | LOW — text edit only |
| 2 | `backend/app/hermes/playbooks/quote/SKILL.md` | Same fix as #1 (runtime playbook) | LOW — text edit only |
| 3 | `backend/app/agent.py` line ~1713 | Add `reconcile_external_effects_on_boot()` call in `startup()`/`lifespan()` | VERY LOW — one-line addition, function is idempotent |
| 4 | `jarvis-builder.md` | Change `backend/exports` → `<repo>/exports/` | LOW — path correction, matches `config.py` and root rule |

**ACTION:** Execute #1-4 immediately. These are text/one-line changes with verified low risk.

---

## 🔍 PHASE 2: Medium-Priority Fixes (Verify Before Running)

| # | File | Change | Verification Needed |
|---|------|--------|---------------------|
| 5 | `00-jarvis-core.mdc` | Reword turn-ledger sentence: "synchronous by default; server-ledger variant behind `turn_ledger_enabled` (off by default)" | Read current text, confirm rewording |
| 6 | `.cursor/skills/jarvis-architecture/SKILL.md` | Replace "dual-write with Honcho" with correct SQLite+LanceDB description | Read current Honcho line, replace |
| 7 | `backend/app/quote.py:_rm_basis_date_check()` | Change `age is None: return _check("rm_basis_date", True, ...)` to return failing check (WARN/BLOCKER) instead of passing | Read the function, confirm the empty-date branch already returns BLOCKER, make `age is None` consistent |
| 8 | `ops/42-dispatch.mdc` | Trim to under 400 words (test `test_rule_budget.py::test_word_budgets` currently fails at 402) | Read the file, identify ~2 lines to trim; run `pytest -m "not live_service" test_rule_budget.py` after edit |

**ACTION:** Read files for #5-8, make edits, then run applicable tests.

---

## 🛑 PHASE 3: Product Decision Points (STOP — Wait for Your Input)

### Decision A: Master Data Default (LOGIC-2)
**Issue:** MHR owner-attestation invariant is inert when `masterdata_enabled=False` (the shipped default)

**Options:**
- (a) Change `masterdata_enabled` default to `True` in `backend/app/config.py`
- (b) Add attestation-equivalent to markdown fallback (new `mhr-demo.md` companion file with owner sign-off dates)
- (c) Leave as-is — the code bug exists but is "by design" for demo desks

**Choose: (a), (b), or (c)**

### Decision B: Turn Ledger Primary Model (ARCH-4)
**Issue:** Two chat-turn state models exist; which is "primary"?

**Options:**
- (a) Flip `turn_ledger_enabled=True` by default in `config.py` and treat sync path as deprecated
- (b) Keep `turn_ledger_enabled=False` (default) and explicitly mark ledger path as "future work, not yet load-bearing" in `00-jarvis-core.mdc`
- (c) Leave both paths wired but add clear documentation disambiguation

**Choose: (a), (b), or (c)**

### Decision C: Canvas Scope (ARCH-7)
**Issue:** Canvas violates "single pane" invariant by being a separate app

**Options:**
- (a) Document Canvas as explicitly out of scope for single-pane mandate in rule files
- (b) Begin folding Canvas into Pane/lens model as fourth lens/Engineering panel (significant frontend work)
- (c) Leave as-is with addendum in rule files

**Choose: (a), (b), or (c)**

### Decision D: Feature Flag Sunset Plans (ARCH-6)
**Issue:** Five feature flags permanently fork business concepts with no sunset plan

**Options:**
- (a) Create "flag ledger" doc recording expected flip conditions for each flag and fallback removal timeline
- (b) For each flag, add explicit labeling in code/output: e.g. `mhr_demo_floor` check result labeled "unattested demo fallback"
- (c) Leave as-is — flags are at different stages of rollout

**Choose: (a), (b), or (c)**

### Decision E: LanceDB Read Path (ARCH-3)
**Issue:** LanceDB mirror is write-only; `search()` queries SQLite only; `get_summary()` reports misleading `"engine": "lancedb+sqlite"`

**Options:**
- (a) Wire `search()` to actually query LanceDB when available, with SQLite fallback — adds ANN read path
- (b) Remove LanceDB write path entirely + misleading `engine` string; keep SQLite-only
- (c) Leave as-is — LanceDB provides future-readiness even if not used today

**Choose: (a), (b), or (c)**

---

## ✅ PHASE 4: Lower-Priority / Conditional Fixes (After Above Complete)

| # | File | Change | Dependencies |
|---|------|--------|-------------|
| 9 | `backend/app/quote.py:_rm_basis_age_days()` / `_rm_basis_date_check()` | Fix malformed RM-basis date silently passing → fail closed (LOW) | After Phase 2/3 complete |
| 10 | `frontend/src/lib/orchestratorFsm.ts` | Consolidate greeting fallback strings (`_social_reply`) into one owned location (LOW) | After Phase 1-3 stable |
| 11 | `backend/app/config.py` | Add "flag ledger" documentation for 5 feature flags (MEDIUM) | After Decision D in Phase 3 |
| 12 | `backend/app/memory/store.py` | Either wire `search()` to LanceDB (Decision E) OR remove write path (b) | After Decision E in Phase 3 |

---

## ⛔ SAFETY GUARANTEES — THESE MUST NOT CHANGE WITHOUT EXPLICIT PRODUCT DIRECTION

- ❌ The three intent classifiers — do not restructure without consolidated replacement preserving deterministic regex safety net and 432 tests
- ❌ `except Exception: pass` pattern on instrumentation — do not change to logged exceptions without also adding `logger.debug(...)` and compelling reason
- ❌ Roster agent frontmatter `model: inherit` — do not change without paired launch-infra clarification
- ❌ `domain/30-quote-playbook.mdc`'s nonexistent glob path — flag but don't restructure
- ❌ `jarvis-react-bits/catalog.md` stale references — update only as part of full React Bits refresh

---

## 🚀 EXECUTION CHECKLIST

### Immediate (Phase 1):
- [ ] Edit `.cursor/skills/jarvis-quote-playbook/SKILL.md` — fix stop rule text
- [ ] Edit `backend/app/hermes/playbooks/quote/SKILL.md` — same fix
- [ ] Add `reconcile_external_effects_on_boot()` call in `main.py` startup
- [ ] Fix `jarvis-builder.md` exports path: `backend/exports` → `<repo>/exports/`

### Pending Your Decisions (Phase 2+3):
- [ ] **Decision A:** Master data default — (a/b/c)?
- [ ] **Decision B:** Turn ledger primary — (a/b/c)?
- [ ] **Decision C:** Canvas scope — (a/b/c)?
- [ ] **Decision D:** Feature flag sunset plans — (a/b/c)?
- [ ] **Decision E:** LanceDB read path — (a/b/c)?

### After Decisions Confirmed:
- [ ] Execute Phase 2 edits (#5-8)
- [ ] Run `pytest -m "not live_service"` to verify no breaks
- [ ] Execute Phase 4 fixes as applicable

---