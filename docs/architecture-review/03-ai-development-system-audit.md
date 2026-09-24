# AI-development system audit

**Scope:** Every Cursor rule (`.cursor/rules/**/*.mdc`), skill (`.cursor/skills/**`), subagent prompt (`.cursor/agents/**`), `AGENTS.md`, and the runtime Hermes playbook (`backend/app/hermes/playbooks/quote/SKILL.md`) was read in full during this audit, not sampled. This document verifies every claim against the actual current repository content on branch `overhaul`.

**Governing question:** *if a highly capable but imperfect coding agent followed these instructions literally, would they reliably produce good engineering work in this repository?* The answer, on the evidence found, is: **mostly yes for scoped/domain rules, with one serious, concrete instruction-vs-code contradiction that is not hypothetical (`AI-1` below), one governance-test failure already in the tree (`AI-2`), and one platform-level observation about instruction staleness that this very audit session experienced firsthand (`AI-3`).**

---

## Finding AI-1 — The quote-proof "stop" rule is stated incorrectly in two AI-facing instruction documents, contradicting both the code and a third, correct instruction document

**Priority: CRITICAL**

**Finding.** Three documents describe when `quote_verify`/`quote_send` should refuse to queue a send. Two of them are wrong, and one of the two wrong ones is **the live playbook a production Hermes agent reads and reasons from at runtime** — this is not a Cursor-agent-only documentation bug, it is a bug in the instruction set of the shipped product's own AI brain.

