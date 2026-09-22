# Jarvis — Vision Workbook

**Purpose:** Discuss and lock every foundational aspect of the product before expanding capabilities.  
**Mode:** Personal project — optimize for correctness and longevity, not time-to-market.  
**Status:** Vision decisions complete (2026-09-14). Foundation build plan accepted — see [`FOUNDATION_BUILD_PLAN.md`](FOUNDATION_BUILD_PLAN.md).  
**Seeded from:** Owner vision (2026-09-14) + as-built snapshot in `docs/CURRENT.md`.

---

## How to use this workbook

For each **Aspect** section:

1. Read **Intent** (what we believe you want).
2. Review **Open questions** — answer / amend in conversation.
3. Capture a **Decision** (Accepted / Deferred / Rejected) and any **Constraints**.
4. Only after foundations are locked do we turn decisions into a phased build plan.

Mark decisions inline when agreed, e.g.:

> **Decision:** Accepted — Hermes is the primary conversational brain.  
> **Constraint:** HITL required for any external send/write.

---

## 0. North star

### Intent

A **24/7 AI office assistant** that does grunt work on the computer, stays under human authority when it matters, and eventually runs fully local. Jarvis is the **orchestrator**: talks to the user, remembers context, and assigns work to specialized sub-agent teams. Hermes (local agent) carries most of the intelligence; online models (e.g. Gemini) are used when local capability or speed is insufficient, or when the user explicitly delegates.

### Hard goals (non-negotiable until we rewrite them)


| #   | Goal                                       | Notes                                                             |
| --- | ------------------------------------------ | ----------------------------------------------------------------- |
| G1  | Conversational memory + intelligence       | Cross-session identity, preferences, ongoing work                 |
| G2  | Fast, efficient, accurate responses        | Latency and correctness both matter                               |
| G3  | Latest stable stack                        | Next.js, Python/FastAPI, Hermes, etc. — stay current              |
| G4  | Offline-first data + local vector DB / RAG | Anything downloadable/savable should live locally for fast recall |


### Ultimate objective (one sentence)

> Jarvis runs the office’s computer grunt work continuously, orchestrates specialist agents, obeys HITL, and progressively becomes fully local — without becoming a brittle pile of hardcoded rules.

### Open questions

- [ ] What does “perfect foundational aspects” mean in priority order for *you* (memory first? latency? local RAG? orchestration?)?
- [ ] What is the first “real office day” success story you want Jarvis to complete end-to-end?
- [ ] Any hard deadline (even soft personal ones), or truly open-ended?

### Decision

*The most critical foundational aspects are memeory and latency. We will work on hardening the other apects as we go.*  

*Following is the "real office day" story that i want Jarvis to succeed at :*  
*I get to the office at 9 am and say "Good morning Jarvis. Whats up?". Jarvis has already been primed with todays whether report and all the recent emails and any calender events for today. It replies with a witty remark, tells me about the whether and of any critical news from the previous night shift production. On the right side of the HUD, i can see that Jarvis has a list of suggested tasks for me in the form of elegant modals. The tasks are as follows :*  
*1) Title : "Mr. Deepak from KOSO India Pvt Ltd has mailed us with 14 drawings and is asking for a quote within the next 15 days."*  
*What jarvis has done : Downloaded the pdf and image attachments locally as soon as the mail arrived.*  
*suggestions on the modal : *  
*a) Start Engineering review and quote generation for components [Starts a new chat window with an AI service of user's choice. The user may decide to use an API service or use Jarvis itself through hermes]*  
*b) Only create calender events for the deadline*  
*c) Mark as read and add to 'to-do' list*

*2) Title : "Production from yesterday night was 82% with several machines experiencing downtime"*  
*What jarvis has done : Studied the production report filled by shop floor supervisor and prepared a detailed summary for the user about what was produced, which mahine experienced downtime, which component's delivery schedule might be impacted by the production loss, etc.*  
*a) Review production log*  
*b) Create a meeting event at 4 pm today with core staff members with the subject of resolving downtime issues.*  
*c) Mark instance for weekly production review*  
*d) Open chat window [this window will be used by the user to ask jarvis to perfrom custom tasks in relation to this instance]*  

I decide to complete the first suggested task. I open the chat modal window to start an engineering review of the components mentioned in the mail. Jarvis asks me which drawing to work on first. I pick the drawing, Jarvis sends the drawing to a Gemini Vision Model using my API key for dimensional analysis of the component (this is beacuse jarvis doesnt have vision capabilities yet). While we wait for gemini to reply, jarvis asks me about the raw material grade used for the component if it is not evident from the mail already. it also asks for any other relevant information.  
When the dimensional analysis arrives, jarvis uses a special custom 'skill' which enables it to work on the data in a specific way and create a detailed quotation for the job (We will work on these 'skills' as we deploy the project).  
Jarvis displayed the quotation in a live google sheets field where i can edit things if i want or ask jarvis to make any changes. Then i approve the quote for the said component and ask jarvis to send it to Mr. Deepak in Pdf format.  
Jarvis drafts a final email with the quote attachment and waits for my approval to actually send it through my gmail account.  

