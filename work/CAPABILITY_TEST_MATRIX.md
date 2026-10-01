# Jarvis — Capability & Workflow Test Matrix

**Updated:** 2026-10-02  
**What this is:** a catalog of behaviors worth checking. It is not an architecture or layout contract. Section order, scroll, rendering, and libraries may change. Judge a row by the business outcome it names, not by the screen arrangement in an older build.  
**Business requirements:** `docs/PRODUCT_BRIEF.md`. Code map: `docs/CURRENT.md`.

---

### Tags
| Tag | Meaning |
|-----|---------|
| **desk** | Needs Hermes, real Google OAuth, GPU Ollama, Gemini speech playback, or physical mic/speaker |
| **cloud** | HUD layout/scroll/cards verifiable headless; or logic covered by `backend/tests` |
| **offline** | Runnable with `pytest -m "not live_service"` (partial coverage — still re-test live) |
| **retired** | Case kept for history; skip this pass (one-line why in the row) |

### How to use a row

Check one case, note pass or fail, and fix it in whatever way the code actually needs. A background helper is optional. Live Hermes, Google sign-in, speech playback, and a physical mic or speaker are needed only for cases tagged **desk**. Layout and scroll can be checked in a browser, including headless Chrome.

---

## A. Conversation, Brain & Semantic Router

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| A1 | Casual chat (greeting / small talk) | On **Casual**: "Hey, what's up?" | Snappy reply (≤~5s warm); router `casual_chat`; RES.01 or chat path | desk |
| A2 | Work chat without tools | "Summarize what an RFQ is for our shop" | Accurate; no invented prices/qty | desk · offline |
| A3 | Hermes timeout → soft fallback | Kill gateway mid-turn or cold CLI | No blank HUD; Gemini/legacy answers | desk |
| A4 | Voice + type parity | Same ask via mic and keyboard | Same outcome (API + mic pipeline) | desk |
| A5 | Drawing-session chat | Open drawing conversation (should land **Engineering**); ask about the part | Stays in drawing/vision context | desk |
| A6 | Everyday desk vs discussion | Ambient ask → New discussion → leave → resume from Open notes | Chatter stays on correct `session_id`. Unpinned empty/everyday desk **does not** auto-scroll to Monitor | desk · cloud |
| A7 | Job from suggested RFQ | "Start engineering review & quote" on RFQ card | Opens/resumes workflow note on **Engineering**; not ambient dump | desk |
| A8 | Router `tool_ops` → Hermes | "Search my inbox for Deepak" (Hermes warm) | Hermes turn first; OPS/SEC agent highlighted | desk |
| A9 | Router `tool_ops` local fallback | Same ask with Hermes down | Snapshot/local mail path; no 30s hang | desk · offline |
| A10 | Router `casual_chat` override | "What is an RFQ?" | Chat brain; not mis-routed to mail tools | desk |
| A11 | Router `vision_task` | In drawing session: "What are the dimensions?" | Drawing chat / vision path; DAT.03 highlight | desk |
| A12 | Router `ui_command` (local) | "Hide the dock" / "Show conversations" | No Hermes; `ui_action` in response; dock toggles on **Casual** chrome | desk · cloud |
| A13 | `target_agent` orchestra stamp | Mail read vs draft vs OEE ask | Correct RES/SEC/DAT/OPS node lights (Casual dots; Monitor still suns) | desk · cloud |
| A14 | Local-fast snapshot path | "Any unread mail?" (snapshot warm) | Skips Hermes when snapshot-ready; real inbox | desk · offline |
| A15 | Hermes compose fill | Incomplete compose draft | Fill prefers Hermes gateway then Gemini | desk |
| A16 | Task for Gemini (HITL) | "Task for Gemini: summarize this PDF outline" | Queues HITL; no silent send | desk |

