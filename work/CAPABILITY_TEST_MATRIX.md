# Jarvis — Capability & Workflow Test Matrix

**Method:** Test one use case at a time → note pass/fail + latency → small fix → re-test → next.  
**Status:** Desk model implemented — **capability test run ready**.  
**Prerequisite:** Multi-conversation desk (ambient + named discussions + job workflows) is live on the Orchestrator HUD.  
**Sources:** Vision office-day story, foundation plan, `docs/CURRENT.md`, `AGENTS.md`.

**Pass criteria (default):** correct behavior, HITL never skipped on external write, no HUD errors, note latency vs target (casual ≤~5s warm; simple tools ≤~15s).

### Agent-assisted run protocol

While you test in the HUD, tell the coordinator your observations (ID + what you saw). The coordinator will:

1. Read **`work/LAST_TURNS.md`** (auto-updated last 20 chat/confirm turns) for what Jarvis said/did.
2. Log the result (template below).
3. Delegate to a **background worker** (`jarvis-uiux` / `jarvis-voice` / `jarvis-workflows` / `jarvis-builder`) so testing can continue — placed on the desk machine or in the cloud per the rule below.
4. Summarize the fix when the worker reports back; re-test that ID if you want.

Every kickoff to a worker must be self-contained: the worker inherits nothing from this chat, so the goal, repro, files in scope, and acceptance check all have to be spelled out in the kickoff itself.

Skills: `jarvis-capability-test`, `jarvis-observation-dispatch`. Rules: `.cursor/rules/jarvis-capability-run.mdc`.  
API mirror: `GET /api/turns/recent`.

### Where a fix can run

A cloud worker is an isolated VM: no HUD, no browser, and no reach to Hermes (`:8642`), Voicebox (`:17493`), or Google credentials. Any ID whose target is judged by *looking at* or *listening to* something — HUD rendering/layout, scroll behavior, card animation, weather/task-panel content, or TTS latency/double-play — can only be verified on the desk machine with the live services running. That covers section **E (Office-day HUD)** end to end, the voice-latency half of **A4**, and the visual half of **B1–B2** (blast-radius card, Authorize button). Sections whose target is a data/logic fact (correct numbers, no invented content, HITL gating, API status codes) can be fixed and verified by a cloud worker against `backend/tests` or curl, then handed back for the live re-test.

---

## A. Conversation & brain

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| A1 | Casual chat (greeting / small talk) | “Hey what’s up?” | Snappy, coherent, Hermes when warm |
| A2 | Work chat without tools | “Summarize what an RFQ is for our shop” | Accurate, no fake numbers |
| A3 | Hermes timeout → soft fallback | Force slow Hermes / kill gateway mid-turn | No blank HUD; Gemini/legacy answers |
| A4 | Voice + type parity | Same ask via mic and keyboard | Same outcome |
| A5 | Drawing-session chat | Open drawing conversation; ask about part | Stays in drawing context |
| A6 | Everyday desk vs discussion | Ambient ask → New discussion → leave → resume from Open notes | Chatter stays on correct thread |
| A7 | Job from suggested RFQ | Start engineering review & quote | Opens/resumes workflow note; not ambient dump |

## B. HITL & safety

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| B1 | Blast-radius card | Any outbound pending | Shows irreversibility 1–5 + consequence |
| B2 | Authorize send (button) | Draft → Authorize | Sends only after Authorize |
| B3 | Reject send | Draft → Reject | Nothing sent; calm cancel speak |
| B4 | Voice Authorize (“yes”) with compose edits | Edit draft fields → say yes | Sends **edited** fields, not stale |
| B5 | Calendar Authorize | Queue event → Authorize | Event created (no `_jarvis` crash) |
| B6 | Sheets write Authorize | Queue shop write → Authorize | Cells update only after Authorize |
| B7 | No silent Drive upload on HUD load | Open HUD with RFQ mail present | No unexpected Drive files |

## C. Mail

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| C1 | Search / list mail | “Any unread mail?” | Real inbox results |
| C2 | Read mail | “Open Deepak’s last email” | Summary + body on board |
| C3 | Draft compose (tight trigger) | “Draft an email to X saying …” | Modal; subject optional |
| C4 | Incomplete draft follow-up | Draft without body → dictate body | Fills body; doesn’t false-Authorize |
| C5 | Speech email repair | Spoken `pratik.28 1293@gmail.com` | Correct address |
| C6 | Reply with attachments | Reply path + attachments | HITL before send |
| C7 | Save mail attachments (explicit) | Ask to save drawings from mail | Local save; Drive only if intended |

## D. Calendar & briefing

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| D1 | Morning brief | “Good morning / brief me” | Weather + mail + calendar (witty, short) |
| D2 | List calendar | “What’s on today?” | Today’s events |
| D3 | Create event (HITL) | “Create a 4pm downtime meeting” | Pending → Authorize → created |
| D4 | Suggested-task → calendar action | Card “Only create calendar deadline” | Correct event draft |

