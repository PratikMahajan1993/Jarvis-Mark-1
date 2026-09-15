# Jarvis — Capability & Workflow Test Matrix

**Updated:** 2026-09-16 (semantic router, Orchestrator FSM, CI suite)  
**Method:** Test one use case at a time → note pass/fail + latency → small fix → re-test → next.  
**Status:** Desk model + semantic router live — **capability test run ready**.  
**Prerequisite:** Multi-conversation desk (ambient + named discussions + job workflows) on `OrchestratorShell` with strict FSM (`orchestratorFsm.ts`).  
**Sources:** `docs/CURRENT.md`, `AGENTS.md`, `backend/app/semantic_router.py`, `backend/tests/README.md`.

**Pass criteria (default):** correct behavior, HITL never skipped on external write, no HUD errors, note latency vs target (casual ≤~5s warm; simple tools ≤~15s; HUD idle <~2s).

### Tags

| Tag | Meaning |
| --- | ------- |
| **desk** | Needs Hermes, Voicebox, real Google OAuth, GPU Ollama, or physical mic/speaker |
| **cloud** | HUD layout/scroll/cards verifiable headless; or logic covered by `backend/tests` |
| **offline** | Runnable with `pytest -m "not live_service"` (partial coverage — still re-test live) |

### Agent-assisted run protocol

While you test in the HUD, tell the coordinator your observations (ID + what you saw). The coordinator will:

1. Read **`work/LAST_TURNS.md`** (auto-updated last 20 chat/confirm turns) for what Jarvis said/did.
2. Log the result (template below).
3. Delegate to a **background worker** (`jarvis-uiux` / `jarvis-voice` / `jarvis-workflows` / `jarvis-builder`) so testing can continue — placed per placement policy below.
4. Summarize the fix when the worker reports back; re-test that ID if you want.

Every kickoff to a worker must be self-contained: goal, repro, files in scope, acceptance check.

Skills: `jarvis-capability-test`, `jarvis-observation-dispatch`. Rules: `.cursor/rules/jarvis-capability-run.mdc`.  
API mirror: `GET /api/turns/recent`.

### Where a fix can run

Cloud workers lack Hermes (`:8642`), Voicebox (`:17493`), real Google OAuth, GPU-representative Ollama, and physical mic/speaker — checks needing those stay **desk**. Cloud *can* build/serve the HUD and drive headless Chrome (`--enable-unsafe-swiftshader` for orb WebGL — see `jarvis-react-bits` skill). Section **E** (HUD/FSM layout) is mostly **cloud** except live Voicebox timing. Section **K** (voice) is mostly **desk**. Semantic router logic is **cloud** + **offline**; live orchestra highlight is **desk**.

---

## A. Conversation, brain & semantic router

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| A1 | Casual chat (greeting / small talk) | “Hey, what’s up?” | Snappy reply; router `casual_chat`; RES.01 or chat path | desk |
| A2 | Work chat without tools | “Summarize what an RFQ is for our shop” | Accurate; no invented prices/qty | desk · offline |
| A3 | Hermes timeout → soft fallback | Kill gateway mid-turn or cold CLI | No blank HUD; Gemini/legacy answers | desk |
| A4 | Voice + type parity | Same ask via mic and keyboard | Same outcome (API + mic pipeline) | desk |
| A5 | Drawing-session chat | Open drawing conversation; ask about the part | Stays in drawing/vision context | desk |
| A6 | Everyday desk vs discussion | Ambient ask → New discussion → leave → resume from Open notes | Chatter stays on correct `session_id` | desk · cloud |
| A7 | Job from suggested RFQ | “Start engineering review & quote” on RFQ card | Opens/resumes workflow note; not ambient dump | desk |
| A8 | Router `tool_ops` → Hermes | “Search my inbox for Deepak” (Hermes warm) | Hermes turn first; OPS/SEC agent highlighted | desk |
| A9 | Router `tool_ops` local fallback | Same ask with Hermes down | Snapshot/local mail path; no 30s hang | desk · offline |
| A10 | Router `casual_chat` override | “What is an RFQ?” | Chat brain; not mis-routed to mail tools | desk |
| A11 | Router `vision_task` | In drawing session: “What are the dimensions?” | Drawing chat / vision path; DAT.03 highlight | desk |
| A12 | Router `ui_command` (local) | “Hide the dock” / “Show conversations” | No Hermes; `ui_action` in response; dock toggles | desk · cloud |
| A13 | `target_agent` orchestra stamp | Mail read vs draft vs OEE ask | Correct RES/SEC/DAT/OPS node lights on Orchestra | desk · cloud |
| A14 | Local-fast snapshot path | “Any unread mail?” (snapshot warm) | Skips Hermes when snapshot-ready; real inbox | desk · offline |
| A15 | Hermes compose fill | Incomplete compose draft | Fill prefers Hermes gateway then Gemini | desk |
| A16 | Task for Gemini (HITL) | “Task for Gemini: summarize this PDF outline” | Queues HITL; no silent send | desk |