At 6 pm (Shift end), Jarvis has a daily report ready for me.  

When i go home, i can still talk to jarvis via Telegram/email/misc to ask it to do tasks for me.

## 1. Product identity & roles

### Intent

Clarify what Jarvis **is** vs Hermes, Honcho, Gemini, and sub-agents — so we don’t rebuild the same confusion.


| Role                             | Proposed responsibility                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------ |
| **User**                         | Speaks goals; Authorizes/Rejects consequential actions                                     |
| **Jarvis (orchestrator)**        | Conversation face, HUD/voice, HITL gates, connector ownership, task routing to specialists |
| **Hermes**                       | Primary local cognitive engine (tools, planning, most chat)                                |
| **Honcho (or local equivalent)** | Long-term user/work memory modeling                                                        |
| **Gemini / online LLM**          | Overflow: vision, heavy research, when Hermes is slow/unable, or explicit “delegate”       |
| **Sub-agent teams**              | Domain specialists (mail, research, drawings, quotes, browser tasks, …)                    |


### Open questions

- [x] When you say “talk to Jarvis = talk to the local LLM directly,” do you mean: (A) no Jarvis middle-brain at all, Hermes only; or (B) thin Jarvis shell that always forwards to Hermes? → **(B)**
- [x] Should the **HUD still be Jarvis-branded** while Hermes is invisible infrastructure? → **Yes**
- [x] How many specialist “teams” do you want named on day one vs invented later by Hermes? → **Soft / Hermes-invented early; fixed roster later if needed**
- [x] Is “Jarvis” allowed to refuse work that isn’t HITL-safe, or only pause for Authorize? → **Pause for Authorize; hard safety denies only**

### Decision

> **Decision:** Accepted — **(B)** thin Jarvis shell: the user always talks to “Jarvis”; Hermes is the invisible primary brain; Gemini is overflow / vision / explicit delegate. The HUD stays Jarvis-branded. Specialist teams may stay soft and Hermes-invented early. Jarvis **pauses for Authorize** on consequential actions rather than silently refusing, except for hard safety denies.  
> **Constraint:** No external send/write without HITL.  
> **Link:** §0 office-day story is the acceptance narrative for “foundation working.” Foundation focus remains memory + latency.

---

## 2. Conversational memory & intelligence (G1)

### Intent

Persistent memory so Jarvis knows who you are, how you work, and what’s in flight — without re-explaining every session.

### Options on the table


| Option                                            | Pros                                                                      | Cons                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Honcho cloud** (current)                        | Wired; dialectic user modeling; Hermes-native                             | Credits eventually run out; data leaves machine          |
| **Honcho self-host**                              | Same product, $0 platform fee                                             | Docker/Postgres/Redis ops; you pay local LLM for deriver |
| **Hermes built-in MEMORY.md / USER.md only**      | Free, simple                                                              | Weak modeling; size caps                                 |
| **Local vector RAG (G4) + structured profile DB** | Full offline control; fast retrieval                                      | Need to design schemas & ingestion                       |
| **Hybrid**                                        | Honcho (or local Honcho) for “who I am”; local RAG for docs/mail/drawings | More moving parts; clearest long-term fit                |


### Open questions

- [x] Prefer **self-host Honcho now** to avoid long-term cloud cost, even if setup is heavier? → **Keep Honcho cloud for now; build local DB in parallel for later cutover (not self-host Honcho as the next step)**
- [x] What must be remembered forever vs session-only vs “forget after N days”? → **Yes, via collections / retention policies in the local DB (forever, rolling session, TTL)**
- [x] Memory of **people** (vendors, staff), **jobs/RFQs**, **preferences**, **past decisions** — same store or separated? → **Same local system, separated namespaces/collections**
- [x] Should memory be **queryable by you** (“what do you know about me?”) as a first-class feature? → **Yes; summarize / forget on request**

### Decision

> **SUPERSEDED 2026-09-22 — local-first, no cloud memory.** The owner locked: strip Honcho
> entirely; memory and knowledge run 100 % local on SQLite + LanceDB. The destination below was
> already local; what changed is that there is no cloud stage and no dual-write phase. Current
> lock: [`ARCHITECTURE_POINTS.md`](ARCHITECTURE_POINTS.md) · design:
> [`OPUS_ARCHITECTURE_MANIFEST.md`](OPUS_ARCHITECTURE_MANIFEST.md) §4B, §8.6. The paragraphs below
> are kept as the record of how the decision was reached.

