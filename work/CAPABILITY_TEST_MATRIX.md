# Jarvis — Capability & Workflow Test Matrix

**Updated:** 2026-09-17 (three HUD workspaces + staged morph)  
**Method:** Test one use case at a time → note pass/fail + latency → dispatch fix → continue. Coordinator does not patch code.  
**Status:** Workspace HUD live on `OrchestratorShell` — **this pass ready**.  
**Prerequisite:** One shell (`OrchestratorShell` at `:3000`), two state layers that must never collapse:
- `HudWorkspace`: Casual | Monitor | Engineering (job of the screen)
- Turn FSM (`orchestratorFsm.ts`): IDLE | LISTENING | THINKING | SPEAKING | AWAITING_HITL | EXECUTING  
**Sources:** `docs/CURRENT.md` (as-built; may lag workspaces), `AGENTS.md`, `work/UI_UX_POINTS.md`, `work/ARCHITECTURE_POINTS.md`, `work/APP_FEATURES.md`.

### How this pass differs (2026-09-17)

First run against the **three-workspace** desk: Casual mint orb, Monitor Evil Eye + still suns + Findings, Engineering drawing bench. Workspace is orthogonal to the turn FSM. Switches **morph** (presence ~1.2s → theme → chrome); reduced-motion snaps. Monitor has **no Aero Shards** and **no revolving orbs**. `/canvas` is **not** the primary desk (M1 retired). HITL copy on this desk is **Authorize / Reject**. Latency targets unchanged: casual ≤~5s warm; simple tools ≤~15s; HUD idle <~2s.

Prior 2026-09-15/16 notes (brain, HITL, mail) still apply to those IDs; they do **not** cover P-section workspace cases.

**Pass criteria (default):** correct behavior, HITL never skipped on external write (do not mark pass if Authorize was bypassed), no HUD errors, note latency vs target.

### Tags

| Tag | Meaning |
| --- | ------- |
| **desk** | Needs Hermes, Voicebox, real Google OAuth, GPU Ollama, or physical mic/speaker |
| **cloud** | HUD layout/scroll/cards verifiable headless; or logic covered by `backend/tests` |
| **offline** | Runnable with `pytest -m "not live_service"` (partial coverage — still re-test live) |
| **retired** | Case kept for history; skip this pass (one-line why in the row) |

### Agent-assisted run protocol

**Run log (this pass):** [`work/CAPABILITY_TEST_RUN_2026-09-17.md`](CAPABILITY_TEST_RUN_2026-09-17.md) — full per-case fields, env snapshot, scoreboard. The short template below is the minimum; the run log is what the coordinator actually fills.

While you test in the HUD, tell the coordinator your observations (ID + what you saw). The coordinator will:

1. Read **`work/LAST_TURNS.md`** (auto-updated last 20 chat/confirm turns) for what Jarvis said/did.
2. Log the result into the **run log** (and the short template below).
3. Delegate to a **background worker** (`jarvis-uiux` / `jarvis-voice` / `jarvis-workflows` / `jarvis-builder`) so testing can continue — placed per placement policy below.
4. Summarize the fix when the worker reports back; re-test that ID if you want.

Every kickoff to a worker must be self-contained: goal, repro, files in scope, acceptance check.

Skills: `jarvis-capability-test`, `jarvis-observation-dispatch`. Rules: `.cursor/rules/jarvis-capability-run.mdc`.  
API mirror: `GET /api/turns/recent`.

### Where a fix can run

Cloud workers lack Hermes (`:8642`), Voicebox (`:17493`), real Google OAuth, GPU-representative Ollama, and physical mic/speaker — checks needing those stay **desk**. Cloud *can* build/serve the HUD and drive headless Chrome (`--enable-unsafe-swiftshader` for orb/eye WebGL — see `jarvis-react-bits` skill). Section **E** (HUD/FSM) and **P** (workspaces/morph/skins) are mostly **cloud** except live Voicebox timing and talk-jump that needs a brain. Section **K** (voice) is mostly **desk**. Semantic router logic is **cloud** + **offline**; live orchestra highlight is **desk**.

