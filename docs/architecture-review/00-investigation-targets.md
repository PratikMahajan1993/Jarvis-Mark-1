# Investigation targets (ranked reconnaissance)

Prioritized areas for **follow-up investigation** based on this audit. Observations only — no redesign or fix prescriptions.  
**Uncertainty:** items marked *Unknown — requires further investigation.*

---

## Priority legend

| Priority | Meaning |
| --- | --- |
| **P0** | Likely affects correctness, safety, or operator trust if misunderstood |
| **P1** | Significant product/architecture gap or active overhaul risk |
| **P2** | UX, docs, or maintainability drift; degraded experience |
| **P3** | Cleanup, test hygiene, or latent tech debt |

Categories: **ARCH** architecture, **LOGIC** domain correctness, **UI** HUD/UX, **AI-DEV** instructions/agents/skills.

---

## P0

| ID | Cat | Target | Grounding | Investigation question |
| --- | --- | --- | --- | --- |
| P0-1 | LOGIC | Quote send / verify / HITL proof gates | `quote.py`, `hermes/mcp_server.py`, `test_quote_proof_gates.py`, `test_quote_playbook.py` | Do runtime paths enforce attested MHR, RM basis age (30d), delivery stage (warn draft / block send), and verify failure `stop` consistently with `work/ARCHITECTURE_POINTS.md`? |
| P0-2 | LOGIC | Hermes session per quote | `hermes/bridge.py` (`_quote_conversation_key`, session file), `test_hermes_quote_session.py` | After quote start, are follow-up turns isolated from `default` session and protected against duplicate concurrent Hermes calls? |
| P0-3 | ARCH | HITL claim-once / authorize semantics | `agent.resolve_pending`, `hermes/hitl.py`, pending table | Is duplicate Authorize rejected at DB/API layer as living notes require? |
| P0-4 | LOGIC | Safety deny phrases | `intent.SAFETY_DENY_PHRASES`, tool execution paths | Are deny phrases blocked on all execution routes (Hermes MCP + legacy tools), or only specific classifiers? |
| P0-5 | ARCH | API auth middleware vs HUD | `main.py` `mutating_local_auth_middleware`, `frontend/src/lib/api.ts` `mutatingAuthHeaders` | When HUD is opened from non-localhost origin with ledger/HITL mutations, is bearer token configuration documented and tested (`test_lan_confirm_blocked.py` scope)? |

---

## P1

| ID | Cat | Target | Grounding | Investigation question |
| --- | --- | --- | --- | --- |
| P1-1 | ARCH | Turn ledger default off vs HUD/API dual paths | `config.turn_ledger_enabled=False`, `main.api_chat` branches, `OrchestratorShell` ledger + `TurnStageLine`, `00-jarvis-core.mdc` wording | What is the intended production default? Are reconcile/SSE paths tested under flag-on in CI? |
| P1-2 | ARCH | Memory read path (LanceDB vs SQLite) | `memory/store.py` (`_lance_upsert` vs `search()` cosine on SQLite vectors only), `rag/search.py`, manifest §6.4 / K5 | Is LanceDB ever queried for recall, or only best-effort mirror? Does `real_embeddings_enabled` change read behavior? |
| P1-3 | LOGIC | Master data feature flag | `masterdata_enabled=False`, `masterdata/*`, migrations 0004–0007 | Which quote/pricing paths use SQL master data vs `client-names.md` / demo tables when flag off? |
| P1-4 | LOGIC | Vision quota / consent / bench | `vision/*`, `knowledge/*`, flags `vision_bench_enabled`, `knowledge_cards_enabled`, engineering UI components | Which gates are implemented vs scaffold-only relative to manifest §8 vision locks? |
| P1-5 | ARCH | Semantic router ↔ Hermes ↔ legacy triangle | `semantic_router.py`, `agent._run_agent` routing order | For `tool_ops` Hermes timeout, catalog all fallbacks (quote string, legacy, casual Gemini) and whether router stamps appear in HUD agents payload. |
| P1-6 | LOGIC | RFQ `reason_rfq` vs shop-quote playbook | `rfq.py`, `intent`, `test_rfq.py`, playbook SKILL | When is `reason_rfq` still invoked, and does it conflict with “no drawing path” quote rules? |
| P1-7 | ARCH | Snapshot / mail sync correctness | `snapshot.py`, `mail_sync.py`, `connectors/gmail.py` | Production Gmail volume behavior (`docs/CURRENT.md` “still deepen”) — worker continuity, error surfacing, stale reads. |
| P1-8 | AI-DEV | Instruction corpus vs locks | See `00-ai-instruction-inventory.md` Honcho/ledger/skin drift table | Which docs/skills must be reconciled so agents do not reintroduce stripped Honcho or wrong shell model during overhaul? |

---

## P2

