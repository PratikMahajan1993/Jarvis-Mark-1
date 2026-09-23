# Architecture points

Living notes from conversation. Update when the owner changes how Jarvis is structured.  
As-built snapshot: [`docs/CURRENT.md`](../docs/CURRENT.md) · locked vision: [`VISION_WORKBOOK.md`](VISION_WORKBOOK.md)

---

## Current lock (updated 2026-09-22)

- **Jarvis** is the thin orchestrator (HUD, voice, HITL, connectors, routing). The user always talks to Jarvis.
- **Hermes** is the brain for shop jobs and tools. **Casual chat** skips Hermes and goes straight to Gemini (speed). Gemini remains vision / overflow / explicit Task.
- **One HUD shell** — `OrchestratorShell`. Do not bring `HudShell` back as the primary desk. Do not split into three Next.js routes.
- **Two layers of state, never collapsed:**
  - `HudWorkspace`: `casual` | `monitor` | `engineering` (job of the screen)
  - `JarvisState` turn FSM: `IDLE` | `LISTENING` | `THINKING` | `SPEAKING` | `AWAITING_HITL` | `EXECUTING`
- Name workspace 2 **Monitor** in code. FSM `IDLE` still means “no turn in flight.”
- **Hybrid switch:** auto from focus when unpinned; pin locks until unpin. Pin does not block explicit work (switcher, + New, RFQ engineering, focusing a job/drawing). Empty-desk / timeout must not yank a pinned workspace.
- **Talk-jump from Monitor:** short status questions stay; mail/chat → Casual; drawing/quote/strategy → Engineering.
- Frontend skins: `orchestrator/casual/`, `monitor/`, `engineering/`, `shared/`. Shell stays the conductor (FSM, voice, API).
- HITL before send mail, calendar writes, quote send, CNC promote, sheet overwrite, broad memory wipe. **The owner is the sole commercial signer** — no approval tiers, no delegation — so authorisation must be claim-once (a duplicate click is the only way a second approval can exist), and a queued quote Authorize never expires silently.
- **Memory is 100 % local:** SQLite for the ledger, LanceDB for vectors, no cloud memory service. Honcho is stripped; `VISION_WORKBOOK` §2’s dual-write plan is superseded.
- **Cloud vision is three-gated:** per-customer consent defaults to **deny** (NDA drawings never leave); **only an owner action spends a unit** — automated ingest stops at the free local extract and flags `needs_vision`, so no watch, retry, background job, or tool call can charge the pool; and authorised customers share a cap of **5 documents per 10:00→10:00 cycle**, with a sixth asking for an override worth one document and a pack over four sheets asking first. An override never grants consent. Known drawings answer from their saved card without a call.
- **Tool wear is manual-log only** for now — `toolwatch` v0 from spoken/typed insert-change entries. No FOCAS/MTConnect, no sensors, no `machine_telemetry` in this phase.
- Max **3** expanded Open notes.
- Files only under `<repo>/exports`. Data under `<repo>/data/`.
- Brain never invents prices, mail, or calendar facts — tools own those.
- Monitor WebGL is **Evil Eye only**, reduced-res / 30fps, and **pauses** when Monitor is not the live presence. Aero Shards stay vendored but are **not** on the Monitor desk. Casual LightRays/Particles **pause** off Casual. Pause also on hidden tab / reduced motion.
- HUD workspace changes morph in layers (presence → theme → chrome); do not swap desks in one frame.
- Agent roster is **data-driven** (`backend/app/agents.py` / API `agents`); names may change without rewriting the HUD.
- **Jobs are Hermes playbooks, not extra agents.** One Hermes brain. `RES.01` / `SEC.02` / `DAT.03` / `OPS.04` stay HUD orchestra labels. Repeatable shop work lives in a playbook folder (process + toolbox + fail-able proof + `notes.md` loop). Do not dump job SOPs into `SOUL.md`. First playbook: RFQ/quote.
- **Quote start is many doors, one playbook.** RFQ email, urgent walk-up, hard-copy in the office, old WhatsApp/email file. No extra intent-model layer for that. Existing thin router (`semantic_router.py`) only stamps coarse HUD route; Hermes + shop-quote `When to use` (owner’s actual phrases) loads the job. Casual paraphrase is expected.
- **Quote drawing lookup:** focus → named local search → save mail attach → ask for photo/drop. Ambiguous or missing path: ask. Do not quote from a Gmail thumbnail or “last file in DB.”
- **This overhaul runs on local agents** (owner, 2026-09-23). Cursor workers for the manifest chunks stay on this machine, on branch `overhaul`. They do not run as cloud agents. Parallel chunks use separate local git worktrees so they do not share one working tree. Wave 1 tests use a temporary database and do not migrate `data/jarvis.db`.
- **Quote money path:** labour-only vs buy raw material first. Default is per customer (some labour-only, some must buy RM); this order’s mail or a verbal “with material” overrides it. If unknown, ask. RM price is a supplier quote when it has arrived; if not, an estimate is allowed only from historical transactions and market trend, and it must be marked as an estimate. Machining cost uses each machine type’s **minimum MHR as a floor** (quoted rate may be higher). The demo rate table in the local DB is the production source while the Master data UI is deferred, filled with the owner’s real rates — a rate prices a quote only once **owner-attested** and no longer equal to its shipped seed value, and a missing machine, missing rate, or unlisted machine **blocks** the send rather than skipping the check. Outsource when there is no suitable machine, the customer asked, capacity is full, or the process is not done in-house (heat treat, plating, grinding, and similar). Every price line must be present before send, and a raw-material basis older than **30 days** blocks the send with no override. **Delivery is never computed** — no capacity model, no lead-time arithmetic — but Jarvis insists on one: the proof is stage-aware, warning at draft so pricing can be reviewed and blocking at send, with the field carried inline on the Authorize card. Customer and party fields come from Master data later. **Never underquote:** do not drop below minimum MHR, do not omit an outsource or a required raw-material cost, and do not add material cost on a labour-only order. Jarvis does not invent an RM figure, the MHR floor, or an outsource price with no source.

