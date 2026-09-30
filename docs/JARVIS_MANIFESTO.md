# Jarvis Manifesto

**Locked:** 30 September 2026  
**Status:** Product intent. This document governs future development. `docs/SYSTEM_TRUTH.md` describes the desk as it runs today. Where the two differ, this manifesto is the intent to build toward.

---

## 1. The Executive Vision & Guiding Philosophy

Jarvis is the office instrument of a precision machining company with one proprietor, who is also the only programmer. It exists so a finished-component price can leave the building correctly, and so the owner can finish that price without walking off a machine to sit in the office.

The first workflow is an RFQ taken through to a PDF the owner authorizes. Everything else is in service of that spine, or it waits.

### Tenets

1. **The owner releases every commercial promise.** A price, a delivery date, a purchase commitment, and a drawing leave only by the owner's hand.
2. **Numbers come from records.** Hours, mass, money, rates, and margin comparisons are computed from stored rows. A model may plan, phrase, and propose. It may not invent a rate, a dimension, a date, or a price.
3. **A suggestion never writes the price.** The owner sets the selling price from who the customer is. Jarvis may suggest a move. The suggestion does not change the figure.
4. **The print is confirmed by a person.** Vision fills cells. The owner accepts or corrects them. A spoken or typed correction stays unconfirmed until the owner accepts it.
5. **Three cells cannot be assumed.** Revision, quantity, and material (grade and condition together) are confirmed before the quote moves to the phone and again before the email. Other callouts may travel labelled.
6. **One live quote.** The owner's private thread holds one quote. A second RFQ waits on the desk until that quote is parked or finished.
7. **The desk sees the print. The phone finishes the quote.** Vision and cell confirmation happen on the monitor. The rest of the workflow, including the quote email, happens in the owner's private WhatsApp.
8. **Presence is not data.** The particle field shows whether Jarvis is listening, thinking, speaking, or waiting. It never shows a price, a margin, a tolerance, an assumption count, or a customer name.
9. **An external act has one outcome.** A quote email is sent, failed, or unknown. Unknown waits. A quote already marked sent does not send again.
10. **Nothing is transmitted to a machine.** Jarvis may draft a program and a setup chart. A person promotes them. Jarvis never sends them to a control, a DNC link, or the machine network.

---

## 2. Target Personas & Ergonomic Principles

### Personas

| Person | Where they meet Jarvis | What they may finish | What stays with the owner |
|---|---|---|---|
| **Owner** | The desk, then his private WhatsApp. He is the only person on that thread. | The quote, from confirmed cells through the email. Master data, from the desk page or from that same thread. | He is the only editor of master data, the only sender of drawings, and the only person who sets customer-visible status. |
| **Quality inspector** | A marked role. Not the desk. | An inspection result: job identity, measured values, and a disposition of accept, reject, or rework. Sheet and PDF. A corrected result, the same way, after a wrong release. | Price, delivery date, and customer-visible status. |
| **Other staff** | WhatsApp now. A dedicated app later. A second Google account. They do not live on the desk. | A customer email that contains only questions. A supplier email that requests a quote or a missing fact. | Margins, quote emails, inspection release, and pulling a drawing. |
| **Supervisors** | One WhatsApp group the owner has registered. | They receive a drawing when the owner asks Jarvis to send it there. | They cannot request the file. Membership of the group is the owner's responsibility in WhatsApp. |
| **Customer** | A small status page, and WhatsApp messages asking for an update. | They can read a status and a delivery date the owner has already entered. | Price, margin, machine rate, and the drawing. An assumption is confirmed by email reply, never by WhatsApp. |

Customer-visible statuses are: **Order received, In process, Halted, Inspection, Ready, Dispatched.**

If the status or the date is missing, Jarvis tells the customer it will ask the shop, and it pings the owner. Halted is spoken as Halted. If the owner has typed a reason, Jarvis reads that reason.