> **Decision:** Accepted — **dual-write memory, local-first destination.**  
> **Now:** Keep **Honcho cloud** as the live dialectic / Hermes memory provider.  
> **Also now:** Implement **local vector DB + structured store**; continuously mirror/update **profile summaries, preferences, people/jobs facts, and other durable docs** into the local DB so a later cutover does not start from zero.  
> **Later:** Switch Hermes/Jarvis primary recall to local DB and retire or idle Honcho when local quality is good enough.  
> **Layout:** Namespaces for preferences/profile (long-lived), people, jobs/RFQs/decisions, session chatter (rolling/TTL), plus document corpus (Aspect 5).  
> **UX:** User can ask what Jarvis knows; forget/wipe on request (broad wipe may use HITL).  
> **Backup:** Hermes built-in MEMORY.md / USER.md remains a thin fallback.

---

## 3. Speed, efficiency, accuracy (G2)

### Intent

Responses feel snappy; tools do the right thing; fewer multi-minute stalls.

### Tension to resolve

- Hermes-first + rich memory + tools → smarter but slower.
- Hardcoded shortcuts → faster but dumber (what you want to reduce).

### Open questions

- [x] Target latency bands: casual reply < ?s; tool turn < ?s; long jobs OK async? → **Casual ≤ ~5s warm; simple tools ≤ ~15s; long jobs async with progress**
- [x] When Hermes is slow, auto-fallback to Gemini vs ask you vs wait? → **Wait to ~30s; then ask or soft-fallback; user can also request Gemini**
- [x] Accuracy > speed when they conflict? (e.g. wrong email vs 3s delay) → **Accuracy > speed for mail/quotes/numbers; speed for chitchat**
- [x] Is “thinking visible on HUD” (progress) enough for long tasks? → **HUD progress + optional spoken status; background prep OK for reports**

### Decision

> **Decision:** Accepted — measure and harden latency; never fake instant on hard jobs.  
> **Targets:** casual Hermes ≤ ~5s when warm; simple tool turns ≤ ~15s; long jobs (quote, vision, research) async with HUD progress.  
> **Slow path:** wait up to ~30s; then ask or soft-fallback to Gemini for that turn; user may also say “use Gemini.”  
> **Tradeoff:** accuracy over speed for consequential content; speed over flourish for greetings.  
> **Visibility:** HUD progress + optional voice status; morning/evening briefs may be prepared in background.

---

## 4. Tech stack currency (G3)

### Intent

Stay on latest **stable** versions; avoid permanent tech debt from pinned old majors.

### Current stack (to verify/update in planning)

- Frontend: Next.js (App Router) + React
- Backend: FastAPI + Python
- Agent: Hermes Agent + gateway
- Memory: Honcho (cloud today)
- LLM overflow: Gemini API
- Data: SQLite (Jarvis) + Hermes session DB

### Open questions

- [x] Pin to LTS / current stable only, or track bleeding-edge Hermes releases? → **Latest stable; not bleeding-edge-by-default**
- [x] Windows-native forever, or eventual WSL/Linux/Docker-first for local models? → **Windows-native now; Docker/WSL later if local models need it**
- [x] Any stack you want **out** long-term (e.g. Next.js → something else)? → **No — keep Next.js + FastAPI**

### Decision

> **Decision:** Accepted — stay current on stable stack.  
> **Policy:** Latest stable Next.js / FastAPI / Hermes; avoid chasing every pre-release.  
> **Runtime:** Windows-native now; Docker/WSL when local models require it.  
> **Keep:** Next.js App Router + FastAPI + Hermes gateway + Gemini overflow.  
> **Memory note:** Honcho cloud + local vector DB dual-write (Aspects 2 & 5).

---

## 5. Offline-first data & local RAG (G4)

### Intent

Download/save everything practical locally. Local **vector database** powers RAG so Jarvis answers from *your* corpus fast.

### Candidate corpus (discuss what belongs)

- Emails / threads (metadata + bodies where allowed)
- Calendar events
- Shop sheets / Excel / exports
- Engineering drawings / PDFs / OCR or vision summaries
- Research notes & quotes
- Conversation-derived facts / profile summaries (dual-written while Honcho cloud is live)
- User-provided files & bookmarks

### Open questions

- [x] Vector DB preference: **Chroma / Qdrant / LanceDB / sqlite-vec / other**? → **LanceDB or sqlite-vec first (embedded); revisit Qdrant if needed**
- [x] Embeddings: local model vs API embeddings (offline purity vs quality)? → **Prefer local; API only if quality/speed forces it**
- [x] Ingestion: automatic on connect vs nightly vs on-demand (“index my inbox”)? → **Auto on mail/attachments/production/drawings landing + nightly sweep + on-demand reindex**
- [x] What must **never** leave the machine (even for Gemini)? → **Raw drawings, full mail bodies, production detail by default — only if user explicitly delegates that file/task**
- [x] How does RAG interact with Hermes tools — Jarvis RAG service Hermes calls via MCP? → **Yes — Jarvis MCP search/upsert; Hermes does not own the vector DB**

