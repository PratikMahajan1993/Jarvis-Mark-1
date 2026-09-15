# Jarvis — install & desk setup

Guide for a **fresh machine** or **migrating from another PC**. For what works today, see [`CURRENT.md`](CURRENT.md). For capability testing, see [`../work/CAPABILITY_TEST_MATRIX.md`](../work/CAPABILITY_TEST_MATRIX.md).

---

## 1. Overview — minimum vs full desk

| Tier | You run | You get |
| ---- | ------- | ------- |
| **Minimum** | Python venv + API `:8000`, Next.js HUD `:3000`, `.env` | Demo mail/calendar, local memory/RAG, HITL, browser TTS fallback |
| **Brain desk** | Minimum + **Gemini API key** *or* **Ollama** | Chat, tools, semantic router, compose fill |
| **Full owner desk** | Brain + **Hermes** `:8642` + **Voicebox** `:17493` + **Google OAuth** + **Chrome** | Live mail/calendar, Mark voice, Hermes-first chat, office-day RFQ cards, mic/HITL |

**Degraded modes:** Hermes down → Gemini/Ollama fallback. Voicebox down → browser TTS. No Google token → demo mailbox/calendar (seeded on startup).

Capability matrix tags: **offline/cloud** = minimum OK; **desk** = needs Hermes, Voicebox, Google, GPU Ollama, or physical mic.

---

## 2. Requirements