A staff member who tries an act reserved for the inspector or the owner is refused, and the owner is pinged.

### Ergonomic principles

- **One operator, one monitor, 8 GB of video memory.** The desk machine is a single screen. Text, cells, and the drawing stay sharp. The particle field, the parallax, and the section snap stay in their normal motion.
- **The drawing is the brightest object.** During confirmation, the print is not covered by chat and is not competed with by a second status system.
- **The bench is quiet.** Inside Engineering, the quote is a clear, subtle, classy sequence of steps. Chat is available on every step. The steps do not become extra pages in the scroll.
- **The phone is a continuation, not a second quote.** After **Move to WhatsApp**, the bench remains on the monitor and advances as the chat completes each step. The desk mirrors the same thread.
- **Voice is scarce.** With a drawing open, Jarvis speaks a quote blocker once. Every other desk reply has a small button that speaks that reply when pressed. A margin suggestion has no speak button. WhatsApp stays text. If speech cannot play, the line remains on screen.
- **Pings find the owner on the floor.** An approval waiting while he is with an operator reaches him on WhatsApp. He does not walk to the office for it.

---

## 3. The Unified Layout & Layering System

The desk is one vertical page. The order is **Monitor, then Casual, then Engineering.** A feature section may slot into that order later. Master data is a separate page the owner opens on purpose. It is not a section of the scroll.

The quote sequence lives as a stepped bench inside Engineering. Scrolling is how the owner leaves the bench. It is not how he advances a quote step.

### Four layers

| Layer | Role | Motion |
|---|---|---|
| **L0 Backdrop** | The slow field behind the page. | Parallax at a fraction of the scroll. |
| **L1 Presence** | One WebGL particle field, fixed to the viewport. One context for the life of the tab. It is never destroyed to change section. | Does not scroll. Morphs by section and by turn. |
| **L2 Work** | The sections, the cards, the drawing, and the Engineering bench. | Scrolls one-to-one with the page. |
| **L3 Chrome** | Status, section navigation, the task dock, the command line, and the speak control on a reply. | Stays above the work. |

A gate that asks the owner to type a name sits above the chrome. On WhatsApp, that same gate is a reply in the private thread, not a modal.

### The particle field while a drawing is up

The field is a swarm behind the page. It already shows the turn: calm while listening, busier while thinking, moving with the voice while speaking, slow and amber while waiting.

While the drawing is up:

- **Confirming or correcting cells.** The field keeps the normal Engineering motion. An unconfirmed callout does not get its own motion. The cell is the signal.
- **A blocker stops the quote.** The field slows and shifts amber, once. Jarvis speaks that blocker once. The field stays amber until the blocker is cleared. The shift is small and slow. The print stays the brightest thing on the screen.
- **The owner presses speak.** The field follows that playback, then returns to the Engineering motion. A silent reply does not move the field.
- **Vision is running.** The field uses the thinking motion for that wait.
- **Price, margin, tolerance class, assumption count, and customer name** do not change the field's color, speed, size, or position.

### Scroll kinematics

- Vertical scroll, with snap, one section to a gesture.
- The active section is the section on screen. The quote does not pull the owner to Engineering by surprise while he is confirming on the bench, and it does not follow him onto WhatsApp by closing the page.
- After handoff, the monitor may keep showing the bench. The conversation continues on the phone. Both show one thread.

---

## 4. Domain Lifecycles & State Machines

### 4.1 RFQ to authorized PDF

The step order is fixed:

1. Confirm the drawing facts.
2. Labour only, or buy the raw material.
3. Supplier request, when material or an outside process is in scope.
4. Machining strategy.
5. Hours at the machine-hour rate.
6. The owner's price.
7. Labelled assumptions.
8. PDF.
9. The owner's send.

**Intake.** A customer is regular only when the owner has set that flag. For a regular customer's RFQ, Jarvis downloads the file and reads text already in the PDF. Cloud vision does not run at intake.