### Decision

> **Decision:** Accepted — offline-first corpus + same local vector/structured stack as Aspect 2.  
> **Engine:** LanceDB or sqlite-vec (embedded, Windows-friendly); Qdrant only if we outgrow embedded.  
> **Embeddings:** Local preferred.  
> **Ingestion:** Automatic when mail/attachments/production/drawings arrive; nightly catch-up; on-demand reindex.  
> **Corpus:** mail, calendar, shop/production, drawings/PDF summaries, research notes, plus dual-written profile/memory docs (Aspect 2).  
> **Privacy:** Sensitive corpus stays local unless user explicitly delegates to Gemini.  
> **Hermes:** RAG via Jarvis MCP only.  
> **Migration:** Dual-write with Honcho cloud until local recall is strong enough to cut over.

---

## 6. Orchestrator & sub-agent teams

### Intent

Jarvis orchestrates; specialists execute. User talks to one face.

### Possible specialist teams (examples — not committed)


| Team                   | Example work                                   |
| ---------------------- | ---------------------------------------------- |
| Comms                  | Draft/reply/search mail; meeting notes         |
| Research               | Web/prices/competition; cite sources           |
| Engineering            | Drawing vision; RFQ reason; CNC notes          |
| Office ops             | Calendar, files, shop log, quotes              |
| Browser / computer-use | “Check this YouTube channel’s latest views”    |
| Delegate               | Package work for Gemini or other remote agents |


### Open questions

- [x] Fixed roster of teams vs Hermes invents specialists dynamically? → **Soft / Hermes-invented early; named patterns not rigid org chart**
- [x] Parallel multi-team jobs with a single HUD summary? → **Yes — activity strip + task modals**
- [x] Sub-agents = Hermes subagents / separate processes / same process different toolsets? → **Hermes subagents/skills/toolsets first; separate processes only when needed**
- [x] How does the user see “who is working” without dashboard clutter? → **Short labels on activity + modal titles; user talks only to Jarvis**

### Decision

> **Decision:** Accepted — Jarvis orchestrates; specialists are soft early.  
> **Teams:** Hermes invents/labels specialists as needed (Comms, Engineering, Research, Ops, Browser, Delegate as patterns). Fixed roster only later if useful.  
> **Parallelism:** Multiple jobs OK; HUD uses activity strip + suggested-task modals (office-day story), not a heavy org chart.  
> **Implementation:** Hermes subagents / skills / toolsets inside one gateway first; separate processes only for isolation or long-running workers.  
> **Visibility:** Short agent labels on activity + modal titles; conversation face remains Jarvis only.

---

## 7. Hermes-first intelligence (reduce hardcoded rules)

### Intent

Majority of AI workload → Hermes. Intent classification and handling should be agentic, not a growing regex forest. Jarvis keeps **guarantees** (HITL, connectors, HUD), not a second brain.

### Proposed split (for debate)


| Jarvis owns (guarantees)  | Hermes owns (judgment)           |
| ------------------------- | -------------------------------- |
| Authorize / Reject        | Understanding asks               |
| Voice/HUD chrome          | Planning & tool choice           |
| Connector auth & APIs     | Draft content, research plans    |
| Audit log / pending queue | When to ask clarifying questions |
| Local RAG index service?  | When to query RAG / which docs   |


### Open questions

- [x] Kill tight mail-trigger phrases and let Hermes always open compose via tools? → **Yes, shrink/remove over time; compose modal stays Jarvis UX filled by Hermes tools**
- [x] Keep a **tiny** deny-list (safety) or zero hardcoded intents? → **Tiny safety deny-list only**
- [x] Persistent rules location: Hermes `SOUL.md` / skills / Jarvis-injected system prompt / all three? → **SOUL.md + skills primary; Jarvis injects session/HITL context only**
- [x] Should Jarvis MCP expose *only* safe tools (draft→pending) so Hermes can’t send raw? → **Yes — queue pending; never raw send/calendar-write**

### Decision

> **Decision:** Accepted — Hermes-first intelligence; Jarvis keeps guarantees only.  
> **Hermes owns:** intent, planning, tool choice, draft content, research plans, clarifications.  
> **Jarvis owns:** HITL queue, connectors, HUD/voice, RAG MCP, audit log.  
> **Routing:** Shrink regex/hardcoded intents over time; retain a **tiny** safety deny-list only.  
> **Rules:** Hermes `SOUL.md` + skills; Jarvis injects session/HITL context only.  
> **MCP:** Safe-by-default — draft/calendar/etc. → pending Authorize; never direct external write.  
> **Compose:** Jarvis modal remains the chrome; Hermes fills it via tools (not a permanent parallel Gemini brain).

---

## 8. HITL & safety

### Intent

Grunt work freely; consequential actions wait for human clearance.

### Open questions

