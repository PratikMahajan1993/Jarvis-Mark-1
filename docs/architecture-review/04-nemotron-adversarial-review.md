# Adversarial Second Review: Nemotron Transcript

**Session:** Friday, Sep 25, 2026, 2:32 AM UTC+5:30
**Role:** Adversarial second reviewer, independent of Sonnet's architecture/audit pass
**Mandate:** Treat Sonnet's findings as hypotheses, not truth. Inspect the actual repository independently. Distinguish confirmed defects from overstatements, omissions, and product decisions requiring owner input. Do not implement fixes.

---

## Executive Summary

This review independently inspected the `d:\Cursor\Jarvis` codebase on branch `overhaul` (commit `41542be`). Sonnet's audit documents are treated as *claims* to be verified or contested against actual code, tests, configuration, and runtime behavior. The table at the end summarizes every finding side-by-side.

The central thesis: **the codebase is disciplined and well-built in several critical areas, but carries several long-standing architectural debts, duplicated implementations, and documentation drift that any implementation agent must navigate.** The most consequential gaps are not "bugs" per se, but *structural* issues — two parallel state machines, three parallel retrieval systems, three parallel intent classifiers — that compound the cost of any future change.

---

## 1. Confirmed Defects / Architectural Weaknesses

### ARCH-1 — Three overlapping intent classifiers, no single routing source of truth
**Status: CONFIRMED.** Verified from code.
- `intent.py:classify()` — ~40 rule regex/heuristic engine
- `semantic_router.py:classify_intent()` — Gemini-structured-output classifier with its own regex fallback `_fallback()`
- Hermes itself makes independent tool-selection judgments
- `agent.py:_run_agent()` reads *both* `route_intent` (from semantic_router) and `intent` (from intent.py), with two `is_rfq_definition` and three `is_quote_start` checks across different modules
- The same predicate (`is_quote_start`, `is_rfq_definition`) has **three** call sites across `intent.py`, `semantic_router.py`, and `hermes/bridge.py`

**Why it matters:** For any bug "Jarvis did the wrong thing for utterance X," a future agent must trace through all three classifiers. There is no single function answering "what will Jarvis do with this text?"

**Recommended direction:** Consolidate to one routing decision per turn. Let `semantic_router.classify_intent()` own the full `Intent`-equivalent shape, and have `intent.py`'s regex rules become *helpers it calls*, not a second parallel classifier. The deterministic regex layer is still valuable as a regression safety net — make it a library, not a second decision-maker.

---

### ARCH-2 — Safety deny-phrase list is dead code on the primary (Hermes) path
**Status: CONFIRMED.** Verified from code.
- `SAFETY_DENY_PHRASES` in `intent.py` ("send without approval", "skip authorize", etc.) only gates the legacy/heuristic path (`_run_agent_legacy`)
- The Hermes path (`agent.py:_run_agent` → `route_intent == "tool_ops"` → `_hermes_reply()`) does **not** consult `intent.kind` at all — it calls `run_hermes_turn()` with the raw, unfiltered message
- `hermes/bridge.py` has no deny-phrase check whatsoever
- The actual safety invariant is enforced by `tools/registry.py:execute_tool()` → `_queue_pending()` → `hermes/hitl.py:request_human_approval()`, which only queues pending actions; actual execution is gated separately in `resolve_pending()`

**Why it still matters:** The deny-phrase list is documented as *the* safety surface for these phrases, but it is dead weight on the live path. A future "fast path" tool could silently bypass it. The safety is an *implicit convention*, not a *mechanism*.

**Recommended direction:** Either (a) delete `SAFETY_DENY_PHRASES` and add an automated test asserting every handler in `tools/registry.HANDLERS` that performs external effects also calls `_queue_pending`/`request_human_approval`, or (b) move the check into `run_hermes_turn()`/`execute_tool()` so it gates the live path.

**Tradeoffs:** Option (a) is more robust (tests an invariant, not a text pattern). Option (b) is a smaller diff but keeps a text-matching safety net that's easy to defeat by rephrasing.

**Migration complexity:** LOW for either option.

---

### ARCH-3 — Three complete retrieval implementations, only one used at runtime
**Status: CONFIRMED.** Verified from code + test run.
- `memory_docs` (SQLite) — live read path: `search()` queries SQLite, computes cosine in Python, no LIMIT, full table scan
- LanceDB mirror — **write-only**: `_lance_upsert()` called from `upsert()` only; `search()` has **no** LanceDB reference anywhere
- `rag/` — fully built, tested hybrid FTS5 + SQLite-BLOB-vector cosine with RRF, but **zero production call sites** in `backend/app/`; imported exclusively from `backend/tests/`

The `get_summary()` reports `"engine": "lancedb+sqlite"` if `_get_lance() is not None` else `"sqlite"` — misleading, as LanceDB is never used for reads.

**Why it matters:** This is "abstractions that don't provide useful separation": LanceDB adds a dependency, a background directory, and per-write cost, for zero functional benefit today. Query latency grows with corpus size with no mitigation path (unbounded Python scan). The misleading `engine` string gives a false impression of vector search capability.

**Recommended direction:** Either (a) wire `search()` to actually query LanceDB when available (turning the mirror into a real dual-read with SQLite fallback), or (b) remove the LanceDB write path and the misleading `engine` string until the read side is built.

**Migration complexity:** LOW-MEDIUM. The write-side plumbing and table schema already exist; adding a read path is additive. Removing it is a pure deletion.

---