| Tool | Version | Notes |
| ---- | ------- | ----- |
| Python | 3.11+ (3.12 recommended) | venv required |
| Node.js | 20+ (22 in CI) | for HUD |
| Git | any | clone repo |
| Chrome | recent | mic / wake word |
| Ollama | optional | if no `GEMINI_API_KEY` — [ollama.com](https://ollama.com) |
| Hermes CLI | optional | full desk — install separately; not in `requirements.txt` |
| Voicebox | optional | full desk — [voicebox.sh](https://voicebox.sh/) desktop app |

**Primary platform:** Windows (PowerShell commands below). macOS/Linux: use `source .venv/bin/activate` and `.venv/bin/uvicorn`; Hermes config path differs from Windows `%LOCALAPPDATA%\hermes\.env`.

---

## 3. Quick start (minimum — demo mode)

From repo root:

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

If no Gemini key:

```powershell
ollama pull llama3.2:1b
```

**Terminal 1 — API** (prefer `127.0.0.1` locally):

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

**Terminal 2 — HUD:**

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:3000**. Try “Brief me.” (demo data without OAuth).

Data dirs `<repo>/data/` and `<repo>/exports/` are created on first API start.

---

## 4. Full desk setup

### 4a. Brain — Gemini or Ollama

In `.env`:

- **Gemini:** set `GEMINI_API_KEY`. `LLM_PROVIDER=auto` picks Gemini when key is set.
- **Ollama:** leave key empty; ensure `ollama serve` and `OLLAMA_MODEL=llama3.2:1b`.

### 4b. Hermes gateway (`:8642`)

1. Install the **hermes** CLI (vendor docs).
2. In Hermes config (Windows: `%LOCALAPPDATA%\hermes\.env`), set:
   - `API_SERVER_ENABLED=true`
   - `API_SERVER_KEY=` same value as Jarvis `HERMES_API_KEY` in `.env`
3. Start gateway: `hermes gateway run` (or login item / service).
4. Jarvis `.env`: `HERMES_ENABLED=true`, `HERMES_GATEWAY_URL=http://127.0.0.1:8642`, `HERMES_PREFER_GATEWAY=true`.
5. On API startup, Jarvis registers MCP (`backend/app/hermes/mcp_server.py`) in the background. Verify: `hermes mcp list`.

### 4c. Voicebox (`:17493`)

1. Install and run Voicebox desktop app.
2. Ensure profile **Mark** exists (`GET http://127.0.0.1:17493/profiles`).
3. Jarvis `.env`: `VOICEBOX_ENABLED=true`, `VOICEBOX_URL=http://127.0.0.1:17493`, `VOICEBOX_PROFILE=Mark`.
4. Jarvis calls **`POST /generate`** only (never `/speak`). TTS cache: `data/tts_cache/`.

### 4d. Google OAuth (live mail / calendar / Drive / sheets)

1. Google Cloud: create a **dedicated** OAuth client for Jarvis (do not reuse a YouTube/other app client — mixed historical scopes break consent). Enable Gmail, Drive, Calendar, Sheets APIs.
2. Redirect URI: `http://127.0.0.1:8000/api/google/callback`
3. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (or `GOOGLE_CLIENT_JSON`) in `.env`.
4. Run API + HUD → Preferences → **Connect Gmail** (must complete on the desk machine).
5. Token saved to `data/google_token.json` (never commit).
6. If Gmail was connected before Calendar scope existed → **Add Calendar** and re-consent.

### 4e. Optional research keys

`GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX`, or `TAVILY_API_KEY`, or `BRAVE_API_KEY`. DuckDuckGo works without keys.

---

## 5. Migrating from another machine

**Copy (secure transfer, never git):**

| Path | When to copy |
| ---- | ------------ |
| `.env` | Always — edit URLs if machine differs |
| `data/jarvis.db` | Keep conversations, mail state, jobs |
| `data/google_token.json` | Same OAuth client ID on new machine |
| `data/memory/` | Keep RAG recall |
| `data/hermes_sessions.json` | Keep Hermes thread map |
| `data/canvas/`, `data/inbox/`, `exports/` | If you use them |
| `frontend/.env.local` | LAN setups only (`NEXT_PUBLIC_API_URL`) |

**Regenerate on new machine:** `.venv/`, `node_modules/`, `.next/`, `data/tts_cache/` (optional).

**Clean install:** omit `jarvis.db` and `google_token.json` — API seeds demo mail/calendar; re-run Connect Gmail.

---

## 6. LAN / second device

1. API: `--host 0.0.0.0 --port 8000`
2. Other device: `http://<desk-ip>:3000` (may need `next dev --hostname 0.0.0.0`)
3. `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://<desk-ip>:8000`
4. Windows Firewall: allow inbound **3000** and **8000** on Private network
5. **Connect Gmail** must run on the desk PC (`127.0.0.1` redirect)

Avoid duplicate listeners on `:8000` (`0.0.0.0` + `127.0.0.1` together causes confusion).

---

## 7. Ports & services

| Port | Service | Exposed to LAN? |
| ---- | ------- | --------------- |
| 3000 | Next.js HUD | Optional |
| 8000 | FastAPI | Optional |
| 8642 | Hermes gateway | No — localhost only |
| 17493 | Voicebox | No — localhost only |
| 11434 | Ollama | No — localhost only |

---

## 8. Verify installation

**Minimum (after API + HUD up):**

```powershell
curl http://127.0.0.1:8000/api/health
.\.venv\Scripts\python -m pytest -m "not live_service" -q
cd frontend
npm run typecheck
npm run lint
```

**Full desk:**

```powershell
curl http://127.0.0.1:8642/health
curl http://127.0.0.1:17493/profiles
curl http://127.0.0.1:8000/api/google/status
hermes mcp list
```

**Expected:** `/api/health` → `"ok": true` when brain (Gemini/Ollama/Hermes) is ready. Voicebox and Google may be `false` on minimum install without breaking core chat.

**Smoke HUD:** http://127.0.0.1:3000 → “Brief me.”

---

## 9. Troubleshooting

| Symptom | Check |
| ------- | ----- |
| Duplicate `:8000` | `netstat -ano \| findstr :8000` — kill extra uvicorn |
| Hermes timeouts | Gateway running? `HERMES_API_KEY` matches Hermes `.env`? |
| No Mark voice | Voicebox app running? Profile **Mark** exists? |
| Gmail not connected | `data/google_token.json` missing or expired → Connect Gmail |
| HUD calls wrong API | `frontend/.env.local` `NEXT_PUBLIC_API_URL` |
| Mail is demo only | Google OAuth not connected — expected on fresh install |

---

## 10. Development / CI

```powershell
pip install -r backend\requirements-dev.txt
python -m pytest -m "not live_service"
```

See [`backend/tests/README.md`](../backend/tests/README.md). Cloud CI runs the same offline suite + frontend typecheck/lint (`.github/workflows/ci.yml`).

---

*Agent roster and test-run protocol: [`AGENTS.md`](../AGENTS.md). Linux cloud bootstrap: [`.cursor/install.sh`](../.cursor/install.sh).*