- [x] What always needs Authorize? → **Outbound email, calendar writes, external posts, destructive file ops, payments; send of quote PDF (not local preview)**
- [x] What is auto-allowed? → **Local reads, indexing, downloads to local store, research/RAG, clarifying questions, Gemini when user already chose that path; read-only browse with HUD visibility**
- [x] Voice Authorize phrases — keep strict short phrases only? → **Yes**
- [x] Multi-step jobs: one Authorize at start vs per external action? → **Per external action**
- [x] “Never done before” browser tasks — always HITL before navigate/login? → **Authorize before login or form-submit; read-only browse auto with HUD visibility**

### Decision

> **Decision:** Accepted — grunt work and local prep run freely; consequential external/destructive actions pause for Authorize.  
> **Auto-allow:** local reads, indexing, downloads to local store, research/RAG, clarifying Qs, Gemini when the user already chose that path, read-only browse (HUD-visible).  
> **Authorize each:** outbound email, calendar writes, external posts, destructive file ops, payments; sending a quote (PDF/email), not merely generating a local/Sheets preview.  
> **Multi-step:** Authorize **per external action**, not one blanket grant at job start.  
> **Voice:** short authorize/reject phrases only.  
> **Novel browser:** Authorize before login or form-submit.  
> **Constraint:** Hard safety denies remain; otherwise pause-for-Authorize (per Aspect 1).

---

## 9. Online overflow (Gemini & friends)

### Intent

Online models help when Hermes can’t, is too slow, or user says “delegate.” Long-term: shrink this surface as local models improve.

### Open questions

- [x] Explicit phrase required (“send this to Gemini”) vs automatic overflow policy? → **Both: explicit delegate + soft overflow after Hermes timeout + capability gaps**
- [x] Which tasks are **Gemini-only for now** (e.g. drawing vision)? → **Vision / drawing analysis Gemini-first until local vision exists**
- [x] Do Gemini jobs still report back into Hermes/Honcho memory? → **Yes — summarize into local DB (+ Honcho while dual-writing)**
- [x] Cost ceiling / monthly budget awareness? → **No hard kill-switch yet; log/HUD visibility; soft budget later**

### Decision

> **Decision:** Accepted — Gemini is overflow and specialist, not the default brain.  
> **Triggers:** user-chosen API path; explicit delegate; soft overflow after Hermes timeout (Aspect 3); capability gaps.  
> **Gemini-first for now:** drawing / vision analysis until local vision exists.  
> **Memory:** results summarized into local DB (and Honcho during dual-write).  
> **Cost:** visibility first; optional soft budget later.  
> **Direction:** shrink Gemini surface as local Hermes + skills improve.

---

## 10. Computer use & novel tasks

### Intent

Jarvis does almost any computer work from simple instructions — including one-off tasks (YouTube views, scrape a page, fill a portal).

### Open questions

- [x] Browser backend: Hermes browser tools / Playwright / dedicated computer-use MCP? → **Hermes first; Playwright/MCP if gaps**
- [x] Sandbox vs real desktop (logged-in Chrome profile)? → **Controlled profile first; real profile later with HITL**
- [x] Credentials: vault / OS keychain / never store? → **OS keychain / Hermes secrets; never plain files; never invent logins**
- [x] Evidence standard: screenshot + numbers spoken back? → **Screenshot + extracted numbers/text on HUD/voice**
- [x] Failure policy: retry, ask user, or escalate to Gemini? → **Retry once → ask user → optional Gemini escalate**

### Decision

> **Decision:** Accepted — novel computer tasks are in scope with evidence and HITL.  
> **Backend:** Hermes browser / computer-use first; Playwright or dedicated MCP only if needed.  
> **Profile:** Controlled browser profile first; personal logged-in profile later under HITL.  
> **Credentials:** OS keychain / Hermes secrets only.  
> **Evidence:** Screenshot + extracted facts on HUD/voice.  
> **Failure:** retry once → ask user → optional Gemini.  
> **HITL:** per Aspect 8 (read-only auto; Authorize before login/form-submit).

---

## 11. Open-source leverage

### Intent

Prefer proven OSS plugins/libraries over inventing infrastructure (Honcho-style), as long as license and local/offline fit the vision.

### Areas to shop (not decide yet)

- Memory / user modeling  
- Vector DB + RAG pipelines  
- Browser / computer use  
- PDF / drawing parsing  
- Speech (STT/TTS) if we leave Chrome-only later  
- Job queues / cron for 24/7 workers

### Open questions

- [x] License comfort: MIT/Apache only, or AGPL OK for personal use? → **AGPL OK for personal use; prefer MIT/Apache when equal**
- [x] Prefer Hermes-native plugins first, then generic Python libs? → **Yes**

### Decision

> **Decision:** Accepted — leverage OSS aggressively when it fits local/offline goals.  
> **Order:** Hermes-native plugins first, then Python libraries.  
> **License:** AGPL acceptable for personal use; prefer MIT/Apache when choosing between equals.

