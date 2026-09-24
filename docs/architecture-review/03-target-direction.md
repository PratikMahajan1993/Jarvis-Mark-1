# Target direction

This document proposes a high-level direction for the application (Part 7) and the AI-development system (Part 8), then a consolidated, prioritized findings list across all four domains (Part 9). It deliberately does **not** propose a rewrite of anything — the evidence gathered across `01`–`03-cross-domain-findings.md` supports incremental correction of specific, located gaps in an otherwise disciplined codebase (see `03-cross-domain-findings.md`, `Cross-8`), not a new architecture.

---

## Part 7 — Target architecture direction

### What should remain unchanged

- **`OrchestratorShell` + `orchestratorFsm.ts`.** Confirmed (`01-architecture-audit.md`, `ARCH-8`) to be a genuinely strong, race-safe design. Do not replace with a generic state library or "simplify" it.
- **The HITL claim-once mechanism** (`_try_claim_pending`, `external_effects` bracket, `LOGIC-1`). Confirmed correct at both client and server layers. Treat as the reference pattern for any new mutating endpoint.
- **The quote domain's proof-gate design** (`quote.py:verify_quote`, BLOCKER/WARN severity model, PDF sha256 drift refusal, `Cross-8`). This is the best-executed part of the codebase; do not touch it beyond the two specific, narrow gaps identified (`LOGIC-2`, `AI-1`).
- **The single-pane / lens model for the primary desk** (`Pane`, `substrate/`, `LENS_LAYOUT`). No architectural objection was found to this model itself; the one open question is Canvas's relationship to it (`ARCH-7`), which is a scoping decision, not a defect in the pane model.
- **The cloud/desk placement policy for AI-development work** (`AI-7`). Independently confirmed accurate in this very audit session. Extend it, don't dilute it.

### What should be simplified

- **`agent.py:_run_agent()`'s routing control flow** (`ARCH-5`). Extract the seven concerns into small, independently named, independently testable handler functions with a short explicit priority list, rather than one 200-line function whose specification is "read the `if` statements in order."
- **The greeting/casual-reply logic's redundancy** (`LOGIC-5`). Not a redesign — just consolidate the deterministic fallback strings into one owned location the other three layers reference, rather than four independently-maintained copies of "what does Jarvis say to 'hello'."

### What should be refactored