| Source | What it says |
| --- | --- |
| `.cursor/rules/domain/30-quote-playbook.mdc` (Cursor rule, correct) | *"Checks are classed: `BLOCKER` or `WARN`. Any BLOCKER ⇒ `stop: true`; **counting failures is not a severity model.**"* |
| `.cursor/skills/jarvis-quote-playbook/SKILL.md` (Cursor skill, **wrong**) | *"`stop: true` when **more than 2** checks fail — fix process; do not queue send. **1–2** failures may still queue Authorize with warnings."* |
| `backend/app/hermes/playbooks/quote/SKILL.md` (runtime Hermes playbook, **wrong**, installed verbatim into the live agent's skill directory by `ensure_playbooks_installed()`) | *"`stop: true` when **more than 2** checks fail — fix process; do not queue send. **1–2** fails: owner may edit and re-verify; send may still queue with loud warnings."* |

**What the code actually does.** `backend/app/quote.py:_finalize_verify()`:
```python
blocker_failures = [c for c in checks if not c["pass"] and c.get("severity", "BLOCKER") == "BLOCKER"]
...
stop = bool(blocker_failures)
```
`stop` is `True` the moment there is **one** `BLOCKER`-severity failure, regardless of count, and `False` for any number of `WARN`-severity failures. There is no "more than 2" threshold anywhere in the implementation. The Cursor rule (`30-quote-playbook.mdc`) matches this exactly; the skill and the runtime playbook do not.

**Why it matters — this is not a cosmetic doc-drift issue.** `backend/app/hermes/playbooks/quote/SKILL.md` is copied verbatim into `{hermes_home}/skills/shop/quote/SKILL.md` on every API startup (`hermes/bridge.py:ensure_playbooks_installed()`) and is the actual text the live Hermes agent reads to decide how to talk to the shop owner about a quote's readiness. Under the playbook's stated (wrong) rule, Hermes could reasonably narrate to the owner *"two checks failed but that's within our two-failure allowance, queuing the send now"* for a quote with, say, one BLOCKER (missing outsource price) and one WARN — and then `quote_send`'s actual `verify_quote(stage="send")` call would refuse (`stop: true` because of the one BLOCKER) the instant it tried, producing a confusing contradiction between what the agent just told the owner and what the tool does. This is exactly the audit brief's "two code paths implement the same business rule differently" and "UI/agent communicates something the backend doesn't guarantee" patterns, except the "UI" here is the shop owner's own AI aide narrating an incorrect policy about money.

**Likely root cause.** The Cursor rule (`30-quote-playbook.mdc`) reads as a *later, corrected* restatement — its explicit callout "counting failures is not a severity model" reads like a direct, deliberate correction of the exact mistake still present in the other two files, suggesting the correction was made in one place (the Cursor rule, most likely during the `overhaul` rule-tree reorganization) and never propagated to the skill or — critically — the actual runtime playbook file, which is a separate file that required its own edit.

**Consequences if left unchanged.** The runtime agent (Hermes) can misstate quote-send readiness to the shop owner in a way that would be corrected by the tool's hard refusal, but only after the owner has already been told something inaccurate about the state of their own quote. The Cursor skill perpetuates the same wrong mental model in any future coding agent that reads it before touching quote code, risking a "fix" that reintroduces a count-based threshold into the code to match the (wrong) skill text.

**Recommended change.** Correct both the skill and the live playbook to match the Cursor rule and the code: any BLOCKER stops; WARN never stops, regardless of count. This is a two-file text edit, not a code change (the code is already correct).

**Example of better guidance (for the playbook specifically, since it is Hermes-facing prose, not a Cursor rule):** *"`jarvis_quote_verify` returns pass/fail per check with a severity. Any single BLOCKER means `jarvis_quote_send` will refuse — do not tell the owner it's queueable. WARN-only results may still queue, however many WARNs there are."*

**Maintenance implication.** Any domain rule that has a runtime-playbook counterpart (today: only quote, but `31-gcode-optimiser.mdc` anticipates a `hermes/playbooks/gcode/` in the same shape) needs an explicit "these two files must agree" note and, ideally, a test that diffs the two for the specific numeric/severity claims that must match — the same category of protection `test_rule_budget.py` already provides for rule word counts, but for *content consistency* between the Cursor rule and the runtime playbook it describes.

---

## Finding AI-2 — The rule tree's own governance test is currently failing on this branch

**Priority: HIGH**

**Finding.** `python -m pytest -m "not live_service"` was run in full during this audit: 432 passed, **1 failed** — `backend/tests/test_rule_budget.py::test_word_budgets`, because `.cursor/rules/ops/42-dispatch.mdc` is 402 words against its own declared 400-word cap (`STANDARD_MAX_WORDS = 400`). `git log -- .cursor/rules/ops/42-dispatch.mdc` shows the file was modified in the immediately preceding commit on this branch (`41542be`, "chore: allow explicitly authorized direct work") — the commit that added the "Exception — explicit direct work" paragraph analyzed favorably elsewhere in this audit for its *content* (see `03-cross-domain-findings.md`) but which was not checked against the test suite that exists specifically to govern rule-file size before being committed.

**Why it matters.** This is the single most concrete, reproducible piece of evidence in this entire audit for the question "would a capable but imperfect agent following these instructions produce good engineering work" — because the answer here is observable, not inferred: an agent (of some kind, on this exact branch, in a commit dated the same day as this audit) edited a rule file and did not run `pytest -m "not live_service"` before committing, despite `.cursor/rules/ops/40-tests.mdc` itself saying *"Default CI / local isolated run: `pytest -m "not live_service"` must pass without external services"* and despite `test_rule_budget.py` existing for exactly this purpose. The rule tree is meant to be a trustworthy, tested artifact (`ops/40-tests.mdc`: *"`backend/tests/test_rule_budget.py` enforces `.cursor/rules/` word caps and frontmatter — update it when tiering law changes, not when product behaviour changes."*) — right now it is not, on the default branch, at the moment this audit ran.

**Likely root cause.** No rule or skill in the corpus instructs an agent to run the backend test suite specifically *after editing a rule file* — the testing rule (`ops/40-tests.mdc`) is scoped by glob to `backend/tests/**` and frontend test files, and does not fire for edits to `.cursor/rules/**` itself, so an agent editing a rule file under Cursor's normal glob-based auto-attachment would not automatically be shown `ops/40-tests.mdc` at all.

**Consequences if left unchanged.** The rule tree accretes exactly the kind of unchecked growth the budget system exists to prevent, silently, because nothing in the instruction system tells an agent editing a rule file that a test exists to check that edit.

**Recommended change.** Two independent, complementary fixes: (1) immediately, trim `ops/42-dispatch.mdc` back under 400 words (a content edit, not proposed here since this audit does not modify rule files — flagged for the next remediation pass); (2) add `globs: .cursor/rules/**/*.mdc` (or a dedicated short rule) so editing any rule file surfaces a reminder to run `test_rule_budget.py` specifically, not the full suite, since that file is fast and self-contained.

**Maintenance implication.** This is a cheap, durable fix (one glob addition) that closes a real, demonstrated gap — worth prioritizing precisely because the evidence that it's needed already exists in this repository's git history, not because of a hypothetical.

---

## Finding AI-3 — This audit session's own injected "always-on" rules were stale, contradicting the repository's explicit anti-legacy governance test

**Priority: HIGH — platform/environment-layer observation, not a repository-content bug**

**Finding.** At the start of this very session, this agent's system context included four "always applied workspace rules" quoted verbatim under the filenames `.cursor/rules/jarvis-subagent-dispatch.mdc`, `.cursor/rules/jarvis-living-notes.mdc`, `.cursor/rules/jarvis-core.mdc`, and `.cursor/rules/jarvis-capability-run.mdc`, each with substantial, specific content (ports, stack details, dispatch procedure, etc.). Verified directly against the actual repository (`git ls-files .cursor/rules/`, and a filesystem `find` for those exact filenames anywhere under the workspace): **none of these four files exist anywhere in this checkout, tracked or untracked.** Further, `backend/tests/test_rule_budget.py` contains `LEGACY_ALWAYS_ON = {"jarvis-core.mdc", "jarvis-capability-run.mdc", "jarvis-subagent-dispatch.mdc", "jarvis-living-notes.mdc", "jarvis-react-bits.mdc"}` and `test_no_legacy_always_on_rules()` **explicitly asserts these exact filenames must not exist** — i.e. the repository itself has a governance test proving these files were deliberately retired as part of the `overhaul` rule-tree reorganization (they were superseded by `00-jarvis-core.mdc`, `ops/42-dispatch.mdc`, `ops/41-living-notes.mdc`, and `frontend/21-react-bits.mdc` respectively), yet this session's initial context served their retired content as current, authoritative, always-on instruction.

**Why it matters.** This is direct, first-hand, reproducible evidence of the exact risk the audit brief asks about under "Could the instructions cause agents to... blindly follow stale instructions?" It happened in this session, to this agent, verifiably. The content itself was not badly wrong in substance (it described a plausible, mostly-consistent prior version of the same architecture), but it is a **different, superseded instruction layer** than the one the repository's own tests certify as current, and nothing in how it was presented distinguished it as historical. A less careful agent — or this same agent, on a task that did not involve independently re-deriving every claim from source, as this audit was explicitly instructed to do — would have no signal to distrust it.

**Likely root cause — REQUIRES FURTHER INVESTIGATION.** This audit cannot see inside Cursor's own rule-injection/caching pipeline. Plausible mechanisms include: a cached environment/session snapshot taken before the `overhaul` rule-tree reorganization commits landed, and not invalidated when the branch's `.cursor/rules/` tree changed underneath it; or a separate, non-repository rule-storage layer (e.g. account- or workspace-level rules outside git) that has not been updated to match the repository's migration. Both are plausible; this audit has no way to distinguish them from the repository side alone.

**Consequences if left unchanged.** Any Cursor Cloud Agent run against this repository may be silently governed by a superseded instruction set that the repository's own tests were specifically written to retire, with no in-band way for the agent (or the user) to detect the mismatch short of an audit like this one that cross-checks injected content against `git ls-files`.

**Recommended direction.** This is not a repository-content fix (there is nothing to change in the tracked files — they are correct and internally consistent). The recommendation is process-level: when a repository undergoes a rule-tree reorganization with a governance test asserting old filenames are gone (exactly as `overhaul` did), that should be treated as a signal to also invalidate any cached/session-level rule injection tied to that repository, and/or the always-on injected rule set should self-identify its provenance (e.g. a source commit or timestamp) so a mismatch like this one is visible without a full audit. This recommendation is aimed at how Cursor Cloud Agents are operated against this repo going forward, not at a file in this repo.

**Maintenance implication.** Worth re-checking at the start of any future long-running or high-stakes session on this repository: compare injected always-on rule filenames against `git ls-files .cursor/rules/` before trusting them as current.

---

## Finding AI-4 — `jarvis-architecture` skill's memory description is stale (Honcho)

**Priority: MEDIUM**

**Finding.** `.cursor/skills/jarvis-architecture/SKILL.md`, under "Stack," states: *"Memory: SQLite + LanceDB; dual-write with Honcho when Hermes remembers."* Verified: zero occurrences of `honcho` (any case) anywhere in `backend/app/`. The actual mirror module is `memory/mirror.py`, and `work/ARCHITECTURE_POINTS.md` records Honcho as deliberately stripped. This is the same drift the prior reconnaissance pass flagged (`00-ai-instruction-inventory.md` §9) — independently re-confirmed here, not merely carried forward.

**Why it matters.** This skill is explicitly the "read when unsure which module owns a concern" document (its own description: *"Use when changing HUD/API behavior, adding features, debugging mail/TTS/Hermes/conversations, or when unsure which module owns a concern."*) — i.e. it is deliberately positioned as a first stop for exactly the kind of question ("how does memory work here?") where this stale line would actively mislead.

**Recommended change.** Replace with: *"Memory: SQLite (`memory_docs`, source of truth) + LanceDB (best-effort write-side mirror only — reads are SQLite-only today, see `memory/store.py:search()`)."* This phrasing also has the side benefit of correctly describing `ARCH-3` (the LanceDB write-only gap) at the point future agents would first learn about the memory system, rather than only in this audit.

**Maintenance implication.** LOW cost, ongoing risk if not fixed — every future agent who reads this skill before touching memory code starts from a wrong premise.

---

## Finding AI-5 — `00-jarvis-core.mdc`'s ledger wording overstates the default runtime behavior

**Priority: MEDIUM**

**Finding.** The one always-on rule states: *"One shell: `OrchestratorShell`. Turn state is a server ledger projected by `frontend/src/lib/orchestratorFsm.ts`."* This is worded as a statement of current, unconditional fact. Verified: `turn_ledger_enabled: bool = False` is the default in `config.py`, and the synchronous `ChatResponse` path (not a server ledger) is what actually runs unless that flag is explicitly set. The sentence is *aspirationally* true (it describes the target architecture, and the code to make it true exists — see `ARCH-4`) but not *currently* true for a default desk.

**Why it matters.** This is the one rule every single agent working in this repository always sees, regardless of what file they're touching (`alwaysApply: true`, the only file with that setting per the rule tree's own governance test `test_only_t0_always_apply`). A wording that overstates ledger adoption in this specific always-on slot risks an agent reasoning about "the turn ledger" as the live source of truth for chat state when reviewing or extending chat behavior, when the code they are actually looking at (the synchronous path) is what a real desk runs.