## E. Office-day HUD

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| E1 | Fast HUD bootstrap | Cold open `:3000` | Idle UI &lt; ~2s; no long blank |
| E2 | Weather chip | Open HUD | Sensible local weather line |
| E3 | RFQ suggested cards | Refresh office tasks | Cards from drawing/RFQ mail |
| E4 | Production suggested card | Shop log bound | Human-readable OEE (no raw dict dump) |
| E5 | Card → engineering chat | “Start engineering review & quote” | Opens useful work thread |
| E6 | Card → custom chat | “Open chat for custom tasks” | Discusses that instance |
| E7 | Dismiss task | Dismiss button | Stays dismissed on reload |

## F. Shop / sheets / docs

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| F1 | Read shop sheet / OEE | “What’s shop OEE?” | Real numbers; no invention |
| F2 | Bind / ensure shop sheet | Bind by name/URL | Bound + readable |
| F3 | Update shop sheet (HITL) | Ask to write a cell | Authorize then write |
| F4 | Create local spreadsheet/PDF/doc | Ask to make a note/PDF | Artifact in exports |

## G. RFQ → quote → send (office-day spine)

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| G1 | Inbound drawing RFQ detect | Mail with drawing attachments | Task card / RFQ row |
| G2 | Vision on drawing | Analyze local drawing path | Dimensions; unreadable called out |
| G3 | Quote build (sheet) | Build quote from part + notes | Editable quote artifact |
| G4 | Quote PDF | Export quote PDF | PDF artifact |
| G5 | Quote send (HITL) | Queue quote email + PDF | Blast-radius 5; send only on Authorize |
| G6 | Full dry-run loop | Brief → RFQ card → vision → quote → Authorize | Aspect 14 gate |

## H. Memory & RAG

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| H1 | Remember preference | “Remember I prefer short briefings” | Stored locally (+ Honcho if Hermes) |
| H2 | Recall | “What do you know about me?” / memory search | Correct recall |
| H3 | Forget / wipe (HITL for broad wipe) | Forget one fact; wipe namespace | Single delete OK; wipe needs Authorize |
| H4 | RAG on shop/mail fact | Index then ask a corpus question | Useful hit, not hallucinated |
| H5 | Dual-write | Remember via tool; check local store | Profile/jobs namespace updated |

## I. Metrics & ops

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| I1 | `/api/metrics` latency | Casual hammers | p50/p95 visible |
| I2 | Mission audit steps | After a tool turn | prompt/tool/result logged |
| I3 | Health Hermes transport | `/api/health` | gateway vs cli correct |

## J. Stretch (later)

| ID | Capability | How to test | Target |
| -- | ---------- | ----------- | ------ |
| J1 | Browser evidence pack | Record evidence for a URL | Files under data/browser_evidence |
| J2 | Live browser task + HITL | Novel web task | Evidence + Authorize before consequential action |
| J3 | Evening report | End-of-day ask | Useful daily summary |
| J4 | Remote channel (Telegram etc.) | Out of foundation | Deferred |

---

## Suggested test order (first pass)

1. **A1** casual latency — **PASS-ish (retest 2026-09-15):** multi-turn on `default` (greet → √3 → ×7 → thanks). Hermes `ok` each turn; follow-up math kept context; HUD single voice line. Earlier “what can you do” still Hermes-identity bleed once. Warm chat path live; ≤5s still limited by Hermes tool prompt size.  
2. **A2** work chat no tools — **PASS (2026-09-15 API):** RFQ summary for shop; ~11s; no fake $-style numbers; empty scene.  
3. **A3** Hermes down → fallback — **PASS (retest 2026-09-15):** gateway down → ~9.5s Gemini definition of RFQ; no pending/email_send; no Drawing RFQ board. Fix: `is_rfq_definition` + skip cold CLI when gateway preferred.  
4. **A4** voice+type parity — **PASS partial (2026-09-15):** same typed ask twice via `/api/chat` both nonempty (~12–15s). Mic not exercised (same API pipeline).  
5. **B1–B4** HITL trust  
6. **C3–C5** draft compose  
7. **D1** morning brief  
8. **E1–E4** HUD cards  
9. **F1** shop OEE  
10. **G2–G5** quote path  
11. **G6** full office-day dry-run  
12. **H1–H4** memory/RAG  
13. Stretch **J*** only after G6 green  

## Log template (per case)

```
ID:
Result: pass | fail | flaky
Latency:
Notes:
Fix (if any):
Retest:
```

---

*Next: pick an ID (recommend **A1**) when you’re ready. The coordinator will keep the matrix moving and delegate to workers on your observations — desk machine for anything visual or audible, cloud otherwise.*
