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

- `docs/CURRENT.md` — as-built quote bullets
- Playbook source: `backend/app/hermes/playbooks/quote/SKILL.md` (skill name **shop-quote**)
- Cursor architecture: `jarvis-architecture` skill + `reference.md` quote table

## Where things live

| What | Path |
| ---- | ---- |
| Playbook source (repo) | `backend/app/hermes/playbooks/quote/` — `SKILL.md`, `notes.md`, `files/`, `examples/` |
| Installed copy | `{hermes home}/skills/shop/quote` — `HERMES_HOME` env or `~/.hermes`; copied by `ensure_playbooks_installed()` in `hermes/bridge.py` on API startup |
| Tool logic | `backend/app/quote.py`, `backend/app/tools/registry.py` |
| MCP surface | `backend/app/hermes/mcp_server.py` — `jarvis_quote_*` |
| Start routing | `backend/app/intent.py` — `is_quote_start()` |
| Hermes + fallback | `backend/app/agent.py` — `_hermes_reply`; on error/timeout (`hermes_timeout_sec`, default 30) speaks locally: *“Which drawing should I quote — an inbox attachment, a file on the desk, or a photo?”* |
| Router | `backend/app/semantic_router.py` — quote start → `tool_ops`, `DAT.03` (even if “drawing” would be vision) |
| Tests | `backend/tests/test_quote_playbook.py`, `test_semantic_router.py` |
| DEMO MHR table | `files/mhr-demo.md` — **demo floors only**, not shop truth |

Session data: SQLite `data/jarvis.db` — `messages`, `memories` (quote facts), `pending_actions` (HITL). Hermes thread ids: `data/hermes_sessions.json`. Playbook files are **not** the chat log.

## MCP / registry tools

- `jarvis_quote_analyze_drawing` — after a path exists; vision helper, not step 1
- `jarvis_quote_build` — optional `scope`, `rm_source`, `rm_source_note`, `rm_price`, `machine`, `machining_rate`
- `jarvis_quote_pdf`
- `jarvis_quote_verify` — proof before send
- `jarvis_quote_send` — queues **Authorize** only; refuses when verify `stop: true`
- `jarvis_quote_playbook_note` — owner corrections → `notes.md`

Brain must **not** invent raw material prices, MHR floors, or outsource numbers. Never underquote.

## Real order (after drawing path exists)

1. Labour-only vs buy raw material (customer default; mail/verbal overrides; else ask).
2. Supplier quote or labeled estimate from history/market trend.
3. Strategy (ops, outsource, machines, tooling).
4. Machining cost at or above minimum MHR for chosen machine.
5. Short formal quotation email — total in bold, PDF attached; **send waits for Authorize**.

## Proof & send

- Always run `jarvis_quote_verify` before claiming ready to send.
- More than **2** failed checks → `stop: true`; `quote_send` will not queue.
- **1–2** failures may still queue Authorize with warnings.
- Delivery time does **not** block send.

## No drawing path

- Ask where the drawing lives (inbox attachment, desk file, photo).
- **Do not** call `reason_rfq` — that path queues holding email + calendar deadline and assumes the sheet was not seen.
- `is_quote_start` must **not** return the `rfq_reason` intent path.

## Good first turn

1. User says “start quote workflow” (or similar) → router `tool_ops` / DAT.03.
2. Hermes loads **shop-quote** via `skill_view` and follows playbook.
3. If no path yet, ask for drawing location — do not invent a sheet or analyze nothing.

## HUD workspace

- **Talk-jump to Engineering** only when current workspace is **monitor** (`talkJumpWorkspace` in `hudWorkspace.ts`).
- Same quote/drawing words spoken on **Casual** stay on Casual.
- Pending calendar/mail/quote modal on page open = **restored HITL** from `loadSessionSurface`, not a new request.

## Do not

- Add a separate “quote agent” or paste the whole playbook into `SOUL.md` (SOUL points at shop-quote; playbook stays in skills tree).
- Treat `mhr-demo.md` as live shop rates.
- Jump workspace to Engineering from Casual on quote keywords.
- Call `reason_rfq` for quote **starts** without a drawing in focus.
- Commit secrets, `.env`, or customer emails in docs or notes.

## Verify

```text
python -m pytest backend/tests/test_quote_playbook.py backend/tests/test_semantic_router.py -q
```

Live: Hermes `:8642` warm, API `:8000`, say “start quote workflow” — expect Hermes or 30s timeout then the fixed drawing-path question.