**Recommended change.** A minimal, budget-conscious rewording such as: *"Turn state model: synchronous by default; a server-ledger-backed variant exists behind `turn_ledger_enabled` (off by default) and is projected by `orchestratorFsm.ts` when on."* This is a two-clause addition, well within the T0 200-word cap that governs this specific file (`test_t0_word_budget`), and removes the ambiguity without expanding scope.

**Maintenance implication.** Once `turn_ledger_enabled` is ever flipped to the default (a decision flagged as `PRODUCT DECISION REQUIRED` in `01-architecture-audit.md`, `ARCH-4`), this line should be revisited again — it is exactly the kind of rule text that will need a second look at that time, so noting the dependency here is itself useful for future maintainers.

---

## Finding AI-6 — Skill-level "verify" sections are trustworthy and well-scoped (positive finding)

**Priority: N/A (positive)**

Every skill file's "Verify" section was checked against the actual repository and found accurate: `jarvis-architecture/SKILL.md`'s `python -m pytest -m "not live_service"` command works exactly as stated (confirmed by running it during this audit); `jarvis-quote-playbook/SKILL.md`'s `python -m pytest backend/tests/test_quote_playbook.py backend/tests/test_semantic_router.py -q` targets real, existing test files; `jarvis-react-bits/SKILL.md`'s headless-Chrome WebGL flag (`--enable-unsafe-swiftshader`) is a specific, falsifiable, and correctly-scoped claim (not a vague "should work" statement) about a real, previously-encountered failure mode. This is a genuinely good pattern — instructions that give an agent an executable, checkable command rather than prose — and should be the template for how any *new* skill's verification section is written, in contrast to some rule text elsewhere (e.g. `AI-5`) that states architecture as unconditional fact with no way to check it inline.