---

## A. Conversation, brain & semantic router

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| A1 | Casual chat (greeting / small talk) | On **Casual**: “Hey, what’s up?” | Snappy reply (≤~5s warm); router `casual_chat`; RES.01 or chat path | desk |
| A2 | Work chat without tools | “Summarize what an RFQ is for our shop” | Accurate; no invented prices/qty | desk · offline |
| A3 | Hermes timeout → soft fallback | Kill gateway mid-turn or cold CLI | No blank HUD; Gemini/legacy answers | desk |
| A4 | Voice + type parity | Same ask via mic and keyboard | Same outcome (API + mic pipeline) | desk |
| A5 | Drawing-session chat | Open drawing conversation (should land **Engineering**); ask about the part | Stays in drawing/vision context | desk |
| A6 | Everyday desk vs discussion | Ambient ask → New discussion → leave → resume from Open notes | Chatter stays on correct `session_id`; unpinned ambient returns **Monitor** | desk · cloud |
| A7 | Job from suggested RFQ | “Start engineering review & quote” on RFQ card | Opens/resumes workflow note on **Engineering**; not ambient dump | desk |
| A8 | Router `tool_ops` → Hermes | “Search my inbox for Deepak” (Hermes warm) | Hermes turn first; OPS/SEC agent highlighted | desk |
| A9 | Router `tool_ops` local fallback | Same ask with Hermes down | Snapshot/local mail path; no 30s hang | desk · offline |
| A10 | Router `casual_chat` override | “What is an RFQ?” | Chat brain; not mis-routed to mail tools | desk |
| A11 | Router `vision_task` | In drawing session: “What are the dimensions?” | Drawing chat / vision path; DAT.03 highlight | desk |
| A12 | Router `ui_command` (local) | “Hide the dock” / “Show conversations” | No Hermes; `ui_action` in response; dock toggles on **Casual** chrome | desk · cloud |
| A13 | `target_agent` orchestra stamp | Mail read vs draft vs OEE ask | Correct RES/SEC/DAT/OPS node lights (Casual dots; Monitor still suns) | desk · cloud |
| A14 | Local-fast snapshot path | “Any unread mail?” (snapshot warm) | Skips Hermes when snapshot-ready; real inbox | desk · offline |
| A15 | Hermes compose fill | Incomplete compose draft | Fill prefers Hermes gateway then Gemini | desk |
| A16 | Task for Gemini (HITL) | “Task for Gemini: summarize this PDF outline” | Queues HITL; no silent send | desk |

## B. HITL & safety

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| B1 | Blast-radius card | Any outbound pending | Irreversibility 1–5 + consequence text | desk · cloud |
| B2 | Authorize send (button) | Draft → **Authorize** (not Shall I) | Sends only after Authorize | desk |
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