## B. HITL & safety

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| B1 | Blast-radius card | Any outbound pending | Irreversibility 1–5 + consequence text | desk · cloud |
| B2 | Authorize send (button) | Draft → **Authorize** | Sends only after Authorize | desk |
| B3 | Reject send | Draft → **Reject** | Nothing sent; calm cancel speak | desk |
| B4 | Voice Authorize (“yes”) with compose edits | Edit draft fields → say yes | Sends **edited** fields, not stale | desk |
| B5 | Calendar Authorize | Queue event → Authorize | Event created (no `_jarvis` meta leak) | desk · offline |
| B6 | Sheets write Authorize | Queue shop cell write → Authorize | Cells update only after Authorize | desk |
| B7 | No silent Drive upload on HUD load | Open HUD with RFQ mail present | No unexpected Drive files | desk |
| B8 | CNC promote Authorize | Queue CNC program promote | Blast-radius high; machine-ready only after Authorize | desk · offline |
| B9 | Quote send Authorize | Queue quote email + PDF | Blast-radius 5; send only on Authorize | desk · offline |
| B10 | Browser action HITL | Queue browser task via tool | Evidence recorded; Authorize before consequential step | desk · offline |
| B11 | Email forward Authorize | Forward with attachment path | HITL before send | desk |
| B12 | Memory namespace wipe (HITL) | Broad forget/wipe request | Single-fact OK; broad wipe needs Authorize | desk · offline |
| B13 | Keyboard HITL (Y / N) | Pending panel focused; press Y then N on separate runs | Same as Authorize/Reject buttons | desk · cloud |
| B14 | FSM re-entrancy guard | Send while THINKING/EXECUTING | Second send refused; no stranded state | desk · cloud |
| B15 | Reject keeps HITL open | Reject compose fill-in | Panel stays; `resolving` then restored | desk · cloud |

## C. Mail

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| C1 | Search / list mail | “Any unread mail?” | Real inbox results on board or speak | desk |
| C2 | Read mail | “Open Deepak’s last email” | Summary + body on SpotlightCard board | desk |
| C3 | Draft compose (tight trigger) | “Draft an email to X saying …” | `DraftComposeModal`; subject optional | desk · offline |
| C4 | Incomplete draft follow-up | Draft without body → dictate body | Fills body; doesn’t false-Authorize | desk |
| C5 | Speech email repair | Spoken `pratik.28 1293@gmail.com` | Correct address in draft | desk · offline |
| C6 | Reply with attachments | Reply path + attachments | HITL before send | desk |
| C7 | Save mail attachments (explicit) | “Save drawings from that email” | Local save under exports/data; Drive only if asked | desk |
| C8 | Snapshot refresh | “Refresh my mail” / fresh intent | Snapshot rebuild; faster repeat read | desk |
| C9 | Attachment-only mail speak | Mail with attachments, minimal body | Useful speak line (not “on the board” alone) | desk |
| C10 | Forward email | “Forward that email to …” | Draft/HITL path; no silent forward | desk |
| C11 | Bulk 100d mail sync | `POST /api/mail/sync` or OAuth reconnect; poll `GET /api/mail/sync` | `synced_count` climbs; `gmail-*` rows >> 20; status → `done` | desk |
| C12 | Spam filter + allowlist | Inspect skipped vs kept in sync state; spot-check Supabase/ERPNext/Frappe mail | Promo/spam dropped; allowlisted vendor mail kept | desk |
| C13 | Mail RAG corpus | After bulk sync: “What did Supabase bill last month?” / memory recall | Answer from indexed `mail:{id}` corpus, not hot snapshot only | desk · offline |