## B. HITL & Safety

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| B1 | Blast-radius card | Any outbound pending | Irreversibility 1–5 + consequence text | desk · cloud |
| B2 | Authorize send (button) | Draft → **Authorize** (not Shall I) | Sends only after Authorize | desk |
| B3 | Reject send | Draft → **Reject** | Nothing sent; calm cancel speak | desk |
| B4 | Voice Authorize ("yes") with compose edits | Edit draft fields → say yes | Sends **edited** fields, not stale | desk |
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

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| C1 | Search / list mail | "Any unread mail?" | Real inbox results on board or speak | desk |
| C2 | Read mail | "Open Deepak's last email" | Summary + body on SpotlightCard board | desk |
| C3 | Draft compose (tight trigger) | "Draft an email to X saying …" | `DraftComposeModal`; subject optional | desk · offline |
| C4 | Incomplete draft follow-up | Draft without body → dictate body | Fills body; doesn't false-Authorize | desk |
| C5 | Speech email repair | Spoken `pratik.28 1293@gmail.com` | Correct address in draft | desk · offline |
| C6 | Reply with attachments | Reply path + attachments | HITL before send | desk |
| C7 | Save mail attachments (explicit) | "Save drawings from that email" | Local save under exports/data; Drive only if asked | desk |
| C8 | Snapshot refresh | "Refresh my mail" / fresh intent | Snapshot rebuild; faster repeat read | desk |
| C9 | Attachment-only mail speak | Mail with attachments, minimal body | Useful speak line (not "on the board" alone) | desk |
| C10 | Forward email | "Forward that email to …" | Draft/HITL path; no silent forward | desk |
| C11 | Bulk 100d mail sync | `POST /api/mail/sync` or OAuth reconnect; poll `GET /api/mail/sync` | `synced_count` climbs; `gmail-*` rows >> 20; status → `done` | desk |
| C12 | Spam filter + allowlist | Inspect skipped vs kept in sync state; spot-check Supabase/ERPNext/Frappe mail | Promo/spam dropped; allowlisted vendor mail kept | desk |
| C13 | Mail RAG corpus | After bulk sync: "What did Supabase bill last month?" / memory recall | Answer from indexed `mail:{id}` corpus, not hot snapshot only | desk · offline |

## D. Calendar & Briefing

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| D1 | Morning brief | "Good morning / brief me" | Weather + mail + calendar; short, witty | desk |
| D2 | List calendar | "What's on today?" | Today's events from real calendar | desk |
| D3 | Create event (HITL) | "Create a 4pm downtime meeting" | Pending → Authorize → created | desk |
| D4 | Suggested-task → calendar action | RFQ card "Only create calendar deadline" | Correct event draft pending | desk |
| D5 | Briefing glance / watch | After brief, check `/api/glance` or watch chip | Critical items surface; no crash | desk · cloud |

## E. Orchestrator HUD & FSM

Running HUD is `JarvisRoot` + `Desk`, not `OrchestratorShell` / lens tabs / Pane.

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| E1 | Fast HUD bootstrap | Cold open `:3000` | Landing overlay first (gates in parallel). Idle desk after min ~1.4 s (0.6 s on same-tab refresh), hard cap 4 s. Lands on pinned saved section, else restored conversation category, else Monitor. No long blank | cloud |
| E2 | Weather chip | Open **Monitor** and **Casual** | Sensible local weather on Monitor rail (`features/weather` → `monitor.rail`) and Casual right rail (`shrink-0`). Full feature-slot check is **S5** | desk · cloud |
| E3 | RFQ suggested cards | Refresh office tasks | Cards from drawing/RFQ mail (Casual "Suggested"; Monitor "Findings") | desk |
| E4 | Production suggested card | Shop log bound | Human-readable OEE (no raw dict dump) | desk |
| E5 | Card → engineering chat | "Start engineering review & quote" | Opens useful workflow thread on **Engineering** | desk |
| E6 | Card → custom chat | "Open chat for custom tasks" | Discusses that instance on **Casual** | desk |
| E7 | Dismiss task | Dismiss button | Stays dismissed on reload | desk · cloud |
| E8 | FSM IDLE → LISTENING | Space / mic while idle and **not in a field** | Mic opens; substrate listening controls. Space in the baton types a space (see **E19**) | desk · cloud |
| E9 | FSM no listen while SPEAKING | Mic during TTS playback | Structurally refused (no second recognizer) | desk |
| E10 | FSM THINKING before network | Send any chat | "Orchestrating…" / transmitting immediately; not blank | cloud |
| E11 | FSM AWAITING_HITL panel | Any pending action | HitlModal + blast-radius; **Authorize / Reject / Later**; compose uses DraftComposeModal. Modal opens **in place** (no auto-scroll). Park/resume is **S3** | desk · cloud |
| E12 | VoiceLine vs board ownership | Read mail / open compose | Center VoiceLine hidden; board/modal owns text | cloud |
| E13 | Mail board scroll | Long mail thread on board | Scroll on SpotlightCard `bodyClassName`, not outer card | cloud |
| E14 | Orchestra agent states | After mail/OEE/HITL turns | Casual: node `active`/`waiting` dots. Monitor: matching still suns under the presence line | desk · cloud |
| E15 | Activity stream | After a few turns | Recent SYS/OPS/SEC lines; max ~8; on Monitor (chrome stays while you scroll) | cloud |
| E16 | Open notes cap | On Casual, open 4th discussion | Max **3** expanded; oldest parked | desk · cloud |
| E17 | Casual substrate swarm | Load **Casual** | Cortex Dinamico particle swarm on the root canvas. **Fail** if React Bits Particles / `JarvisCore` desk orb returns | cloud |
| E18 | Persist focused note | Reload with note open | Restores conversation from `localStorage` | desk · cloud |
| E19 | Escape / Space shortcuts | Focus the baton; type Space. Then click empty chrome and press Space. Escape during listen | Space **types** in the baton and any field. Space is **mic** when not in a field. Space **never** scrolls the page. Escape stops listen; no stuck FSM | desk · cloud |

