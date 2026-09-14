# Overview

Local-first work HUD. Tony speaks or types; Jarvis answers on a fullscreen board.

- **You:** Tony
- **Google:** `pgeneration.mech@gmail.com`
- **HUD:** http://localhost:3000 (`frontend/`)
- **API:** http://localhost:8000 (`backend/`)
- **DB:** `backend/data/jarvis.db`

Run: uvicorn with `--reload` from repo root on 8000; `npm run dev` in `frontend/` on 3000.

Secrets stay in `.env`. Never commit `.env`, `google_token.json`, or the database.

Longer as-built: [docs/AS_BUILT.md](../docs/AS_BUILT.md). Runbook: [README.md](../README.md).

Tony’s working notes: [workbook.md](workbook.md).
