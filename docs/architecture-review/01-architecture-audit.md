# Architecture audit

**Scope:** Independent verification of module boundaries, dependency direction, coupling/cohesion, and structural risk in the Jarvis backend (`backend/app/`) and frontend (`frontend/src/`), on branch `overhaul` at commit `41542be` (rechecked live at the time of this audit; see "Verification method").

**Method:** This document does **not** carry forward conclusions from `docs/architecture-review/00-*.md` without independent verification. Every finding below cites the actual file and code read during this pass. Where the recon docs' claims were checked and found *inaccurate or incomplete*, that is stated explicitly (see "Corrections to prior reconnaissance"). Where a recon claim was checked and confirmed, it is cited as confirmed, not repeated as new.

**Priority legend** (investigation/remediation priority, not a quality score):

| Priority | Meaning |
| --- | --- |
| CRITICAL | Structural risk with plausible path to money/safety/trust failure, or actively breaks a stated invariant |
| HIGH | Significant, verified structural cost or gap; not actively on fire but expensive to leave |
| MEDIUM | Real but bounded cost; worth planning for, not urgent |
| LOW | Hygiene / clarity; low blast radius |

---

## Corrections to prior reconnaissance

Before presenting new findings, three claims in `00-*.md` were checked directly and found to be **wrong or overstated**. Calling these out matters because the AI-development system explicitly asks future agents to treat living docs as authoritative — these are exactly the kind of stale claim that would misdirect a future agent if not corrected here.

1. **`live_service` pytest marker "not registered."** `00-ai-instruction-inventory.md` and `00-investigation-targets.md` (P3-1) state the marker is referenced by rules/skills but "not found in `conftest.py`." Verified: it **is** registered, in `/workspace/pytest.ini` (`markers = live_service: ...`), which is the idiomatic place for pytest marker registration — `conftest.py` was simply the wrong file to check. The marker is actively used in `backend/tests/test_stability_e2e.py` and `backend/tests/test_hermes_e2e.py`. **There is no drift here.** This investigation target should be closed, not pursued further.
2. **Talk-jump casual→engineering guard.** `00-investigation-targets.md` (P2-10) flags this as needing confirmation. Verified directly in `frontend/src/components/orchestrator/hudWorkspace.ts`: `talkJumpWorkspace()` opens with `if (current !== "monitor") return null;`, so the jump can only ever fire when the user is already on Monitor. From Casual or Engineering, quote/drawing words never auto-switch. **The implementation matches the documented lock exactly.**
3. **Honcho dual-write.** Confirmed no `honcho` string anywhere in `backend/app/` (grep), and `memory/mirror.py` is the actual local-upsert module. This matches the recon's own conclusion, but it's worth stating plainly here: **Honcho is fully gone from code**; the remaining risk is purely documentation staleness in `work/VISION_WORKBOOK.md` and `work/CAPABILITY_TEST_MATRIX.md`, which is an AI-development-system finding (see `03-ai-development-system-audit.md`), not an architecture finding.

One new, more consequential correction was found during this pass, not flagged in the recon docs at all:

4. **The repository's own rule-budget test is currently failing.** `python -m pytest -m "not live_service"` was run in full during this audit (432 passed, 1 failed, 11 deselected). The failure is `backend/tests/test_rule_budget.py::test_word_budgets`: `.cursor/rules/ops/42-dispatch.mdc` is 402 words against a self-declared 400-word cap. `git log` shows this file was edited in the immediately preceding commit (`41542be`, "chore: allow explicitly authorized direct work") without re-running the test suite. This is evidence, not speculation — see `03-ai-development-system-audit.md` for the full analysis; it is noted here because it means **the repository's default test run is currently red on `overhaul`**, which any architecture or logic finding below should be read in light of (a green baseline was not assumed).

---

## Finding ARCH-1 — Three independent, overlapping intent classifiers with no single source of routing truth

**Priority: HIGH**

**Finding.** A single user utterance can pass through up to three independent classification systems before Jarvis decides what to do with it: (a) `backend/app/intent.py:classify()` — a ~40-rule regex/heuristic engine producing an `Intent(kind=...)`; (b) `backend/app/semantic_router.py:classify_intent()` — a Gemini-structured-output classifier producing `IntentClassification(intent=ui_command|casual_chat|vision_task|tool_ops, target_agent=...)`, with its own parallel regex fallback (`_fallback()`) for when Gemini is unavailable; and (c) Hermes itself, an external LLM agent that makes its own tool-selection judgement once a turn reaches it. `agent.py:_run_agent()` then interleaves the outputs of (a) and (b) with more than a dozen `if`/`elif` branches (drawing-session override, `is_rfq_definition` special-case duplicated as an early check in both `intent.py` and re-imported into `semantic_router.py`, `is_quote_start` special-cased in three files: `intent.py`, `semantic_router.py`, and `hermes/bridge.py`).