---

## 12. UX surface (HUD, voice, presence)

### Intent

Talk to Jarvis as a person; see status without a cluttered “AI dashboard.”

### Open questions

- [x] Voice-first forever, or keyboard-equal? → **Voice-first, keyboard-equal**
- [x] Minimal HUD (current orchestrator) vs richer ops screens later? → **Grow from current orchestrator toward office-day HUD (task modals, activity); avoid cluttered dashboard**
- [x] 24/7 means: always-on wake word, tray app, or gateway-only until spoken to? → **Hermes gateway always on + wake/proactive workers; tray optional later**
- [x] How should long jobs interrupt you (speak, HUD only, notification)? → **HUD progress + optional speak; Telegram/etc. when away (office-day)**

### Decision

> **Decision:** Accepted — talk to Jarvis as a person; light ops chrome.  
> **Input:** Voice-first, keyboard-equal.  
> **HUD:** Evolve current orchestrator toward office-day task modals + activity; not a dense AI dashboard.  
> **Presence:** Gateway always on; proactive workers for brief/prep; tray app optional later.  
> **Interrupts:** HUD progress + optional voice; remote channels when away from desk.  
> **Conversations (desk model):** Three kinds — (1) **Everyday desk** ambient for quick asks (no need to resume), (2) **Named discussions** you leave and reopen from Open notes, (3) **Job/workflow** threads bound to RFQs/drawings/quotes. Center HUD is always “who you’re talking to now”; draft email / HITL is an overlay interrupt, not a new conversation. Shared long-term memory across threads; session chatter stays per thread.

---

## 13. Data, privacy, retention

### Intent

Local-first; cloud only when chosen.

### Open questions

- [x] Retention for mail bodies / drawings / voice transcripts? → **Mail/drawings/production kept locally; voice transcripts short retention or on-demand**
- [x] Export/wipe commands (“forget me”, “purge RAG”)? → **Yes — first-class**
- [x] Single-user forever, or eventual multi-user profiles? → **Single-user for the foreseeable future**

### Decision

> **Decision:** Accepted — local-first, single-user, controllable retention.  
> **Keep local:** mail, drawings, production, and other office corpus.  
> **Voice transcripts:** short retention or on-demand save.  
> **Controls:** export + wipe (“forget me”, “purge RAG”) as first-class features.  
> **Users:** single-user for now.

---

## 14. Success metrics (personal, not startup)

### Intent

Know when a foundation is “good enough” to expand.

### Candidate metrics (pick later)

- Median conversational latency  
- % turns handled by Hermes vs Gemini  
- HITL miss rate (action without authorize) = 0  
- Memory useful recall in real weeks of use  
- RAG hit quality on shop questions  
- One novel browser task completed with evidence

### Open questions

- [x] Which 3 metrics matter most to *you* for “foundation done”? → **(1) casual Hermes latency on target (2) HITL miss rate = 0 (3) office-day loop: morning brief + one RFQ/quote path with Authorize send**

### Decision

> **Decision:** Accepted — foundation is “done enough to expand” when:  
>
> 1. Casual Hermes latency meets warm target (Aspect 3).
> 2. HITL miss rate = 0 (no external write without Authorize).
> 3. Office-day loop works: morning brief + one RFQ/quote path ending in Authorize-to-send.
>
> **Stretch:** local RAG useful on a real shop question; one novel browser task with evidence.

---

## 15. Suggested discussion order

Recommended sequence for our next chats (adjust freely):

1. **Product identity** (Aspect 1) — Jarvis vs Hermes boundary
2. **HITL** (Aspect 8) — safety envelope
3. **Memory** (Aspect 2) — Honcho self-host vs hybrid + RAG
4. **Offline RAG** (Aspect 5) — corpus + vector DB
5. **Hermes-first routing** (Aspect 7) — remove hardcoded intents
6. **Orchestrator / teams** (Aspect 6)
7. **Speed policy** (Aspect 3)
8. **Computer use** (Aspect 10)
9. **Gemini overflow** (Aspect 9)
10. **Stack & UX** (Aspects 4, 12)
11. **Metrics** (Aspect 14) → then write the phased build plan

---

## 16. Parking lot

Ideas that appear during discussion but must not derail foundations.

**Triage (2026-09-14):** Foundation only borrows *thin* slices of #4 and #7. Items 1–3, 5–6 stay deferred until office-day foundation metrics are green.