---

## Finding AI-7 — Placement policy (cloud vs. desk) is one of the most mature parts of the instruction system

**Priority: N/A (positive)**

**Finding.** The dispatch rule (`ops/42-dispatch.mdc`), `AGENTS.md`, and `jarvis-observation-dispatch/SKILL.md` all state a **consistent, specific, falsifiable** placement policy: cloud-by-default for anything HUD-rendering/layout/scroll/card-state (because a headless browser with one specific launch flag can actually verify it — the flag itself is documented, not hand-waved), and desk-only for exactly five named dependencies (Hermes `:8642`, Voicebox `:17493`, real Google OAuth, GPU-representative Ollama, physical mic/speaker). This was independently exercised during this very audit: the backend and frontend were started in this cloud sandbox from a cold `.venv`/`node_modules`, `GET /api/health` responded correctly reporting Hermes/Voicebox as unavailable (exactly as the policy predicts for a cloud VM), and a computer-use walkthrough of the live HUD was dispatched successfully in this same environment (see `03-ui-ux-audit.md`) — confirming the policy's central claim in practice, not just on paper.

**Why this matters for the target direction.** This is the pattern other parts of the instruction system should be measured against: specific, falsifiable, and independently confirmed true. It should not be diluted or genericized in any future rule-tree consolidation.

