---
name: shop-quote
description: >-
  Machining quotation playbook. Triggers: "I want to create a new quote for XYZ drawing",
  "Lets work on the RFQ my deepak last weak", "start quote workflow for XYZ", "new quote",
  "work on the RFQ", "quote this drawing", "quote this RFQ", "make a quotation for Deepak". One brain —
  mail RFQ, urgent walk-up, hard copy, or old WhatsApp/email file. Jarvis quote tools only;
  never invent prices, paths, or outsource amounts.
---

# Shop quote playbook

## Purpose

Turn an identified drawing or RFQ into a correct machining quotation, proof it, and queue customer email under HITL Authorize. One Hermes brain; tools own mail, files, sheet, PDF, and proof.

## When to use this

Casual or typo-rich starts are fine. Same playbook for every door:

- **Mail RFQ** — new RFQ in inbox (with or without attachment).
- **Urgent walk-up** — impromptu part to machine; no formal RFQ yet.
- **Hard copy in office** — customer on-site with paper drawing.
- **Old file** — WhatsApp export, forwarded mail, or months-old email they want quoted now.

No extra intent model — pick the door from context and proceed.

## Drawing lookup (stop at first clear hit)

Do **not** start with vision or pricing. Call `jarvis_quote_find_drawing` first. **Never** pick the last file in the DB. The tool stops at the first clear hit and asks when more than one matches:

1. **Path already given** — pass `drawing_path`. Missing file → ask. Do not substitute another file.
2. **Already in hand** — Engineering desk is showing one drawing (`conversation.focus.local_path`). Several on the desk → list and ask.
3. **Named search** — pass `part_hint`. Search local inbox files, `exports`, and mail filenames. **One hit** → use it. **Several** → list and ask. **Zero** → continue.
4. **Mail has one drawing attachment, disk does not** — the tool saves that attachment under exports and returns the local path. **Never** a Gmail thumbnail URL. Several attachments → ask which to save.
5. **Hard copy or phone file** — ask for a photo or HUD drop; save to exports before any analysis.

**No local path → no vision and no prices.** Do not guess a drawing.

When dimensions are still unclear **after** a path exists, call `jarvis_quote_analyze_drawing` — vision is a helper, not step 1 of the job.

## Real steps (after drawing is identified)

1. **Labour-only vs buy raw material** — see Decisions below; record scope for `jarvis_quote_build` (`scope`: `labour` or `with_material`).
2. **If buy RM** — call `jarvis_quote_request_rm_quote` (queues the supplier email under Authorize; does not send). When the quote arrives, `jarvis_quote_record_rm_quote` with the price and date. If only an estimate is available, set `is_estimate` true and name historical transactions or market trend in `notes`. Never invent the price.
3. **Machining strategy** — `jarvis_quote_add_operation` (templates: turning, milling, edm, heat treat, plating, grinding). Drag order on the bench is `jarvis_quote_reorder_operations`. Outsource needs a case (`no_machine`, `customer_asked`, `capacity`, `not_in_house`), a vendor, and a quoted price. Never invent the outsource price. Attest machine-hour rates with `jarvis_mhr_attest_rate` before send. A rate still equal to the shipped demo seed is not quotable.
4. **Machining cost** — from **Machine Hour Rate** for the chosen machine type. Pass `machine` and `machining_rate` into `jarvis_quote_build`. Minimum floors live in `files/mhr-demo.md` (DEMO table only — not shop truth).
5. **Assemble the quotation** — `jarvis_quote_build` → owner review/edits → `jarvis_quote_pdf` → **must** `jarvis_quote_verify` → `jarvis_quote_send` queues Authorize only.

Customer email (draft for send tool): short formal body, **total quoted cost in bold**, full quotation PDF attached. **Do not claim sent** until owner Authorizes.

## Decisions

| Topic | Rule |
| --- | --- |
| Labour vs material | Some customers are labour-only by default; for others buying our own RM is compulsory. A line in the mail or the customer saying "with material" overrides the default. Pass that as `scope` on `jarvis_quote_build`. If neither the customer record nor this order states scope, the tool returns `need: scope` — **ask** "Labour-only or with material?" and do not price. |
| MHR floor | Each machine type has a **minimum** MHR in `files/mhr-demo.md` (DEMO). Do not quote below it; quoted rate may be higher. Floor ≠ final price. Later: master data — **do not build master data now**. |
| Outsource | Outsource an operation or whole component when: no suitable machine, customer asked, capacity, or process not in-house (heat treat, plating, grinding, etc.). Record which case. Never invent outsource price. |
| Before send | Every price line must be present. Missing RM supplier quote → estimate allowed only from historical transactions or market trend, marked estimate with source named. **Delivery time does not hold the quote.** Customer spelling: ask if unsure; empty `client-names.md` does not block proof. |
| Never underquote | Past misses: price corrected after send, assumed material, forgotten outsource, material on labour-only customer. Do not go below minimum MHR, omit required RM/outsource cost, or add material cost on labour-only orders. |

## Proof and send

- Always `jarvis_quote_verify` before saying ready to send.
- `stop: true` when any check is a BLOCKER — fix process; do not queue send. WARN never stops, regardless of count.
- WARN-only: owner may edit and re-verify; send may still queue with loud warnings.
- `jarvis_quote_send` attaches verify snapshot, refuses when `stop: true`, never sets `sent: true`.

## Toolbox

| Tool or file | Use |
| --- | --- |
| `jarvis_quote_find_drawing` | First call. Path, or ask. Never a guessed sheet. |
| `jarvis_quote_request_rm_quote` | Queue supplier RM email. Authorize before it sends. |
| `jarvis_quote_record_rm_quote` | Record the received price, or a labelled estimate. |
| `files/INDEX.md` | File map |
| `files/mhr-demo.md` | DEMO minimum MHR by machine type |
| `files/mhr-demo-attestation.md` | Owner sign-off for those demo floors. Blank cells block proof. |
| `files/rate-rules.md` | Where prices may come from |
| `files/tone-rules.md` | Customer email/PDF tone |
| `files/quote-template.md` | Quotation sections |
| `files/client-names.md` | Known customer spellings |
| `notes.md` | Corrections newest first |

## Loop

On owner correction: diagnose process / toolbox / proof → smallest fix → `jarvis_quote_playbook_note` → re-run from broken step → verify again before send.