| # | Idea | Tag | Foundation action |
| - | ---- | --- | ----------------- |
| 1 | Toolsmith (auto-write skills) | **Post-foundation** | Keep curated Hermes skills only; no auto skill synthesis. |
| 2 | Red Team debate swarm | **Post-foundation** | Single-path planning for office-day; swarm later for big vendor/pricing calls. |
| 3 | Ghost Assist (clipboard / ambient) | **Post-foundation** | Office-day proactive = mail/hot-folder suggestions only; no clipboard watching in foundation. |
| 4 | Blast-radius HITL card | **Foundation (thin)** | v0: action summary + irreversibility 1–5 + one-line “what happens.” Skip ERP/financial simulation until those systems exist. |
| 5 | Adaptive vocal pacing | **Post-foundation (polish)** | One solid voice first; cadence modulation later. |
| 6 | Pipeline necromancy (72h nudges) | **Post-foundation** | Needs stable mail index + quote tracking + HITL drafts; expand after RFQ loop. |
| 7 | Black-box / time-travel debug | **Foundation (thin)** | v0: structured mission audit log (prompt/tools/results/cost). Scrubber UI / re-branch later. |

### 1. The Autonomous Skill Synthesizer (The "Toolsmith" Protocol)
**Tag: Post-foundation — do not build in foundation.**

Most agents use a fixed set of pre-written tools. When Jarvis encounters a repeatable task it doesn't know how to do (e.g., *"Track the price of titanium sheet metal on this supplier's raw website every Tuesday"*), it doesn't just perform a one-off browser scrape.

- **How it works:** A specialized background subagent opens a headless browser, writes a Python script using Playwright, executes and unit-tests it in an isolated scratchpad, wraps it into a native Hermes Skill (`.py` + `.md`), and registers it into `~/.hermes/skills/`.
- **The result:** Jarvis literally writes its own software capabilities on the fly and expands its permanent skill tree without you writing a line of code.
- **Why deferred:** Unsafe/unstable until computer-use + HITL are boringly reliable; foundation uses manual/curated skills (e.g. quote).

### 2. "The Red Team" / Dialectical Consensus Swarm
**Tag: Post-foundation — do not build in foundation.**

When making big decisions (pricing, vendor selection, architecture choices), single LLM outputs often suffer from sycophancy or tunnel vision.

- **How it works:** When tasked with complex evaluations, Jarvis spawns two competing subagents:
  - **The Optimist/Dealmaker:** Focuses on speed, low cost, and immediate upside.
  - **The Risk Auditor/Skeptic:** Stress-tests supply-chain fragility, hidden fees, warranty clauses, and technical debt.
- **The presentation:** They debate in a local sandbox thread. Jarvis reads the transcript and presents you with a concise executive synthesis showing where both sides agree and the single biggest point of friction requiring your judgment.
- **Why deferred:** Doubles cost/latency; not required for morning brief or first quote path.

### 3. Ambient Workflow Anticipation ("The Ghost Assist")
**Tag: Post-foundation — do not build in foundation (clipboard). Hot-folder may follow office-day mail ingest.**

Instead of waiting for you to issue a prompt, Jarvis passively monitors local context (recent clipboard text, files dropped in a designated hot-folder, or active terminal outputs).

- **How it works:** If you copy an invoice ID or open a PDF of a technical drawing, a local subagent immediately runs in the background. It cross-references your offline vector database (Honcho/Chroma) and pre-fetches the supplier's previous purchase orders, revision history, and open payment tickets.
- **The payoff:** When you open your Jarvis UI to ask a question, the dashboard greets you with: *"I saw you pulled up Drawing #4092. I've already loaded the supplier change-log and checked open POs. What's the plan?"*
- **Why deferred:** Clipboard watching is noisy and privacy-heavy; office-day “mail arrived → download → suggest” is enough proactive for v1.

### 4. Blast-Radius & Impact Simulation for HITL Approvals
**Tag: Foundation (thin) — full ERP/financial simulation stays parking lot.**

Most approval queues just show a "Send Email" or "Execute Action" button. Jarvis should evaluate the downstream consequences before you click.

- **How it works:** Alongside the proposed action, Jarvis displays a **Blast-Radius Card**:
  - **Financial Impact:** *"Commits $14,200 from operational reserve."*
  - **Downstream Tasks Created:** *"Triggers 2 warehouse delivery windows; updates 1 ERP ledger."*
  - **Irreversibility Score:** A rating from 1 (readily undoable) to 5 (money moved / public broadcast sent).
- You gain instantaneous situational awareness before signing off on any automated background task.
- **Foundation slice (v0):** action summary + irreversibility 1–5 + one-line “what will happen.” No ERP/ledger/warehouse blast until those connectors exist.

### 5. Adaptive Vocal Persona & Acoustic Pacing
**Tag: Post-foundation (polish).**

Instead of a static, monotonous assistant voice, Jarvis modulates its vocal pacing, timbre, and delivery based on operational priority.

- **Low Stakes / Morning Overview:** Relaxed, conversational cadence, prioritizing narrative over pure density.
- **Urgent / Time-Sensitive Conflict:** Rapid, crisp, bullet-style voice delivery that cuts directly to the required decision without pleasantries.
- **Deep Explanations:** Slower cadence, pausing slightly between complex technical clauses (e.g., when breaking down an engineering tolerance error).
- **Why deferred:** Does not unlock office-day; ship one solid voice first.

