# Cross-domain findings

Findings below span two or more of: (A) architecture, (L) logic/correctness, (U) UI/UX, (D) AI-development system. Each cites the single-domain findings it draws from (see `01-architecture-audit.md`, `02-logic-audit.md`, `03-ui-ux-audit.md`, `03-ai-development-system-audit.md`) and explains the causal link between domains, which is the point of this document — these are not just "the same bug counted twice."

---

## Cross-1 — A documentation bug in a runtime-agent-facing file is simultaneously an AI-dev-system finding and a live product-logic finding

**Domains: D + L.** **Priority: CRITICAL.**

`AI-1` (AI-development-system audit) describes the `>2 failures` vs. "any BLOCKER" contradiction in the quote-proof "stop" rule. Ordinarily, a wrong Cursor rule or skill is purely a *coding-agent* risk — it could mislead a future human/AI contributor editing `quote.py`, but it has no runtime effect on the shipped product, because Cursor rules aren't loaded by the running application. This case is different **specifically because** one of the three places the wrong rule lives is `backend/app/hermes/playbooks/quote/SKILL.md`, which is copied into the live Hermes agent's own skill directory and read by it *at runtime, in production*. This collapses the usual architecture/AI-dev-system boundary: an "AI-instruction quality" bug and a "logic/correctness" bug are, in this one case, the literal same three lines of text. Any future audit or process that treats "Cursor rules/skills" and "runtime Hermes playbooks" as separate review tracks (one for developer-experience concerns, one for product-correctness concerns) will miss this class of issue, because it lives in both tracks depending only on which file happens to contain it. **Implication for review process:** any change to a domain rule that has a `hermes/playbooks/*/SKILL.md` counterpart should be reviewed as a product-behavior change, not merely a documentation change, and vice versa.

---

## Cross-2 — The three-classifier routing architecture (ARCH-1) is exactly why the AI-instruction corpus needs, but lacks, a single "how does a message actually get routed" reference

**Domains: A + D.** **Priority: HIGH.**

`ARCH-1` documents that `intent.py`, `semantic_router.py`, and Hermes's own judgement jointly determine what happens to an utterance, with `is_quote_start`/`is_rfq_definition` cross-imported to keep two of the three in sync. The AI-development-system audit independently found (`jarvis-architecture/reference.md`'s "Semantic router" section) that the *documentation* of this system is a four-line bullet list that undersells the actual complexity: it says "`tool_ops` prefers Hermes in `agent.py`; falls back to local snapshot / legacy on error" — which is true but omits the snapshot-fast-path override that runs *even when the router says `tool_ops`* (`agent.py`'s own comment "(A14)"), the shop-sheet carve-out, and the quote-start special case. This is not a documentation-accuracy bug in isolation (nothing in the doc is *false*) — it is a case where an architecture that is genuinely this layered **cannot** be adequately described in the four-line style the rest of the corpus otherwise uses successfully (contrast with `AI-6`/`AI-7`'s praise for concrete, falsifiable instructions elsewhere). The cross-domain lesson: **the routing architecture's complexity (an architecture finding) is the root cause of the documentation's necessary incompleteness (an AI-dev-system finding)** — no amount of doc editing fixes this without first addressing `ARCH-1` itself, or at minimum building the sequence-diagram-style reference this corpus does not currently have for this one especially tangled flow.

---

## Cross-3 — HITL is the load-bearing safety invariant, but it is enforced entirely by *convention*, not by a single, checkable mechanism, and no instruction says so

**Domains: A + L + D.** **Priority: HIGH.**

`ARCH-2`/`LOGIC-1`/`LOGIC-3` collectively establish that the real safety boundary in this system is not the deny-phrase list, not a single gate function, but the *fact that every side-effecting tool handler in `tools/registry.py` happens to call `_queue_pending()`*. This is correct today (verified: every handler that reaches a `connectors.*` call does so). It is also **entirely unenforced as an invariant** — nothing in the code, and nothing in the AI-instruction corpus, states "every new tool handler that performs an external effect must call `request_human_approval` before executing, and this is checked by test X." `.cursor/rules/backend/11-hitl-safety.mdc` describes the *pattern* correctly ("Tools and MCP: Send mail, calendar writes... → queue Authorize; never set sent: true") but as a prose instruction for a human/agent to *remember* when writing a new handler, not as a structural guarantee. This is the single most consequential place in the whole review where architecture (a convention-based safety boundary), logic (verified correct today), and the AI-development system (no instruction converts the convention into an enforced rule) all point at the same gap. **This is the audit's strongest candidate for a "test as documentation" investment**: a single new test that walks `tools/registry.HANDLERS`, statically or behaviorally confirms every handler that can reach an external connector also reaches `_queue_pending` first, would convert an implicit, cross-cutting invariant that currently depends on every future contributor (human or AI) independently knowing to preserve it, into something the test suite itself protects — exactly like `test_rule_budget.py` already does for rule-file size, just for a much higher-stakes invariant.