Workspace skins for this shell live in **P**. These IDs are the turn FSM + Casual chrome that still apply.

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| E1 | Fast HUD bootstrap | Cold open `:3000` | Idle UI <~2s; no long blank; lands in a workspace (often Monitor if ambient) | cloud |
| E2 | Weather chip | Open **Casual** (not Monitor) | Sensible local weather in right rail (`shrink-0`); **absent on Monitor** | desk · cloud |
| E3 | RFQ suggested cards | Refresh office tasks | Cards from drawing/RFQ mail (Casual “Suggested”; Monitor “Findings”) | desk |
| E4 | Production suggested card | Shop log bound | Human-readable OEE (no raw dict dump) | desk |
| E5 | Card → engineering chat | “Start engineering review & quote” | Opens useful workflow thread on **Engineering** | desk |
| E6 | Card → custom chat | “Open chat for custom tasks” | Discusses that instance on **Casual** | desk |
| E7 | Dismiss task | Dismiss button | Stays dismissed on reload | desk · cloud |
| E8 | FSM IDLE → LISTENING | Space / mic while idle | Mic opens; Casual orb `listening` (Monitor eye stays the presence) | desk · cloud |
| E9 | FSM no listen while SPEAKING | Mic during TTS playback | Structurally refused (no second recognizer) | desk |
| E10 | FSM THINKING before network | Send any chat | “Orchestrating…” / transmitting immediately; not blank | cloud |
| E11 | FSM AWAITING_HITL panel | Any pending action | HitlModal + blast-radius; **Authorize / Reject**; compose uses DraftComposeModal | desk · cloud |
| E12 | VoiceLine vs board ownership | Read mail / open compose | Center VoiceLine hidden; board/modal owns text | cloud |
| E13 | Mail board scroll | Long mail thread on board | Scroll on SpotlightCard `bodyClassName`, not outer card | cloud |
| E14 | Orchestra agent states | After mail/OEE/HITL turns | Casual: node `active`/`waiting` dots. Monitor: matching still suns (see P12) | desk · cloud |
| E15 | Activity stream | After a few turns | Recent SYS/OPS/SEC lines; max ~8; visible across workspaces | cloud |
| E16 | Open notes cap | On Casual, open 4th discussion | Max **3** expanded; oldest parked | desk · cloud |
| E17 | React Bits Casual orb | Load **Casual** | Mint `JarvisCore` Particles/LightRays; no layout break. Not the Monitor eye | cloud |
| E18 | Persist focused note | Reload with note open | Restores conversation from `localStorage` | desk · cloud |
| E19 | Escape / Space shortcuts | Escape during listen; Space when allowed | Listen stops; no stuck FSM | desk · cloud |

## P. HUD workspaces, morph & skins (this pass)

Orthogonal to section E (turn FSM). All three skins live in one `OrchestratorShell` — no extra Next routes.

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| P1 | Three workspaces, one shell | Click Casual / Monitor / Engineering in the top-left switcher | Same page (`:3000`); labels match; FSM (idle/listen) does not change workspace by itself | cloud |
| P2 | Hybrid auto from focus (unpinned) | Unpin. Open a discussion → Casual. Open a drawing/job → Engineering. Return to everyday/ambient desk | Ambient empty desk → **Monitor**. Pin off is required | cloud |
| P3 | Pin locks auto | Pin Casual. Focus a discussion (would stay). Empty-desk / timeout must not yank. Switcher, + New, RFQ engineering, focusing a job/drawing still allowed | Pin holds auto-switch; explicit work still moves | cloud |
| P4 | Talk-jump: short status stays | Pin off. On **Monitor**, type “what’s the status?” or “any updates” | Stays Monitor; no morph to Casual | desk · cloud |
| P5 | Talk-jump: mail/chat → Casual | On **Monitor**, “any unread mail?” or “hey, what’s up?” | Morphs to **Casual** before/with the turn | desk |
| P6 | Talk-jump: drawing/quote/strategy → Engineering | On **Monitor**, “quote this drawing” / “machining strategy for the part” | Morphs to **Engineering** | desk |
| P7 | Staged morph — presence | Casual → Monitor (and back). Watch the center | Orb ↔ eye ↔ bench crossfade in the **same center**, ~1.2s. **No black gap** | cloud |
| P8 | Staged morph — theme then chrome | Same switch, keep watching | Warm Monitor tokens **after** presence. Rails, weather, Findings, still suns fade **last** (~2.4s) | cloud |
| P9 | Reduced-motion snap | Enable OS/browser `prefers-reduced-motion`, switch workspace | Instant snap; no staged delay / black flash | cloud |
| P10 | Monitor Evil Eye (stock + budget) | Open Monitor; leave it ~10s; then switch away | Centered eye; stock props (`eyeColor="#FF6F37"`, intensity 1.5, pupil 0.6, iris 0.25, glow 0.3, scale 0.8, noise 1, pupilFollow 1, flameSpeed 1, bg `#120F17`). Internal ~55% / 30fps. **Pauses** off Monitor (tab hidden or other workspace) | cloud |
| P11 | Monitor chrome (what is hidden) | Sit on Monitor after chrome lands | **No** Aero Shards. **No** weather card. **No** left Open-notes rail. **No** giant “Awaiting instruction” over the eye. **No** bottom `[RES.01]` dots. Findings rail on the right (same task data, “Findings” heading). CommandBaton quieter; switcher + Prefs + activity stay | cloud |
| P12 | Monitor still suns | Monitor after chrome | Quiet horizontal row of small amber discs **below** the eye — not a revolving orbit. Active a touch brighter; codes muted. Fade in with chrome (last) | cloud |
| P13 | Casual chrome | Switch to Casual; wait for chrome | Mint orb; left Open notes (max 3); weather `shrink-0`; suggested tasks; CommandBaton; tiny orchestra dots. Accent `#7dffe0` | cloud |
| P14 | Engineering bench | Switch to Engineering (empty job and/or a drawing job) | Drawing-first bench (~55% viewer + ~40% quote/status stack). **No** competing full-page WebGL (no eye, no Casual orb under drawings, no shards). SpotlightCard / GlareHover OK | cloud |
| P15 | HITL copy on every workspace | Queue a pending action from Casual, then glance Monitor/Engineering with a pending if available | Overlay buttons **Authorize / Reject** (not Shall I). Overlay, not a new conversation | desk · cloud |
| P16 | ~~Aero Shards on Monitor~~ | — | **SKIP this pass.** Owner removed shards; bit stays vendored only. Fail if they reappear on Monitor | retired |
| P17 | ~~Revolving agent orbs~~ | — | **SKIP this pass.** Replaced by still suns (P12). Fail if orbs orbit the eye again | retired |

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