### 6. Pipeline Necromancy (Autonomous Stalled-Deal Reviver)
**Tag: Post-foundation — after RFQ/quote loop + mail index.**

Human operators lose tens of thousands of dollars simply because follow-ups go cold after a quote is sent.

- **How it works:** A cron subagent tracks external correspondence latency across all clients and suppliers. If a counterpart hasn't replied in 72 hours, it searches recent market news, commodity price trends, or project milestones to draft an organic, context-rich nudge—not a generic *"Just checking in,"* but a high-value prompt: *"Noticing domestic freight surcharges are scheduled to update Friday; wanted to ensure we locked in last week's quote before that goes into effect."*
- **Why deferred:** Needs stable correspondence tracking and HITL-gated outbound drafts; expand after foundation RFQ metric is green.

### 7. "Black Box" State Snapshots & Time-Travel Debugging
**Tag: Foundation (thin) — scrubber / re-branch UI stays parking lot.**

Because Jarvis will autonomously coordinate multi-step background jobs across multiple subagents, things will occasionally fail or hallucinate.

- **How it works:** Every autonomous mission logs a step-by-step state snapshot: model prompt, subagent tool response, token cost, and DOM screenshot (for web tasks).
- **UI integration:** Your Next.js interface includes an interactive **Scrubber Bar**. If an agent drafted the wrong email, you drag the slider back 3 steps to see exactly what bad assumption derailed the reasoning, tweak the premise in text, and re-branch the subagent tree from that point.
- **Foundation slice (v0):** structured mission audit log (prompt / tools / results / cost) for debug + metrics. No scrubber UI or time-travel re-branch until multi-step missions are common.

---

## 17. Decision log


| Date       | Aspect               | Decision | Notes                                                                                                           |
| ---------- | -------------------- | -------- | --------------------------------------------------------------------------------------------------------------- |
| 2026-09-14 | 0 — North star       | Accepted | Foundation priority: memory + latency. Office-day story locked as target narrative.                             |
| 2026-09-14 | 1 — Product identity | Accepted | Thin Jarvis shell; Hermes primary brain; Gemini overflow; Jarvis-branded HUD; pause-for-Authorize.              |
| 2026-09-14 | 8 — HITL & safety    | Accepted | Per-action Authorize for external/destructive; auto-allow local prep/RAG/read-only browse; short voice phrases. |
| 2026-09-14 | 2 — Memory           | Accepted | Dual-write: Honcho cloud live now; local vector/structured DB mirrored for later cutover. **Superseded 2026-09-22: 100 % local, Honcho stripped.** |
| 2026-09-14 | 5 — Offline RAG      | Accepted | Embedded vector DB (LanceDB/sqlite-vec); local embeddings; auto ingest; RAG via Jarvis MCP.                     |
| 2026-09-14 | 7 — Hermes-first     | Accepted | Hermes owns intent/planning; Jarvis guarantees only; tiny deny-list; safe MCP; SOUL+skills.                     |
| 2026-09-14 | 6 — Orchestrator     | Accepted | Soft Hermes-invented teams; parallel jobs; subagents/skills first; light HUD labels.                            |
| 2026-09-14 | 3 — Speed            | Accepted | Latency targets; 30s then soft Gemini fallback; accuracy>speed for consequential work.                          |
| 2026-09-14 | 9 — Gemini overflow  | Accepted | Explicit + soft overflow + vision-first Gemini; results back to local memory; shrink over time.                 |
| 2026-09-14 | 10 — Computer use    | Accepted | Hermes browser first; controlled profile; keychain secrets; evidence + HITL; retry then ask.                    |
| 2026-09-14 | 11 — OSS             | Accepted | Hermes plugins first; AGPL OK personally; prefer MIT/Apache when equal.                                         |
| 2026-09-14 | 4 — Stack            | Accepted | Latest stable; Windows now; keep Next+FastAPI; dual-write memory.                                               |
| 2026-09-14 | 12 — UX              | Accepted | Voice-first keyboard-equal; office-day HUD; gateway always on; light interrupts; **desk model** (ambient / discussion / job). |
| 2026-09-14 | 13 — Privacy         | Accepted | Local-first single-user; export/wipe; short voice transcript retention.                                         |
| 2026-09-14 | 14 — Metrics         | Accepted | Latency + HITL=0 + office-day RFQ/quote loop; stretch RAG + browser task.                                       |
| 2026-09-14 | Foundation plan      | Accepted | Phased build in `FOUNDATION_BUILD_PLAN.md`; gates P0→P4; parking lot #4/#7 thin only.                           |


---

*End of workbook. Vision decisions locked. Parking lot triaged. Foundation plan: [`FOUNDATION_BUILD_PLAN.md`](FOUNDATION_BUILD_PLAN.md).*