# Rate rules

## Authorized sources

- Owner-stated numbers in chat or spreadsheet edits
- Output rows from `jarvis_quote_build` / local quotation artifact
- Bound shop sheet via `jarvis_read_shop_sheet` when owner explicitly binds rates there
- **RM supplier quote** when scope is with material — record amount and supplier; pass `rm_price`, `rm_source`, and notes into `quote_build`
- **RM estimate** (only before send if supplier quote not in yet): historical shop transactions or market trend — must set `rm_source: estimate` and non-empty `rm_source_note` naming that source
- **Machining**: hours × rate from Machine Hour Rate; rate must respect **minimum** in `mhr-demo.md` for that machine type (DEMO floors)
- **Outsource**: line item only after owner or vendor provides a number — never model-invented

## Never from

- Model guessing unit prices, MHR, margins, material, or outsource
- Web search without owner confirmation
- Reusing an old quote unless owner says to reuse that job
- Gmail thumbnail URLs or unspecified paths

## Scope

- **Labour-only**: no raw-material purchase line on the quote; do not charge material on labour-only customers.
- **With material**: RM cost line required before send (supplier quote or marked estimate with source).

Empty or TBD unit prices fail proof until the owner fills them.