**Evidence.**
- `backend/app/agent.py` lines ~1070–1256 (`_run_agent`): `route_intent = getattr(route, "intent", None)` (from semantic_router) is read, then `intent = classify(message)` (from intent.py) is computed separately, and the function branches on **both**, e.g. `if route_intent == "tool_ops": hit = _hermes_reply(...)` sits alongside `if local_fast and mail_pref_ok and _skip_brain(intent.kind, message): return _local_legacy()`.
- `backend/app/semantic_router.py` imports `is_rfq_definition` and `is_quote_start` directly from `intent.py` to keep its own classification consistent — a tacit admission that the two classifiers must agree on at least these two predicates, achieved by cross-importing rather than by there being one predicate owner.
- `backend/app/hermes/bridge.py:hermes_conversation_title()` and `_instructions()` **also** call `is_quote_start(message)` a third time, to decide which Hermes conversation thread to route into and what system prompt to send — the same predicate is now load-bearing in three different modules for three different decisions (Jarvis-side routing, Hermes-side routing, Hermes-side prompting).

**Why it matters.** For any bug report of the shape "Jarvis did the wrong thing for utterance X," a future agent (human or AI) must trace the utterance through `intent.py`, `semantic_router.py`, and then reconstruct what Hermes itself would plausibly have done with the resulting message — there is no single function that answers "what will Jarvis do with this text," only three functions whose interaction has to be read together. This directly matches the task's watch-list item "modules doing too many things" / "duplicated concept."

**Likely root cause.** Incremental evolution: `intent.py`'s comment block says outright "Hermes-first routing... When Hermes is available, run_agent owns judgment for almost everything. Jarvis keeps ONLY: tight mail_draft compose chrome... pending Authorize/drawing-session exceptions... this tiny safety deny surface." That comment describes an *intended* end state where `intent.py` is a thin residual. The semantic router was added later as a faster Gemini-based front door. Neither fully replaced the other, so both are now permanently load-bearing.

**Consequences if left unchanged.** Every new capability (a new intent kind, a new tool) has to be reasoned about across three decision points instead of one, and the cost compounds — this is precisely the "architecture that makes future features unnecessarily expensive" pattern called out in the audit brief.

**Recommended direction.** Consolidate to one routing decision per turn: let `semantic_router.classify_intent()` (already the fast, LLM-structured front door) own the full `Intent`-equivalent shape, and have `intent.py`'s regex rules become *helpers it calls*, not a second parallel classifier invoked independently in `agent.py`. `is_quote_start`/`is_rfq_definition` should have exactly one call site whose result is threaded through, not re-derived three times.

**Tradeoffs.** The regex layer in `intent.py` is valuable specifically because it is deterministic and testable without a model call (see `CASES` table at the bottom of the file, used for regression testing routing without any network dependency) — collapsing it entirely into the LLM router would remove that determinism. The right target is not "delete intent.py" but "make it a library, not a second decision-maker."

**Migration complexity: MEDIUM.** No schema change; this is a control-flow refactor inside `agent.py` plus a signature change to `semantic_router`. Behavior-preserving refactor is achievable with the existing `CASES` regression table as a safety net, but the branching in `_run_agent` (~200 lines) needs careful, incremental extraction, not a rewrite.

---

## Finding ARCH-2 — The safety deny-phrase gate does not gate the primary (Hermes) execution path

**Priority: CRITICAL (as an investigation/documentation priority — see mitigating control below)**

**Finding.** `backend/app/intent.py` defines `SAFETY_DENY_PHRASES` ("send without approval", "skip authorize", "bypass hitl", "auto send all mail", "delete all memory", "wipe all memory") with a comment describing it as "this tiny safety deny surface (phrases that must never auto-execute)." The check lives entirely inside `classify()`: `if any(phrase in low for phrase in SAFETY_DENY_PHRASES): return Intent("chat", query=text)`. Tracing every call site that can execute a tool:

