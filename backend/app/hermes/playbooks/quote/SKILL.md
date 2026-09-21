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

Do **not** start with vision or pricing. Resolve the drawing first. **Never** pick the last file in the DB.

1. **Already in hand** — owner just dropped a file, or Engineering desk is already showing the drawing. Confirm filename/revision with the owner.
2. **Named search** — search local inbox files, `exports`, and mail for the part name or filename. **One hit** → use it. **Several** → list and ask. **Zero** → continue to mail attachment or ask.
3. **Mail has attachment, disk does not** — save attachment to a local path under exports (or tool-provided path). Quote that path only — **never** a Gmail thumbnail URL.
4. **Hard copy or phone file** — ask for a photo or HUD drop; save to exports before any analysis.

**No local path → no vision and no prices.** Do not guess a drawing.

When dimensions are still unclear **after** a path exists, call `jarvis_quote_analyze_drawing` — vision is a helper, not step 1 of the job.

## Real steps (after drawing is identified)

1. **Labour-only vs buy raw material** — see Decisions below; record scope for `jarvis_quote_build` (`scope`: `labour` or `with_material`).
2. **If buy RM** — request a supplier quote; when it arrives, record price and source. If only an estimate is available before send, mark `rm_source: estimate` and name the source (historical transactions / market trend) in `rm_source_note`.
3. **Machining strategy** — with the owner or team: operations sequence, in-house vs outsource, machines, special tooling. When outsourcing, record **which case** applied (see Decisions) — do not invent the outsource price.
4. **Machining cost** — from **Machine Hour Rate** for the chosen machine type. Pass `machine` and `machining_rate` into `jarvis_quote_build`. Minimum floors live in `files/mhr-demo.md` (DEMO table only — not shop truth).
5. **Assemble the quotation** — `jarvis_quote_build` → owner review/edits → `jarvis_quote_pdf` → **must** `jarvis_quote_verify` → `jarvis_quote_send` queues Authorize only.

Customer email (draft for send tool): short formal body, **total quoted cost in bold**, full quotation PDF attached. **Do not claim sent** until owner Authorizes.

## Decisions

| Topic | Rule |
| --- | --- |
| Labour vs material | Some customers are labour-only by default; for others buying our own RM is compulsory. A line in the mail or the customer saying "with material" overrides the default. If neither customer record nor this order states scope — **ask**. |
| MHR floor | Each machine type has a **minimum** MHR in `files/mhr-demo.md` (DEMO). Do not quote below it; quoted rate may be higher. Floor ≠ final price. Later: master data — **do not build master data now**. |
| Outsource | Outsource an operation or whole component when: no suitable machine, customer asked, capacity, or process not in-house (heat treat, plating, grinding, etc.). Record which case. Never invent outsource price. |
| Before send | Every price line must be present. Missing RM supplier quote → estimate allowed only from historical transactions or market trend, marked estimate with source named. **Delivery time does not hold the quote.** Customer spelling: ask if unsure; empty `client-names.md` does not block proof. |
| Never underquote | Past misses: price corrected after send, assumed material, forgotten outsource, material on labour-only customer. Do not go below minimum MHR, omit required RM/outsource cost, or add material cost on labour-only orders. |

## Proof and send

- Always `jarvis_quote_verify` before saying ready to send.
- `stop: true` when more than 2 checks fail — fix process; do not queue send.
- 1–2 fails: owner may edit and re-verify; send may still queue with loud warnings.
- `jarvis_quote_send` attaches verify snapshot, refuses when `stop: true`, never sets `sent: true`.

## Toolbox

| File | Use |
| --- | --- |
| `files/INDEX.md` | File map |
| `files/mhr-demo.md` | DEMO minimum MHR by machine type |
| `files/rate-rules.md` | Where prices may come from |
| `files/tone-rules.md` | Customer email/PDF tone |
| `files/quote-template.md` | Quotation sections |
| `files/client-names.md` | Known customer spellings |
| `notes.md` | Corrections newest first |

## Loop

On owner correction: diagnose process / toolbox / proof → smallest fix → `jarvis_quote_playbook_note` → re-run from broken step → verify again before send.