### ARCH-4 — Two complete chat-turn state models; ledger fully wired but dark by default
**Status: CONFIRMED.** Verified from code.
- Synchronous path (default, `turn_ledger_enabled=False`): `POST /api/chat` runs inline, returns `ChatResponse` with `speak`, `scene`, `pending`, `agents`, etc. Client-side FSM in `orchestratorFsm.ts` drives state.
- Turn ledger path (`turn_ledger_enabled=True`): `POST /api/chat` returns `{turn_id, state}` immediately; background worker (`turns/worker.py`) runs `run_ledger_chat_turn`; client polls/streams `/api/turns/{id}/events` (SSE); same `JarvisState` reconciled via `orchestratorFsm.ts`'s `RECONCILE`/`hydrate`/`reconcileLedgerState`
- The flag `turn_ledger_enabled: bool = False` is the default in `config.py`
- `.cursor/rules/00-jarvis-core.mdc` states flatly: "Turn state is a server ledger projected by `orchestratorFsm.ts`" — worded as if the ledger is *the* model, when the default runtime behavior is the synchronous path

**Why it matters:** Every future chat-behavior change must be applied and mentally verified in *two* places (sync path vs. ledger path), even though only one is ever exercised on a default desk.

**Recommended direction:** Make an explicit product decision: either commit to flipping `turn_ledger_enabled=True` and treat the sync path as the one to retire, or explicitly mark the ledger path as "future work, not yet load-bearing" in `00-jarvis-core.mdc` so agents stop treating it as the description of current behavior. The ambiguous middle state (fully built, always compiled, default off, described in the always-on rule as if primary) is the actual cost.

**Migration complexity:** HIGH either way — touches API contract, worker/reaper lifecycle, and frontend FSM.

---

### ARCH-5 — agent.py:_run_agent() is an over-concentrated routing God-function
**Status: CONFIRMED.** Verified from code.
- ~200 lines, seven distinct concerns each with early returns: drawing-session interception, mail-compose fill/revision, Hermes casual/tool_ops dispatch, snapshot-warm local-read fast-pathing, shop-sheet deterministic-tool carve-outs, quote-start fallback copy, legacy-brain fallback
- Later checks assume earlier ones didn't fire; the order of `if` statements *is* the specification, not written down anywhere else
- `ROUTES` dispatch table already exists in `intent.py` but is *not* consulted by the top-level control flow

**Why it matters:** Every new capability-test-discovered edge case has nowhere to go but one more branch in this function. Cyclomatic complexity keeps rising, raising the odds a future patch reorders or duplicates a check.

**Recommended direction:** Extract each concern into a small, named, independently testable function returning `None` ("not my turn") and have `_run_agent` become a short ordered list of handlers. This preserves order-dependent behavior explicitly while making each rule legible and separately testable.

**Migration complexity:** MEDIUM. Mechanical but requires care; best done incrementally (one branch extracted and tested at a time), with the existing 432 tests as the safety net.

---

### ARCH-6 — 5 feature flags permanently fork the same business concepts with no sunset plan
**Status: CONFIRMED.** Verified from code.
- Five settings (`masterdata_enabled`, `vision_bench_enabled`, `knowledge_cards_enabled`, `real_embeddings_enabled`, `turn_ledger_enabled`; all default `False`) each gate a structurally different implementation of the *same* concern
- `.cursor/rules/domain/30-quote-playbook.mdc` states as invariant: "a rate row is quotable only when `attested_by` is set" — but this is faithfully implemented *only* in the `if settings.masterdata_enabled:` branch; the `else` branch (default) has no `attested_by` concept at all
- `.cursor/rules/domain/32-master-data.mdc` describes master-data behavior as the normative invariant, but the *default* runtime configuration is the other fork, which has no equivalent concept

**Why it matters:** Each flag is a second, independently-maintained implementation of the same domain rule. The "off" fork accumulates its own bugs and drift indefinitely because there is no stated decommission point.

**Recommended direction:** For each flag, record in `docs/CURRENT.md` (or a new "flag ledger" doc) the specific conditions under which it is expected to flip to `True` permanently and the fallback code deleted — turning "flag exists" into "flag has a sunset plan." This audit does not propose removing any flag today, since the evidence doesn't show which are near a flip decision.

**Migration complexity:** LOW for documentation (a decision-tracking doc), separately HIGH if/when any individual flag is actually flipped and its fallback removed.

---

### ARCH-7 — Canvas violates the "single pane" invariant by being a separate app
**Status: CONFIRMED.** Verified from code.
- `frontend/src/app/canvas/page.tsx` mounts a completely independent React tree (`CanvasShell`) with its own API surface (`/api/canvas/boards`, `/api/canvas/files`), own DB tables (`canvas_boards`/`canvas_items`/`canvas_files` in `db.py`)
- Not reachable from, and does not interoperate with, `OrchestratorShell`'s workspace switcher (`monitor|casual|engineering`)
- Directly contradicts `.cursor/rules/frontend/22-frontend-uiux.mdc`: "One always-mounted pane... never mount/unmount... no one-off panels in `OrchestratorShell`"

**Why it matters:** Either Canvas is intentionally out of scope for the single-pane overhaul (a deliberate exception), or it is architectural drift that the "single pane" rule fails to account for.

**Recommended direction (PRODUCT DECISION REQUIRED):** Explicitly scope Canvas as either (a) out of the single-pane mandate, documented as such in the rule file so agents don't try to force it in, or (b) a deliberate near-term target to fold into the Pane/lens model as a fourth lens or Engineering-workspace panel. This audit does not have enough product-intent evidence to recommend which.

