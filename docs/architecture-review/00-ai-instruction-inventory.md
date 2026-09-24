# AI instruction inventory (reconnaissance)

Inventory of repository-local instructions for humans and Cursor agents: rules, skills, agent prompts, playbooks, and key product docs that steer development. **Observations only** — no remediation proposals.

**Uncertainty:** *Unknown — requires further investigation.*

---

## 1. Top-level maps

| File | Role |
| --- | --- |
| `AGENTS.md` | Roster (`jarvis-uiux`, `jarvis-voice`, `jarvis-workflows`, `jarvis-builder`), placement policy (cloud vs desk), docs-of-record table |
| `docs/CURRENT.md` | As-built product snapshot |
| `work/ARCHITECTURE_POINTS.md` | Living architecture locks + dated log |
| `work/UI_UX_POINTS.md` | Living UI intent |
| `work/APP_FEATURES.md` | Living capability intent |
| `work/VISION_WORKBOOK.md` | Long-form vision (sections superseded in log) |
| `work/OPUS_ARCHITECTURE_MANIFEST.md` | Target architecture / wave plan (large) |
| `work/CAPABILITY_TEST_MATRIX.md` | Test IDs and logging |
| `work/FOUNDATION_BUILD_PLAN.md` | Older foundation plan |

---

## 2. Cursor rules (`.cursor/rules/`)

**Always-on:**

| File | `alwaysApply` | Summary |
| --- | --- | --- |
| `00-jarvis-core.mdc` | **true** | Stack, ports, OrchestratorShell, HITL, data paths, playbooks; cites `docs/CURRENT.md` + manifest |

**Scoped (globs in frontmatter — all `alwaysApply: false` unless noted):**

| File | Globs (abbrev.) | Topic |
| --- | --- | --- |
| `backend/10-api-python.mdc` | `backend/app/**/*.py` | API/Python conventions |
| `backend/11-hitl-safety.mdc` | agent, main, hermes, tools | HITL gates |
| `backend/12-data-schema.mdc` | db, schemas, migrations, masterdata | Schema/migrations |
| `backend/13-turn-ledger.mdc` | turns, agent, main | Turn ledger |
| `frontend/20-hud-shell.mdc` | orchestrator, orchestratorFsm | Shell + FSM |
| `frontend/21-react-bits.mdc` | `frontend/**/*.{tsx,ts,css}` | React Bits placement |
| `frontend/22-frontend-uiux.mdc` | frontend ts/tsx/css | UI/UX |
| `domain/30-quote-playbook.mdc` | quote, playbooks, tests | Quote playbook |
| `domain/31-gcode-optimiser.mdc` | cnc_suggest, playbooks/gcode | G-code optimiser |
| `domain/32-master-data.mdc` | masterdata, migrations | Master data |
| `domain/33-knowledge-rag.mdc` | memory, knowledge | RAG/knowledge |
| `domain/34-drawing-vision.mdc` | quote, vision, knowledge | Drawing vision |
| `ops/40-tests.mdc` | backend/tests, frontend tests | Testing |
| `ops/41-living-notes.mdc` | (no globs) | When to edit `work/*_POINTS.md` |
| `ops/42-dispatch.mdc` | (no globs) | Coordinator dispatch + capability run protocol |

### Rules not present in repo (observation)

Some Cursor Cloud / workspace injections reference paths like `.cursor/rules/jarvis-core.mdc`, `jarvis-subagent-dispatch.mdc`, `jarvis-living-notes.mdc`, `jarvis-capability-run.mdc` — **these filenames do not exist** in the checkout; nearest equivalents are `00-jarvis-core.mdc`, `ops/42-dispatch.mdc`, `ops/41-living-notes.mdc`. *Whether the IDE merges legacy names — Unknown — requires further investigation.*

---

## 3. Cursor skills (`.cursor/skills/`)