---

## Finding AI-8 — Missing guidance: no instruction tells an agent when a domain rule and its runtime-playbook counterpart must be checked together

**Priority: MEDIUM**

**Finding.** `AI-1` is a direct, demonstrated consequence of a missing piece of guidance: nothing in `.cursor/rules/domain/30-quote-playbook.mdc`, `.cursor/skills/jarvis-quote-playbook/SKILL.md`, or `ops/40-tests.mdc` tells an agent editing quote-domain logic that there are **three** places a given business rule (like the BLOCKER/WARN severity model) can live — the Cursor rule, the Cursor skill, and the Hermes-installed runtime playbook — and that changing the rule in one without the other two is a silent, hard-to-detect drift, precisely because the Cursor rule and skill are read by *coding* agents while the third is read by a *production runtime* agent (Hermes) that no Cursor-side test currently exercises for content accuracy.

**Recommended change.** Add a short, explicit note to `domain/30-quote-playbook.mdc` (well within its domain-expanded 750-word budget) naming the three locations and stating they must agree; longer-term, a test similar in spirit to `test_rule_budget.py` that extracts specific numeric/severity claims from the Cursor rule and the runtime playbook and diffs them would close this permanently rather than relying on an agent remembering to check by hand.

**Maintenance implication.** This class of gap (domain logic mirrored into a runtime-agent-facing prose file) will recur for any future playbook (`31-gcode-optimiser.mdc` already anticipates `hermes/playbooks/gcode/`) — the guidance should be general ("any domain rule with a `hermes/playbooks/*/SKILL.md` counterpart..."), not quote-specific, so it transfers automatically to the next playbook.

---

## Finding AI-9 — Missing guidance: no instruction addresses security, dependency management, or "when to stop and ask"

**Priority: MEDIUM**

**Finding.** Across all 16 rules, 5 skills, 4 agent prompts, and `AGENTS.md`, the following categories from the audit brief's own checklist have **no dedicated instruction anywhere in the corpus**: (a) security review practices beyond the specific HITL/consent/vision-quota domain rules (which are excellent *domain-specific* security controls but are not framed as "security" generically — e.g. there is no instruction about secret-scanning, dependency-vulnerability triage, or what to do if an agent discovers a credential in a file); (b) dependency management (no rule addresses how/when to add a new Python or npm package, pin versions, or evaluate a new dependency's footprint — relevant given the codebase already carries multiple optional heavy dependencies: `lancedb`, `pymupdf`/`pypdfium2`, `mcp`); (c) an explicit, general "when should an agent stop and ask the product owner instead of guessing" rule — the closest equivalents are domain-specific ("Unresolved alias → ask; never guess," `32-master-data.mdc`; "Missing trusted geometry → refuse," `31-gcode-optimiser.mdc`) but there is no repo-wide principle stating this pattern generally, so it has to be independently rediscovered per domain rather than applied as a standing default.