| ID | Cat | Target | Grounding | Investigation question |
| --- | --- | --- | --- | --- |
| P2-1 | UI | Perf gate failures | `work/perf/phase-6.json`, `docs/CURRENT.md`, `perf-gate.mjs` | Which long tasks (>50ms) remain on initial load, and do they block shipped UX targets in `work/SONNET_UI_VISION.md`? |
| P2-2 | UI | Substrate vs React Bits EvilEye | `substrate/*`, `21-react-bits.mdc`, `JarvisCore`, `AgentOrbit` | Is EvilEye still mounted on monitor path, or fully superseded by substrate shader weights? |
| P2-3 | UI | Pane settle / rapid lens switch | `paneStore.ts` watchdog 1400ms, `frontend/scripts/phase-3-rapid-switches.mjs` | Can `displayLens` desync from `lens` under retarget during rapid workspace switches? |
| P2-4 | UI | Open notes cap enforcement | `MAX_OPEN_CONVERSATIONS` UI slice vs backend `conversations` | Does API reject a fourth expanded note or only HUD hide? |
| P2-5 | ARCH | Canvas app coupling | `/canvas` route, `/api/canvas/*` | Is canvas part of overhaul scope or legacy parallel surface? |
| P2-6 | LOGIC | Shop state / toolwatch / cycletime | `shop/state.py`, `toolwatch.py`, migrations 0011, 0016, 0013 | End-to-end operator flows from HUD speech to persisted shop log — which are wired vs API-only? |
| P2-7 | ARCH | RAG tables vs memory_docs | migrations `0010_rag.sql`, `memory/store.py`, `rag/ingest.py` | Two retrieval systems — when does each get used (tools, eval, hybrid search tests)? |
| P2-8 | AI-DEV | Capability matrix staleness | `CAPABILITY_TEST_MATRIX.md` Honcho rows vs ARCHITECTURE lock | Which matrix IDs reference removed integrations? |
| P2-9 | ARCH | Cloud vs local overhaul policy | `work/ARCHITECTURE_POINTS.md` 2026-09-23 log | How is branch `overhaul` merged/tested given local-only worker policy? *Process — Unknown outside repo.* |
| P2-10 | UI | Talk-jump from casual/engineering | `talkJumpWorkspace` guard | Confirm casual quote phrases do **not** auto-switch to engineering unless user manually switches (product lock). |

---

## P3

| ID | Cat | Target | Grounding | Investigation question |
| --- | --- | --- | --- | --- |
| P3-1 | AI-DEV | pytest marker naming | `conftest.py` vs skill `jarvis-architecture` | Should docs reference `api_service` only, or add `live_service` marker? |
| P3-2 | ARCH | Hermes gateway health gate | `hermes_gateway_reachable` requires `hermes_api_key` | Desks without API key — does `hermes_available()` false-negative and force legacy path always? |
| P3-3 | ARCH | Uvicorn bind `0.0.0.0` in environment.json | vs rules preferring 127.0.0.1 | Ghost listeners / middleware client_host behavior on desk. |
| P3-4 | LOGIC | `brain_lock` scope | `conversations.brain_lock` wrapping `run_agent` | Interaction with turn ledger worker concurrent sessions — deadlock or queue behavior? |
| P3-5 | UI | Lab routes security | `/lab/diarize` | Exposed in production builds? Auth? |
| P3-6 | ARCH | Domain rule globs missing paths | `31-gcode-optimiser.mdc` references `backend/app/machining/**` | *Directory existence — Unknown*; glob may never attach. |
| P3-7 | LOGIC | Demo job seed | `jobs.seed_demo_job()` in `init_db` | Still relevant on production desk or test-only artifact? |
| P3-8 | AI-DEV | Duplicate dispatch docs | `AGENTS.md`, `ops/42-dispatch.mdc`, agent headers | Single source of truth for coordinator — maintenance cost only. |

---

## Suggested investigation sequencing (process note)

Not a recommendation — ordering observed by dependency:

1. **P0 LOGIC** quote/HITL/Hermes session (money + external effects).  
2. **P1 ARCH** turn ledger + memory read path (foundational behavior vs UI).  
3. **P1 AI-DEV** instruction drift (prevents wrong fixes during overhaul).  
4. **P2 UI** perf + pane settle (operator-visible).  
5. **P3** hygiene.

---

## Traceability

Findings derive from:

- `docs/architecture-review/00-codebase-map.md`
- `docs/architecture-review/00-ui-ux-inventory.md`
- `docs/architecture-review/00-ai-instruction-inventory.md`
- Source symbols cited in those documents.

---

## Audit uncertainties (global)

| Topic | Status |
| --- | --- |
| Live desk `.env` values (flags, keys) | Unknown — requires further investigation |
| Hermes gateway internal tool loop | External to repo |
| Whether Cursor merges legacy rule filenames | Unknown — requires further investigation |
| Full Canvas UI component graph | Not expanded in UI inventory |
| Exact delivery-date stage in quote HITL payload | Not verified in this pass |
| `live_service` pytest marker | Not registered in `conftest.py` |