## D. Calendar & briefing

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| D1 | Morning brief | “Good morning / brief me” | Weather + mail + calendar; short, witty | desk |
| D2 | List calendar | “What’s on today?” | Today’s events from real calendar | desk |
| D3 | Create event (HITL) | “Create a 4pm downtime meeting” | Pending → Authorize → created | desk |
| D4 | Suggested-task → calendar action | RFQ card “Only create calendar deadline” | Correct event draft pending | desk |
| D5 | Briefing glance / watch | After brief, check `/api/glance` or watch chip | Critical items surface; no crash | desk · cloud |

## E. Orchestrator HUD & FSM

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| E1 | Fast HUD bootstrap | Cold open `:3000` | Idle UI <~2s; no long blank | cloud |
| E2 | Weather chip | Open HUD | Sensible local weather in right rail (`shrink-0`) | desk · cloud |
| E3 | RFQ suggested cards | Refresh office tasks | Cards from drawing/RFQ mail | desk |
| E4 | Production suggested card | Shop log bound | Human-readable OEE (no raw dict dump) | desk |
| E5 | Card → engineering chat | “Start engineering review & quote” | Opens useful workflow thread | desk |
| E6 | Card → custom chat | “Open chat for custom tasks” | Discusses that instance | desk |
| E7 | Dismiss task | Dismiss button | Stays dismissed on reload | desk · cloud |
| E8 | FSM IDLE → LISTENING | Space / mic while idle | Mic opens; orb `listening` mode | desk · cloud |
| E9 | FSM no listen while SPEAKING | Mic during TTS playback | Structurally refused (no second recognizer) | desk |
| E10 | FSM THINKING before network | Send any chat | “Orchestrating…” immediately; not blank | cloud |
| E11 | FSM AWAITING_HITL panel | Any pending action | HitlModal + blast-radius; compose uses DraftComposeModal | desk · cloud |
| E12 | VoiceLine vs board ownership | Read mail / open compose | Center VoiceLine hidden; board/modal owns text | cloud |
| E13 | Mail board scroll | Long mail thread on board | Scroll on SpotlightCard `bodyClassName`, not outer card | cloud |
| E14 | Orchestra agent states | After mail/OEE/HITL turns | Correct node `active` or `waiting` | desk · cloud |
| E15 | Activity stream | After a few turns | Recent SYS/OPS/SEC lines; max ~8 | cloud |
| E16 | Open notes cap | Open 4th discussion | Max **3** expanded; oldest parked | desk · cloud |
| E17 | React Bits orb | Load HUD | Particles/LightRays on JarvisCore; no layout break | cloud |
| E18 | Persist focused note | Reload with note open | Restores conversation from `localStorage` | desk · cloud |
| E19 | Escape / Space shortcuts | Escape during listen; Space when allowed | Listen stops; no stuck FSM | desk · cloud |

## F. Shop / sheets / CNC / docs

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| F1 | Read shop sheet / OEE | “What’s shop OEE?” | Real numbers; no invention | desk · offline |
| F2 | Bind / ensure shop sheet | Bind by name/URL | Bound + readable | desk |
| F3 | Update shop sheet (HITL) | Ask to write a cell | Authorize then write | desk |
| F4 | Create local spreadsheet/PDF/doc | “Make a PDF note of …” | Artifact under `<repo>/exports` | desk · offline |
| F5 | CNC suggest | “Suggest G-code for this feature” | Draft program; not promoted without HITL | desk · offline |
| F6 | CNC promote (HITL) | Promote suggested program | See **B8** | desk · offline |
| F7 | Google Sheet disabled handling | Sheets API disabled/unbound | Clear speak; no fake numbers | desk · offline |
| F8 | Glance critical OEE | Low OEE in snapshot | Surfaces in glance/briefing keys | desk · offline |