| Skill dir | SKILL.md purpose | Companion files |
| --- | --- | --- |
| `jarvis-architecture` | Stack, ownership table, verify commands | `reference.md` |
| `jarvis-quote-playbook` | RFQ/quote/Hermes/MCP/debug | — |
| `jarvis-react-bits` | HUD accents, headless WebGL flag | `catalog.md` |
| `jarvis-capability-test` | Matrix run/logging | — |
| `jarvis-observation-dispatch` | When/how to spawn roster workers | — |

Skills are referenced from `AGENTS.md` and rule `description` frontmatter for auto-routing.

---

## 4. Cursor subagent prompts (`.cursor/agents/`)

| File | Agent id | Owns (from prompt) |
| --- | --- | --- |
| `jarvis-builder.md` | jarvis-builder | General impl, verify, restarts |
| `jarvis-uiux.md` | jarvis-uiux | Layout, React Bits, weather/tasks |
| `jarvis-voice.md` | jarvis-voice | Voicebox, TTS, speak bridge |
| `jarvis-workflows.md` | jarvis-workflows | Mail, HITL, RFQ, calendar, Hermes tools |

Dispatch policy duplicates `ops/42-dispatch.mdc` and `AGENTS.md`: coordinator should not implement; workers use `model: composer-2.5-fast`.

---

## 5. Environment / install instructions

| File | Content |
| --- | --- |
| `.cursor/environment.json` | `install.sh`, uvicorn on `0.0.0.0:8000`, `npm run dev` |
| `.cursor/install.sh` | venv, deps, `.env.example` copy |

**Observation:** `00-jarvis-core.mdc` and historical rules prefer API on `127.0.0.1:8000`; cloud terminal uses `0.0.0.0:8000` — binding mismatch across instruction sources.

---

## 6. Hermes playbook instructions (runtime AI)

Installed from `backend/app/hermes/playbooks/` to Hermes home (`ensure_playbooks_installed()` in `bridge.py`).

**Quote playbook tree:**

| Path | Role |
| --- | --- |
| `playbooks/quote/SKILL.md` | Hermes skill definition (shop-quote) |
| `playbooks/quote/notes.md` | Operator loop notes |
| `playbooks/quote/files/*.md` | Rate rules, client names, templates, mhr-demo (demo floors called out in `CURRENT.md`) |
| `playbooks/quote/examples/README.md` | Examples |

MCP tool surface: `backend/app/hermes/mcp_server.py` (registers `jarvis_quote_*`, memory, mail, etc. for Hermes gateway).

---

## 7. In-app “instructions” to models (not Cursor)

| Module | Instruction-like content |
| --- | --- |
| `semantic_router.py` | `SYSTEM` prompt for Gemini flash router (intents + orchestra codes) |
| `intent.py` | Legacy routing comments (Hermes-first vs fallback) |
| `think.py` / tool refiners | Post-tool narration prompts |
| `gemini_client.py` | Model calls for chat/tools |
| Playbook markdown | Shop quote SOP for Hermes agent |

---

## 8. Relationship diagram (instruction layers)

```text
Owner intent
  → work/*_POINTS.md (living notes, ops/41-living-notes)
  → work/OPUS_ARCHITECTURE_MANIFEST.md (target)
  → docs/CURRENT.md (as-built)

Cursor coordinator
  → AGENTS.md + ops/42-dispatch.mdc
  → spawns .cursor/agents/*.md workers
  → workers load 00-jarvis-core + scoped .mdc + skills

Implementation
  → backend agent/Hermes/MCP/playbooks
  → frontend OrchestratorShell constraints (20-hud-shell, 21-react-bits)
```

---

## 9. Instruction drift observations (facts only)