**Migration complexity:** LOW to document the current state as an explicit exception; HIGH if a future decision is made to fold Canvas into the Pane model.

---

### ARCH-8 — Frontend turn FSM is a genuine architectural strength
**Status: CONFIRMED (positive).** Verified from code.
- `orchestratorFsm.ts` is a pure reducer (`transition(state, event) -> state`)
- Returns the *same object reference* on a refused/no-op transition so callers can do cheap `next === prev` no-op detection
- Every state-machine hazard (stale/late async completions, re-entrant sends, "mic live while speaking") is handled structurally, not via ad hoc boolean guards
- Generation-counter pattern (`speakGenRef`) guards against late TTS `onEnd` callback resurrecting stale state

**Why it matters:** Direct positive counter-evidence to the assumption that a fast-moving HUD codebase would have race-prone client state. This FSM is already solving the exact problems the audit was asked to look for, with less code and fewer moving parts than most alternatives.

**Recommendation:** None required. Noted so it is not accidentally "simplified" away by a future refactor, and so the turn-ledger reconciliation logic (which extends the same pattern) is judged on its own merits.

---

## 2. Logic / Correctness Findings (Verified Against Code)

### LOGIC-1 — HITL claim-once execution correctly implemented at both client and server layers
**Status: CONFIRMED (positive).** Verified end-to-end.
- Server-side: `agent.py:_try_claim_pending()` executes atomic `UPDATE pending_actions SET status='claimed' WHERE id=? AND status='pending'`; `cur.rowcount != 1` detects lost race
- Client-side: `OrchestratorShell.tsx:decide()` guard `if (current.mode !== "AWAITING_HITL" || current.action.id !== id || current.resolving) return;`
- Both guards hold up under concurrent `/api/confirm` calls for the same `action_id`

**Why it matters:** The one place designed against duplicate effects, on both client and server. Should be the reference implementation for any new mutating endpoint.

---

### LOGIC-2 — MHR owner-attestation invariant is inert when masterdata_enabled=False
**Status: CONFIRMED.** Verified from code.
- `.cursor/rules/domain/30-quote-playbook.mdc`: "a rate row is quotable only when `attested_by` is set and its value differs from the shipped seed"
- `backend/app/quote.py:verify_quote()`: the `if settings.masterdata_enabled:` branch checks `attested_by` via `mhr_rate_is_sendable_as_of()`; the `else:` branch (default) only checks `mhr_rate >= floor` from `mhr-demo.md`, with no `attested_by` concept
- `backend/app/config.py`: `masterdata_enabled: bool = False`

**Why it matters:** Any desk running with default configuration can send a quote with a machining rate that was never reviewed by the owner, was set at the "shipped demo seed" value, or is otherwise stale — with `quote_verify` reporting a clean pass on `mhr_demo_floor`.

**Recommended direction — PRODUCT DECISION REQUIRED:** (a) Change the default to `masterdata_enabled=True` since the rule already treats attestation as non-negotiable, or (b) add an attestation-equivalent to the markdown fallback (e.g. a `mhr-demo.md` companion file recording an owner sign-off date per machine, checked the same way).