## P. Sections, Orb Morph & Pin (This Pass)

All three sections live on one `Desk` page under `JarvisRoot` — no extra Next routes, no lens switcher.

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| P1 | Three sections, one page | Click Monitor / Casual / Engineering in left **SectionNav** | Same page (`:3000`); labels match order Monitor → Casual → Engineering. FSM does not change section by itself | cloud |
| P2 | Auto-from-focus; no ambient jump | Unpin. Open a discussion → Casual. Open a drawing/job → Engineering. Return to everyday/ambient (minimize / everyday note) | Discussion/job still auto-scroll. Empty/everyday desk **stays put** — no auto-jump to Monitor | cloud |
| P3 | Pin blocks auto only | Pin. Trigger a server hint or auto-focus that would otherwise scroll. Then hand-scroll, click SectionNav, PageUp/PageDown, Alt+1–9 | Pin drops automatic scrolls. Hand scroll / nav / keys still move | cloud |
| P4 | Server hint: short status stays | Pin off. On **Monitor**, type "what's the status?" or "any updates" | Stays Monitor. Client `talkJumpWorkspace` is **retired**; jumps come from `ui: {section, reason}` | desk · cloud |
| P5 | Server hint: mail/chat → Casual | On **Monitor**, "any unread mail?" or "hey, what's up?" | Scrolls to **Casual**. Same quote/drawing words **on Casual** stay Casual unless quote-start / drawing vision (**P6**) | desk |
| P6 | Server hint: drawing/quote → Engineering | On **Monitor**, "quote this drawing" / "machining strategy for the part". On **Casual**, quote-start or vision with a drawing | Scrolls to **Engineering**; Casual quote-start opens the stage on that drawing. Engineering yields only to **explicit** (nav / "back to chat") | desk |
| P7 | Orb morph follows scroll | Scroll Monitor ↔ Casual ↔ Engineering (slow and a flick) | One particle swarm; formulas blend with scroll (ASCI → Cortex → CHAT GPT). Direct jump does not flash the in-between shape. **No black gap. No Evil Eye** | cloud |
| P8 | Fixed chrome; baton dim | Same scroll, watch L3 | StatusCluster, SectionNav, TaskDock, CommandBaton stay fixed. Backdrop/theme blend with scroll. Baton dims while moving, restores ~400 ms after | cloud |
| P9 | Reduced-motion snap | Enable OS/browser `prefers-reduced-motion`, change section | Instant snap; no wave/bulge / staged delay / black flash | cloud |
| P10 | ~~Monitor Evil Eye~~ | — | **SKIP.** Eye shader / `EvilEye` removed; swarm is the presence. Fail if the stock eye returns on Monitor | retired |
| P11 | Monitor chrome | Sit on Monitor after landing | Findings rail on the right. Weather **is** on the rail (feature — **S5**). **No** Aero Shards. **No** left Open-notes rail. **No** giant "Awaiting instruction". CommandBaton quieter; SectionNav + pin + Prefs + activity stay | cloud |
| P12 | Monitor still suns | Monitor after landing | Quiet horizontal row of small amber discs **below** the presence line — not a revolving orbit. Active a touch brighter; codes muted | cloud |
| P13 | Casual chrome | Scroll to Casual | Cortex swarm; left Open notes (max 3); weather; suggested tasks; CommandBaton; tiny orchestra dots. Accent `#7dffe0` | cloud |
| P14 | Engineering bench + deck | Scroll to Engineering (empty deck, then a drawing job) | Empty: stacked task deck as hero (thumbs, quote-step chip). Active job: drawing stage + quote stack; deck pile on the left; card morphs into the stage. Dim side orb. **No** second WebGL. SpotlightCard / GlareHover OK | cloud |
| P15 | HITL copy on every section | Queue a pending action from Casual, then glance Monitor/Engineering with a pending if available | Overlay **Authorize / Reject / Later** (not Shall I). Opens **where you are** — no scroll. Orb centres while the modal is open; a parked chip does not | desk · cloud |
| P16 | ~~Aero Shards on Monitor~~ | — | **SKIP this pass.** Owner removed shards; bit stays vendored only. Fail if they reappear on Monitor | retired |
| P17 | ~~Revolving agent orbs~~ | — | **SKIP this pass.** Replaced by still suns (P12). Fail if orbs orbit the presence again | retired |