- **The three-way intent-classification triangle** (`ARCH-1`, `Cross-2`). Target: `semantic_router.classify_intent()` becomes the single decision-maker; `intent.py`'s regex rules become library functions it calls (preserving their valuable determinism and existing `CASES` regression table), rather than a second, independently-invoked classifier in `agent.py`.
- **The safety deny-phrase mechanism** (`ARCH-2`). Target: either delete it as dead weight and replace the *implicit* "every side-effecting tool queues HITL" convention with an *enforced*, tested invariant (`Cross-3`'s recommendation — a registry-walking test), or relocate the deny-phrase check to actually gate the Hermes path it currently misses.
- **`reconcile_external_effects_on_boot()`'s call site** (`LOGIC-3`). Target: call it from `main.py:startup()`, not only lazily inside `resolve_pending()`.

### What should be moved

- Nothing significant was found that is in the *wrong module* per se — the module-ownership table in `.cursor/rules/backend/10-api-python.mdc` was checked against the actual code and holds up well (each concern largely lives where the rule says it should). The one soft exception is Canvas, which is arguably in the wrong *scope* (a separate app inside a "single pane" frontend package) rather than the wrong *module* — see "What should be introduced," below.

### What should be introduced

- **A LanceDB read path** in `memory/store.py:search()` (`ARCH-3`), completing work that was already half-built (the write side exists), rather than leaving the write-only mirror in place indefinitely with a misleading self-reported "engine" string.
- **A registry-invariant test** for the HITL pattern (`Cross-3`): walk `tools/registry.HANDLERS`, confirm every handler that reaches a `connectors.*` call also reaches `_queue_pending`/`request_human_approval` first.
- **A rule↔runtime-playbook consistency check** for any domain rule with a `hermes/playbooks/*/SKILL.md` counterpart (`AI-1`, `AI-8`, `Cross-1`, `Cross-7`) — starting with quote, generalized for gcode when that playbook exists.
- **A short, general "missing data is an ask, not a guess" principle** (`AI-9`), generalizing a pattern currently only stated per-domain.
- **An explicit decision record for each feature flag's sunset conditions** (`ARCH-6`, `Cross-5`) — not a code change, a short living document.

### What should be removed

- **Nothing is recommended for outright removal at this time.** The turn ledger, LanceDB write path, and feature-flagged fallbacks are all more valuable finished or explicitly scoped than deleted (see "introduced," above) — this audit found no dead architecture whose cost clearly outweighs the cost of finishing or documenting it. The one candidate for removal (the safety deny-phrase list, `ARCH-2`) is offered as an *either/or* with "make it real," precisely because the evidence doesn't clearly favor one over the other — that is a product/security-posture call, not an engineering-only one.

### Important architectural boundaries to hold going forward

1. **Every external or destructive tool effect must be queued via `request_human_approval` before any connector call.** This is already true; it should become an enforced invariant, not a remembered convention (`Cross-3`).
2. **Workspaces (`casual|monitor|engineering`) and turn state (`IDLE|...|EXECUTING`) are orthogonal layers and must never collapse into one model.** Already correctly held in both code and rules (`frontend/20-hud-shell.mdc`); worth stating here because it is exactly the kind of boundary that erodes silently under feature pressure.
3. **A feature flag that forks a business-rule implementation is not "done" until its sunset condition is written down.** Not currently held; recommended as a new standing practice (`ARCH-6`).
4. **A domain rule's runtime-playbook counterpart is part of the same specification, not a separate document.** Not currently held; the direct cause of `AI-1`/`Cross-1`.

### Important invariants (state explicitly, since several are currently implicit)

- Claim-once execution for every `pending_actions` row (implicit in code, should be explicit and tested — `Cross-3`).
- `stop: true` on `quote_verify` is severity-based (any BLOCKER), never count-based (`AI-1`).
- `reconcile_external_effects_on_boot()` runs at process boot, not only opportunistically (`LOGIC-3`).
- MHR sendability requires attestation *regardless of `masterdata_enabled`* — currently not true; this is the one invariant that needs a product decision before it can be stated as a boundary (`LOGIC-2`).

---

## Part 8 — Target AI-development system direction

### Which rules should remain

All 16 current rule files (`00-jarvis-core.mdc` through `ops/42-dispatch.mdc`) are, in substance, well-scoped and largely accurate (the notable exceptions are itemized below, not structural). The tiered structure itself (T0 always-on / T1 globbed / T2 description-only) enforced by `test_rule_budget.py` is a good pattern and should remain.

### Which should change

- **`00-jarvis-core.mdc`**: reword the turn-ledger sentence to state it is off-by-default with a ledger variant behind a flag, not as unconditional current fact (`AI-5`).
- **`ops/42-dispatch.mdc`**: trim back under its own 400-word budget (`AI-2`) — the content added in the "explicit direct work" exception is sound; it needs tightening, not removal.
- **`.cursor/skills/jarvis-architecture/SKILL.md`**: fix the Honcho line (`AI-4`).
- **`.cursor/skills/jarvis-quote-playbook/SKILL.md`** and **`backend/app/hermes/playbooks/quote/SKILL.md`**: fix the `>2 failures` → "any BLOCKER" language to match `domain/30-quote-playbook.mdc` and the code (`AI-1` — the single highest-priority instruction fix in this entire audit, given its direct runtime-agent impact).

### Which should be removed

- No rule or skill file should be deleted outright. The closest candidate is discussed below under "merged."

### Which should be merged

- **`jarvis-observation-dispatch` (skill) and `ops/42-dispatch.mdc` (rule)** currently restate the same roster table and the same five-dependency desk-only list in two places with no clear division of responsibility between them (the one genuine skill/rule duplication found in this audit with no "rule=constraint, skill=procedure" split to justify it). Recommend: the rule keeps the constraint ("must use roster + Composer 2.5 Fast + closed kickoff"); the skill keeps only the capability-test-specific procedure (classify observation → which roster agent → prompt template) and refers to the rule for the roster table itself, rather than repeating it.

### Which should be split

- No current file is large or multi-purpose enough to warrant splitting. `domain/30-quote-playbook.mdc` is close to its domain-expanded 750-word cap but is a single coherent concern (quote correctness) and reads as appropriately dense rather than as multiple concerns glued together.

### Which new rules are needed

- **A short "missing data → ask" principle** (`AI-9`), likely `ops/43-uncertainty.mdc`, generalizing the pattern already present per-domain.
- **A short rule (or an addition to `ops/40-tests.mdc`'s glob) that fires when a rule file itself is edited**, reminding the agent to run `test_rule_budget.py` (`AI-2`).

### Which new skills are needed

- None. The five existing skills cover their intended scopes well (see the skill-by-skill table in `03-ai-development-system-audit.md`); the gap found (`AI-8`) is better closed with a rule addition + a test than a new skill, since it is a "must never forget this constraint" item, not a "here is a multi-step how-to" item.

### What should be encoded as stable principles (rules) vs. left as documentation

- **Rules (stable, enforceable, short):** the HITL invariant (`Cross-3`), the claim-once pattern, the severity-based (not count-based) proof model, the workspace/turn-state orthogonality boundary. These describe things that must never silently regress and are cheap to state briefly.
- **Documentation (`docs/CURRENT.md`, `work/*_POINTS.md`), not rules:** the specific current values of feature flags, the specific current module line counts, and anything else that is a *snapshot* of the system rather than a *constraint* on it. The rule tree already mostly gets this distinction right (`backend/10-api-python.mdc`'s own closing line: *"Skills carry long procedures; this file states only break-if-wrong constraints"*) — the target direction is to hold every rule file to that same standard, and move anything that reads as a snapshot rather than a constraint into `docs/CURRENT.md` instead.

### What should NOT be encoded in AI instructions at all

- **Specific numeric business thresholds that already live in code and are more likely to drift in prose than in code** (the exact failure mode of `AI-1`) should, where possible, be described in rules by *reference to the deciding code's behavior* ("any BLOCKER, per `_finalize_verify`'s severity classing") rather than by *restating the threshold in prose* that can silently diverge from the code it describes. This is a general principle worth adopting repo-wide: prefer "the code decides X; here is where" over "X is currently 30 days / >2 failures / etc." in any rule or skill whose corresponding value already exists as a named constant or function in the codebase.

---

## Part 9 — Prioritized findings

Findings are grouped by domain. Priority reflects investigation/remediation urgency, not a quality judgment. "Effort" is a rough qualitative read (LOW/MEDIUM/HIGH) based on the migration-complexity assessments already given in each finding's own section.

### A. Architecture

| ID | Priority | Impact | Effort | Dependencies | Risk of leaving unchanged |
| --- | --- | --- | --- | --- | --- |
| ARCH-2 | CRITICAL (investigation) | Safety-relevant; currently mitigated by HITL convention, not mechanism | LOW | None | A future new tool could open a real gap with no test to catch it |
| ARCH-1 | HIGH | Every routing bug costs 3× the investigation time | MEDIUM | None | Compounding cost on every future routing change |
| ARCH-4 | HIGH | Two full state models to maintain; always-on rule overstates one as primary | HIGH (to resolve either direction) | Product decision on ledger rollout | Continued double-maintenance burden, agent confusion |
| ARCH-3 | MEDIUM-HIGH | Misleading capability self-report; latent scale ceiling | LOW-MEDIUM | None | Query latency degrades silently as corpus grows |
| ARCH-5 | MEDIUM | Rising complexity cost on every new routing edge case | MEDIUM | None | Compounding, not urgent |
| ARCH-6 | MEDIUM | No sunset plan for 5 permanently-forked implementations | LOW (doc only) | Product input per flag | Forks drift further apart the longer they're unaddressed |
| ARCH-7 | MEDIUM (product decision) | Ambiguity for future agents editing frontend under the "single pane" rule | LOW (to document); HIGH (to actually fold in) | Product decision | Contradictory instructions to future agents persist |

### B. Logic/correctness

| ID | Priority | Impact | Effort | Dependencies | Risk of leaving unchanged |
| --- | --- | --- | --- | --- | --- |
| LOGIC-2 | HIGH (product decision) | Underquoting risk — the owner's own named worst-case failure mode | LOW (flip default) / MEDIUM (add attestation to fallback) | Product decision | Real financial risk on the default configuration |
| LOGIC-3 | HIGH | Crash-recovery guarantee doesn't hold as named/promised | LOW | None | Stuck, invisible pending actions after a crash until unrelated future traffic |
| LOGIC-4 | MEDIUM | Retry UX is less informative than intended; not a safety gap | LOW | None | Confusing "Already handled" message on a genuine network retry |
| LOGIC-5 | MEDIUM | Persona/tone can visibly diverge by backend availability with no indication why | LOW | None | Product-tone changes require touching 3-4 files, risk of drift |
| LOGIC-7 | MEDIUM | Instrumentation can silently stop working with zero observability | LOW | None | A real bug in telemetry becomes permanently invisible |
| LOGIC-6 | LOW-MEDIUM | Unconfigurable concurrency cap with no queued-state UI signal | LOW | More evidence of real multi-session load | Currently unconfirmed as a live problem |

### C. UI/UX

| ID | Priority | Impact | Effort | Dependencies | Risk of leaving unchanged |
| --- | --- | --- | --- | --- | --- |
| UX-8 | CRITICAL | A safety-critical-looking control (bench Authorize/Reject) is fully inert and indistinguishable from the real one | LOW (disable+label interim) / MEDIUM (full wiring) | None for interim fix | A real quote could be "rejected" via a dead button with the owner believing it worked |
| UX-1 | HIGH | Every new install's first substantive sentence is raw `.env` variable names | LOW | None | First impression actively works against the product's own persona design |
| UX-2 | HIGH | The highest-stakes modal has the weakest accessibility markup in the app | LOW | Product decision on Escape-for-HitlModal semantics | Screen-reader/keyboard users get materially worse support for the most consequential decision |
| UX-9 | MEDIUM | A successful result can visually read as a stall | LOW | None | Confusing "is it broken" moments on the single most common interaction (chat) |
| UX-3 | MEDIUM | Unexplained internal jargon on every single Authorize/Reject decision | LOW | None | Persona/tone inconsistency at the highest-attention moment |
| UX-4 | MEDIUM | No visual distinction between demo/seed data and a real in-progress job | LOW-MEDIUM | Small backend flag | First-use vs. returning-user confusion in Engineering |
| UX-10 | LOW-MEDIUM | Same concept named 3-4 different ways in adjacent UI | LOW | None | Slower onboarding mental-model formation |
| UX-6 | LOW-MEDIUM | Keyboard Authorize/Reject shortcuts exist but are never shown | LOW | None | Undiscovered power-user affordance |
| UX-5 | LOW-MEDIUM | Responsive layout works; one post-dismissal overlap risk unverified live | — | Further interactive mobile-width testing | Unknown until verified |

See `03-ui-ux-audit.md` for full findings, evidence, and screenshots.

### D. AI-development system

| ID | Priority | Impact | Effort | Dependencies | Risk of leaving unchanged |
| --- | --- | --- | --- | --- | --- |
| AI-1 | CRITICAL | Live production agent (Hermes) can misstate quote-send readiness to the shop owner | LOW (two text edits) | None | Confusing, trust-eroding agent/tool mismatches on real quotes |
| AI-2 | HIGH | Rule governance test is failing right now, on the default branch | LOW | None | Rule tree accretes unchecked, defeating the point of the budget system |
| AI-3 | HIGH (platform-level) | This session was itself governed partly by stale, retired instructions | Not directly fixable from repo content | Cursor platform-side investigation | Any future session could be silently misgoverned the same way |
| AI-4 | MEDIUM | First-stop architecture doc gives a wrong premise for memory questions | LOW | None | Every future agent trusting this doc starts from a wrong model |
| AI-8 | MEDIUM | No repo-wide instruction protects rule/playbook consistency generally | LOW (rule) / MEDIUM (automated check) | None | `AI-1`-class bugs will recur for the next playbook (gcode) |
| AI-9 | MEDIUM | "Ask, don't guess" only exists per-domain, not as a standing default | LOW | None | New domains re-derive (or fail to derive) the same principle independently |
| AI-10 | MEDIUM | All 4 agent-prompt frontmatters say `model: inherit`, contradicting the dispatch rule's explicit "do not inherit" | LOW | None | A future maintainer trusts the wrong source about which model actually runs |
| AI-11 | MEDIUM | `jarvis-builder.md`'s exports path (`backend/exports`) contradicts the root rule and code (`<repo>/exports/`) | LOW | None | A literal reading would write files to the wrong directory |
| AI-12 | LOW-MEDIUM | `catalog.md` references a deleted component and misdescribes the orb's current implementation | LOW | None | An agent following the pointer looks for a nonexistent file |
| AI-13 | LOW | One domain rule's glob points at a renamed/nonexistent file | LOW | None | That rule doesn't auto-attach when editing the file it's actually meant to govern |

### Additional logic/correctness items surfaced by targeted follow-up verification

| ID | Priority | Impact | Effort | Dependencies | Risk of leaving unchanged |
| --- | --- | --- | --- | --- | --- |
| LOGIC-4a | HIGH | Authorize-time send doesn't re-run `verify_quote`; ad hoc `quote_verify` calls are always draft-severity | LOW | None | A quote can be authorized against a stale proof result; Hermes can report "proof passed" using the lenient view right before a stricter send-time refusal |
| LOGIC-4b | LOW-MEDIUM | A malformed RM-basis date silently passes instead of failing closed | LOW | None | Inconsistent with the rule's own "missing data is a failure, not a skip" principle |
| ARCH-3 (extended) | MEDIUM-HIGH | A third, fully-built, fully-tested retrieval stack (`rag/`) has zero production call sites | LOW (doc) / HIGH (consolidate) | Product decision: which retrieval system is the future one | Two parallel retrieval systems both receive maintenance cost for one live capability |

---

## What requires product-owner clarification (consolidated)

- **`LOGIC-2` / `ARCH-6`**: should `masterdata_enabled` become the default, or should the demo-floor fallback gain an attestation-equivalent? This is the single highest-stakes open question in the review.
- **`ARCH-4`**: is the turn ledger intended to become the default execution model, and on what timeline? Until decided, `00-jarvis-core.mdc`'s wording should be corrected regardless (`AI-5`), independent of which way the decision goes.
- **`ARCH-7`**: is Canvas in scope for the single-pane overhaul, or a deliberately separate surface?
- **`ARCH-2`**: is the deny-phrase list meant to be a real, hardened safety gate (worth investing in making it actually gate the Hermes path), or is the HITL-everywhere convention considered sufficient on its own (in which case the deny list should be removed as it currently only adds false confidence)?
- **`ARCH-3`/`Cross-9`-adjacent**: with three complete retrieval implementations now confirmed (`memory_docs` SQLite — live; LanceDB — write-only; `rag/` hybrid FTS+vector — fully built and tested, zero production imports), which one is meant to be the system going forward? Maintaining all three in a working, tested state has an ongoing cost with no current runtime benefit from two of them.
- **`UX-8`**: is the Engineering bench's Authorize/Reject pair intended to be wired to real quote sends soon (in which case the interim fix is "disable + label as preview"), or is bench-level quote approval not actually part of the near-term product plan (in which case it should be removed or clearly marked as a design preview, not left live-looking)?

## What requires further investigation (consolidated, not yet conclusively evidenced)

- **Flow 4 (drawing-vision consent/quota gate, `vision/gate.py`)** was not independently re-derived from source to the same depth as the quote/HITL/mail flows in this pass, despite the domain rule's unusually strong language ("cannot be overridden"). Given the financial and confidentiality stakes the rule itself names, this should be the first target of a follow-up code-level pass.
- **`AI-3`'s root cause** (why this session's initial context carried retired rule content) is outside this repository's visibility and needs a platform-side look, not a repo-side one.
- **The exact yes/no word-list parity between `intent.py`'s `_YES_SHORT`/`_NO_SHORT` and `voice.ts`'s `classifyDecision`** (flagged in `02-logic-audit.md`, Flow 1) was identified as a duplication risk but not diffed character-for-character in this pass.
