---
name: jarvis-quote-playbook
description: >
  Run or debug the shop quote / RFQ workflow: shop-quote Hermes skill, jarvis_quote_* MCP
  tools, quote_verify proof, Engineering workspace, is_quote_start routing, and Hermes timeout
  fallback. Use when fixing quote send, drawing path, MHR floors, or playbook install.
---

# Shop quote playbook (shop-quote)

24/7 assistant delegates quoting through **one Hermes brain** and **Jarvis MCP tools** — not a new specialist agent. Orchestra code **DAT.03** on the HUD is a label only.

## Read first

- `docs/SYSTEM_TRUTH.md` — §3 HITL, §4 Quote Workflow (locked rules, MHR floor, proof, override gates)
- `.cursor/rules/domain/30-quote-playbook.mdc` — break-if-wrong constraints
- Playbook source: `backend/app/hermes/playbooks/quote/SKILL.md` (skill name **shop-quote**)
- Cursor architecture: `jarvis-architecture` skill

## Debug procedure

1. Run the offline tests first — do not start with the live desk:
   ```
   python -m pytest backend/tests/test_quote_playbook.py backend/tests/test_semantic_router.py -q
   ```
2. If a live repro is needed: API `:8000`, Hermes `:8642` warm. Say "start quote workflow" and watch for either Hermes output or the 30 s timeout fallback line: *"Which drawing — inbox attachment, file on desk, or photo?"*
3. Check `work/LAST_TURNS.md` (or `GET /api/turns/recent`) for the last ≤ 20 exchanges before judging speak/board/pending.

## Common failure shapes

- **Hermes timeout → fallback fires.** Check Hermes is up (`GET :8642/health`); do not raise the timeout without measuring.
- **`stop: true` on verify.** Read the BLOCKER list off the verify response. Do not paper over it in `quote.py`.
- **`quote_send` queues but never sends.** Expected — HITL requires a manual Authorize. A queued card with `stop: false` is the *correct* end state of a tool call.
- **No drawing path.** Do **not** call `reason_rfq` from a quote start. The fallback line is the right end state.
- **Demo rates treated as live.** With `masterdata_enabled` on, floors come from `machine_hour_rates`, not `files/mhr-demo.md`. An unattested seed value is a BLOCKER, not a fallback.

## Do not

- Add a separate "quote agent" or paste the whole playbook into `SOUL.md`.
- Call `reason_rfq` for quote **starts** without a drawing in focus.
- Commit secrets, `.env`, or customer emails in docs or notes.
- Invent raw-material prices, MHR floors, or outsource numbers in the brain.

## Verify

Offline pytest above. Live: warm Hermes, API :8000, say "start quote workflow" — expect Hermes or the 30 s timeout then the fixed drawing-path question.