Engineering workspace is the visual home; tools/HITL unchanged.

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| G1 | Inbound drawing RFQ detect | Mail with drawing attachments | Task card / RFQ row | desk |
| G2 | Vision on drawing | Analyze local drawing path | Dimensions; unreadable called out | desk |
| G3 | Quote build (sheet) | Build quote from part + notes | Editable quote artifact | desk |
| G4 | Quote PDF | Export quote PDF | PDF in exports | desk · offline |
| G5 | Quote send (HITL) | Queue quote email + PDF | See **B9** | desk · offline |
| G6 | Full dry-run loop | Brief → RFQ card → vision → quote → Authorize | Aspect 14 office-day gate (Engineering bench for the job) | desk |
| G7 | RFQ intake API | `POST /api/rfqs/intake` or tool path | Row created; links to mail/job | desk · offline |
| G8 | RFQ reason / status | Ask about RFQ status in workflow note | Consistent job/RFQ row | desk · offline |
| G9 | Quote proof (`quote_verify`) | After a built quote, run verify (empty prices vs filled fixture) | Checklist on Engineering stack; `stop` when >2 fails; evidence traces to sheet/PDF | desk · offline |
| G10 | Shop-quote playbook load | After API restart, ask “quote this drawing” with Hermes warm | Hermes loads shop-quote skill (not SOUL dump); tools own numbers; send still Authorize | desk |

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
| I3 | Health Hermes transport | `GET /api/health` | gateway vs cli; voicebox block; HUD `:3000` up | desk · cloud |
| I4 | Turn log | After chat/confirm | `work/LAST_TURNS.md` + `/api/turns/recent` updated | desk · offline |
| I5 | Voicebox status | `GET /api/voicebox/status` | Mark profile; cache count | desk |
| I6 | Offline CI suite | `python -m pytest -m "not live_service"` | 197+ pass; no live services | cloud · offline |
| I7 | Frontend CI checks | `npm run typecheck` + `npm run lint` | Clean (warnings OK) | cloud · offline |
| I8 | Data path resolution | API started from repo root | Uses `<repo>/data` not CWD-relative ghost paths | desk · offline |
| I9 | API-only e2e | API up: `pytest -m api_service` | Stability endpoints green | desk · cloud |