---

## Log

### 2026-09-23 — Overhaul workers are local

Owner: do not dispatch cloud agents for this overhaul. Use local agents. The manifest’s cloud placement (§5.6) is overridden for the duration of the overhaul; the §8 product locks are unchanged. Parallel chunks get separate local worktrees. Live `data/jarvis.db` is not the migration target for wave 1 tests.

Owner confirmed the wave-1 fences: PG1 rejects an undated raw-material basis and leaves the 30-day age comparison to Q5b; V1 creates `vision_quota_usage` and `disclosure_log` without a `customers` foreign key (`customer_id` nullable, no consent row); the three domain rules are pasted verbatim and the 400-word cap does not apply to them (cap 750), while every other scoped rule stays ≤400 words and the always-on core stays under 200.

### 2026-09-22 — Three refinements after review (vision spend, delivery stage, one worker per file)

Owner, on the edges raised in manifest §6.28–§6.31 and the wave-1 dispatch plan:

- **Automated ingest never spends a vision unit.** Mail ingest runs the free local text extraction and flags the drawing `needs_vision`; the 5-per-cycle Gemini quota is consumed only when the owner explicitly opens that RFQ at the desk. Multi-page threshold check approved (default 4 sheets).
- **Delivery insists but does not block the draft.** A missing delivery date warns at draft so pricing can be reviewed, and blocks the final Authorize to send. The proof therefore takes a stage.
- **One worker per file.** The three proof gates merge into a single `PG1` chunk rather than three parallel workers colliding in `quote.py`.

### 2026-09-22 — Seven executive decisions locked (manifest §8)

Owner locked, after reviewing [`OPUS_ARCHITECTURE_MANIFEST.md`](OPUS_ARCHITECTURE_MANIFEST.md):

1. **Cloud vision** — default-deny per customer; authorised customers capped at 5 drawings per 10:00→10:00 cycle across automated ingest *and* manual uploads; a sixth needs an explicit manual override.
2. **Rate data** — keep the `source_kind='demo'` table; the owner fills it with real shop rates. Sendability therefore hinges on **attestation**, not storage.
3. **Sign-off** — owner alone. No multi-tier approval workflow.
4. **Telemetry** — `toolwatch` v0 on the manual shop log; FOCAS/MTConnect deferred to a later phase.
5. **Estimate staleness** — raw-material basis older than 30 days is a hard block on send.
6. **Memory** — strip Honcho; 100 % local-first on LanceDB + SQLite.
7. **Delivery** — never guessed or calculated; the field stays empty and blocks Authorize until the owner fills it. Reverses interview Q7 on that point; the block sits at Authorize, not at build.