- **Legacy/heuristic path** (`_run_agent_legacy` → `_heuristic_tools`/`_try_model_route`): does consult `classify(message)`, so a deny phrase here degrades to `Intent("chat")` and no tool fires. This path *is* gated.
- **Hermes path** (`agent.py:_run_agent`, the `if route_intent == "tool_ops": hit = _hermes_reply(force_casual=False)` branch): `route_intent` comes from `semantic_router.classify_intent()`, which is computed *before* `intent = classify(message)` is even assigned in the function, and the Hermes branch does not consult `intent.kind` at all — it calls `run_hermes_turn(message, session_id, ...)` with the **raw, unfiltered message**. `hermes/bridge.py:run_hermes_turn` / `_run_via_gateway` / `_run_via_cli` perform no deny-phrase check whatsoever; the message goes straight into the Hermes system prompt.
- Because `semantic_router.py`'s own classification is marker-based (`_WORK_MARKERS` includes "send", "authorize"), a phrase like *"send without approval"* is very likely to be classified `tool_ops` by the router's own fallback heuristic (`_fallback()`) even without Gemini, meaning this is not a hypothetical, hard-to-reach edge case — it is the router's normal behavior for message text containing common work-verb tokens.

**Mitigating control (why this is not immediately exploitable).** Every side-effecting tool exposed to Hermes goes through `backend/app/tools/registry.py:execute_tool()`, and every handler that performs an external effect (`_draft_email`, `_forward_email`, `_send_email`, `_create_calendar_event`, `_memory_forget` with `wipe_namespace=True`, `_quote_send`, shop-sheet writes) calls `_queue_pending()` → `hermes/hitl.py:request_human_approval()`, which only ever inserts a **pending, unexecuted** row (`db.add_pending(...)`) — it "Never executes connectors" (its own docstring). Actual execution only happens in `agent.py:resolve_pending()`, gated by the atomic claim described in `ARCH-2`'s sibling finding `LOGIC-1`. `mcp_server.py` (the Hermes-facing tool surface) does not even register a `jarvis_send_email` tool — only `jarvis_draft_email`, which always queues. So an utterance containing a deny phrase cannot, today, cause an unauthorized send purely because the deny-phrase check didn't fire — the HITL layer would still intercept it.

**Why it still matters at CRITICAL investigation priority.** The deny-phrase list is documented, in the file's own header comment and in `.cursor/rules/backend/11-hitl-safety.mdc` ("Safety deny-list: block tool names/paths that skip HITL for destructive or external ops"), as *the* safety surface for this class of phrase. It is not. The actual safety invariant — "every tool that performs an external or destructive effect must queue HITL, with no exceptions" — exists, but only as an implicit pattern followed by every handler in `tools/registry.py` today; it is not enforced by any test that walks the tool registry and asserts each side-effecting handler calls `_queue_pending`, and it is not what the deny-phrase code or its accompanying comments claim to be doing. A future contributor who adds a new Hermes-callable tool with a genuine bypass (e.g. a "quick reply" tool that calls `send_email` directly for speed) would have no deny-list, no test, and no rule to stop them — the current safety is a *convention*, not a *mechanism*, and the one piece of code that reads like a mechanism (the deny list) is dead weight for the path where it would matter most.

**Likely root cause.** `intent.py`'s own comments show self-awareness that Hermes routing was added *after* the deny-list existed ("Hermes-first routing (Aspect 7)... Legacy RULES below remain for Gemini/legacy fallback when Hermes is down") — the deny list predates Hermes-first routing and was never re-wired into the new primary path.

**Consequences if left unchanged.** Not an active vulnerability today (HITL backstops it), but a false sense of security in the code and in `.cursor/rules/backend/11-hitl-safety.mdc`'s wording, and a latent gap that a future "fast path" tool could silently open.

**Recommended direction.** Either (a) delete `SAFETY_DENY_PHRASES` and its `classify()` check as genuinely dead code, and instead add an automated test that asserts every handler registered in `tools/registry.HANDLERS` which performs a `connectors.*` call also calls `_queue_pending`/`request_human_approval` (turning the implicit convention into an enforced invariant), or (b) if the deny-phrase concept is wanted as defense-in-depth, move the check into `run_hermes_turn()` itself (or `execute_tool()`) so it actually gates the live path, not the path that is already fully superseded.

