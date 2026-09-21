# Quotation template (outline)

Fill from owner-confirmed scope, strategy, and `jarvis_quote_build` rows — not from model-invented prices.

1. **Header** — Quotation title, date, customer, part name / revision, drawing filename.
2. **Scope** — Labour-only **or** with material (who supplies RM). One line.
3. **Material & RM** — Grade if with material; supplier quote or marked estimate with source note if used.
4. **Machining** — Operations summary, machine(s), MHR-based machining lines where applicable.
5. **Outsource** — Separate lines per outsourced operation; note reason (capacity, process, customer request, no machine).
6. **Line items table** — Item, material/qty, unit price, notes (from spreadsheet artifact).
7. **Total** — Grand total (matches email bold total).
8. **Terms** — Shop terms if owner provided; otherwise omit.
9. **Send** — Proof via `jarvis_quote_verify`; queue email via Authorize only.