---

## Cross-4 — The turn-ledger dual-architecture (ARCH-4) already required, and got, careful documentation — showing the corpus *can* handle hard cases well when it tries

**Domains: A + D.** **Priority: N/A (positive, informs target direction).**

Unlike `Cross-2`, the turn-ledger split is described with real care: `.cursor/rules/backend/13-turn-ledger.mdc` states the legal state table, the lease/reaper timing, the idempotency contract, and explicitly calls out "Client fetch timeout is not cancellation" as a named hazard — and `frontend/src/lib/orchestratorFsm.ts`'s own code comments independently reconstruct the same hazard analysis (late `SPEAK_END`, re-entrant sends) without needing the rule to tell it to. The one gap (`AI-5`) is narrow and specific: the *always-on* T0 rule's one-sentence summary of this same system overstates its default-on status, while the *scoped* rule that a ledger-touching agent would actually be shown gets it exactly right. **Cross-domain lesson:** the corpus's failure mode is not "doesn't know how to document something hard" (it clearly does, in the scoped rule) — it's specifically that the *always-on, everyone-sees-it-regardless-of-task* T0 slot is the one place where a short summary sentence lost the nuance the longer, correctly-scoped sibling rule preserved. This should directly inform any T0-rule edit: prefer "see the scoped rule for the real model" phrasing over restating a simplified (and here, wrong) version of a nuanced system in the one slot with no room to be nuanced.

---

## Cross-5 — Feature-flag forking (ARCH-6) is invisible to the AI-instruction corpus as a single concept, even though every domain rule that touches it independently rediscovers the same pattern

**Domains: A + D.** **Priority: MEDIUM.**

`domain/32-master-data.mdc`, `domain/30-quote-playbook.mdc`, and `domain/33-knowledge-rag.mdc` each separately describe a flag-gated fallback for their own concern (master data vs. markdown; real embeddings vs. hash-v1) with genuinely good, specific guidance *within* their domain — but there is no rule or skill that names "feature-flagged dual implementation" as a repository-wide pattern with its own house rules (e.g. "every flag-gated fallback must be labeled as such in its own output," which `33-knowledge-rag.mdc` already does say for hash embeddings specifically: *"Hash-of-words fallback... must be labelled — not silently equivalent to ONNX embeddings"* — a good instinct that is not generalized to the other flags, e.g. nothing requires `mhr-demo.md`'s floor value to be labeled as "unattested demo fallback" in `quote_verify`'s own output the same way `_check("mhr_demo_floor", ...)`'s evidence string could trivially say). **Recommendation carried into the target-direction doc:** generalize the "label the weaker fallback" instinct already present in `33-knowledge-rag.mdc` into a repo-wide, one-sentence principle, rather than leaving each domain rule to reinvent it (or not) independently.

---

## Cross-6 — The API auth middleware's simplicity is a strength, but the UX for the one case it blocks has no owner

**Domains: A + U.** **Priority: MEDIUM.**

`mutating_local_auth_middleware` (verified in `main.py`) is a clean, small, easily-reasoned-about gate: local requests pass, LAN-allowlisted+bearer-token requests pass, everything else gets a bare `401 {"detail": "Unauthorized"}` JSON body. This is architecturally sound (`ARCH`-level: no finding). But `frontend/src/lib/api.ts`'s `json()` helper, on any non-2xx response, does `throw new Error(await response.text())` — meaning a blocked mutating request from a non-allowlisted origin would surface to the user as a raw `{"detail":"Unauthorized"}` string inside whatever generic error-handling the calling component has (`OrchestratorShell.tsx`'s `catch` blocks generally do `err instanceof Error ? err.message : "..."` then `setError(msg)`, rendering the raw JSON text in the small red error line under the orb). **No UI/UX flow exists for "you're on the wrong network/device for this action"** — it would present identically to a generic connection failure, with a confusing raw JSON fragment visible instead of the plain-English "Request failed" fallback other error paths use. This is a small, specific, verifiable UX gap whose root cause is architectural (the backend correctly refuses, but returns raw detail text with no client-side translation layer for auth-class errors specifically).

---

## Cross-7 — Testing strategy protects almost every domain rule's *numeric* claims but not the *narrative* claims Hermes and skills carry

**Domains: L + D.** **Priority: MEDIUM.**