**Tradeoffs.** Option (a) is more robust (tests an invariant, not a text pattern that's trivially rephrased) but requires writing a registry-walking test. Option (b) is a smaller diff but keeps a text-matching safety net that is easy to defeat by rephrasing ("please forward this without needing my okay" would not match any current phrase).

**Migration complexity: LOW** for either option — this is a small, contained, well-testable change once the direction is chosen.

---

## Finding ARCH-3 — Memory/RAG system writes to two stores but only ever reads from one; the reported "engine" is misleading

**Priority: MEDIUM-HIGH**

**Finding.** `backend/app/memory/store.py` maintains `memory_docs` in SQLite as the source of truth and *also* best-effort mirrors every upsert into LanceDB (`_lance_upsert`). `search()` — the only read path used by the `memory_search` tool, the MCP tool `jarvis_memory_search`, and `rag/search.py`'s hybrid logic — queries **SQLite exclusively**: it `SELECT`s every row in the namespace (or the whole table if no namespace is given), computes `cosine(qvec, vec)` for each row **in Python**, sorts, and slices. LanceDB is never opened for a read anywhere in `backend/app/`. Despite this, `get_summary()` reports `"engine": "lancedb+sqlite" if _get_lance() is not None else "sqlite"` — i.e. it reports LanceDB as part of the active retrieval engine merely because the *connection* succeeded, not because it is used for anything beyond writes.

**Evidence.** `backend/app/memory/store.py`: `_lance_upsert()` is called from `upsert()` (write path) only; `search()` (lines ~130–174) has no LanceDB reference at all, only `db.connect()` + a Python-side `for row in rows: score = cosine(...)` loop with no `LIMIT` in the SQL — the full table (or full namespace) is loaded into Python memory before scoring on every single search call.

**Why it matters.** This is exactly the "abstractions that don't actually provide useful separation" pattern: LanceDB adds a dependency (`lancedb` optional import), a background directory (`data/memory/lancedb/`), and a per-write cost, for zero functional benefit today, while giving anyone reading `get_summary()`'s output (including the `memory_summary` tool result that could be surfaced to Hermes or the owner) a false impression that vector search is happening in a purpose-built vector engine. It also means the unbounded full-table Python scan is the *actual* performance ceiling for memory recall, which will degrade linearly as `corpus`/`profile`/`session` rows grow — with no index, no LanceDB ANN lookup, and no `LIMIT` in the SQL query itself.

**Likely root cause.** LanceDB integration was added defensively/optionally (the whole module wraps every Lance call in `try/except Exception: pass`, explicitly commented "Lance optional — SQLite remains source of truth") as a stepping stone toward real vector search, and the read side was never finished.

**Consequences if left unchanged.** Query latency grows with corpus size with no mitigation path already in place; the `real_embeddings_enabled` flag (ONNX embeddings) compounds this by making each row's vector larger without changing the O(n) scan cost. The misleading `engine` string could cause a future agent (or the product owner) to reasonably-but-wrongly conclude vector search is more capable than it is when deciding whether memory/RAG needs further investment.

**Recommended direction.** Either wire `search()` to actually query LanceDB when available (turning the mirror into a real dual-read with a fallback to the SQLite path when Lance is unavailable — consistent with the existing "SQLite remains source of truth for writes, Lance for scale-out reads" framing already implied by the code comments), or remove the LanceDB write path and the misleading `engine` string until the read side is built, whichever the product priority supports. **This is a case where the evidence supports "the abstraction is missing where it matters" (a real ANN read path), not "delete the abstraction"** — LanceDB was clearly chosen for a reason (scale), and the write-side plumbing already exists; finishing the read side is the smaller, less risky move.

**Tradeoffs.** Finishing the LanceDB read path adds a runtime dependency on an external table format actually being queried in the hot chat-turn path (latency, another failure mode to handle gracefully). Removing it is simpler but throws away completed work and removes the natural next step if RAG usage grows.

**Migration complexity: LOW-MEDIUM.** The write-side plumbing and table schema already exist; adding a read path is additive, not a rewrite. Removing it is a pure deletion.

**Update — independently confirmed and extended by a targeted follow-up pass.** A second, dedicated retrieval stack exists in parallel: `backend/app/rag/` (`rag/search.py:hybrid_search()` — FTS5 + SQLite-BLOB-vector cosine, fused with RRF — plus `rag/ingest.py`, backed by migration `0010_rag.sql`'s `rag_documents`/`rag_chunks`/`rag_fts` tables). This is a **third** storage/read mechanism beyond `memory_docs` (SQLite) and the LanceDB mirror described above. A repo-wide grep for `from .rag` / `from ..rag` / `from app.rag` confirms it is imported **exclusively from `backend/tests/`** (`test_hybrid_search.py`, `test_rag_eval.py`, `test_embedding_selector.py`) — **zero production call sites in `backend/app/`**. The live `memory_search` tool (`tools/registry.py:_memory_search`) calls `memory.search()`, not `rag.hybrid_search()`. So the codebase carries three complete retrieval implementations (`memory_docs`/SQLite cosine — live; LanceDB mirror — write-only, dead for reads; `rag_*`/hybrid FTS+vector — fully built and tested, but entirely unreached at runtime) for what is conceptually one capability. This raises this finding's priority: it is not just "the second store is write-only," it is "there is a third, complete, tested, unused implementation sitting next to the other two." Whether `rag/` is a deliberate future replacement for `memory/store.py` or an abandoned earlier iteration is not determinable from the code alone — **REQUIRES FURTHER INVESTIGATION / PRODUCT DECISION REQUIRED**: which of `memory/store.py` and `rag/` is meant to be the long-term retrieval system should be decided before either receives further investment, since maintaining both in a working, tested state indefinitely (as is happening now) doubles the cost of any future retrieval-quality change for no current runtime benefit.

---

## Finding ARCH-4 — Two complete, parallel "what is chat doing right now" models, one of them fully wired but dark by default

**Priority: HIGH**

**Finding.** There are two independent, fully implemented state models for a chat turn's lifecycle:

1. **Synchronous path** (default, `turn_ledger_enabled=False`): `POST /api/chat` runs the whole turn inline and returns a `ChatResponse` (`speak`, `scene`, `pending`, `agents`, ...). Client-side truth lives in `frontend/src/lib/orchestratorFsm.ts`'s `JarvisState` (`IDLE|LISTENING|THINKING|SPEAKING|AWAITING_HITL|EXECUTING`), driven purely by local events (`SEND`, `SPEAK_START`, etc.).
2. **Turn ledger path** (`turn_ledger_enabled=True`): `POST /api/chat` returns only `{turn_id, state}` immediately (`backend/app/main.py:api_chat`); a background worker (`turns/worker.py`) runs `run_ledger_chat_turn`; the client polls/streams `/api/turns/{id}/events` (SSE) and reconciles the *same* `JarvisState` via a **second, distinct code path**: `orchestratorFsm.ts`'s `RECONCILE`/`hydrate`/`reconcileLedgerState` functions, which map server `ServerTurn.state` (`QUEUED|RUNNING|AWAITING_HITL|EXECUTING|DONE|FAILED|ABANDONED`) onto the identical `JarvisState` union.

Both models are fully built end-to-end: reaper daemon (`turns/reaper.py`, started conditionally in `main.py`'s `lifespan` only `if settings.turn_ledger_enabled`), SSE streaming (`turns/events.py`), a dedicated `TurnStageLine` component, and `OrchestratorShell`'s `reconcileOpenTurn()` which runs unconditionally on every mount/focus regardless of the flag (it simply gets `{enabled: false, turns: []}` back from `/api/turns/open` and no-ops).

**Evidence.** `backend/app/config.py`: `turn_ledger_enabled: bool = False` with the comment "dark until HUD reconciles against server rows." `backend/app/main.py:api_chat` branches on the flag as its very first statement. `frontend/src/lib/orchestratorFsm.ts` contains a `hydrate()`/`reconcileLedgerState()` pair whose only caller in the shipped HUD is `reconcileOpenTurn()`, which is called unconditionally at bootstrap and on window focus (`OrchestratorShell.tsx`) — so this code runs on every page load, for a feature that is off by default, purely to discover it's off (`data.enabled` false) and no-op.

**Why it matters.** This is the single largest standing "abstraction that doesn't (yet) provide useful separation" in the codebase: it is not a small optional flag, it is two complete state machines, one backend worker subsystem, and one SSE transport, all of which any future change to "how does a chat turn state work" must be understood in light of, even though only one of the two is ever exercised on a default desk. `.cursor/rules/00-jarvis-core.mdc` (the one always-on rule) states flatly "Turn state is a server ledger projected by `orchestratorFsm.ts`" — worded as if the ledger is *the* model, when the default runtime behavior is the synchronous path.

**Likely root cause.** This reads as a deliberate, in-progress migration ("accept-then-work" architecture) that has not yet been switched on, consistent with `work/ARCHITECTURE_POINTS.md`'s framing of `overhaul` as an active transition branch.

**Consequences if left unchanged.** Every future chat-behavior change (routing, HITL wording, error copy) has to be applied and mentally verified in *two* places (`agent.py:_run_agent`/`run_ledger_chat_turn` both call the same `run_agent`, so the core logic is shared — but the surrounding lifecycle, error handling, and reconciliation are not) to avoid the two paths silently diverging. The rule wording actively risks agents optimizing for the ledger path as if it were primary, when it is not what a live desk actually runs.

**Recommended direction.** Make an explicit decision and record it as a `PRODUCT DECISION REQUIRED`: either commit a rollout date/criteria for flipping `turn_ledger_enabled=True` and start treating the sync path as the one to retire, or explicitly mark the ledger path as "future work, not yet load-bearing" in `00-jarvis-core.mdc` so agents stop treating it as the description of current behavior. Either is fine; the ambiguous middle state (fully built, always compiled, default off, described in the always-on rule as if primary) is the actual cost.

**Tradeoffs.** Committing to the ledger path gains genuine crash-recoverable, reconcilable turns (arguably a real robustness win per `backend/13-turn-ledger.mdc`'s stated goals) at the cost of the added SSE/worker/reaper operational surface. Reverting to sync-only would let a large amount of already-written code be deleted, simplifying the mental model, at the cost of losing the reconciliation robustness this was presumably built to solve.

**Migration complexity: HIGH** either way — this is not a quick fix; it touches the API contract, the worker/reaper lifecycle, and the frontend FSM's biggest and most carefully-commented code path.

---

## Finding ARCH-5 — `agent.py:_run_agent()` is an over-concentrated routing God-function

**Priority: MEDIUM**

**Finding.** `_run_agent()` (backend/app/agent.py, roughly lines 1050–1256, ~200 lines) is the single function responsible for: drawing-session interception, mail-compose fill-in/revision, Hermes casual/tool_ops dispatch with force-casual flags, snapshot-warm local-read fast-pathing, shop-sheet deterministic-tool carve-outs, quote-start fallback copy, and final legacy-brain fallback — seven distinct concerns, each with its own early-return, layered in a specific, load-bearing order (later checks assume earlier ones didn't fire). `route_for(kind).tools` (the `ROUTES` dispatch table already defined in `intent.py`) exists and is *sometimes* consulted (`_gate_calls`, `_try_model_route`) but the top-level control flow in `_run_agent` does not itself dispatch through that table — it is bespoke `if`/`elif` chains layered on top of it.

**Evidence.** Direct line-by-line read of `agent.py`'s `_run_agent`; comments within it ("Snapshot-warm read paths: local-first even when router says tool_ops (A14)", "Shop sheet reads/writes: deterministic tools own OEE — Hermes must not define it from memory", "Soft fallback / Hermes-down: definitional RFQ must be chat, never reason_rfq") each name a distinct historical bug-fix or product decision, encoded as one more branch in the same function.

**Why it matters.** Every one of those comments documents a *specific* incident-driven carve-out. That is a legitimate way to build a rules-based router incrementally, but the accumulation means the function's real behavior can only be understood by reading it top-to-bottom in order — the order of the `if` statements *is* the specification, and it is not written down anywhere else. This is the textbook "architecture that makes testing difficult" pattern: `backend/tests/` has good coverage of individual scenarios (432 passing tests), but the interaction *order* between these seven branches is implicit in the function body, so a change to branch 3 can silently change what branch 6 sees.

**Likely root cause.** Organic accretion of edge cases discovered through the capability-test process (`work/CAPABILITY_TEST_MATRIX.md`), each fixed as a targeted branch rather than a structural change, which is individually reasonable but compounds.

**Consequences if left unchanged.** Each new capability-test-discovered edge case has nowhere to go but one more branch in this function, and cyclomatic complexity keeps rising, raising the odds a future patch (by a human or an AI agent working file-locally without full context) reorders or duplicates a check.

**Recommended direction.** Extract each concern into a small, named, independently testable function returning either a `ChatResponse` or `None` ("not my turn to handle this"), and have `_run_agent` become a short ordered list of `for handler in HANDLERS: result = handler(...); if result is not None: return result`. This preserves the existing order-dependent behavior explicitly (order of the list) while making each rule legible and separately unit-testable without constructing the whole surrounding context.

**Tradeoffs.** This is a refactor with behavior-preservation risk if done carelessly — the existing 432 tests are the safety net, but some of the seven branches share mutable local state (`intent`, `hermes_last_error`) across branches in ways that would need explicit threading through the new handler signatures.

**Migration complexity: MEDIUM.** Mechanical but requires care; best done incrementally (one branch extracted and tested at a time), not as a single rewrite.

---

## Finding ARCH-6 — Feature flags fork the same business concept into two permanently-maintained implementations

**Priority: MEDIUM**

**Finding.** Five settings (`masterdata_enabled`, `vision_bench_enabled`, `knowledge_cards_enabled`, `real_embeddings_enabled`, `turn_ledger_enabled`; all default `False`) each gate a structurally different implementation of the *same* concern rather than a simple on/off feature: e.g. `quote.py:verify_quote()`'s customer-spelling check reads from `customer_aliases`/`customers` SQL tables when `masterdata_enabled` else parses `client-names.md` with a loose substring match (`norm in n.lower() or n.lower() in norm`); its MHR-floor check queries `machine_hour_rates` with `effective_from`/attestation semantics when enabled, else parses a static `mhr-demo.md` markdown table with no attestation concept at all (see `LOGIC-2` in `02-logic-audit.md` for the correctness consequence of this specific fork).

**Evidence.** `backend/app/quote.py:verify_quote()`, `build_quote()`, `_load_quote_rows()` all contain explicit `if settings.masterdata_enabled: ... else: ...` forks for customer name matching, MHR floor lookup, and quote-row persistence (SQL revision vs. session-memory JSON blob). `backend/tests/` does exercise the `True` branch for 5 of these flags in dedicated test files (`test_vision_consent.py`, `test_quote_revisions.py`, `test_machine_rates.py`, `test_routings.py`, `test_parties.py` for `masterdata_enabled`; 1 file for `vision_bench_enabled`; 3 for `knowledge_cards_enabled`; 2 for `turn_ledger_enabled`) — so this is **not** an untested-flag problem (a claim this audit explicitly avoids making without evidence); it is a **permanently-forked-implementation** problem.

**Why it matters.** Each flag is not a toggle for a small variance but a second, independently-maintained implementation of the same domain rule, matched to a different storage substrate. `.cursor/rules/domain/32-master-data.mdc` and `30-quote-playbook.mdc` describe the master-data-enabled behavior as the normative invariant ("a rate row is quotable only when `attested_by` is set..."), but the *default* runtime configuration is the other fork, which has no equivalent concept.

**Likely root cause.** Staged rollout: master data / vision bench / knowledge cards / real embeddings are each genuinely more expensive subsystems (new tables, new UI, an ONNX model) being rolled out behind flags while a legacy/demo fallback keeps the desk usable — a reasonable strategy on its own.

**Consequences if left unchanged.** The "off" fork accumulates its own bugs and drift indefinitely because there is no stated decommission point; two implementations of "is this customer name known" or "is this machining rate acceptable" must be kept in sync in every future change to either concept.

**Recommended direction.** For each flag, record (in `docs/CURRENT.md` or a new short "flag ledger" doc, not scattered across rule files) the specific conditions under which it is expected to flip to `True` permanently and the fallback code deleted — turning "flag exists" into "flag has a sunset plan." This is a documentation/process recommendation, not a code change, and deliberately does not propose removing any flag today, since the evidence doesn't show which are near a flip decision.

**Tradeoffs.** None significant — this is a low-cost, high-clarity change (a decision-tracking doc), not a redesign.

**Migration complexity: LOW** (documentation), **separately HIGH** if/when any individual flag is actually flipped and its fallback removed (not scoped here).

---

## Finding ARCH-7 — Canvas is a fully separate application inside the "single pane" HUD

**Priority: MEDIUM — PRODUCT DECISION REQUIRED**

**Finding.** `frontend/src/app/canvas/page.tsx` mounts a completely independent React tree (`CanvasShell`) with its own API surface (`/api/canvas/boards`, `/api/canvas/files`, own DB tables `canvas_boards`/`canvas_items`/`canvas_files` in `db.py`) that is not reachable from, and does not interoperate with, `OrchestratorShell`'s workspace switcher (`monitor|casual|engineering`). This directly contradicts the frontend architecture rule's own stated invariant: `.cursor/rules/frontend/22-frontend-uiux.mdc`: "One always-mounted pane... never mount/unmount... no one-off panels in `OrchestratorShell`." Canvas is not a panel inside the pane at all — it is a second, unrelated Next.js route and app shell.

**Evidence.** `frontend/src/app/canvas/page.tsx`; `backend/app/main.py` canvas routes (`/api/canvas/boards`, `/api/canvas/files`, etc., verified directly in the route list read during this audit); no cross-reference from `OrchestratorShell.tsx`, `hudWorkspace.ts`, or `lenses.ts` to the Canvas route or its data.

**Why it matters.** Either Canvas is intentionally out of scope for the single-pane overhaul (a legitimate, deliberate exception — collaborative whiteboarding is a genuinely different interaction mode than a voice-first HUD, and forcing it into the pane model might be wrong), or it is architectural drift that the "single pane" rule fails to account for. The audit brief explicitly calls out "modules doing too many things" and "duplicated concepts" — a second, fully independent app surface living inside the same frontend package is worth a deliberate call, not silence.

**Likely root cause.** Canvas predates or was built in parallel with the Pane/lens overhaul and was never migrated or explicitly retired from scope.

**Consequences if left unchanged.** Continued ambiguity for future agents: `.cursor/rules/frontend/22-frontend-uiux.mdc`'s globs (`frontend/src/**/*.{ts,tsx,css}`) technically apply to Canvas's files too, but its "One always-mounted pane" instruction cannot be satisfied by code that, by construction, is a separate route — an agent editing Canvas under that rule's guidance would be given contradictory instructions.

**Recommended direction (PRODUCT DECISION REQUIRED).** Explicitly scope Canvas as either (a) out of the single-pane mandate, documented as such in the rule file so agents don't try to force it in, or (b) a deliberate near-term target to fold into the Pane/lens model as a fourth lens or an Engineering-workspace panel. This audit does not have enough product-intent evidence to recommend which.

**Tradeoffs.** N/A pending the decision above.

**Migration complexity:** LOW to document the current state as an explicit exception; HIGH if a future decision is made to fold Canvas into the Pane model (it would need its own lens, its own panel layout entries, and reconciliation with the substrate WebGL/lens-transition model).

---

## Finding ARCH-8 — Frontend turn/FSM design is a genuine architectural strength, worth protecting

**Priority: N/A (positive finding — informs "what to keep" in target direction)**

**Finding.** `frontend/src/lib/orchestratorFsm.ts` is unusually well-built relative to the rest of the codebase and should be explicitly called out as a pattern to preserve and extend, not "fix." It is a pure reducer (`transition(state, event) -> state`), returns the *same object reference* on a refused/no-op transition specifically so callers can do cheap `next === prev` no-op detection (`OrchestratorShell.tsx`'s `applyEvent`), and every state-machine hazard called out in the audit brief — stale/late async completions, re-entrant sends, "mic live while speaking" — is handled structurally (there is no transition *out of* `SPEAKING` that produces a listening-capable state) rather than via ad hoc boolean guards scattered through the component. The generation-counter pattern (`speakGenRef`) additionally guards against a late TTS `onEnd` callback resurrecting a stale state after a newer turn has already superseded it.

**Evidence.** `frontend/src/lib/orchestratorFsm.ts` full read; `OrchestratorShell.tsx`'s `applyEvent`, `decide()`, and `applyResponse()` all consistently route state changes through this reducer rather than ad hoc `setState` calls.

**Why it matters.** This is direct, positive counter-evidence to a default assumption that a fast-moving HUD codebase would have race-prone client state. It did not. This should inform the target direction: **do not** propose replacing this FSM with a generic state library or "simplifying" it — it is already solving the exact problems (stale async, re-entrancy, contradictory concurrent flags) the audit was asked to look for, and doing so with less code and fewer moving parts than most alternatives would.

**Recommendation.** None required. Noted so it is not accidentally "simplified" away by a future well-meaning refactor, and so the turn-ledger reconciliation logic (`hydrate`/`reconcileLedgerState`, see `ARCH-4`) — which extends the same pattern — is judged on its own (dormant-by-default) merits, not blamed for the FSM's design.

---

## Summary table

| ID | Priority | One-line |
| --- | --- | --- |
| ARCH-1 | HIGH | Three overlapping intent classifiers, no single routing source of truth |
| ARCH-2 | CRITICAL (investigation) | Safety deny-phrase list is dead code on the primary (Hermes) path; HITL layer is the real, undocumented backstop |
| ARCH-3 | MEDIUM-HIGH | Three complete retrieval implementations exist (`memory_docs` SQLite — live; LanceDB — write-only; `rag/` hybrid FTS+vector — fully built, tested, zero production call sites); self-reported "engine" is misleading |
| ARCH-4 | HIGH | Two complete chat-turn state models; ledger fully wired but dark by default, described as primary in the always-on rule |
| ARCH-5 | MEDIUM | `agent.py:_run_agent` is a ~200-line, order-dependent routing God-function |
| ARCH-6 | MEDIUM | 5 feature flags permanently fork the same business concepts with no sunset plan |
| ARCH-7 | MEDIUM (product decision) | Canvas violates the "single pane" invariant by being a separate app |
| ARCH-8 | N/A (positive) | Frontend turn FSM is a genuine strength; protect it from "simplification" |