| Topic | Sources in tension | Observation |
| --- | --- | --- |
| **Honcho / dual-write** | `work/ARCHITECTURE_POINTS.md` (strip Honcho, local-first); `jarvis-architecture/SKILL.md` line “dual-write with Honcho”; `work/VISION_WORKBOOK.md` (superseded banner but body retains Honcho tables); `docs/CURRENT.md` (Honcho cutover “still deepen”) | Backend code uses `memory/mirror.py` (local upsert); no `honcho` string in `backend/app/` grep; skill text stale vs living lock |
| **Turn ledger as primary** | `00-jarvis-core.mdc` (“Turn state is a server ledger projected by orchestratorFsm”); `config.turn_ledger_enabled` default **False**; sync `/api/chat` still default path | Wording implies ledger is normative; runtime default is synchronous chat unless env enables ledger |
| **Workspace skins** | `ARCHITECTURE_POINTS` “Frontend skins: orchestrator/casual/…” | Directories not in repo; pane lens model is actual structure |
| **React Bits / Monitor** | `21-react-bits.mdc`: EvilEye monitor-only; `docs/CURRENT.md`: substrate lens shader replaces per-workspace Evil Eye mount | Possible doc lag relative to substrate overhaul — *exact EvilEye mount in JarvisCore/AgentOrbit — requires file-level confirmation beyond this audit* |
| **Manifest vs code module names** | Manifest references `memory/dual_write.py` | File renamed to `memory/mirror.py`; manifest chunk K8 describes rename — code matches mirror, manifest text partially stale |
| **Capability matrix Honcho** | `CAPABILITY_TEST_MATRIX.md` cases H1, O6 mention Honcho | Living lock says Honcho stripped — matrix rows may be obsolete |
| **pytest marker** | Skill says `-m "not live_service"` | `conftest.py` only registers `api_service` marker |
| **API bind address** | Rules: prefer 127.0.0.1; environment.json: 0.0.0.0 | Affects LAN middleware tests (`test_lan_confirm_blocked.py`) vs dev habits |
| **Delivery date block** | ARCHITECTURE lock: warn at draft, block at send | *Exact stage wiring in quote.py/HITL payload — not verified in this pass* |
| **Cloud agent on overhaul** | ARCHITECTURE log 2026-09-23: overhaul workers local only | This reconnaissance ran in cloud workspace — process observation outside repo content |

---

## 10. Rule ↔ code alignment (spot checks)

| Rule claim | Implementation anchor |
| --- | --- |
| Max 3 expanded open notes | `OrchestratorShell` `MAX_OPEN_CONVERSATIONS = 3`; DB/conversations enforcement in backend (*full enforcement path — see `conversations.py`*) |
| Talk-jump only from monitor | `talkJumpWorkspace()` early return when `current !== "monitor"` |
| Voicebox `/generate` only | `voicebox.py`, `main.py` `/api/tts` |
| Quote fallback string on Hermes miss | `agent.py` `is_quote_start` block |
| HITL before send | `tools/registry.py` `_queue_pending` → `request_human_approval` |
| Files only under exports | `settings.exports_dir`, tool paths |

---

## 11. Files intentionally excluded from “AI instructions”

- Application source outside `.cursor/` and playbooks (behavioral, not agent-facing).
- `.env.example` (secrets template) — not opened in this audit.
- Gitignored runtime logs (`work/LAST_TURNS.md`, `work/LIVE_TEST.md`) — generated by API, not source-of-truth instructions.

---

## 12. Quick index (all `.mdc` + skills + agents)

```
.cursor/rules/00-jarvis-core.mdc
.cursor/rules/backend/{10,11,12,13}-*.mdc
.cursor/rules/frontend/{20,21,22}-*.mdc
.cursor/rules/domain/{30,31,32,33,34}-*.mdc
.cursor/rules/ops/{40,41,42}-*.mdc
.cursor/skills/jarvis-{architecture,quote-playbook,react-bits,capability-test,observation-dispatch}/SKILL.md
.cursor/agents/jarvis-{builder,uiux,voice,workflows}.md
backend/app/hermes/playbooks/quote/SKILL.md
AGENTS.md
```
