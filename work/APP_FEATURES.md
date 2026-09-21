# App features

Living notes from conversation. Update when the owner asks for a capability (new, changed, or deferred).  
Capability tests: [`CAPABILITY_TEST_MATRIX.md`](CAPABILITY_TEST_MATRIX.md).

---

## Current lock (2026-09-16)

### Product

- 24/7 AI assistant for personal grunt work and the machining company.
- Talk to Jarvis. Hermes owns shop jobs (mail tools, quotes, specialists). **Casual chat is Gemini-direct** and should feel instant and witty. Gemini still covers vision and explicit Task.

### Desk conversations

- **Everyday desk** — ambient, no need to resume.
- **Named discussions** — leave and reopen from Open notes (max 3 expanded).
- **Jobs / workflows** — bound to RFQs, drawings, quotes.

### Already in the desk (keep)

- Voice in/out (Space/mic, Voicebox TTS, browser plays once).
- Mail snapshot, draft compose, HITL send.
- Calendar (HITL on writes).
- Weather + suggested office-day tasks.
- Quote path: analyze drawing, build quote, PDF, HITL send. **In flight:** Hermes quote playbook (SKILL.md + toolbox + `quote_verify` proof + notes loop). Brain still does not invent prices.
- Local memory / RAG; remember / forget (broad wipe may HITL).
- Google connect (Gmail/Sheets/Drive) via Prefs.
- Activity log (last 8).

### In flight (this overhaul)

- Three HUD workspaces with switcher + pin + auto/talk-jump.
- Monitor: Evil Eye + still sun-agent orbs under the eye + Findings rail (no Aero Shards, no revolving orbit).
- Casual: React Bits for mail/tool boards (legacy HUD widgets out).
- Engineering bench: drawing + quote + machining strategy in one workspace.
- **Live capability-test recorder:** HUD + API append a rolling file automatically while the desk is used (`work/LIVE_TEST.md` + JSONL). Distinct from the human verdict log (`work/CAPABILITY_TEST_RUN_*.md`).
- **Quote playbook (Hermes skill):** one folder for the RFQ/quote job; fail-able proof before Authorize; corrections go into `notes.md`, not only chat. Morning brief / production-log / end-of-day stay separate future playbooks.
- **Quote drawing lookup (find, don’t guess):** (1) file already in hand (just dropped, or Engineering already showing it) → confirm name; (2) named search in local inbox files / `exports` / mail — one hit use it, several list and ask, zero next step; (3) mail has attachment but disk doesn’t → save then quote from local path; (4) hard copy / phone file → ask for photo or HUD drop. No path → no vision, no prices. Never pick “whatever was last in the DB.”
- **Quote steps (owner order, interview Q3):** (1) labour-only vs buy raw material; (2) if buy RM, request supplier quote and note it when it arrives; (3) machining strategy with the team or alone — operations, outsource, machines, special tooling; (4) machining cost from Machine Hour Rate (MHR); (5) assemble into the quotation format with special notes and delivery time, then send. Brain does not invent the MHR floor or an unsourced price.
- **Labour vs raw material (interview Q4):** some customers are labour-only by default; for some, buying our own RM is compulsory. A line in the mail, or the customer saying so verbally, overrides the default. If neither the customer record nor this order says, ask — do not guess.
- **Machine Hour Rate (interview Q5):** each machine type has a fixed **minimum** MHR. Quotes must not go below it; the quoted rate may be higher. For now Jarvis reads machine details and minimum MHR from a **demo table in the local DB**. Later, a shop **Master data** store holds this and more. Brain does not invent the floor.
- **Outsource (interview Q6):** an operation or the whole component goes out when any of these is true — no suitable machine, the customer asked, the shop is at capacity, or it is a process they do not do (heat treat, plating, grinding, and the like). Jarvis records which case it is; it does not decide the outsource price.
- **Before send (interview Q7):** the whole quotation is checked; every price line must be present. If the raw-material supplier quote is not in yet, the owner may **estimate** from historical transactions and the market trend and put that figure in — it must be marked as an estimate and trace to those sources, not a free guess. Delivery time does **not** hold the quote. Customer name and the rest of the party data come from Master data later.
- **Never underquote (interview Q8):** past misses include a price corrected after send, an assumed material, a forgotten outsource, and quoting material for a labour-only customer. The quote must not go below real cost: minimum MHR is a floor, outsource and raw material must be included when they apply, and a labour-only customer must not be charged as if the shop bought the material.
- **Customer email (interview Q9):** short formal body. The total quoted cost of the component is in **bold**. The full quotation PDF is attached. Sending still waits for Authorize.
- **Labour vs raw material (interview Q4):** some customers are labour-only by default; for some, buying our own RM is compulsory. A line in the mail, or the customer saying so verbally, overrides the default. If neither the customer record nor this order says, ask — do not guess.
- **Machine Hour Rate (interview Q5):** each machine type has a fixed **minimum** MHR. Quotes must not go below it; the quoted rate may be higher. For now Jarvis reads machine details and minimum MHR from a **demo table in the local DB**. Later, a shop **Master data** store holds this and more. Brain does not invent the floor.
- **Outsource (interview Q6):** an operation or the whole component goes out when any of these is true — no suitable machine, the customer asked, the shop is at capacity, or it is a process they do not do (heat treat, plating, grinding, and the like). Jarvis records which case it is; it does not decide the outsource price.
- **Before send (interview Q7):** the whole quotation is checked; every price line must be present. If the raw-material supplier quote is not in yet, the owner may **estimate** from historical transactions and the market trend and put that figure in — it must be marked as an estimate and trace to those sources, not a free guess. Delivery time does **not** hold the quote. Customer name and the rest of the party data come from Master data later.
- **Never underquote (interview Q8):** past misses include a price corrected after send, an assumed material, a forgotten outsource, and quoting material for a labour-only customer. The quote must not go below real cost: minimum MHR is a floor, outsource and raw material must be included when they apply, and a labour-only customer must not be charged as if the shop bought the material.