## S. Scroll HUD (Landing, Snap, Dock, Deck, Feature)

Checks the old lens matrix cannot cover. Keep this list short.

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| S1 | Landing gates | Cold open `:3000`. Repeat with a same-tab refresh | Overlay names a real gate (Waking substrate · Loading desk · Checking Hermes · Ready). Gates: substrate, fonts, desk, Monitor DOM, Casual DOM, Engineering chunk prefetch. Hermes is **display-only** and never blocks exit. Min 1.4 s cold / 0.6 s refresh; cap 4 s. Then instant jump to the target section | cloud |
| S2 | Section snap (`lock`) | Wheel through the page; PageUp/PageDown; Alt+1–3. Try Space on empty chrome vs in the baton | Always rest on a section top; one gesture → one section (~0.9 s, expo-out). PageUp/PageDown/Alt+n jump. Space does **not** snap (see **E19**) | cloud |
| S3 | TaskDock Later park / resume | Queue HITL → **Later**. Click the dock chip. Try to Authorize from the chip | Modal morphs to a TaskDock chip; FSM returns to IDLE (chat/mic work). Chip reopens the full modal — **never** Authorize/Reject from the chip. Client TTL `parkedAt`+30 min unless `expires_at`, then Authorize reopens | desk · cloud |
| S4 | Engineering deck drop | On Engineering with an empty (or hero) deck, drop a drawing PDF | Prompt: quote workflow vs view/discuss. Quote starts shop-quote (`quote this drawing`); discuss opens the drawing without queuing send. Thumbs render (pdf.js page 1, IndexedDB by sha256). Front card morphs into the stage | desk · cloud |
| S5 | Weather as feature | Open Monitor; inspect the rail Slot | Chip comes from `features/weather` on slot `monitor.rail` (`defineFeature` + `<Slot>`). Not a core-only leftover. Casual may still show a chip; Monitor is the feature home | desk · cloud |

## F. Shop / Sheets / CNC / Docs

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| F1 | Read shop sheet / OEE | "What's shop OEE?" | Real numbers; no invention | desk · offline |
| F2 | Bind / ensure shop sheet | Bind by name/URL | Bound + readable | desk |
| F3 | Update shop sheet (HITL) | Ask to write a cell | Authorize then write | desk |
| F4 | Create local spreadsheet/PDF/doc | "Make a PDF note of …" | Artifact under `<repo>/exports` | desk · offline |
| F5 | CNC suggest | "Suggest G-code for this feature" | Draft program; not promoted without HITL | desk · offline |
| F6 | CNC promote (HITL) | Promote suggested program | See **B8** | desk · offline |
| F7 | Google Sheet disabled handling | Sheets API disabled/unbound | Clear speak; no fake numbers | desk · offline |
| F8 | Glance critical OEE | Low OEE in snapshot | Surfaces in glance/briefing keys | desk · offline |

## G. RFQ → Quote → Send (Office-Day Spine)