**Open.** Vision runs when the owner opens the job, and only when that customer's record allows the drawing to leave the premises. Vision writes each callout into its cell. An empty mandatory cell stays empty. A missed callout is not filled by a guess.

**Confirm.** The owner accepts each cell. A correction, typed or spoken, writes the cell and leaves it unconfirmed until he accepts it. Grade and condition occupy the material cell together (for example SS316, annealed).

**Hard cells.** Revision, quantity, and material must be confirmed. They cannot be tagged as assumptions. **Move to WhatsApp** stays hidden until those three are confirmed and every other mandatory cell is either confirmed or tagged.

**Assumptions.** Heat treat, finish, and GD&T may be tagged. The tag is visible on every later step and on the draft PDF until a customer email clears it. The owner may still send with tags open. The PDF names them as assumptions.

**Handoff.** **Move to WhatsApp** carries the one live quote into the owner's private thread. The customer never receives the PDF on WhatsApp. The supervisor group is not part of this thread. The bench mirrors the thread and advances as each step completes.

**One quote.** The owner may park the live quote from the thread. A new RFQ stays on the desk until he parks or finishes the live one. He may start a master-data edit mid-quote. Jarvis labels every turn **Quote** or **Master data**. Until that edit's repeat-back is finished or cancelled, a send word does not send the quote. The quote waits at the same step, then Jarvis returns him there. The open quote keeps the rates it has already resolved unless he asks Jarvis to reprice it.

**Price.** The owner sets the selling price. Jarvis may suggest a higher or lower price only when at least three won jobs match this job on both primary process (turning, milling, turn-mill, or grinding) and tolerance class (standard or tight). The formula is (sell price − total cost) ÷ sell price. Total cost is machining, raw material, outsource, and special tooling. The machine-hour rate already contains overhead. The suggestion is text in the owner's thread. It never writes the price. Staff never see it. It has no speak button. Otherwise Jarvis stays silent.

**Supplier figures.** A raw-material price older than 30 days, and an outsource price older than 30 days, are shown with their age. Stale material, and a missing raw-material price, stop the send until the owner types the customer's exact name and the age Jarvis is showing. A missing price is shown with no age. Stale outsource is a warning on the PDF and does not stop the send.

**Send gates.** All of these are true before the email exists:

- Revision, quantity, and material are confirmed.
- Every other mandatory cell is confirmed or still tagged, and the PDF shows the tags.
- If any assumption is open, the owner has typed the customer's exact name from the master record. A short name or an alias is refused, and Jarvis shows the name it needs.
- If material is stale or missing, the owner has typed that same name and the age Jarvis is showing.
- Delivery, if it appears where a customer can read it, is a date the owner typed. Jarvis does not calculate one.

**Customer reply to an assumption.** An email that accepts the assumption in words clears that tag. A reply that changes the value writes the new value, leaves the cell unconfirmed, and keeps the tag. A reply Jarvis cannot read stays tagged and is shown to the owner. Nothing in that mail changes the price until the owner confirms the cell. WhatsApp does not clear a tag.

**Mail outcome.** Each send attempt ends as **sent**, **failed**, or **unknown**. Jarvis does not send again on its own. Unknown waits for the owner. A second attempt on a quote already marked sent shows the first result and does not create another email.

### Quote states

| State | Meaning | Leaves when |
|---|---|---|
| `intake` | File stored. Embedded text only. | The owner opens the job. |
| `on_desk` | Vision has filled cells. The owner is confirming. | Hard cells are confirmed and every other mandatory cell is confirmed or tagged. |
| `blocked` | A hard cell is empty, or a blocker has been spoken. | The owner clears it. The field stays amber until then. |
| `handoff_ready` | **Move to WhatsApp** is available. | The owner moves the quote. |
| `live` | The one quote in the private thread. The bench mirrors it. | He parks it, or the send attempt ends. |
| `parked` | Off the thread. The desk holds the step and the resolved rates. | He resumes it, and no other quote is live. |
| `detour` | A master-data repeat-back is open. The quote waits at its step. | He finishes or cancels the repeat-back. |
| `release_hold` | A send gate is waiting: exact name, or name and age. | He satisfies the gate. |
| `sending` | The email has been claimed. | The attempt settles. |
| `sent` | The customer has the email. | Terminal for that send. A repeat shows this result. |
| `failed` | The email did not leave. | A new owner act may try again. |
| `unknown` | The line died during the handoff to the network. | The owner decides. Jarvis does not retry. |

