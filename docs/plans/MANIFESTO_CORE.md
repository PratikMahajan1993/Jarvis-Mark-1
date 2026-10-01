# Manifesto core implementation plan

The coding agent implements this plan as written. It does not interview. It does not add a gate this plan does not name, and it does not delete a gate this plan says to keep.

The quote spine is **core**. Do not run `npm run new:feature` for it. Edits to `backend/app/quote.py`, the Engineering bench, Hermes config, and the particle field are allowed for the slices below. A later plug-in feature still must not edit `core/`, `substrate/`, the turn reducer, or the root layout.

Product intent: `docs/JARVIS_MANIFESTO.md`. As-built: `docs/CURRENT.md`. Where they differ, the manifesto wins for new work. Do not re-decide a locked manifesto rule.

## Already shipped — do not rebuild

- One scrolling desk, four layers, one WebGL field: `frontend/src/core/desk/Desk.tsx`, `frontend/src/core/sections/registry.ts`.
- Engineering drawing plus quote sheet: `frontend/src/core/sections/engineering/EngineeringSection.tsx`, `frontend/src/components/bench/QuoteSheet.tsx`.
- `quote_verify` blockers, including raw-material basis older than 30 days at send, in `backend/app/quote.py`. Keep that age check. The manifesto adds an owner override; it does not remove the check.
- Claim-once mail outcomes `sent` / `failed` / `unknown`, with boot reconciliation to `needs_human` and no silent retry, in `backend/app/agent.py`.
- Vision consent default-deny and the document cap, master-data page, temporal dated rates, HITL Authorize / Reject / Later.
- Feature plug-in: `npm run new:feature`, including `--section`, `--migration`, and jobs started from the API lifespan.

## Slice 1 — Confirmable drawing cells and send proof

Owner: core. Files: `backend/app/quote.py`, a new numbered migration under `backend/migrations`, tests beside `backend/tests/test_quote_playbook.py`.

Store these cells on the quote revision. Each cell is `empty`, `proposed`, `confirmed`, or `assumption`.

- Hard cells, which cannot be `assumption`: `revision`, `quantity`, `material` (grade and condition in one cell, for example `SS316, annealed`).
- Assumption-capable cells: `heat_treat`, `finish`, `gdt`.

Rules:

- Vision may write `proposed` only. An empty cell stays empty. A spoken or typed correction writes the value and leaves the cell unconfirmed until an explicit accept.
- `quote_verify` at `stage='send'` is a BLOCKER when any hard cell is not `confirmed`.
- An open assumption does not by itself block the draft. At send it is a BLOCKER until the stored override contains the customer's exact master-data name. A short name or alias does not satisfy it. The PDF text for a still-open assumption must include the word assumption. Slice 1 checks that string on the quote record the PDF is built from. It does not redesign the PDF layout.
- Stale or missing raw-material price stays a send BLOCKER. It clears only when the same override also stores the age string Jarvis showed (`30` or the actual age, or `none` when the price is missing). Stale outsource stays a warning and does not stop the send.
- Keep the existing rule that an empty delivery date blocks send. Do not calculate a delivery date.

Check: pytest covers hard-cell block, assumption block without the exact name, assumption send after the exact name, stale material block without name and age, and stale material send after both are stored. `quote_send` still refuses when `quote_verify` sets `stop`.

## Later slices — do not start until the reviewer says the previous slice passed

Phone transport is parked (Slice 4). Any step that sends on WhatsApp or Telegram waits with it. Desk and email work may continue.

- **Slice 2 — Bench and voice.** A stepped sequence inside Engineering, not new scroll pages: confirm, labour or material, supplier, strategy, hours, owner price, assumptions, PDF, send. **Move to WhatsApp** stays hidden until every hard cell is confirmed and every other mandatory cell is confirmed or tagged. Chat stays on every step. With a drawing open, auto-speech is one quote blocker only. Each desk reply gets a speak control except a margin suggestion. WhatsApp stays text. Particle field: normal Engineering motion while confirming; amber and slow while a blocker is uncleared; thinking motion while vision runs. Price, margin, tolerance, assumption count, and customer name do not change the field. Files: Engineering section, `frontend/src/lib/voice.ts`, orb state in the Engineering formula controls.
- **Slice 3 — One live quote.** Persist `intake`, `on_desk`, `blocked`, `handoff_ready`, `live`, `parked`, `detour`, `release_hold`, `sending`, `sent`, `failed`, `unknown`. One live quote in the owner thread. Park from that thread. A second RFQ stays on the desk. A master-data detour is labelled and a send word does not send until the repeat-back is finished or cancelled. The open quote keeps resolved rates until an explicit reprice.
- **Slice 4 — Phone transport. PARKED.** Do not implement this slice. WhatsApp is not set up on Hermes. The owner may choose Telegram instead. Do not enable `platforms.whatsapp`. Do not add a Telegram adapter. Do not send quote text, drawings, or status to either channel. The Engineering control may keep the label Move to WhatsApp and may only store `handoff_ready`. It must not open a chat. Resume this slice only after the owner names the channel.
- **Slice 5 — Price hint and assumption mail.** Suggest a margin move only after three won jobs share primary process and tolerance class. Formula `(sell − total cost) / sell`. Total cost is machining, raw material, outsource, and special tooling. The hint never writes the price, never speaks, and is never shown to staff. An accepting customer email clears a tag. A reply that changes the value writes it unconfirmed and keeps the tag. An unreadable reply stays tagged.
- **Slice 6 — Phone master data. PARKED with Slice 4.** Repeat-back edits from a messenger wait until the owner names WhatsApp or Telegram. The desk master-data page stays the writer.
- **Slice 7 — One shop brain.** Configure Hermes so an unreachable online model calls Ollama on this machine. Do not add a Jarvis planner that calls Ollama for shop turns. Shop arithmetic stays in `quote.py`. If the local model cannot finish a tool step, the quote pauses. Cloud vision stays off while the line is down. The desk can still open a local drawing, confirm cells, price from master data, and write a draft PDF.
- **Slice 8 — P1, without a messenger.** Inspector release of job, measurements, and accept/reject/rework, with no price and no delivery date, and no change to customer-visible status. Staff mail of questions only, or a supplier enquiry, held when the draft contains a price, a date, or a commitment. Customer status from owner-typed status and date only, returned by the API. Statuses: Order received, In process, Halted, Inspection, Ready, Dispatched. Drawing send by email only when the owner asks and the component is Active, to one named person. Messenger and supervisor-group sends stay parked with Slice 4.
- **Slice 9 — P2, after P1 is reviewed.** Draft a program and a setup chart under `exports/nc/`. A person promotes. No transmission to a control, DNC, or machine network. Do not answer whether an old program is valid for a new revision. No staff mobile app in this slice.

## Out of scope

Direct use of a generated program on a machine. Jarvis choosing the selling price. Jarvis calculating a delivery date. A second shop planner beside Hermes. Any phone route except the owner's private WhatsApp for master data or for finishing a quote.
