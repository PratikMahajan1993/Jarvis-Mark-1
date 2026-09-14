# Quote skill (curated — foundation Phase 2)

When the user asks to quote a machined component from a drawing / RFQ:

1. Confirm which drawing (filename / revision).
2. If dimensions are unclear, call Gemini vision via Jarvis tools / conversation path — do not invent sizes.
3. Ask for material grade if missing.
4. Call Jarvis quote tools (`quote_build` / sheet bind) to populate a live quotation sheet.
5. After human edits/approval, create PDF and `jarvis_draft_email` with the PDF attached.
6. Never claim the quote was emailed until Authorize.

Prefer Jarvis MCP tools over free-form guesses. Accuracy over speed for money figures.
