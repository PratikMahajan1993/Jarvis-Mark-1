# Logic and correctness audit

**Scope:** Independent trace of state transitions, concurrency, idempotency, error recovery, and the most important business/user/data flows, verified directly against `backend/app/` and `frontend/src/` on branch `overhaul`. Findings are labeled with the same CRITICAL/HIGH/MEDIUM/LOW investigation-priority scale as the architecture audit. Uncertain items are explicitly marked **REQUIRES FURTHER INVESTIGATION**; product-ambiguous items are marked **PRODUCT DECISION REQUIRED**.

---

## Part A — Correctness findings

### Finding LOGIC-1 — HITL claim-once execution is correctly implemented (positive, verified)

**Priority: N/A (positive finding, confirmed robust)**

Two independent double-execution guards were traced end to end and both hold up:

1. **Server-side atomic claim.** `agent.py:_try_claim_pending(action_id)` executes `UPDATE pending_actions SET status='claimed', claim_id=?, claimed_at=? WHERE id=? AND status='pending'` and checks `cur.rowcount != 1` to detect a lost race — this is a correct, single-statement, race-free claim under SQLite's transaction semantics (each `db.connect()` context commits on exit; WAL mode + `busy_timeout=5000` is configured in `db.py:_configure_connection`). `resolve_pending()` calls this immediately after the `action.get("status") != "pending"` fast-path check, so two concurrent `/api/confirm` calls for the same `action_id` — whether from a genuine double-click, a browser retry, or two separate tabs — can never both pass the claim; the loser gets `_already_handled_response()`.
2. **Client-side FSM guard.** `OrchestratorShell.tsx:decide()` opens with `if (current.mode !== "AWAITING_HITL" || current.action.id !== id || current.resolving) return;`, and the reducer transition `DECIDE_APPROVE`/`DECIDE_REJECT` (`orchestratorFsm.ts`) itself refuses (`return state`, same reference) unless `state.mode === "AWAITING_HITL" && !state.resolving && state.action.id === event.actionId`. A double-click is blocked before the second network call is even made.

**Why this is worth stating explicitly.** The audit brief asks specifically to look for "retries can produce duplicate effects" and "authorization is incomplete or duplicated." This is the one place in the codebase that was clearly designed against exactly that risk, on both the client and the server, independently. It should be treated as the reference implementation for any new mutating endpoint, not something needing further hardening.

---

### Finding LOGIC-2 — MHR "owner-attested" invariant is not enforced in the default (flag-off) configuration

**Priority: HIGH — PRODUCT DECISION REQUIRED**

**Finding.** `.cursor/rules/domain/30-quote-playbook.mdc` states as a non-negotiable: *"Sendability follows attestation, not storage... a rate row is quotable only when `attested_by` is set and its value differs from the shipped seed. An unattested row, or one still holding the shipped seed number, is a BLOCKER."* This is faithfully implemented in `backend/app/quote.py:verify_quote()` — but **only inside the `if settings.masterdata_enabled:` branch**, which calls `masterdata.mhr_lookup.machine_hour_rate_as_of()` and `mhr_rate_is_sendable_as_of()` to check `attested_by`. In the `else` branch — which is what actually runs with the shipped default `masterdata_enabled=False` — the check degrades to: `demo_mins = _parse_mhr_demo_mins(); floor = demo_mins.get(machine.lower()); ... elif mhr_rate >= floor: checks.append(_check("mhr_demo_floor", True, ...))`. There is no `attested_by` concept, no "shipped seed" concept, and no BLOCKER for an unreviewed rate in this branch at all — any machining rate at or above the static number in `backend/app/hermes/playbooks/quote/files/mhr-demo.md` passes.

**Evidence.** Direct read of `backend/app/quote.py:verify_quote()`, the `if machine or mhr_rate is not None:` block (~lines 862–981): the `if settings.masterdata_enabled:` branch computes `floor` from `machine_hour_rate_as_of()` and gates on `mhr_rate_is_sendable_as_of(rate_row)` (attestation-aware); the `else:` branch computes `floor = demo_mins.get(machine.lower())` and gates only on `mhr_rate >= floor` (attestation-unaware). `backend/app/config.py`: `masterdata_enabled: bool = False`.

**Why it matters.** The rule file frames underquoting from an un-reviewed or stale rate as *the specific failure the owner has actually suffered* ("a price corrected after send, an assumed material..."). The mechanism built to prevent exactly that (attestation-aware MHR floor checking) is present in the code but inert in the default configuration. This is not a hypothetical: it is the literal out-of-the-box behavior of `verify_quote(stage="send")`, the function whose entire purpose is to be the last gate before a quote email queues for Authorize.