## J. Desk, conversations & UI commands

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| J1 | Hide dock (voice) | On Casual: “Hide conversations” | `ConversationRail` hidden; speak confirms | desk · cloud |
| J2 | Show dock | “Show the dock” | Rail visible again | desk · cloud |
| J3 | Minimize note | “Minimize the drawing note” | DB `minimized`; rail updates | desk · cloud |
| J4 | Expand / open note | “Open the piston chat” | Note expanded + focused | desk · cloud |
| J5 | UI command miss | “Check my mail” (not UI) | Not routed as UI; normal mail path | desk |
| J6 | New discussion | + New / “start a discussion about …” | New row; session bound; explicit Casual | desk · cloud |
| J7 | Minimize active → ambient | Minimize focused note | Returns to everyday desk; unpinned → **Monitor** | desk · cloud |
| J8 | Workflow resume key | Resume RFQ job by `resume_key` | Same workflow note, not duplicate; **Engineering** | desk · offline |

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

Prefer **Engineering** workspace for these (P14). Tools unchanged.

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| L1 | Open drawing conversation | Upload/start drawing note | Drawing session kind; viewer on Engineering bench | desk |
| L2 | Drawing chat | Ask about features/dims | Gemini drawing model or vision tool | desk |
| L3 | Marked PDF export | Mark up drawing → save | `POST /api/drawings/marked` artifact | desk |
| L4 | Serve drawing file | Open `/api/drawings/{filename}` | PDF/image serves from data dir | desk · offline |
| L5 | Quote analyze drawing tool | `quote_analyze_drawing` on path | Structured dims/feasibility text | desk |

## M. Canvas & artifacts

| ID | Capability | How to test | Target | Tags |
| -- | ---------- | ----------- | ------ | ---- |
| M1 | ~~Canvas as primary desk~~ | Open `:3000/canvas` only if checking leftover route | **SKIP as primary desk.** Engineering workspace is the bench. Optional smoke: page may still load; do not treat as the HUD | retired |
| M2 | Board CRUD | Create/rename board via API | `/api/canvas/boards` round-trip | desk · offline |
| M3 | Canvas file upload | Upload image/PDF to board | Stored under data; served back | desk |
| M4 | Show artifact on HUD | Tool returns artifact widget | SceneBoard / Engineering stack displays artifact | desk |
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

## Suggested test order (2026-09-17 workspace pass)

Coordinator confirms **I3** (health) before any A/P4+ brain cases. Skip **P16, P17, M1** (retired). Offline **I6–I7** only if you want a CI baseline this session.

1. **I3** — HUD `:3000`, API `:8000/api/health`, Hermes `:8642`, Voicebox `:17493`  
2. **E1, P1** — bootstrap + three workspaces in one shell  
3. **P7, P8, P9** — staged morph (presence → theme → chrome; reduced-motion)  
4. **P10, P11, P12** — Monitor eye, chrome, still suns  
5. **P13, E2, E16, E17** — Casual orb, weather, notes cap  
6. **P14** — Engineering bench, no extra WebGL  
7. **P2, P3** — auto-from-focus + pin  
8. **P4, P5, P6** — talk-jump (needs typing; P5/P6 need a brain)  
9. **P15, E11, B2–B3** — Authorize / Reject  
10. **E8–E10, E14–E15** — FSM + orchestra/activity  
11. **A1–A3, A8–A10, A14** — brain routing (Hermes warm)  
12. **K1–K3, K6** — voice trust  
13. **C3–C5, C8** — compose path  
14. **D1–D2** — briefing  
15. **E3–E7, A7** — office-day cards  
16. **F1, F5** — shop + CNC  
17. **G2–G6, L1–L2** — quote / drawing spine  
18. **H1–H4** — memory  
19. **N1–N2** — connectors  
20. **O*** only after **G6** green  

## Log template (per case)

Minimum (chat reply). Full field set: [`CAPABILITY_TEST_RUN_2026-09-17.md`](CAPABILITY_TEST_RUN_2026-09-17.md).

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

*Re-run workspace IDs (P*) this pass. Prior results are not valid for P1–P15, E2/E17 (workspace-scoped), or talk-jump. Semantic-router IDs A8+ / FSM E8+ were already stale after the 2026-09-16 merge.*

---

*Pick an ID when ready (this pass: coordinator **I3**, then **E1** / **P1**). The coordinator keeps the matrix moving and delegates fixes on your observations.*