## G. RFQ → quote → send (office-day spine)

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| G1 | Inbound drawing RFQ detect | Mail with drawing attachments | Task card / RFQ row | desk |
| G2 | Vision on drawing | Analyze local drawing path | Dimensions; unreadable called out | desk |
| G3 | Quote build (sheet) | Build quote from part + notes | Editable quote artifact | desk |
| G4 | Quote PDF | Export quote PDF | PDF in exports | desk · offline |
| G5 | Quote send (HITL) | Queue quote email + PDF | See **B9** | desk · offline |
| G6 | Full dry-run loop | Brief → RFQ card → vision → quote → Authorize | Aspect 14 office-day gate | desk |
| G7 | RFQ intake API | `POST /api/rfqs/intake` or tool path | Row created; links to mail/job | desk · offline |
| G8 | RFQ reason / status | Ask about RFQ status in workflow note | Consistent job/RFQ row | desk · offline |

## H. Memory & RAG

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| H1 | Remember preference | “Remember I prefer short briefings” | Stored locally (+ Honcho if Hermes) | desk · offline |
| H2 | Recall | “What do you know about me?” / memory search | Correct recall | desk · offline |
| H3 | Forget / wipe (HITL for broad wipe) | Forget one fact; wipe namespace | See **B12** | desk · offline |
| H4 | RAG on shop/mail fact | Index then ask corpus question | Useful hit, not hallucinated | desk · offline |
| H5 | Dual-write | Remember via tool; check local store | Profile/jobs namespace updated | desk · offline |
| H6 | Mail reindex | Reindex mail into memory | Search hits recent mail facts | desk · offline |

## I. Metrics, health & ops

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| I1 | `/api/metrics` latency | Several chat turns | p50/p95 visible | desk · offline |
| I2 | Mission audit steps | After a tool turn | prompt/tool/result logged in `/api/missions` | desk · offline |
| I3 | Health Hermes transport | `GET /api/health` | gateway vs cli; voicebox block | desk · cloud |
| I4 | Turn log | After chat/confirm | `work/LAST_TURNS.md` + `/api/turns/recent` updated | desk · offline |
| I5 | Voicebox status | `GET /api/voicebox/status` | Mark profile; cache count | desk |
| I6 | Offline CI suite | `python -m pytest -m "not live_service"` | 197+ pass; no live services | cloud · offline |
| I7 | Frontend CI checks | `npm run typecheck` + `npm run lint` | Clean (warnings OK) | cloud · offline |
| I8 | Data path resolution | API started from repo root | Uses `<repo>/data` not CWD-relative ghost paths | desk · offline |
| I9 | API-only e2e | API up: `pytest -m api_service` | Stability endpoints green | desk · cloud |

## J. Desk, conversations & UI commands

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| J1 | Hide dock (voice) | “Hide conversations” | `ConversationRail` hidden; speak confirms | desk · cloud |
| J2 | Show dock | “Show the dock” | Rail visible again | desk · cloud |
| J3 | Minimize note | “Minimize the drawing note” | DB `minimized`; rail updates | desk · cloud |
| J4 | Expand / open note | “Open the piston chat” | Note expanded + focused | desk · cloud |
| J5 | UI command miss | “Check my mail” (not UI) | Not routed as UI; normal mail path | desk |
| J6 | New discussion | + New / “start a discussion about …” | New row; session bound | desk · cloud |
| J7 | Minimize active → ambient | Minimize focused note | Returns to everyday desk cleanly | desk · cloud |
| J8 | Workflow resume key | Resume RFQ job by `resume_key` | Same workflow note, not duplicate | desk · offline |

## K. Voice & TTS

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| K1 | Single speak (no double) | Any speak line | One audio stream; no 15s replay | desk |
| K2 | Voicebox cutover | Voicebox warm | Browser TTS ≤~1.4s then Mark voice | desk |
| K3 | Late clip discarded | Slow Voicebox response | Late blob not played after bridge owns line | desk |
| K4 | TTS prefetch | Send chat | `/api/tts` warms cache; faster replay | desk |
| K5 | Preferences voice toggle | Disable voice in prefs | No TTS; HUD still updates text | desk · cloud |
| K6 | HITL confirm mic | After speak ends with pending | Confirm listen opens; yes/no works | desk |
| K7 | Compose dictation mic | Incomplete compose missing body | Mic fills body without false authorize | desk |