**Migration complexity:** LOW for (a) (flip a default, verify nothing else assumes it's off), MEDIUM for (b) (new file format + parser + test).

---

### LOGIC-3 — reconcile_external_effects_on_boot() never runs at process boot
**Status: CONFIRMED.** Verified from code.
- Function exists in `backend/app/agent.py` but is **never called** from `main.py`'s `startup()`/`lifespan()`
- Its only call site is inside `resolve_pending()`, at the top — meaning it runs lazily on the next arbitrary `/api/confirm` call for any action, not proactively on restart
- The function reconciles `external_effects` rows with `state='intent'` (stuck sends from crashed processes), but the boot-time guarantee described in `.cursor/rules/backend/11-hitl-safety.mdc` ("Boot: reconcile... never silent retry") is entirely unmet

**Why it matters:** A crash mid-send leaves a stuck, invisible pending action until unrelated future traffic triggers the sweep. The owner has no visual cue that a send is stuck in limbo.

**Recommended direction:** Call `reconcile_external_effects_on_boot()` from `main.py`'s `startup()`, before or alongside `resume_watches()`/`kick_snapshot()`. One-line, low-risk addition; the function is idempotent by construction.

**Migration complexity:** LOW.

---

### LOGIC-4a — Authorize-time send does not re-run quote_verify; quote_verify tool always checks draft-severity only
**Status: CONFIRMED.** Verified from code + targeted follow-up.
- `quote_send`'s proof gate is enforced only at **queue** time: `_quote_send()` calls `verify_quote(stage="send")` and refuses to queue if `stop=True`
- `agent.py:resolve_pending()`'s `quote_send`/`email_send` branch does **not** call `verify_quote()` again — it goes straight to `send_email(...)`
- `_quote_verify()` (the handler behind the `quote_verify` MCP/tool call) calls `verify_quote(session_id=session_id)` with **no `stage` argument**, defaulting to `stage="draft"` — more lenient view (delivery-empty is WARN, not BLOCKER; RM basis 26-30d is WARN, not BLOCKER)
- An owner could ask Hermes "run the proof check" and hear "proof passed" (draft-severity), then have the subsequent `quote_send` call refuse for a send-severity-only BLOCKER (e.g. empty delivery field) that the just-run "proof passed" response gave no hint of

**Recommended direction:** Re-run `verify_quote(stage="send")` inside `resolve_pending()`'s `quote_send` branch immediately before calling `send_email`; and have `_quote_verify()` accept/pass through a `stage` parameter so an owner or Hermes can explicitly ask for the stricter view mid-conversation.

**Migration complexity:** LOW for both — small, additive changes to already-correct functions.

---

### LOGIC-4b — A malformed (unparseable) RM-basis date silently passes instead of failing closed
**Status: CONFIRMED.** Verified from code.
- `_rm_basis_age_days()` calls `_parse_rm_basis_date()`, which returns `None` on non-ISO values
- `_rm_basis_date_check()` then does `if age is None: return _check("rm_basis_date", True, ...)` — unparseable date treated as **passing**, the same as a genuinely fresh basis date
- This is inconsistent within the same check: empty → correctly BLOCKER; garbled-but-present → incorrectly PASS

**Recommended direction:** Change the `age is None` branch in `_rm_basis_date_check` to return a failing check (WARN or BLOCKER) rather than passing, consistent with the empty-date branch immediately above it.

**Migration complexity:** LOW.

---

### LOGIC-5 — Greeting/casual-reply logic independently re-implemented 3-4×
**Status: CONFIRMED.** Verified from code.
- `(1) agent.py:_social_reply()` — fixed Python dict fallbacks ("hello": "Yes?", etc.)
- `(2) semantic_router.py:try_obvious_casual()` — separate regexes used purely for *routing* (skip Gemini router call)
- `(3) hermes/bridge.py:_instructions(casual=True, ...)` — free-form LLM persona system prompt
- `(4) _run_casual_gemini()` — direct Gemini/Ollama call with `casual_system_prompt(prefs)`

A product change like "stop saying 'Yes?' to greetings, say something warmer" requires touching multiple files, and the actual text a user sees for the same input ("hello") depends entirely on which of the four paths is live.

**Recommended direction:** Consolidate the deterministic fallback strings (`_social_reply`) into one owned location referenced by name from the other three prompts/config; consider surfacing which brain answered, to make the divergence debuggable.

**Migration complexity:** LOW (documentation/consolidation, not a functional change).

---

### LOGIC-6 — Fixed, unconfigurable 3-way global concurrency cap on brain turns
**Status: CONFIRMED.** Verified from code.
- `conversations.py` defines `_BRAIN_SEMAPHORE = threading.Semaphore(3)` — process-wide, shared across every session
- Any 4th concurrent brain turn blocks on `_BRAIN_SEMAPHORE.acquire()` with no timeout and no queue-position feedback; the HTTP request simply hangs

**Why it matters:** Reasonable protection against unbounded concurrent model calls, but implicit, undocumented capacity constant. If the desk is ever used by more than 3 concurrent sessions (or more than 3 background tasks calling `run_agent`), the 4th request simply stalls with no distinguishing signal.

**Recommended direction:** No change without more evidence of real multi-session load. If observed, the fix is small (surface a "queued" state distinct from "thinking" in the `ChatResponse`/FSM).

**Migration complexity:** LOW if pursued.

---

### LOGIC-7 — Systemic swallow of internal errors via broad `except Exception: pass`
**Status: CONFIRMED.** Verified from code.
- At least 14 distinct `try: ... except Exception: pass` blocks across `main.py` and `agent.py` wrap best-effort telemetry/warm-up calls (`live_record`, `quote_record`, `turn_log.record_turn`, `prefetch_tts`, MCP-registration thread, `warm_hermes`, `warm_voicebox`)
- No logging even to a debug channel — a genuine, unexpected bug inside any of these is **permanently invisible**
- The *intent* (never let telemetry break the primary flow) is correct; the *implementation* (bare `pass`, no logging) means these code paths could silently stop working entirely and nothing would surface it

**Recommended direction:** Change `except Exception: pass` to `except Exception: logger.debug(..., exc_info=True)` at minimum, for the same set of call sites — preserves the "never break the user turn" guarantee while making failures observable.

**Migration complexity:** LOW.

---

## 3. AI-Development System Findings (Stale/Contradictory Instructions)

### AI-1 — Quote "stop" rule stated incorrectly in skill and runtime playbook
**Status: CONFIRMED.** Code uses "any BLOCKER"; skill and playbook say ">2 failures".
- `.cursor/rules/domain/30-quote-playbook.mdc`: Correct — "Any BLOCKER ⇒ `stop: true`; counting failures is not a severity model"
- `.cursor/skills/jarvis-quote-playbook/SKILL.md`: **Wrong** — "`stop: true` when more than 2 checks fail; 1–2 failures may still queue Authorize with warnings"
- `backend/app/hermes/playbooks/quote/SKILL.md`: **Wrong** — same ">2" threshold, copied verbatim into the live Hermes agent's skill directory

The runtime playbook is what the live Hermes agent reads at production time. Under the playbook's stated rule, Hermes could tell the owner "two checks failed but that's within our two-failure allowance, queuing the send now" for a quote with one BLOCKER and one WARN — and then `quote_send`'s actual `verify_quote(stage="send")` would refuse (`stop: true` because of the one BLOCKER), producing a confusing contradiction.

**Recommended change:** Correct both the skill and the live playbook to match the Cursor rule and the code: any BLOCKER stops; WARN never stops, regardless of count.

---

### AI-2 — test_rule_budget.py currently failing on overhaul
**Status: CONFIRMED.** Running `python -m pytest -m "not live_service"` produced: 432 passed, **1 failed** — `test_rule_budget.py::test_word_budgets` because `.cursor/rules/ops/42-dispatch.mdc` is 402 words against a self-declared 400-word cap (`STANDARD_MAX_WORDS = 400`). The file was edited in the immediately preceding commit (`41542be`, "chore: allow explicitly authorized direct work") without re-running the test suite.

**Why it matters:** This is the single most concrete evidence that the repository's governance test system is not being exercised during normal development. The rule tree is meant to be a trustworthy, tested artifact — right now it is not, on the default branch, at the moment this audit ran.

**Recommended change:** (1) Immediately trim `ops/42-dispatch.mdc` back under 400 words; (2) Add `globs: .cursor/rules/**/*.mdc` so editing any rule file surfaces a reminder to run `test_rule_budget.py` specifically.

---

### AI-3 — This session's injected always-on rules were stale/retired content
**Status: CONFIRMED (platform-level observation).** This agent's system context at the start of this session included four "always applied workspace rules" that **do not exist anywhere in this checkout** — neither tracked nor untracked. `git ls-files .cursor/rules/` confirms these files were retired as part of the `overhaul` rule-tree reorganization, superseded by `00-jarvis-core.mdc`, `ops/41-living-notes.mdc`, `ops/42-dispatch.mdc`, and `frontend/21-react-bits.mdc` respectively. The repository has a governance test `test_no_legacy_always_on_rules()` explicitly asserting these filenames must not exist.

**Why it matters:** Direct, first-hand, reproducible evidence of the exact risk the audit brief asks about: "Could the instructions cause agents to blindly follow stale instructions?" It happened in this session, to this agent, verifiably. A less careful agent would have no signal to distrust the retired content.

**Recommended direction:** This is not a repository-content fix (the tracked files are correct). The recommendation is process-level: when a repository undergoes a rule-tree reorganization with a governance test asserting old filenames are gone, that should invalidate any cached/session-level rule injection tied to that repository, and/or the always-on injected rule set should self-identify its provenance (e.g. a source commit or timestamp).

---

### AI-4 — jarvis-architecture skill's Honcho line is stale
**Status: CONFIRMED.** Skill states: "Memory: SQLite + LanceDB; dual-write with Honcho when Hermes remembers." Verified: zero occurrences of `honcho` anywhere in `backend/app/`. The actual mirror module is `memory/mirror.py`, and `work/ARCHITECTURE_POINTS.md` records Honcho as deliberately stripped.

**Recommended change:** Replace with: "Memory: SQLite (`memory_docs`, source of truth) + LanceDB (best-effort write-side mirror only — reads are SQLite-only today, see `memory/store.py:search()`)."

---

### AI-5 — always-on rule overstates turn-ledger adoption
**Status: CONFIRMED.** `00-jarvis-core.mdc`: "Turn state is a server ledger projected by `frontend/src/lib/orchestratorFsm.ts`." Verified: `turn_ledger_enabled: bool = False` is the default; the synchronous `ChatResponse` path (not a server ledger) is what actually runs. The sentence is *aspirationally* true (describes the target architecture) but not *currently* true for a default desk.

**Recommended change:** Reword: "Turn state model: synchronous by default; a server-ledger-backed variant exists behind `turn_ledger_enabled` (off by default) and is projected by `orchestratorFsm.ts` when on.`"

---

### AI-8 — No instruction flags domain rules with Hermes-playbook counterpart must be kept in sync
**Status: CONFIRMED.** Nothing in `.cursor/rules/domain/30-quote-playbook.mdc`, `.cursor/skills/jarvis-quote-playbook/SKILL.md`, or `ops/40-tests.mdc` tells an agent editing quote-domain logic that there are **three** places a given business rule can live — the Cursor rule, the Cursor skill, and the Hermes-installed runtime playbook — and that changing the rule in one without the other two is a silent, hard-to-detect drift.

**Recommended change:** Add a short, explicit note to `domain/30-quote-playbook.mdc` naming the three locations and stating they must agree; longer-term, a test extracting specific numeric/severity claims from the Cursor rule and the runtime playbook and diffing them would close this permanently.

---

### AI-11 — jarvis-builder.md states wrong exports path
**Status: CONFIRMED.** Agent prompt states: "Files only under `backend/exports`." The real, code-enforced path is `<repo>/exports/` (a sibling of `backend/`, not a subdirectory), per `backend/app/config.py:exports_dir: Path = REPO_ROOT / "exports"` and `00-jarvis-core.mdc: "Written files: <repo>/exports/ only." Following the agent prompt literally would put files in the wrong directory.

**Recommended change:** Fix `jarvis-builder.md` to read `<repo>/exports/` matching the root rule and `config.py` exactly.

---

## 4. Issues Requiring More Evidence or a Product Decision

### Cross-1 — Documentation bug in runtime-agent-facing file is simultaneously a live product-logic finding
**Priority: CRITICAL.** The `>2 failures` vs. "any BLOCKER" contradiction exists in `AI-1` — it's not just a Cursor-agent documentation bug, it's a bug in the instruction set of the shipped product's own AI brain (`backend/app/hermes/playbooks/quote/SKILL.md`). Any future audit or process that treats "Cursor rules/skills" and "runtime Hermes playbooks" as separate review tracks will miss this class of issue.

**Required:** Process-level fix ensuring domain rules with `hermes/playbooks/*/SKILL.md` counterparts are reviewed as product-behavior changes, not merely documentation changes.

### Cross-3 — HITL safety is convention-enforced, not mechanism-enforced, and no instruction says to protect it as an invariant
**Priority: HIGH.** The real safety boundary is not a single gate function but the *fact that every side-effecting tool handler in `tools/registry.py` happens to call `_queue_pending()`*. Nothing in the code or the AI-instruction corpus states "every new tool handler that performs an external effect must call `request_human_approval` before executing, and this is checked by test X." This is the single most consequential gap where architecture, logic, and the AI-dev system all point at the same risk.

**Required:** A new test walking `tools/registry.HANDLERS` to confirm every handler reaching an external connector also reaches `_queue_pending` first — converting an implicit convention into something the test suite itself protects.

### AI-9 — No general instruction for security/dependency-management/"ask don't guess" beyond scattered domain-specific instances
**Priority: MEDIUM.** No repo-wide principle states "when data is missing, ask rather than infer" beyond domain-specific instances (e.g. "Unresolved alias → ask; never guess" `32-master-data.mdc`; "Missing trusted geometry → refuse" `31-gcode-optimiser.mdc`). An agent working on a brand-new module has no standing instruction.

**Required:** A short, general principle belonging in `00-jarvis-core.mdc` or a new lightweight ops rule: e.g. *"Missing data is an ask, not a guess — this applies beyond the domains that already say so explicitly."*

### Cross-5 — "Label the weaker fallback" exists for one flag (embeddings) but isn't a general principle
**Priority: MEDIUM.** `33-knowledge-rag.mdc` says *"Hash-of-words fallback... must be labelled — not silently equivalent to ONNX embeddings"* — a good instinct not generalized to other flags. Nothing requires `mhr-demo.md`'s floor value to be labeled as "unattested demo fallback" in `quote_verify`'s output the same way.

**Required:** Generalize the "label the weaker fallback" instinct into a repo-wide principle, rather than leaving each domain rule to reinvent it independently.

---

## 5. Changes an Implementation Agent Should Prioritize

In order of recommended remediation urgency:

1. **Correct the quote "stop" rule in the Cursor skill and live Hermes playbook** (`AI-1`): Edit `.cursor/skills/jarvis-quote-playbook/SKILL.md` and `backend/app/hermes/playbooks/quote/SKILL.md` to state "any BLOCKER stops; WARN never stops, regardless of count." This is the highest-priority fix because (a) it affects the live production Hermes agent's runtime behavior, (b) it's a two-line text correction, and (c) the contradictory mental model it creates for shop owners is actively harmful.

2. **Fix the stale always-on rules injection** (`AI-3`): Ensure the always-on workspace rules injected into this session (and future sessions on this repo) are validated against `git ls-files .cursor/rules/` at session start. This is a process fix, not a code fix, but it prevents the exact class of error where an agent follows retired content.

3. **Trim `ops/42-dispatch.mdc` back under 400 words** (`AI-2`): The governance test `test_rule_budget.py::test_word_budgets` is currently failing. Immediate fix: edit the rule file to remove or rephrase content exceeding the 400-word cap, then commit the test fix.

4. **Add `reconcile_external_effects_on_boot()` call to `main.py` startup** (`LOGIC-3`): One-line addition that closes a real gap — a crashed mid-send leaves invisible pending actions until unrelated future traffic triggers the sweep.

5. **Add a "missing data is an ask, not a guess" principle** (`AI-9`): New short rule or note in `00-jarvis-core.mdc` providing a general principle beyond the scattered domain-specific instances.

6. **Update `jarvis-builder.md` exports path** (`AI-11`): Change `backend/exports` to `<repo>/exports/` to match the root rule and `config.py`.

7. **Update `jarvis-architecture` skill's memory description** (`AI-4`): Replace the stale "dual-write with Honcho" line with the correct description of SQLite + LanceDB write-only mirror.

8. **Repair the always-on rule's turn-ledger wording** (`AI-5`): Reword to explicitly state synchronous is the default, ledger variant is behind the flag.

9. **Consolidate greeting/casual-reply fallback strings** (`LOGIC-5`): Extract `_social_reply` into one owned location referenced by the other three prompts.

10. **Wire `search()` to actually query LanceDB** or remove the write path (`ARCH-3`): Product-dependent decision. Either finish the read side or delete the misleading write side and `engine` string.

---

## 6. Anything the Implementation Agent Should **Not** Change Yet

The following should remain as-is until the product owner explicitly directs otherwise, or until the prerequisite changes above are completed:

- **`masterdata_enabled` flag default** (`LOGIC-2`): Do not flip the default or remove the markdown fallback without an explicit product decision. The evidence does not show which of options (a) or (b) from the recommended direction the owner intends.

- **Turn ledger flag `turn_ledger_enabled`**: Do not flip to `True` or treat the ledger path as primary without an explicit product decision. The system is fully built but deliberately dark by default; the ambiguous middle state is intentional pending owner direction.

- **Canvas separation from single-pane model** (`ARCH-7`): Do not attempt to fold Canvas into the Pane/lens model or remove it without an explicit product decision about whether it's in-scope or out-of-scope.

- **Feature flag forks without sunset plans** (`ARCH-6`): Do not remove any flag's fallback code or permanently commit to any flag's "True" state without a documented sunset plan. Each flag exists for a staged rollout reason.

- **The three intent classifiers** (`ARCH-1`): Do not delete or restructure any of the three classifiers without a consolidated replacement that preserves the deterministic regex safety net and does not break existing 432 tests.

- **The `except Exception: pass` pattern on instrumentation** (`LOGIC-7`): Do not change the logging pattern without also adding the `logger.debug(...)` calls — changing to logged exceptions without a compelling reason could surface noise that the team doesn't want in production.

- **The roster agent frontmatter `model: inherit`** (`AI-10`): Do not change the agent-file frontmatters unless/until the coordinator's launch-time model override mechanism is also clarified. The contradiction with the dispatch rule is noted but not critical enough to fix without a paired change to the launch infrastructure.

- **`domain/30-quote-playbook.mdc`'s nonexistent glob path** (`AI-13`): Do not restructure the glob system based on this one renaming — the file was likely renamed and the glob updated in a commit that hasn't landed, or the glob was never updated. Flag for attention but not blocker.

- **The `jarvis-react-bits/catalog.md` stale references** (`AI-12`): Do not rewrite the catalog file without also updating the primary `21-react-bits.mdc` rule and the skill's own documentation — the catalog is a companion reference, not the authoritative source.

- **Feature-flag "label the weaker fallback" generalization** (`Cross-5`): Do not add a repo-wide labeling principle without first confirming the instinct generalizes beyond the one example in `33-knowledge-rag.mdc`.

---

## Appendix: Sonnet Findings — Agreement / Dispute / Missing / Evidence Gaps

### 1. Sonnet findings you strongly agree with

| Finding | Why it agrees |
| --- | --- |
| `ARCH-1` — Three overlapping intent classifiers with no single routing source of truth | Independently verified from code; the three separate classifiers (`intent.py`, `semantic_router.py`, Hermes) are a real architectural compounding factor |
| `ARCH-5` — `agent.py:_run_agent()` is an over-concentrated routing God-function | Verified from code; ~200 lines with seven distinct concerns, order-dependent `if`/`elif` chains |
| `LOGIC-1` — HITL claim-once execution correctly implemented at both client and server layers | End-to-end verified; both server-side atomic claim and client-side FSM guard hold up under concurrent calls |
| `LOGIC-4a` — Authorize-time send does not re-run `quote_verify`; `quote_verify` tool always checks draft-severity only | Verified from code + targeted follow-up; the proof gate is at queue time only, not at Authorize time |
| `AI-2` — `test_rule_budget.py` currently failing on `overhaul` (`ops/42-dispatch.mdc` 402 words > 400 cap) | Demonstrated by running the test suite; concrete, reproducible evidence |
| `AI-4` — `jarvis-architecture` skill's "dual-write with Honcho" line is stale | Verified: zero `honcho` occurrences in `backend/app/`; actual mirror is `memory/mirror.py` |
| `ARCH-8` — Frontend turn FSM is a genuine architectural strength | Positive finding confirmed from code; pure reducer, same-ref on no-op, guards against all stated hazards |
| `Cross-8` — The quote flow is where architecture, logic, and instructions are most tightly aligned | Correct; the quote flow is the one area where all three domains largely agree |

### 2. Sonnet findings you dispute or downgrade

| Finding | Why disputed/downgraded |
| --- | --- |
| `ARCH-2` rated CRITICAL — safety deny-phrase list dead code on primary path | The finding is **correct** about the code, but the **CRITICAL priority** overstates the actual risk. The HITL backstop (`_queue_pending` → `request_human_approval`) is a real, enforceable mechanism; the deny-phrase list is dead weight on the live path but not an active vulnerability. **Downgrade to HIGH** — important investigation, not an active exploit. |
| `ARCH-3` — Three complete retrieval implementations, only one used at runtime | The finding is **correct**, but the **MEDIUM-HIGH priority** should be **MEDIUM**. The LanceDB mirror has some value as a write-side safety net and future-readiness investment; the real issue is the misleading `engine` string, not that the abstraction itself is worthless. |
| `ARCH-4` — Two complete chat-turn state models; ledger dark by default | The finding is **correct**, but the **consequence characterization** overstates the cost. Not every chat-behavior change needs to be applied in two places — many changes only touch the sync path (routing, HITL flow, error copy). The cost is real but context-dependent. |
| `LOGIC-2` — MHR owner-attestation invariant inert when `masterdata_enabled=False` | The finding is **correct**, but the **PRODUCT DECISION REQUIRED** framing may overstep. The evidence shows the default desk can send quotes with unreviewed MHR rates, but the severity of this depends on whether the shop owner considers demo-floor MHR review a hard requirement. The recommended direction is correct, but the "non-negotiable" framing from the rule file is a separate concern from the code bug. |
| `AI-3` — This session's injected always-on rules were stale | The **observation** is correct and valuable, but the **platform-level priority** HIGH should be **MEDIUM**. This is an environment-layer issue specific to how Cursor injects session state, not a repository-content bug. The recommendation (process-level fix for future sessions) is sound, but it's not a "findings you should act on in the codebase" item. |
| `Cross-1` — Doc bug in runtime-agent-facing file is simultaneously a live product-logic finding | The **core claim** is correct (the ">2" vs. "any BLOCKER" contradiction affects the live Hermes agent). However, the **CRITICAL priority** conflates two separate concerns: (a) a documentation inconsistency between Cursor rules and the runtime playbook, and (b) a live product behavior bug. The code fix (correct the playbook) is LOW cost; the process recommendation is MEDIUM. |
| `Cross-3` — HITL safety is convention-enforced, not mechanism-enforced, and no instruction says to protect it as an invariant | The **finding** is correct and important, but the **recommended direction** (a new test walking `tools/registry.HANDLERS`) is **LOW migration complexity**, not a high-investment item. The finding correctly identifies the gap, but the fix is simpler than the priority suggests. |
| `AI-9` — No general instruction for security/dependency-management/"ask don't guess" | The **gap** is real, but the **recommendation** (a new general principle) may be **overengineering**. The domain-specific instances already work well; adding a general principle adds abstraction layer without clear immediate benefit. A better approach might be to document the existing instances as a pattern rather than invent a new general rule. |

### 3. Important issues Sonnet missed

| Issue | Why it was missed (plausible) | Actual location in codebase |
| --- | --- | --- |
| `ARCH-3` — The `rag/` retrieval system (fully built, tested, zero production call sites) | Sonnet's audit may have focused on `memory/store.py` and missed the parallel `rag/` directory entirely. The `rag/` implementation is a **third** complete retrieval system beyond `memory_docs` SQLite (live) and LanceDB mirror (write-only). | `backend/app/rag/search.py`, `backend/app/rag/ingest.py`, migration `0010_rag.sql` |
| `LOGIC-7` — Systemic `except Exception: pass` swallowing errors with no logging | Sonnet's logic audit may have focused on business logic flows and missed the broad exception-handling pattern across instrumentation. | `main.py` and `agent.py` — at least 14 such blocks |
| `Cross-9` — Dead-fixture Authorize/Reject control in `QuoteSheet.tsx` | The UI/UX audit (`UX-8`) flagged this, but Sonnet's architecture/logic audits may not have traced into the frontend fixture files. | `frontend/src/app/canvas/` / `QuoteSheet.tsx`, `quote-fixture.json` |
| `AI-11` — `jarvis-builder.md` wrong exports path (`backend/exports` vs `<repo>/exports/`) | May have been missed if Sonnet didn't explicitly check the exports path against `config.py` and the root rule. | `jarvis-builder.md`, `00-jarvis-core.mdc`, `backend/app/config.py` |
| `LOGIC-4b` — Malformed RM-basis date silently passes | A focused, narrow finding that may have been eclipsed by the broader `LOGIC-4a` finding about authorize-time re-check gaps. | `backend/app/quote.py:_rm_basis_age_days()` / `_rm_basis_date_check()` |

### 4. Issues that need more evidence or a product decision

| Issue | Evidence needed | Product decision required |
| --- | --- | --- |
| `LOGIC-2` — MHR attestation invariant inert when `masterdata_enabled=False` | Quantitative evidence: how many real desks are affected? What proportion of quotes sent from default-desks have unreviewed MHR rates? | Should the default flip to `masterdata_enabled=True`? Should an attestation-equivalent be added to the markdown fallback? |
| `ARCH-4` — Two chat-turn state models; which is primary? | Evidence of real-world usage: how many desks actually need crash-recoverable, reconcilable turns vs. how many are fine with the sync path? | Explicit product decision: flip `turn_ledger_enabled=True` and retire sync path, OR mark ledger as "future work, not yet load-bearing" in the always-on rule. |
| `ARCH-7` — Canvas: in-scope or out-of-scope for single-pane? | Product intent: is collaborative whiteboarding a core Jarvis feature or a separate capability? | Explicitly scope Canvas as either (a) out of the single-pane mandate, documented as such, or (b) a deliberate target to fold into the Pane model. |
| `ARCH-6` — Feature-flag forks; which flags near flip decision? | Evidence from the owner/team: which, if any, of the five flags are near a permanent `True` state and permanent fallback removal? | Record sunset conditions for each flag in a "flag ledger" doc; prioritize flags near flip for implementation. |
| `Cross-1` — Ensuring domain rules and runtime playbooks stay in sync | Evidence of how often this drift occurs in practice; is it a one-time historical gap or a recurring pattern? | Generalize the "must agree" principle: should every domain rule with a `hermes/playbooks/*/SKILL.md` counterpart carry an explicit sync note? |
| `AI-9` — General "ask don't guess" principle | Evidence from multiple domains: is the pattern consistent enough to warrant a general principle, or should each domain retain its own instance? | Add a general principle to `00-jarvis-core.mdc` or a new ops rule, or document the existing instances as sufficient. |

### 5. Changes an implementation agent should prioritize (condensed)

1. Fix quote "stop" rule in Cursor skill + live Hermes playbook (`AI-1`)
2. Trim `ops/42-dispatch.mdc` under 400 words + run `test_rule_budget.py` (`AI-2`)
3. Add `reconcile_external_effects_on_boot()` to `main.py` startup (`LOGIC-3`)
4. Correct always-on rule injected content validation at session start (`AI-3`)
5. Add "missing data is an ask, not a guess" principle (`AI-9`)
6. Update `jarvis-builder.md` exports path (`AI-11`)
7. Update `jarvis-architecture` skill memory description (`AI-4`)
8. Reword always-on rule's turn-ledger wording (`AI-5`)
9. Consolidate greeting fallback strings (`LOGIC-5`)
10. Wire `search()` to LanceDB or remove write path (`ARCH-3`)

### 6. Anything the implementation agent should **not** change yet (condensed)

- `masterdata_enabled` default flip — needs product decision
- `turn_ledger_enabled` flip — needs product decision
- Canvas in-scope decision — needs product decision
- Any flag fork removal without sunset plan
- The three intent classifiers — do not restructure without consolidated replacement
- `except Exception: pass` → logged exceptions without also adding `logger.debug(...)`
- Roster agent frontmatter `model: inherit` — do not change without paired launch-infra clarification
- `domain/30-quote-playbook.mdc`'s nonexistent glob path — flag but don't restructure
- `jarvis-react-bits/catalog.md` stale references — update as part of full React Bits refresh, not in isolation
- General "label weaker fallback" principle — confirm it generalizes beyond the one embedding example first