Mechanisms and the edges each lock opens (overnight ingest spending the vision budget, multi-sheet packs, a 30-day block with no override, a markdown rate file with no history) are in manifest §0.1, §8, and §6.28–§6.31.

### 2026-09-21 — Knowledge planes: a drawing is remembered, not reprocessed

Owner: when Jarvis discusses an engineering drawing for the first time it saves the **confirmed** information; the next time that drawing comes up it talks from that store instead of processing the drawing again. Jarvis also needs a working memory of the shop floor and other known facts so familiar questions answer fast.

Design answer (proposal in [`OPUS_ARCHITECTURE_MANIFEST.md`](OPUS_ARCHITECTURE_MANIFEST.md) §4B): three planes that never collapse — **ledger** (SQL master data owns every number), **knowledge cards** (per-entity confirmed facts with provenance; only owner-confirmed facts are quotable), **corpus** (chunks for citation). Drawing identity resolves by file hash → text fingerprint → `(customer, drawing_no, revision)`, so a revision change is a diff and a warning, never a silent reuse. Vision re-runs only when the card is missing, the revision changed, the bytes changed, extraction failed, or the owner asks. Shop-floor memory is an event log plus a rebuildable `shop_state` projection with a freshness stamp.

### 2026-09-21 — Architecture manifest requested (proposal, not yet lock)

Owner commissioned a one-time architectural overhaul document: resilience and state reconciliation, the `.cursor/rules` tier system, precision-machining features, master data schema, agent handoff protocol, and blind spots. Lands as [`work/OPUS_ARCHITECTURE_MANIFEST.md`](OPUS_ARCHITECTURE_MANIFEST.md). Nothing in it is a lock until the owner answers §8; `docs/CURRENT.md` stays as-built.

### 2026-09-22 — Casual chat is Gemini-direct

Owner: casual replies should be as fast as the Gemini API allows, and the voice should be witty. Hermes stays on tool and quote turns.

### 2026-09-16 — Three workspaces

Owner: split the HUD by job of the screen so frontend areas have clearer goals.

- Casual = current desk behaviour (mail, simple tasks, drawings-in-chat, historical mail talk).
- Monitor (owner said “idle”) = watch Hermes agents; warmer presence; no weather, no left chat rail.
- Engineering = drawings, quotations, machining strategies as a bench, not another cinematic orb.

Switching: hybrid auto + pin. Monitor talk: status stays, anything else jumps.

### 2026-09-16 — Staged morph; shards off Monitor

Owner: workspace switches must morph (presence first, then palette, then chrome). Aero Shards leave Monitor entirely; Evil Eye is the only Monitor WebGL surface.

### 2026-09-17 — Laptop GPU budget

Owner: Evil Eye must play without lag on almost all laptops. Reduced internal resolution + 30fps; pause off-workspace WebGL (eye and casual rays/particles).

### 2026-09-17 — Hermes playbook loop (quote first)

Owner: apply [The AI Delegation Loop](https://theactionableai.com/guides/ai-delegation-loop/read) to the Hermes brain — one playbook per repeated job (process, toolbox, proof, fix-the-folder-not-the-chat), not one specialist agent per job. Quote is the first playbook. Orchestra codes remain labels. Speed/accuracy scale as more folders + tool-owned numbers + snapshot fast path, not more runtimes.

### 2026-09-17 — Quote can start many ways; no extra intent AI

Owner: RFQ email, improvised urgent job, customer in the office with a hard copy, or an old WhatsApp/email drawing. Typical phrases: “I want to create a new quote for XYZ drawing”, “Lets work on the RFQ my deepak last weak”, “Start quote workflow for XYZ” — tone may be more casual. Asked whether a new intent-recognition layer is needed; lock is no — Hermes + playbook trigger text, existing router stays thin.