**Root cause.** `masterdata_enabled` is a genuinely larger subsystem (new tables, master-data UI deferred per the rule's own text: "`source_kind='demo'` is a supported production source while the Master Data UI is deferred") being staged in behind a flag, and the markdown-fallback path was written as a *bridge*, not as an attestation-equivalent — but nothing marks it as a known-weaker substitute in the code or the rule.

**Consequences if left unchanged.** Any desk running with default configuration (which, per `docs/architecture-review/00-codebase-map.md`'s own reading of `config.py`, is the shipped default) can send a quote with a machining rate that was never reviewed by the owner, was set at the exact "shipped demo seed" value, or is otherwise stale — with `quote_verify` reporting a clean pass on `mhr_demo_floor`.

**Recommended direction — PRODUCT DECISION REQUIRED.** Two defensible options, both requiring an owner call rather than an engineering-only fix: (a) treat `masterdata_enabled=True` as required for any real (non-demo) desk and change the *default*, since the rule already treats attestation as non-negotiable; or (b) add an attestation-equivalent to the markdown fallback (e.g. a sibling `mhr-demo.md` companion file recording an owner sign-off date per machine, checked the same way) so the invariant holds regardless of the flag. This audit does not have evidence of which the owner intends, and it materially affects whether real quotes can be trusted — hence marked as a product decision, not an engineering default.

**Migration complexity:** LOW for (a) (flip a default, verify nothing else assumes it's off), MEDIUM for (b) (new file format + parser + test).

---

### Finding LOGIC-3 — `reconcile_external_effects_on_boot()` does not run on boot

**Priority: HIGH**

**Finding.** The function's own name and its governing rule (`.cursor/rules/backend/11-hitl-safety.mdc`: *"Boot: reconcile `intent`/`unknown` against the provider or park **`needs_human`** — never silent retry"*) both describe boot-time reconciliation. Verified via full read of `backend/app/main.py`'s `startup()`/`lifespan()` and a repo-wide grep: **the function is never called from `main.py`.** Its only call site is inside `agent.py:resolve_pending()`, at the top, meaning it runs lazily on the **next arbitrary `/api/confirm` call for any action**, not proactively when the process actually restarts.

**Evidence.**
```
grep -rn "reconcile_external_effects_on_boot" backend/app backend/tests
backend/app/agent.py:1686:def reconcile_external_effects_on_boot() -> None:
backend/app/agent.py:1713:    reconcile_external_effects_on_boot()   # inside resolve_pending()
backend/tests/test_claim_once.py: (import + direct call in a test)
```
No occurrence in `main.py`'s `startup()` or `lifespan()`, both of which were read in full during this audit.

**Why it matters.** Trace the actual failure mode this exists to catch: the process crashes *after* `_begin_external_effect()` inserts an `external_effects` row with `state='intent'` but *before* the Gmail/Calendar/Sheets call resolves (or between the call resolving and `_settle_external_effect()` persisting the outcome — the exact "partial failure" scenario the audit brief calls out explicitly, and the one the codebase even ships a test hook for: `HitlPostProviderCrash`). On restart, that row sits at `state='intent'` and the corresponding `pending_actions` row sits at `status='claimed'` — **invisible to `GET /api/pending`** (`db.list_pending` filters `WHERE status='pending'` only), so the HUD shows nothing pending for that session, and the owner has no visual cue that a send is stuck in limbo. The stale row is only ever cleaned up — flipped to `needs_human` — the next time *anyone, for any action* calls `/api/confirm`. If no other Authorize/Reject happens in that session again, it never resolves.

**Root cause.** The function was almost certainly designed to be called from `main.py`'s startup, and a call site was added inside `resolve_pending()` as a pragmatic "reconcile lazily whenever we're about to touch pending actions anyway" — which is a reasonable *additional* safety net, but was apparently never also wired into `startup()`, leaving the boot-time guarantee entirely unmet despite the function's name and the rule's explicit wording.

**Consequences if left unchanged.** A crash mid-send leaves a stuck, invisible pending action until unrelated future traffic happens to trigger the sweep — directly contradicting the rule's stated invariant ("Boot: reconcile... never silent retry"; the current behavior is closer to "silent wait," not silent retry, but the visibility gap is the same class of problem the rule is trying to close).

**Recommended direction.** Call `reconcile_external_effects_on_boot()` from `main.py`'s `startup()`, before or alongside `resume_watches()`/`kick_snapshot()`. This is a one-line, low-risk addition; the function is idempotent by construction (it only transitions rows already in `intent`/`unknown`/`sent+claimed` states).

**Tradeoffs.** None meaningful — this closes a real gap with negligible cost. The only reason to hold off is if there's an untested interaction with the DB not being ready yet at that point in `startup()` (it calls `db.init_db()` first already, so this should be safe, but confirm via a test before shipping).

**Migration complexity: LOW.**

---

### Finding LOGIC-4a — Authorize-time execution does not re-run quote proof; `quote_verify` the tool always checks draft-severity only

**Priority: HIGH — independently verified via targeted follow-up read of `agent.py:resolve_pending` and `registry.py:_quote_verify`**

**Finding.** `quote_send`'s proof gate is enforced only at **queue** time: `tools/registry.py:_quote_send()` calls `verify_quote(session_id=session_id, stage="send")` and refuses to queue if `stop=True`, and separately refuses on PDF-sha256 drift. `agent.py:resolve_pending()`'s `quote_send`/`email_send` branch — the code that actually runs when the owner clicks **Authorize** — does **not** call `verify_quote()` again, and does not re-check PDF drift beyond what was already bound at queue time; it goes straight to `send_email(...)`. This means the full proof checklist (customer spelling, MHR floor, RM basis age, delivery, etc.) is evaluated once, at the moment `quote_send` is called, and never again — if session memory backing any of those checks changes between queueing and Authorize (a realistic window, since Authorize is a separate, potentially much later user action, and other tool calls in the same session can freely rewrite `last_quote_*` memory keys in between), the owner authorizes against a proof result that may no longer be true. The PDF-sha256 drift check (`quote_refuse_if_pdf_drift`) narrowly covers "did the PDF bytes change," not "did anything else the proof depends on change."

Separately, `registry.py:_quote_verify()` (the handler behind the `quote_verify` MCP/tool call Hermes and the owner would use mid-conversation to "check if this is ready") calls `verify_quote(session_id=session_id)` with **no `stage` argument**, which defaults to `stage="draft"` inside `verify_quote()`. This means every ad hoc "is this quote ready?" check the owner or Hermes runs mid-flow is evaluated at the **more lenient** draft severity (delivery-empty is WARN, not BLOCKER; RM basis 26-30 days is WARN, not BLOCKER) — only the internal call inside `_quote_send` itself ever passes `stage="send"`. An owner could reasonably ask Hermes "run the proof check" and hear "proof passed" (draft-severity), then have the subsequent `quote_send` call refuse for a send-severity-only BLOCKER (e.g. an empty delivery field) that the just-run "proof passed" response gave no hint of.

**Why it matters.** This is a second, distinct instance of the "proof gate can say one thing while the actual send-time behavior says another" pattern already identified in `AI-1`/`Cross-1`, but here it is a code-level timing/staleness gap rather than a documentation error — the code itself, not just the prose describing it, has two different severity views of the same quote that a user can be shown without warning which one they're looking at.

**Recommended direction.** Re-run `verify_quote(stage="send")` inside `resolve_pending()`'s `quote_send` branch immediately before calling `send_email`, refusing (and surfacing a clear "the quote changed since you authorized it" message) if `stop` is now true; and have `_quote_verify()` accept/pass through a `stage` parameter (defaulting to whatever the caller specifies, with `quote_send`'s internal call remaining `stage="send"`) so an owner or Hermes can explicitly ask for the stricter view mid-conversation rather than only getting it as a side effect of attempting to actually queue a send.

**Migration complexity: LOW** for both — each is a small, additive change to an already-correct function; no schema change.

---

### Finding LOGIC-4b — A malformed RM-basis date silently passes the proof check instead of failing closed

**Priority: LOW-MEDIUM**

**Finding.** `quote.py:_rm_basis_age_days()` calls `_parse_rm_basis_date()`, which returns `None` on any value that isn't a valid ISO date prefix; `_rm_basis_date_check()` then does `if age is None: return _check("rm_basis_date", True, ...)` — i.e. an **unparseable** basis date (a typo, a non-ISO format, stray text) is treated as **passing**, the same as a genuinely fresh basis date, rather than failing closed the way a missing/empty date already correctly does a few lines earlier in the same function (`if basis_date and not _is_tbd(basis_date): ... else: checks.append(_check("rm_basis_date", False, "...requires a dated evidence...", ...))`). This is inconsistent within the same check: empty → correctly BLOCKER; garbled-but-present → incorrectly PASS.

**Why it matters.** The domain rule's own stated philosophy is explicit and directly contradicted by this one code path: *"Missing data is a failure, not a skip."* A malformed date is a milder version of missing data, and the rest of the proof-gate code treats "can't determine X" as a failure everywhere else; this one path is the exception.

**Recommended direction.** Change the `age is None` branch in `_rm_basis_date_check` (or its caller) to return a failing check (WARN or BLOCKER depending on desired strictness) rather than passing, consistent with the empty-date branch immediately above it.

**Migration complexity: LOW.**

---

### Finding LOGIC-4 — Confirm-level idempotency key is never sent by the shipped client

**Priority: MEDIUM**

**Finding.** `POST /api/confirm` accepts an `Idempotency-Key` header and, if present, checks a `confirm_idempotency` table first and returns the cached `response_json` on a repeat (`main.py:api_confirm`). `.cursor/rules/backend/11-hitl-safety.mdc` documents this as current behavior ("`POST /api/confirm` accepts Idempotency-Key; repeats return the first response"). Verified via `grep -rn "Idempotency" frontend/src`: **zero matches.** `frontend/src/lib/api.ts:confirm()` sends no such header. The same is true for `POST /api/chat`'s ledger-mode idempotency key (`main.py:api_chat` generates a fresh random `uuid.uuid4().hex` server-side whenever the header is absent, and the client never sends one either).

**Why it matters.** This does **not** create a double-execution risk (LOGIC-1's DB-level claim-once guard is independent and sufficient), but it means: (a) a genuine network retry from the browser (e.g. a flaky connection re-sending the same POST) will *not* get the exact original response replayed — it will get `_already_handled_response()` ("Already handled.") instead, which is a materially different, less informative message than the real outcome; and (b) the mechanism exists, is documented as current behavior, and is exercised by backend tests, but has **no live caller**, which is exactly the kind of "documented but not actually wired end-to-end" gap the audit brief asks to surface (see also `03-ai-development-system-audit.md` for the AI-instruction-accuracy angle: the rule states this as fact without noting it's server-only).

**Recommended direction.** Either wire the frontend to send a per-decision `Idempotency-Key` (a `crypto.randomUUID()` generated once per `decide()` call and reused only on that call's own retry, if any) so retried confirms replay the real outcome, or update the rule text to note the mechanism is currently server-side-only / test-only, so a future agent doesn't assume the client already does this.

**Migration complexity: LOW.**

---

### Finding LOGIC-5 — Greeting/casual-reply logic is independently re-implemented in at least three places

**Priority: MEDIUM**

**Finding.** The same class of behavior — responding to small talk / greetings — has three independent implementations that can disagree: (1) `agent.py:_social_reply()`, a fixed Python dict (`"hello": "Yes?"`, `"thanks": "Of course."`, etc.) used as a last-resort fallback when the model is offline or returns junk; (2) `semantic_router.py:try_obvious_casual()`, a separate set of regexes (`^(hi|hello|hey|yo|good...)\b`) used purely for *routing* (skip the Gemini router call), not for generating the reply text itself; (3) Hermes's own `_instructions(casual=True, ...)` system prompt (`hermes/bridge.py`), an entirely free-form LLM persona with no knowledge of `_social_reply`'s fixed strings, used whenever Hermes is available and the turn is casual. A fourth, `_run_casual_gemini()`'s direct Gemini/Ollama call with `casual_system_prompt(prefs)`, is a fourth free-form generator for the same "chat" intent kind when Hermes is unavailable.

**Why it matters.** None of these four paths is individually wrong, and each exists for a real reason (deterministic fallback when nothing else works; fast routing shortcut; two different LLM backends' personas) — but a product change like "stop saying 'Yes?' to greetings, say something warmer" requires touching multiple files, and the *actual* text a user sees for the same literal input ("hello") depends entirely on which of the four paths happened to be live at that moment (Hermes up vs down, model provider Gemini vs Ollama, offline vs online) — a real instance of "UI state can diverge from server state" in spirit: the *user-visible persona* diverges depending on invisible backend availability, with no HUD indication of which brain answered.

**Recommended direction.** Not a redesign — the layered-fallback structure is appropriate given the multiple brain backends. Recommend only: consolidate the *deterministic* fallback strings (`_social_reply`) into one owned location referenced by name from the other three prompts/config (so "the canonical greeting tone" is a single string set, even if which generator is live varies), and consider surfacing (even subtly, e.g. in `agents` payload or dev-only diagnostics) which brain answered, to make the divergence debuggable.

**Migration complexity: LOW** (documentation/consolidation, not a functional change).

---

### Finding LOGIC-6 — Cross-session concurrency is capped at a fixed, unconfigurable, unsurfaced limit of 3

**Priority: LOW-MEDIUM — REQUIRES FURTHER INVESTIGATION for real desk usage**

**Finding.** `conversations.py` defines `_BRAIN_SEMAPHORE = threading.Semaphore(3)` — process-wide, shared across every session — plus a per-session `threading.Lock` (`_session_brain_lock`). Any 4th concurrent brain turn (from any session) blocks on `_BRAIN_SEMAPHORE.acquire()` inside `brain_lock()` with no timeout and no queue-position feedback returned to the caller; the HTTP request simply hangs until a slot frees.

**Why it matters.** This is a reasonable protection against unbounded concurrent model calls, but it is an implicit, undocumented capacity constant. If the desk is ever used by more than 3 concurrent human sessions (or more than 3 background tasks that call `run_agent`, e.g. `prime_drawing()` also acquires `brain_lock`), the 4th request simply stalls with no distinguishing signal — from the HUD's perspective this looks identical to "the model is slow," not "you are queued behind other users." Given this is described throughout the docs as a single-owner/small-shop tool, this may never manifest as a real problem — marked **REQUIRES FURTHER INVESTIGATION** because the audit has no evidence of actual concurrent-user counts in practice.

**Recommended direction.** No change recommended without more evidence of real multi-session load; if it is ever observed, the fix is small (surface a "queued" state distinct from "thinking" in the `ChatResponse`/FSM).

**Migration complexity: LOW** if pursued.

---

## Part B — Traced flows

Ten of the most important flows were traced through the actual implementation (entry point → validation → state changes → service/API calls → DB operations → side effects → error paths → retry behavior → concurrency → final state → UI behavior), looking specifically for discrepancies between what the user appears to be doing, what the UI communicates, and what the backend/DB actually guarantee.

### Flow 1 — Synchronous chat turn (default configuration)

1. **Entry point:** `OrchestratorShell.tsx:send(text)`.
2. **Input:** free text from `CommandBaton` or speech-to-text (`voice.ts`).
3. **Client-side validation:** trims and no-ops on empty text; if a HITL panel is open and the text is a short (`≤5` words) yes/no, it's redirected to `decide()` instead of `send()` — this is a **client-side reinterpretation of intent** that has no server-side equivalent check (see discrepancy note below).
4. **State change (client):** `applyEvent({type: "SEND", text})` → FSM enters `THINKING` *before* the network call resolves ("the HUD must never go blank waiting on the network," per the FSM's own comment) — a deliberate, well-reasoned optimistic-UI choice, not a discrepancy risk, because `THINKING` carries no claim about outcome.
5. **API call:** `POST /api/chat {message, session_id}`.
6. **Backend validation/state:** `main.py:api_chat` (ledger off) calls `semantic_router.try_obvious_casual(message) or await classify_intent(message)`, then either `handle_ui_command` or `run_agent(message, session_id, route=classification)` — see `ARCH-1` for the full routing complexity.
7. **Business logic / service calls:** `agent.py:run_agent` → `brain_lock(session_id)` (serializes this session; caps global concurrency at 3, `LOGIC-6`) → `_run_agent` → one of: local snapshot read, Hermes turn, casual Gemini/Ollama, or legacy tool-calling loop.
8. **DB operations:** `db.add_message` (user + assistant turns), `db.add_pending` for any queued external effect, `db.set_focus_pending`, `db.add_audit`.
9. **Side effects:** none external yet at this stage — by design, `/api/chat` never itself sends mail/calendar writes; it only ever *queues* a `pending_actions` row (verified: every mutating tool handler in `tools/registry.py` calls `_queue_pending`, never a connector directly).
10. **Error paths:** virtually every internal step (`live_record`, `quote_record`, `prefetch_tts`, `turn_log.record_turn`) is wrapped in `try/except Exception: pass` — see `LOGIC-7` below for the consequence of this pattern.
11. **Retry behavior:** none at the HTTP layer; a client-side fetch failure surfaces as `showVoice("Connection fault. Awaiting instruction.")` and resets the FSM to `IDLE` — the turn is simply lost from the client's perspective; **the server has no record that the client never received the response** (no idempotency key sent, `LOGIC-4`), so a resend is a brand-new turn.
12. **Concurrency:** serialized per-session via `brain_lock`.
13. **Final state:** `ChatResponse` → `remember_hud()` persists the last response for session-restore (`hud_state` table) → client applies it via `applyResponse()`.
14. **UI behavior:** speaks `speak`, renders `scene` if it has board content, opens `AWAITING_HITL` if `pending` is non-empty.

**Discrepancy noted:** step 3's client-side yes/no short-circuit (`classifyDecision(text)` in `voice.ts`, mirrored separately by `agent.py:classify_decision()` for the case where the client didn't intercept it, e.g. a typed decision while some other race left the FSM not-yet-in-`AWAITING_HITL`) is **the same logic implemented twice**, once in TypeScript and once in Python, with separately maintained word lists (`_YES_SHORT`/`_NO_SHORT` in `intent.py` vs whatever `voice.ts`'s `classifyDecision` contains) — a second, more clearly duplicated instance of the pattern flagged as `LOGIC-5`. **REQUIRES FURTHER INVESTIGATION**: this audit did not diff the two word lists character-for-character to confirm they're in sync; flagging the duplication itself as the finding regardless of current sync state, since drift is inevitable without a shared source.

---

### Flow 2 — HITL Authorize → external send (e.g. `email_send`)

1. **Entry point:** `HitlModal` Authorize button, or spoken "yes"/"authorize."
2. **Validation:** client FSM guard (`decide()`) — see `LOGIC-1`.
3. **API call:** `POST /api/confirm {action_id, approved: true, session_id}`.
4. **Backend:** `resolve_pending()` → `reconcile_external_effects_on_boot()` (see `LOGIC-3` for why this is misnamed/mistimed) → `db.get_pending(action_id)` → status check → `_try_claim_pending` (atomic) → `_begin_external_effect` (`INSERT INTO external_effects ... state='intent'`, unique on `(action_id, provider, request_hash)` via `sqlite3.IntegrityError` catch — a second, independent duplicate-suppression layer keyed by content hash, not just action id) → `connectors.email.send_email(...)` → on success, `_complete_external_provider` settles `state='sent'`; on exception, `_settle_external_effect(state='failed')` + `db.set_pending_status(action_id, "failed")`.
5. **Side effects:** exactly one Gmail send, gated by the claim.
6. **Error paths:** a `send_email` exception returns a **generic** `"Gmail did not take it."` to the user regardless of the actual cause (auth expired, network, quota, malformed address) — the real exception is only logged via `db.add_audit`/`_settle_external_effect(error=...)`, never surfaced. This matches the brief's "errors are represented inconsistently" watch-item: contrast with `calendar_create`'s error path a few lines later in the same file, which *does* forward `str(exc)` (truncated) to the user unless it looks like a traceback. **Two sibling code paths in the same function handle the same class of failure differently** — one always generic, one sometimes specific.
7. **Retry behavior:** none automatic; the user must re-issue the request, which creates a **new** `pending_actions` row (a fresh `action_id`), not a retry of the failed one — the failed row stays `status='failed'` permanently, and `external_effects` for it stays `state='failed'`. There is no user-facing "retry this exact send" affordance; it is always "start over," which is arguably correct (avoids ambiguity about whether the original might have partially succeeded) but is not documented as an intentional choice anywhere.
8. **Final state:** `pending_actions.status='executed'`, `external_effects.state='sent'`.
9. **UI:** `applyResponse` with `fromConfirm: true, approved: true` sets `agents["ops"]="active"` briefly then clears; scene shows "Sent."

**Discrepancy noted:** the copy discipline rule (`11-hitl-safety.mdc`: "Chat and HUD text must not claim an external act succeeded until execution records it") is honored — `sent` widgets only render after `_complete_external_provider` has actually run. No violation found here; this is a second positive/confirmed finding worth carrying into the target-direction doc as a pattern to keep.

---

### Flow 3 — Quote build → verify → send (the highest-stakes flow in the product)

1. **Entry:** Hermes or legacy tool call to `quote_build` (from the `shop-quote` playbook, once a drawing is in focus) → `quote_analyze_drawing` (vision, gated — see Flow 4) → `quote_build` persists rows either to a `quote_revision` (masterdata on) or session-memory JSON (masterdata off, `db.add_memory(session_id, "last_quote_rows", ...)`).
2. **Validation:** `quote_verify(stage="draft")` runs the full checklist in `quote.py:verify_quote()` — rows exist, unit prices positive, qty×rate matches stated total, material present, drawing filename recorded, customer spelling known, scope↔RM consistency, RM basis age (WARN ≤25d, WARN 26-30d, BLOCKER >30d **at draft**), MHR floor (see `LOGIC-2` for the flag-dependent weakness here), delivery days (WARN if empty at draft).
3. **Send attempt:** `quote_send` tool → `queue_quote_send`'s caller (`registry.py:_quote_send`) re-runs `verify_quote(stage="send")` — **BLOCKER severities escalate at this stage** (RM basis >24d→30d window and delivery-empty both flip from WARN to BLOCKER exactly as the domain rule prescribes) — and refuses to even queue the HITL card if `stop=True`.
4. **PDF drift guard:** `quote_refuse_if_pdf_drift()` re-hashes the PDF at send time and compares to the sha256 bound during the last verify call (`db.add_memory(session_id, "last_quote_pdf_sha256", digest)`, written only `if stage_norm != "send"` — i.e. only a *draft*-stage verify updates the binding, so a send-stage verify never re-binds to itself, correctly preventing a "verify at send just rebinds to whatever's there now" loophole).
5. **HITL queue:** `request_human_approval(kind="quote_send", ...)` — same claim-once mechanism as Flow 2.
6. **Execution:** identical to Flow 2's send path once Authorized.
7. **Final state:** `pending_actions.status='executed'`; the verify snapshot used at send time is embedded in the payload (`verify_snapshot=verify_result`), so the Authorize card and audit trail carry the exact proof state that gated the send — a genuinely strong provenance design.

**Discrepancy noted:** none of consequence found in the *code path itself* — this is the most rigorously built flow in the codebase and matches its governing rule (`domain/30-quote-playbook.mdc`) almost line for line. The one confirmed gap is `LOGIC-2` (MHR attestation inert when `masterdata_enabled=False`), which is a **configuration-dependent** discrepancy between "what the rule promises" and "what a default desk enforces," not a bug in the verify logic itself.

---

### Flow 4 — Drawing vision dispatch (consent + quota gate)

1. **Entry:** `quote_analyze_drawing` tool → `quote.py:analyze_drawing_vision(owner_spend=False)` by default → `vision/gate.py:dispatch_drawing_vision(...)`.
2. **Gate 1 (consent):** per `domain/34-drawing-vision.mdc`, default deny unless `customer_terms.allow_cloud_vision=1 and nda=0`. **Not independently re-verified against `vision/gate.py`'s implementation in this pass** — the rule's language ("cannot be overridden... no quota override, urgency, or owner instruction grants consent inside a turn") is unusually strong and specific; **REQUIRES FURTHER INVESTIGATION** to confirm the code enforces this as absolutely as the rule claims, given this audit prioritized the money-moving flows (quote/HITL/mail) for full code-level verification and did not fully trace `vision/gate.py` line by line.
3. **Gate 2 (quota):** 5-drawings-per-cycle, claimed transactionally per the rule ("Claim before dispatch. Insert the usage row inside the same transaction that checks the count, keyed unique on `(cycle_start, file_sha256)`"). **Same caveat** — this audit verified the *rule's* internal consistency and its consistency with the quote-side code that calls into vision, but did not independently re-derive the transactional claim from `vision/gate.py` source in this pass.
4. **Marked explicitly:** the consent/quota gate implementation itself should be a first target for the next investigation pass, given it is (a) financially and legally consequential (customer confidentiality, per-call cost) and (b) not independently verified here to the same depth as Flows 1–3. **REQUIRES FURTHER INVESTIGATION.**

---

### Flow 5 — Mail read/search via the local snapshot (non-Hermes fast path)

1. **Entry:** utterance classified `mail_read`/`mail_search` by `intent.py`, and `_skip_brain(kind, message)` returns `True` when `uses_snapshot(kind) and snapshot_ready() and not wants_fresh(message)`.
2. **Bypass:** this path **skips both Hermes and the Gemini/Ollama brain entirely** — `_run_agent_legacy` is called directly, which calls `execute_tool("read_email"/"search_emails", ...)` against `connectors/email.py` (local SQLite mirror) or `connectors/gmail.py` (live) depending on configuration.
3. **Discrepancy noted (the one worth flagging):** this bypass happens **even when the router (`semantic_router`) classified the turn as `tool_ops` destined for Hermes** — see `agent.py`'s comment "Snapshot-warm read paths: local-first even when router says tool_ops (A14)." This is an intentional, commented override, not a bug, but it means the `target_agent`/`route_intent` stamped onto the `ChatResponse` (via `stamp_route()`) reflects the *router's* classification, not the *path actually taken* — the HUD's agent-orbit visualization could show "DAT.03 / Hermes-ish" attribution for a turn that never touched Hermes at all. **This is a genuine UI/backend discrepancy**: what the UI communicates (which agent handled it, via the orchestra visualization) can diverge from which subsystem actually ran. Low stakes (cosmetic/monitoring only, no functional or safety impact), but worth listing since the brief specifically asks for "what the UI communicates" vs "what the backend actually does" gaps.

---

### Flow 6 — Google OAuth connect

1. **Entry:** `ConnectGoogleModal` → `api.googleAuthUrl()` → browser navigates to `GET /api/google/auth` → `google_auth.auth_url()` → Google consent screen → redirect to `GET /api/google/callback?code=...&state=...` → `google_auth.finish_auth(code, state)` → on success, `kick_mail_bulk(days=100, force=True)` (background sync) → `RedirectResponse(f"{settings.hud_url}/?gmail=1")`.
2. **Client resume:** `OrchestratorShell.tsx` detects `?gmail=1` on mount, opens Preferences, strips the query param from history.
3. **Error path:** `finish_auth` exceptions surface as `HTTPException(400, str(exc))` — a raw exception string rendered as an HTTP error body, which the frontend never calls directly (this route is a full-page redirect target, not a `fetch()`), so a failure here would show the browser's default "this site can't be reached"-style raw error page, not a Jarvis-styled error state. **UI gap**: no in-app handling exists for an OAuth callback failure; the user is dropped onto an unstyled FastAPI error page with no path back into the app. Flagged in the UI/UX audit as well.

---

### Finding LOGIC-7 — Systemic swallow of internal errors via broad `except Exception: pass`

**Priority: MEDIUM**

**Finding.** Across `main.py` and `agent.py`, at least 14 distinct `try: ... except Exception: pass` blocks wrap non-critical instrumentation (`live_record`, `quote_record`, `turn_log.record_turn`, `prefetch_tts`, the MCP-registration background thread, `warm_hermes`, `warm_voicebox`). This is a defensible pattern *specifically because* these are best-effort telemetry/warm-up calls that must never break the user-facing turn — but it is applied uniformly, with no logging even to a debug channel, so a genuine, unexpected bug inside any of these (e.g. a schema mismatch in `live_log.record`) is **permanently invisible** — not just tolerated, but unobservable, since nothing captures the exception at all (no `logger.exception`, no metric increment).

**Why it matters.** The audit brief specifically flags "errors are swallowed" as a risk. This is not blanket bad practice (the *intent* — never let telemetry break the primary flow — is correct), but the *implementation* (bare `pass`, no logging) means these code paths could silently stop working entirely (e.g. `live_log.jsonl` silently stops receiving events) and nothing in the system would ever surface that, including to an agent debugging a "why isn't the capability-test matrix logging anything" report.

**Recommended direction.** Change the pattern from `except Exception: pass` to `except Exception: logger.debug(..., exc_info=True)` (or equivalent) at minimum, for exactly the same set of call sites — this preserves the "never break the user turn" guarantee while making the failure mode observable instead of silent. This is a small, mechanical, low-risk change.

**Migration complexity: LOW.**

---

## Summary table

| ID | Priority | One-line |
| --- | --- | --- |
| LOGIC-1 | N/A (positive) | HITL claim-once is correctly implemented at both client and server layers |
| LOGIC-2 | HIGH (product decision) | MHR owner-attestation invariant is inert when `masterdata_enabled=False` (the shipped default) |
| LOGIC-3 | HIGH | `reconcile_external_effects_on_boot()` never runs at actual process boot |
| LOGIC-4a | HIGH | Authorize-time send does not re-run `verify_quote`; `quote_verify` the tool always checks draft-severity only |
| LOGIC-4b | LOW-MEDIUM | A malformed (unparseable) RM-basis date silently passes instead of failing closed |
| LOGIC-4 | MEDIUM | Confirm/chat idempotency keys are documented but never sent by the shipped client |
| LOGIC-5 | MEDIUM | Greeting/casual-reply logic independently re-implemented 3-4×, can visibly diverge by backend availability |
| LOGIC-6 | LOW-MEDIUM | Fixed, unconfigurable, unsurfaced 3-way global concurrency cap on brain turns |
| LOGIC-7 | MEDIUM | Systemic silent `except Exception: pass` on instrumentation paths, no logging |
| Flow 1 | — | Sync chat turn: yes/no decision-detection duplicated in TS and Python |
| Flow 2 | — | HITL send: inconsistent error-message specificity between sibling handlers (email vs calendar) |
| Flow 3 | — | Quote build/verify/send: no code-level gaps found beyond LOGIC-2; strongest flow in the codebase |
| Flow 4 | — | Drawing vision consent/quota gate: **not independently re-verified at code level this pass — REQUIRES FURTHER INVESTIGATION** |
| Flow 5 | — | Mail snapshot fast-path can make the HUD's "which agent handled this" display diverge from reality (cosmetic) |
| Flow 6 | — | OAuth callback failure has no in-app error handling; drops to a raw FastAPI error page |