**Why it matters.** The domain-specific "ask, don't guess" instances are genuinely strong (see `AI-7`-adjacent praise) precisely because they are concrete — but their concreteness is also why they don't generalize: an agent working on a brand-new module with no domain rule yet written has no standing instruction telling it "when data is missing, ask rather than infer," only a pattern it would have to notice by reading several unrelated domain files and inferring the house style itself.

**Recommended change.** A short, general principle belongs in `00-jarvis-core.mdc` or a new lightweight `ops` rule: something like *"Missing data is an ask, not a guess — this applies beyond the domains that already say so explicitly."* Given `00-jarvis-core.mdc` is already near its 200-word T0 cap, this likely belongs in a new short `ops/43-uncertainty.mdc`-style file rather than being squeezed into T0.

**Maintenance implication.** LOW cost to add; HIGH value as new domains are added, since it removes the need to re-derive the same principle domain-by-domain.

---

## Finding AI-10 — The dispatch rule's "do not inherit parent model" instruction is contradicted by every roster agent's own frontmatter

**Priority: MEDIUM**

**Finding.** `ops/42-dispatch.mdc` and `AGENTS.md` both instruct the coordinator to launch roster workers with `model: "composer-2.5-fast"` and explicitly warn *"do not inherit parent model"* (`ops/42-dispatch.mdc`'s wording, verified: *"Launch Task with **`model: \"composer-2.5-fast\"`** — do not omit; do not inherit parent model."*). Verified directly: all four files in `.cursor/agents/` (`jarvis-builder.md`, `jarvis-uiux.md`, `jarvis-voice.md`, `jarvis-workflows.md`) declare `model: inherit` in their own YAML frontmatter (`grep -n "^model:" .cursor/agents/*.md` returns `inherit` for all four). This does not necessarily mean workers actually run on an inherited model in practice — the model actually used depends on how the coordinator's Task-launching tool call is constructed, not solely on the agent file's own frontmatter — but it means the instruction the coordinator is told to follow ("do not inherit") is not corroborated by, and reads as inconsistent with, the one place a future maintainer would naturally look to confirm which model a given roster agent runs on.

**Why it matters.** A future agent asked to "check what model the workflows specialist uses" would read `jarvis-workflows.md`'s frontmatter and reasonably conclude `inherit`, contradicting the dispatch rule's explicit instruction to the coordinator. Whichever is actually authoritative (the dispatch rule's launch-time override, most likely, given Cursor's Task tool lets the caller specify a model independent of a resumed agent's own file) should be reflected consistently in both places, or the agent-file frontmatter should be removed/commented to avoid the contradiction.

**Recommended change.** Either update the four agent-prompt frontmatters to `model: composer-2.5-fast` (making the file self-consistent with how it's actually meant to be launched), or add a one-line note in each agent file acknowledging that `model: inherit` in this file is overridden by the coordinator's launch-time setting per `ops/42-dispatch.mdc`.

**Maintenance implication.** LOW cost; prevents a plausible future misreading.

---

## Finding AI-11 — An agent prompt states a different exports path than the root rule and the actual code

**Priority: MEDIUM**

**Finding.** `.cursor/agents/jarvis-builder.md`: *"Files only under `backend/exports`."* `00-jarvis-core.mdc`: *"Written files: `<repo>/exports/` only."* `backend/app/config.py`: `exports_dir: Path = REPO_ROOT / "exports"` — i.e. the real, code-enforced path is `<repo>/exports/`, a sibling of `backend/`, not a subdirectory of it. `backend/exports` (as literally written in the agent prompt) would be a different, nonexistent directory. This is a direct, verifiable path contradiction between an agent-facing instruction file and both the always-on rule and the actual `Settings` default.

**Why it matters.** `jarvis-builder` is the general-implementer agent — exactly the one most likely to be asked to write a new file-producing tool and to trust this specific sentence about where output must go. Following it literally would put files in the wrong place.

**Recommended change.** Fix `jarvis-builder.md` to read `<repo>/exports/` (or simply "exports/ at the repo root"), matching `00-jarvis-core.mdc` and `config.py` exactly.

**Maintenance implication.** LOW cost; this is exactly the kind of small, mechanical inconsistency worth a periodic automated check (e.g. grep all agent/skill/rule files for the literal string `exports` and confirm they agree), since it's cheap to introduce and easy to miss in review.

---

## Finding AI-12 — A skill companion file (`catalog.md`) references a component that no longer exists and describes the orb's implementation incorrectly

**Priority: LOW-MEDIUM**

**Finding.** `.cursor/skills/jarvis-react-bits/catalog.md` lists `monitor/MonitorDesk.tsx` as an existing consumer of `EvilEye` ("Monitor only; unmount on workspace switch") and describes `JarvisCore.tsx` as using "Particles / LightRays." Verified: `find frontend/src/components/orchestrator -iname "*monitor*"` finds no `MonitorDesk.tsx` anywhere in the tree (only `monitor/AgentOrbit.tsx` exists, a different, still-current component); and `JarvisCore.tsx` renders a locally-defined `OrbDust` canvas function, not the vendored `Particles.tsx` react-bit. Both claims are stale relative to the substrate/pane overhaul.

**Why it matters.** `catalog.md` is the one file `jarvis-react-bits/SKILL.md` explicitly tells an agent to consult for "existing props/colors" before adding a new React Bits accent — an agent following that pointer would look for a nonexistent file and describe the orb's actual implementation incorrectly in any resulting change.

**Recommended change.** Update `catalog.md`'s consumer list to reflect `AgentOrbit.tsx` (not `MonitorDesk.tsx`) and `OrbDust` (not `Particles`) for `JarvisCore.tsx`, consistent with the correction already needed for the main `21-react-bits.mdc` rule's own EvilEye-placement claim (flagged as a possible drift in the original reconnaissance and independently confirmed stale here).

**Maintenance implication.** LOW cost. This is the same staleness pattern as `AI-4` (Honcho) recurring in a different file — worth checking `catalog.md`-style companion files specifically whenever the component they document is refactored, since they are easy to forget relative to the primary rule/skill file.

---

## Finding AI-13 — Several rule globs point at paths that do not exist, and one rule's frontend glob currently matches zero files

**Priority: LOW**

**Finding.** `domain/30-quote-playbook.mdc`'s glob list includes `backend/app/masterdata/rates.py`, which does not exist (the real files are `masterdata/mhr_lookup.py`, `masterdata/lookup.py`, etc.). `domain/31-gcode-optimiser.mdc`'s globs include `backend/app/machining/**` and `backend/app/hermes/playbooks/gcode/**`, neither of which exist yet (only `playbooks/quote/` exists today). `ops/40-tests.mdc`'s glob includes `frontend/**/*.test.ts`/`frontend/**/*.test.tsx`, and no such files exist anywhere in `frontend/` — meaning this rule's frontend-testing guidance currently has no glob that would ever attach it to a real frontend file being edited.

**Why it matters.** A glob-scoped rule with a path that doesn't exist yet is not harmful by itself (it simply never attaches until the path is created, which is presumably the intent for `31-gcode-optimiser.mdc`'s anticipatory globs), but `domain/30-quote-playbook.mdc`'s `rates.py` reference is different in kind: it looks like a **renamed** file the rule's glob was never updated for, not an anticipated future one, since `masterdata/mhr_lookup.py` clearly serves the role `rates.py` would have. If so, an agent editing MHR-rate logic today would not have this rule auto-attached by glob (only by its description, if Cursor's routing falls back to that).

**Recommended change.** Update `domain/30-quote-playbook.mdc`'s glob to `backend/app/masterdata/mhr_lookup.py` (and any other actual masterdata file it should cover) in place of the nonexistent `rates.py`. Leave `31-gcode-optimiser.mdc`'s anticipatory globs as-is (they are plausibly deliberate). No action needed on `40-tests.mdc`'s frontend glob until frontend test files actually exist — flagging it here only so it isn't mistaken for evidence that frontend testing guidance is being silently applied today when it structurally cannot be.

**Maintenance implication.** LOW cost; worth a periodic automated check (a test similar to `test_rule_budget.py` could assert every literal (non-glob-wildcard) path segment in a rule's `globs:` line resolves to an existing file or directory) to catch this class of drift automatically going forward.

---

## Skill-by-skill evaluation

| Skill | Purpose clear? | Scope | Overlap | Should exist? |
| --- | --- | --- | --- | --- |
| `jarvis-architecture` | Yes — single best "start here" doc | Broad by design (it's the map) | Overlaps `AGENTS.md`'s ownership table (acceptable — one is prose, one is a table; both stay short) | Yes, keep. Fix `AI-4` (Honcho line). |
| `jarvis-quote-playbook` | Yes | Correctly scoped to quote domain | Meaningful content overlap with `domain/30-quote-playbook.mdc` (the rule is the enforceable subset; the skill is the workflow narrative) — the overlap is a **feature** here (rules = "break-if-wrong," skills = "how-to"), except where they now disagree (`AI-1`) | Yes, keep, fix `AI-1`. |
| `jarvis-react-bits` | Yes, exceptionally concrete | Correctly scoped | No overlap of concern with `frontend/21-react-bits.mdc` (rule = placement table; skill = code pattern + the WebGL flag) | Yes, keep as the model example (`AI-6`). |
| `jarvis-capability-test` | Yes | Correctly scoped to the live matrix-running loop | None | Yes, keep. |
| `jarvis-observation-dispatch` | Yes | Correctly scoped to the observe→delegate loop | Meaningful overlap with `ops/42-dispatch.mdc` (both describe the roster and placement policy) — this is the one place genuine duplication exists between a rule and a skill with no clear "rule = constraint, skill = procedure" split, since both state the same roster table and the same five desk-only dependencies almost verbatim | Yes, keep, but **should be merged or one should defer to the other** — see `03-target-direction.md`. |

---

## Summary table

| ID | Priority | One-line |
| --- | --- | --- |
| AI-1 | CRITICAL | Quote "stop" rule stated as a >2-count threshold in the Cursor skill **and** the live Hermes runtime playbook; code and the Cursor rule correctly use "any BLOCKER" |
| AI-2 | HIGH | `test_rule_budget.py` is currently failing on `overhaul` (`ops/42-dispatch.mdc` over its own word cap) — demonstrated process gap, not hypothetical |
| AI-3 | HIGH (platform-level) | This session's own injected always-on rules were stale/retired content per the repo's own governance test — observed firsthand |
| AI-4 | MEDIUM | `jarvis-architecture` skill's "dual-write with Honcho" line is stale |
| AI-5 | MEDIUM | The one always-on rule overstates turn-ledger adoption as unconditional current fact |
| AI-6 | N/A (positive) | Skill "Verify" sections are concrete, falsifiable, and confirmed accurate — model pattern |
| AI-7 | N/A (positive) | Cloud/desk placement policy is specific, falsifiable, and was independently confirmed true in this session |
| AI-8 | MEDIUM | No instruction flags that domain rules with a Hermes-playbook counterpart must be kept in sync |
| AI-9 | MEDIUM | No general instruction for security/dependency-management/"ask don't guess" beyond scattered domain-specific instances |
| AI-10 | MEDIUM | All 4 roster agent-prompt frontmatters say `model: inherit`, contradicting the dispatch rule's "do not inherit" instruction |
| AI-11 | MEDIUM | `jarvis-builder.md` states `backend/exports` as the output path; the root rule and code both say `<repo>/exports/` |
| AI-12 | LOW-MEDIUM | `jarvis-react-bits/catalog.md` references a deleted component (`MonitorDesk.tsx`) and misdescribes the orb's current implementation |
| AI-13 | LOW | `domain/30-quote-playbook.mdc`'s glob points at a renamed/nonexistent file (`masterdata/rates.py`); two other rules' globs anticipate not-yet-created paths |