### Wanted (office-day story — not all built)

- Morning brief: weather, overnight mail, calendar, night-shift production.
- RFQ mail → local attachments → engineering review → quote in Sheets → PDF email with Authorize.
- Production-log summary + optional 4pm downtime meeting.
- End-of-day report.
- Remote: Telegram / email / misc when away from the desk.
- Overnight attach download / night-shift ingest as **script-only** Hermes cron (`no_agent=True`) — not an LLM poll every few minutes. Leave LLM cron for summaries.
- Orchestrator HUD drag-and-drop of drawings (HudShell has it; primary desk does not yet) so walk-up / hard-copy / WhatsApp files can land as inbox files.
- Shop **Master data** (machine list, minimum MHR, and more) as the durable source. Until then, a demo table in the local DB.

---

## Log

### 2026-09-22 — Fast, witty casual chat

Owner: casual replies must be as fast as possible on the Gemini API, and Jarvis should be as witty as possible. Shop jobs stay on Hermes. Wit is for conversation, not quotes or invented shop numbers.

### 2026-09-16 — Workspace split as a feature

Owner: Jarvis should have three major states — casual chat/simple tasks, idle/monitor of Hermes agents, and engineering assistant (drawings, quotations, machining strategies). This is both a HUD split and a way to divide the frontend by goal.

### 2026-09-16 — Monitor without shards

Owner: drop Aero Shards from Monitor; keep Evil Eye + orbit + findings.

### 2026-09-17 — Monitor agents stay put

Owner: no revolving sub-agent orbs; sun-agent orbs stay below the eye, quieter.

### 2026-09-17 — Live auto log while testing

Owner: keep the hand-written capability-run log for cases they were satisfied with. Also want a **separate file that records what is happening live automatically** while they test the HUD (not filled by the coordinator after the fact).

### 2026-09-17 — Quote as first Hermes playbook

Owner: upgrade the 24/7 shop assistant using the Actionable AI delegation loop on Hermes. First job is RFQ/quote from drawing. Want speed, accuracy, and scale-as-more-jobs — not a new agent per job.

### 2026-09-17 — Quote drawing sources (interview Q2, locked)

Owner agreed: drawing may already be local from Gmail sync, a hard copy, or a HUD drop. Lookup order is focus → named local search → save mail attach → ask for photo/drop. Never guess. Orchestrator drag-drop is wanted (not built on the primary desk yet).

### 2026-09-22 — Quote email (interview Q9, locked)

Owner: the quotation email is a short formal message. The total quoted cost of the component is in bold in the body. The full quotation PDF is attached.

### 2026-09-22 — Never underquote (interview Q8, locked)

Owner: all of these have happened — a price corrected after sending, an assumed material, a forgotten outsource, and quoting material on a labour-only customer. The thing they absolutely do not want repeated is underquoting a component.

### 2026-09-22 — Before send (interview Q7, locked)

Owner checks the whole quotation; it has to be impeccable. Hold if any price is missing. If the raw-material supplier quote is not in, they may estimate from historical transactions and the market trend. Delivery time does not hold the quote. Customer name and other party data will come from Master data later.

### 2026-09-22 — Outsource (interview Q6, locked)

Owner: any of these can send an operation or the whole component outside — no suitable machine, the customer asked, capacity, or a process they do not do (heat treat, plating, grinding, and similar).

### 2026-09-22 — Minimum MHR (interview Q5, locked)

Owner: every machine type has its own fixed minimum Machine Hour Rate. They do not quote below it; it is a floor, not the price they must charge. For now Jarvis reads machine details and that minimum from a demo table in the local DB. Later a Master data store holds this and more.

### 2026-09-22 — Labour vs raw material (interview Q4, locked)

Owner: sometimes the mail says; sometimes the customer says verbally that the order is with material. Some customers are labour-works only by default; for some it is compulsory to buy our own raw material. Default lives on the customer; this order’s mail or spoken word overrides it.

### 2026-09-22 — Quote steps (interview Q3, locked)

Owner, after the drawing is identified: (1) labour-only or buy raw material; (2) if buy RM, request a supplier quote and note it when received; (3) plan machining strategy alone or with the team — operations, outsource, machines, special tooling; (4) machining cost from Machine Hour Rate; (5) bring costs into the quotation format with special notes and delivery time, then send to the customer. Replaces the stub “vision → sheet → PDF” as the real process.