## L. Drawing, vision & viewer

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| L1 | Open drawing conversation | Upload/start drawing note | Drawing session kind; viewer available | desk |
| L2 | Drawing chat | Ask about features/dims | Gemini drawing model or vision tool | desk |
| L3 | Marked PDF export | Mark up drawing → save | `POST /api/drawings/marked` artifact | desk |
| L4 | Serve drawing file | Open `/api/drawings/{filename}` | PDF/image serves from data dir | desk · offline |
| L5 | Quote analyze drawing tool | `quote_analyze_drawing` on path | Structured dims/feasibility text | desk |

## M. Canvas & artifacts

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| M1 | Canvas page load | Open `:3000/canvas` | CanvasShell renders (SSR off) | cloud |
| M2 | Board CRUD | Create/rename board via API | `/api/canvas/boards` round-trip | desk · offline |
| M3 | Canvas file upload | Upload image/PDF to board | Stored under data; served back | desk |
| M4 | Show artifact on HUD | Tool returns artifact widget | SceneBoard displays artifact | desk |
| M5 | Open local artifact | “Open that spreadsheet” | Opens from exports safely | desk |

## N. Connectors & preferences

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| N1 | Google OAuth status | `GET /api/google/status` | configured/connected flags | desk |
| N2 | Preferences round-trip | Toggle email/voice flags | `PATCH /api/preferences` persists | desk · offline |
| N3 | Email disabled respect | Turn off email in prefs | Mail tools gated politely | desk |
| N4 | Research / web search | “Research latest ISO 9001 changes” | Real search results; cited not invented | desk |
| N5 | Drive find/upload (HITL) | Explicit Drive upload ask | Upload only when intended + authorized | desk |

## O. Stretch (later)

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| O1 | Browser evidence pack | Record evidence for a URL | Files under `data/browser_evidence` | desk |
| O2 | Live browser task + HITL | Novel web task end-to-end | Evidence + Authorize before action | desk |
| O3 | Evening report | End-of-day ask | Useful daily summary | desk |
| O4 | Remote channel (Telegram etc.) | Out of foundation scope | Deferred | — |
| O5 | Lab diarize page | Open `:3000/lab/diarize` | Experimental page loads | cloud |
| O6 | Honcho → local cutover | Memory recall quality | Local RAG stands alone | desk |

---

## Suggested test order (second pass — post semantic router)

Run **I6–I7** first for a green baseline, then live desk:

1. **I3, I8** — health & data paths  
2. **E1, E10–E12, E14–E15** — HUD shell + FSM visuals (**cloud** OK)  
3. **A12–A13, J1–J4** — semantic UI commands + orchestra  
4. **A1–A3, A8–A10, A14** — brain routing  
5. **K1–K3, K6** — voice trust  
6. **B1–B5, B13–B15** — HITL core  
7. **C3–C5, C8** — compose path  
8. **D1–D2** — briefing  
9. **E2–E7, E16–E18** — office-day cards + desk  
10. **F1, F5** — shop + CNC  
11. **G2–G6** — quote spine  
12. **H1–H4** — memory  
13. **L1–L2, M1** — drawing + canvas smoke  
14. **N1–N2** — connectors  
15. **O*** only after **G6** green  

## Log template (per case)

```
ID:
Result: pass | fail | flaky
Latency:
Notes:
Fix (if any):
Retest:
Agent (if dispatched):
```

---

## Appendix: prior run notes (2026-09-15)

| ID | Result | Notes |
| -- | ------ | ----- |
| A1 | PASS-ish | Multi-turn Hermes ok; occasional identity bleed on “what can you do” |
| A2 | PASS | RFQ summary ~11s; no fake numbers |
| A3 | PASS | Gateway down → Gemini ~9.5s |
| A4 | PASS partial | Typed parity only; mic not exercised |

*Re-run all IDs after semantic router + FSM merge — prior results are not valid for A8+ or E8+.*

---

*Pick an ID when ready (recommend **I6** offline baseline, then **E1**). The coordinator keeps the matrix moving and delegates fixes on your observations.*