### 4.2 Master data and temporal validity

The owner is the only editor. The desk page and his private WhatsApp write the same records. No other person has the phone route.

From that thread he may edit customers, machines, materials, suppliers, machine-hour rates, primary process, tolerance class, Regular, Active, cloud-vision consent, and the NDA flag.

A phone edit commits only after a repeat-back. Jarvis states the record, the field, the current value, and the new value, with unit and currency. It writes only when he sends that new value back exactly.

A rate change adds a new dated row and end-dates the old row. Quotes already sent keep the rates they were proved with. A quote already open keeps the rates it has already resolved until the owner asks to reprice that quote. Rates are read as of the quote date.

Regular means intake may download and read embedded text. Active means a drawing may be sent. Cloud-vision consent and NDA together decide whether vision may read that customer's drawing. Unknown consent denies vision.

### Master-data edit states

| State | Meaning |
|---|---|
| `proposed` | Jarvis has echoed record, field, old value, new value, unit, and currency. |
| `committed` | The owner returned the new value exactly. Rates are a new dated row. |
| `cancelled` | The owner cancelled. The quote, if one was live, resumes at its step. |

### 4.3 Drawing distribution

Staff cannot pull a drawing. A customer is not a recipient on this path.

The owner asks, and he names the target. The component's Active flag is set. Otherwise Jarvis refuses.

- **A named person** receives the file by WhatsApp and by email, together, on that send.
- **The registered supervisor group** receives it when the owner explicitly asks for that group. Jarvis does not inspect who is in the group. Any other group is refused until the owner changes the registration.

### 4.4 Inspection

The inspector may write the result to the sheet and send the PDF without the owner. The result carries the job, the measurements, and a disposition: accept, reject, or rework. It carries no price and no delivery date.

A wrong job or a wrong disposition is corrected by another release from the inspector. Customer-visible status does not change as a side effect. The owner sets that status.

### 4.5 Programs

Out of the first horizon, and permanently bounded: Jarvis may draft a program and a setup chart. A person promotes them. Jarvis does not answer whether an old program is still valid for a new revision. Jarvis never transmits to a control, a DNC link, or the machine network. Years of data do not retire that rule.

---

## 5. Architectural & Safety Invariants

### One shop brain

Jarvis talks to Hermes for shop work. Hermes plans the steps and calls the tools. When Hermes cannot reach its online model, Hermes calls a model served on the same machine. Ollama serves that model. Jarvis does not grow a second planner that calls Ollama on its own.

The local model may talk and may call the tools. Hours, mass, and money still come from stored rows. If it cannot finish a tool step, the quote pauses and tells the owner. Cloud vision stays unavailable while the line is down.

Casual conversation and speech may use the cloud. They do not calculate a quote.

### Deterministic and generative

| Deterministic | Generative, then confirmed |
|---|---|
| Hours × machine-hour rate, material cost, totals, margin arithmetic | The wording of a margin suggestion |
| Cell state, assumption tags, PDF labels | Vision's proposed cell values |
| Mail outcome, claim of a send, temporal rate rows | A drafted clarification question |
| Customer status text from fields the owner typed | Planning the next quote step |

A generative line becomes a price, a rate, a date, or a confirmed dimension only through the gate for that fact. The inspector's measurements are the exception he is allowed to release himself.

### Blast radius