Engineering **section** is the visual home; tools/HITL unchanged.

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| G1 | Inbound drawing RFQ detect | Mail with drawing attachments | Task card / RFQ row | desk |
| G2 | Vision on drawing | Analyze local drawing path | Dimensions; unreadable called out | desk |
| G3 | Quote build (sheet) | Build quote from part + notes | Editable quote artifact | desk |
| G4 | Quote PDF | Export quote PDF | PDF in exports | desk · offline |
| G5 | Quote send (HITL) | Queue quote email + PDF | See **B9** | desk · offline |
| G6 | Full dry-run loop | Brief → RFQ card → vision → quote → Authorize | Aspect 14 office-day gate (Engineering bench for the job) | desk |
| G7 | RFQ intake API | `POST /api/rfqs/intake` or tool path | Row created; links to mail/job | desk · offline |
| G8 | RFQ reason / status | Ask about RFQ status in workflow note | Consistent job/RFQ row | desk · offline |
| G9 | Quote proof (`quote_verify`) | After a built quote, run verify (empty prices vs filled fixture) | Checklist on Engineering stack; `stop` when >2 fails; evidence traces to sheet/PDF | desk · offline |
| G10 | Shop-quote playbook load | After API restart, ask "quote this drawing" with Hermes warm | Hermes loads shop-quote skill (not SOUL dump); tools own numbers; send still Authorize | desk |

## H. Memory & RAG

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| H1 | Remember preference | "Remember I prefer short briefings" | Stored locally (+ Honcho if Hermes) | desk · offline |
| H2 | Recall | "What do you know about me?" / memory search | Correct recall | desk · offline |
| H3 | Forget / wipe (HITL for broad wipe) | Forget one fact; wipe namespace | See **B12** | desk · offline |
| H4 | RAG on shop/mail fact | Index then ask corpus question | Useful hit, not hallucinated | desk · offline |
| H5 | Dual-write | Remember via tool; check local store | Profile/jobs namespace updated | desk · offline |
| H6 | Mail reindex | Reindex mail into memory | Search hits recent mail facts | desk · offline |

## I. Metrics, Health & Ops

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| I1 | `/api/metrics` latency | Several chat turns | p50/p95 visible | desk · offline |
| I2 | Mission audit steps | After a tool turn | prompt/tool/result logged in `/api/missions` | desk · offline |
| I3 | Health Hermes transport | `GET /api/health` | gateway vs cli; `tts` names Charon; HUD `:3000` up | desk · cloud |
| I4 | Turn log | After chat/confirm | `work/LIVE_TEST.md` + `/api/turns/recent` updated | desk · offline |
| I5 | Speech health | `GET /api/health` `tts` block | provider gemini, voice Charon, lite model first | desk |
| I6 | Offline CI suite | `python -m pytest -m "not live_service"` | 197+ pass; no live services | cloud · offline |
| I7 | Frontend CI checks | `npm run typecheck` + `npm run lint` | Clean (warnings OK) | cloud · offline |
| I8 | Data path resolution | API started from repo root | Uses `<repo>/data` not CWD-relative ghost paths | desk · offline |
| I9 | API-only e2e | API up: `pytest -m api_service` | Stability endpoints green | desk · cloud |

## J. Desk, Conversations & UI Commands

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| J1 | Hide dock (voice) | On Casual: "Hide conversations" | `ConversationRail` hidden; speak confirms | desk · cloud |
| J2 | Show dock | "Show the dock" | Rail visible again | desk · cloud |
| J3 | Minimize note | "Minimize the drawing note" | DB `minimized`; rail updates | desk · cloud |
| J4 | Expand / open note | "Open the piston chat" | Note expanded + focused | desk · cloud |
| J5 | UI command miss | "Check my mail" (not UI) | Not routed as UI; normal mail path | desk |
| J6 | New discussion | + New / "start a discussion about …" | New row; session bound; auto-scrolls to **Casual** (pin will block) | desk · cloud |
| J7 | Minimize active → ambient | Minimize focused note | Returns to everyday desk; **does not** auto-scroll to Monitor | desk · cloud |
| J8 | Workflow resume key | Resume RFQ job by `resume_key` | Same workflow note, not duplicate; **Engineering** | desk · offline |

## K. Voice & TTS

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| K1 | Single speak (no double) | Any speak line | One audio stream; no 15s replay | desk |
| K2 | Charon speaks the line | Send a short casual line | One Gemini WAV; HUD text matches what is spoken | desk |
| K3 | Quota stays silent | Speech models exhausted | Reply stays on screen; no other voice | desk |
| K4 | TTS prefetch | Send chat | `/api/tts` warms cache; faster replay | desk |
| K5 | Preferences voice toggle | Disable voice in prefs | No TTS; HUD still updates text | desk · cloud |
| K6 | HITL confirm mic | After speak ends with pending | Confirm listen opens; yes/no works | desk |
| K7 | Compose dictation mic | Incomplete compose missing body | Mic fills body without false authorize | desk |

