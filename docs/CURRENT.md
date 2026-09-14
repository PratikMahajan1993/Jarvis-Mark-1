# Jarvis — what works today (2026-09-14)

Short as-built snapshot for a clean replan. Not a roadmap.

## Product shape

- **Jarvis** = HUD + voice + HITL + connectors (Gmail, calendar, shop sheet).
- **Hermes** = cognitive brain (gateway API on `:8642`), preferred over Gemini for open chat.
- **Honcho** = Hermes memory provider (hybrid recall); deepens with Hermes conversations over time.

## Working capabilities

- Orchestrator HUD (Next.js) with voice line, activity, authorize/reject.
- Draft-email compose modal (tight triggers); subject optional / derived from body; Authorize to send via Gmail.
- Hermes warm gateway bridge (OpenAI-compatible `/v1/responses`); ~30s timeout then Gemini/legacy fallback.
- Casual + work chat prefer Hermes when enabled and reachable.
- MCP Jarvis tools for Hermes (HITL queues external writes).
- Shop sheet / snapshot / mail search & read paths from earlier waves (local + Google when connected).

## Deliberate gaps (for the new plan)

- Desktop Hermes sidebar may not list `api_server` sessions created by Jarvis.
- Draft compose still uses Gemini fill, not Hermes.
- Hardcoded intent routing still exists alongside Hermes.
- Honcho profile still early — needs real usage to accumulate.

## Runtime notes

- Start Hermes gateway (login item / `hermes gateway`).
- Jarvis API `:8000`, frontend `:3000`.
- Secrets live in repo `.env` (gitignored) and `%LOCALAPPDATA%\hermes\.env`.