| Class | Acts | Gate |
|---|---|---|
| **Local** | Read a drawing already on disk. Confirm cells. Price from master data. Write a draft PDF on the machine. | No release. |
| **Staff** | Customer email of questions only. Supplier enquiry for a quote or a missing fact. | The draft contains no price, no date, and no acceptance of a term. If it does, it is held and the owner is pinged. |
| **Inspector** | Inspection result and its correction. | The marked inspector. Job, measurements, disposition. |
| **Owner commercial** | Quote email. A delivery date a customer can read. A purchase commitment. Customer-visible status. | The owner's private thread or the desk. Send gates in §4.1. |
| **Owner distribution** | Drawing to a named person, or to the registered supervisor group. | Owner asks. Active component. Exact target. |
| **Owner records** | Any master-data field, including vision consent and NDA. | Repeat-back of the new value. |

### Claim-once

A quote send is claimed once. A repeated authorization of a sent quote returns the first outcome. An unknown attempt is not retried in the background.

### Offline and return

With Hermes up and the internet down, the desk can open a drawing already on disk, take cell confirmations, price from master data, and write a draft PDF.

When the line returns:

- Text already formed in the owner's private thread sends itself.
- A drawing, a customer-status reply, a message to staff, and a message to the supervisor group wait for the owner again.
- Customer mail and supplier mail wait for the owner again, including a quote whose customer name he had already typed.
- Anything the offline model writes while the line is down is shown to the owner before it is allowed to leave.

### Identity of the thread

Send words, names, and confirmations apply to the one live quote, or to the master-data repeat-back currently labelled. They do not cross. Two quotes are never waiting on a bare "send it" in the same thread.

---

## 6. Feature Index & Roadmap Horizons

### P0 — The quote leaves correctly

The first month is this horizon and nothing beyond it.

- Regular-customer intake: download and embedded text only.
- Consent-gated vision on open. Cells filled. Spoken and typed corrections stay unconfirmed until accepted.
- Hard stops on revision, quantity, and material grade plus condition.
- Assumption tags on the bench and on the PDF. Email reply clears or rewrites a tag by the rule in §4.1.
- Engineering stepped bench. Chat on every step. Particle-field and voice rules while the drawing is up.
- **Move to WhatsApp.** One live quote. Park. Master-data detour with labelled turns. The desk mirrors the thread.
- Labour or material, supplier figures, strategy, hours at the attested rate, owner price, silent-unless-qualified margin hint, PDF.
- Send gates: exact customer name, stale or missing material with name and age, 30-day outsource warning on the PDF.
- Mail outcomes: sent, failed, unknown. No second email for a sent quote.
- Master data on its page and on the private thread. Repeat-back. Dated rate rows. Open quotes keep resolved rates until an explicit reprice.
- Hermes as the only shop-brain socket. When its online model is unreachable, Ollama serves the local model Hermes calls.
- Offline desk: local drawing, confirmation, pricing, draft PDF, and the return rules in §5.

### P1 — Other people finish only their own work

- Inspector release and correction, without touching customer-visible status.
- Staff question-only customer mail, and supplier enquiries, held when a draft grows a price, a date, or a commitment.
- Customer status page and WhatsApp updates from owner-typed status and date.
- Drawing distribution: named person on WhatsApp and email together; the one registered supervisor group when the owner asks.
- Owner-typed Halted reasons, read only when present.

### P2 — Prepared machining, still a person's hand

- Draft programs and setup charts for a job the owner is not standing in front of.
- Promotion remains a human act.
- No transmission to a control, a DNC link, or the machine network.
- A staff mobile app may replace WhatsApp as their door. It does not add authority.
- Whether an existing program is valid for a new revision stays out of scope until a separate safety case exists. That case is not implied by this horizon.

### Outside the manifesto

- Direct use of a generated program on a machine.
- Jarvis deciding the selling price.
- Jarvis calculating a delivery date.
- A second planner beside Hermes.
- Any route except the owner's private WhatsApp for master data or for finishing a quote.