## L. Drawing, Vision & Viewer

Prefer the **Engineering** section for these (P14). Tools unchanged.

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| L1 | Open drawing conversation | Upload/start drawing note | Drawing session kind; viewer on Engineering bench | desk |
| L2 | Drawing chat | Ask about features/dims | Gemini drawing model or vision tool | desk |
| L3 | Marked PDF export | Mark up drawing → save | `POST /api/drawings/marked` artifact | desk |
| L4 | Serve drawing file | Open `/api/drawings/{filename}` | PDF/image serves from data dir | desk · offline |
| L5 | Quote analyze drawing tool | `quote_analyze_drawing` on path | Structured dims/feasibility text | desk |

## M. Canvas & Artifacts

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| M1 | ~~Canvas as primary desk~~ | Open `:3000/canvas` only if checking leftover route | **SKIP as primary desk.** Engineering section is the bench. Optional smoke: page may still load; do not treat as the HUD | retired |
| M2 | Board CRUD | Create/rename board via API | `/api/canvas/boards` round-trip | desk · offline |
| M3 | Canvas file upload | Upload image/PDF to board | Stored under data; served back | desk |
| M4 | Show artifact on HUD | Tool returns artifact widget | SceneBoard / Engineering stack displays artifact | desk |
| M5 | Open local artifact | "Open that spreadsheet" | Opens from exports safely | desk |

## N. Connectors & Preferences

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| N1 | Google OAuth status | `GET /api/google/status` | configured/connected flags | desk |
| N2 | Preferences round-trip | Toggle email/voice flags | `PATCH /api/preferences` persists | desk · offline |
| N3 | Email disabled respect | Turn off email in prefs | Mail tools gated politely | desk |
| N4 | Research / web search | "Research latest ISO 9001 changes" | Real search results; cited not invented | desk |
| N5 | Drive find/upload (HITL) | Explicit Drive upload ask | Upload only when intended + authorized | desk |

## O. Stretch (Later)

| ID | Capability | How to Test | Target | Tags |
|----|------------|-------------|--------|------|
| O1 | Browser evidence pack | Record evidence for a URL | Files under `data/browser_evidence` | desk |
| O2 | Live browser task + HITL | Novel web task end-to-end | Evidence + Authorize before action | desk |
| O3 | Evening report | End-of-day ask | Useful daily summary | desk |
| O4 | Remote channel (Telegram etc.) | Out of foundation scope | Deferred | — |
| O5 | Lab diarize page | Open `:3000/lab/diarize` | Experimental page loads | cloud |
| O6 | Honcho → local cutover | Memory recall quality | Local RAG stands alone | desk |

---

## Suggested Test Order (Current Pass)

1. **I3** — HUD `:3000`, API `:8000/api/health`, Hermes `:8642`, `tts` names Charon  
2. **S1, E1, P1** — landing gates + bootstrap + three sections on one page  
3. **S2, P7, P8, P9** — snap + orb morph + chrome; reduced-motion  
4. **P11, P12, P13, E2, S5, E16, E17** — Monitor/Casual chrome, weather as feature, notes cap  
5. **P14, S4** — Engineering deck (morph, thumbs, drop)  
6. **P2, P3** — auto-from-focus (no ambient jump) + pin blocks auto only  
7. **P4, P5, P6** — server `ui` hints (needs typing; P5/P6 need a brain)  
8. **P15, E11, S3, B2–B3** — Authorize / Reject / Later park-resume  
9. **E8–E10, E14–E15, E19** — FSM + orchestra/activity + Space in baton  
10. **A1–A3, A8–A10, A14** — brain routing (Hermes warm)  
11. **K1–K3, K6** — voice trust  
12. **C3–C5, C8** — compose path  
13. **D1–D2** — briefing  
14. **E3–E7, A7** — office-day cards  
15. **F1, F5** — shop + CNC  
16. **G2–G6, L1–L2** — quote / drawing spine  
17. **H1–H4** — memory  
18. **N1–N2** — connectors  
19. **O*** only after **G6** green  

## Log Template (Per Case)

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

**Pick an ID when ready (this pass: coordinator **I3**, then **S1** / **E1** / **P1**). The coordinator keeps the matrix moving and delegates fixes on your observations.**