432 passing tests (verified by running the suite) give strong, direct coverage of the code-level correctness of the quote/HITL/claim-once machinery (`LOGIC-1` through `LOGIC-4`, `test_claim_once.py`, `test_quote_proof_gates.py`, `test_quote_playbook.py` all exist and pass). What is not tested by anything in `backend/tests/`, and cannot be, by construction: whether the **prose** the runtime Hermes agent is instructed with (the playbook `SKILL.md`, `notes.md`) accurately describes what that tested code does — which is exactly how `AI-1` survived undetected. The test suite's own philosophy, correctly stated in `ops/40-tests.mdc` ("assert observable behaviour... over implementation details"), is right for code but has no equivalent for the *narrative accuracy* of agent-facing prose describing that code. This is the same gap as `AI-8`, restated from the testing-strategy angle: the fix belongs in the AI-development-system's process (a content-diff check between rule and playbook), not in `backend/tests/` itself, since the playbook is prose, not code, and pytest cannot meaningfully assert prose accuracy without such a targeted mechanism.

---

## Cross-9 — A fixture built for one purpose (bench UI scaffolding) now sits, unlabeled, where a safety-critical control is expected

**Domains: A + U + D.** **Priority: CRITICAL.**

`UX-8` (UI/UX audit) documents that `QuoteSheet.tsx`'s Authorize/Reject buttons are permanently inert scaffolding, explicitly commented as such in the code, sitting on top of `frontend/src/lib/pane/fixtures/quote-fixture.json` demo data by default. This is simultaneously: an **architecture** finding (a second, parallel, non-wired "Authorize/Reject" surface exists alongside the one real, `resolve_pending`-backed HITL flow that `LOGIC-1` confirms is correctly implemented — i.e. the codebase now has two different things that look like the same safety gate, only one of which is real); a **UI/UX** finding (indistinguishable-from-real dead controls, `UX-8`); and, prospectively, an **AI-development-system** risk: no rule or skill currently tells a future agent asked to "wire up the bench Authorize button" that doing so needs to reuse the exact `resolve_pending`/claim-once/`external_effects` machinery this audit's `LOGIC-1` finding identifies as the one correct reference implementation — without that pointer, a future agent (human or AI) extending `QuoteSheet.tsx` has a plausible path to inventing a **second**, differently-shaped execution path for the same class of action, which is exactly the "two code paths implement the same business rule differently" pattern the audit brief warns about, before it has even happened. **Recommendation carried into the target-direction doc:** when `UX-8` is fixed, the fix should be done by a worker explicitly pointed at `agent.py:resolve_pending`/`decide()` in `OrchestratorShell.tsx` as the pattern to reuse, not left to independently reinvent the flow.

---

## Cross-8 — The single strongest piece of positive cross-domain evidence: the quote flow

**Domains: A + L + D.** **Priority: N/A (positive).**

Worth stating plainly, because the audit brief explicitly warns against manufacturing problems where the evidence doesn't support them: the shop-quote flow is the one place in this entire review where architecture (a clear, single-owner module in `quote.py`), logic (verified correct proof-gate implementation, `LOGIC` audit "Flow 3"), and AI-development instructions (`domain/30-quote-playbook.mdc`, independently confirmed to match the code almost line-for-line) **all agree with each other**, with the sole exception of `AI-1`'s narrow, specific contradiction and `LOGIC-2`'s narrow, specific flag-dependent gap. This is strong evidence that the underlying engineering discipline in this codebase is high where it has been applied carefully — the problems found elsewhere in this review are not evidence of generally sloppy work, they are specific, locatable gaps in an otherwise disciplined system, and should be weighed accordingly when prioritizing remediation.

---

## Summary table

| ID | Domains | Priority | One-line |
| --- | --- | --- | --- |
| Cross-1 | D + L | CRITICAL | Quote "stop" doc bug is simultaneously a live-agent runtime-behavior bug, not just a coding-agent risk |
| Cross-2 | A + D | HIGH | Routing architecture's real complexity exceeds what the corpus's usual four-line doc style can capture |
| Cross-3 | A + L + D | HIGH | HITL safety is convention-enforced, not mechanism-enforced, and no instruction says to protect it as an invariant |
| Cross-4 | A + D | N/A (positive) | Scoped rules handle hard cases well; the always-on T0 slot is where nuance gets lost |
| Cross-5 | A + D | MEDIUM | "Label the weaker fallback" exists for one flag (embeddings) but isn't a general principle |
| Cross-6 | A + U | MEDIUM | Auth-middleware refusals surface as raw JSON in the generic error line; no dedicated UX |
| Cross-7 | L + D | MEDIUM | Tests protect code correctness; nothing protects narrative-prose accuracy against that code |
| Cross-8 | A + L + D | N/A (positive) | The quote flow is where architecture, logic, and instructions are most tightly aligned — the reference example |
| Cross-9 | A + U + D | CRITICAL | A dead-fixture Authorize/Reject control sits where a safety-critical one is expected; no instruction yet points a future fixer at the one correct pattern to reuse |
