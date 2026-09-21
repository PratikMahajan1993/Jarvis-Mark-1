# Jarvis

24/7 shop assistant. You speak or type; the app owns voice, tools, HUD, and confirmations. **Hermes** on `http://127.0.0.1:8642` is the primary brain. **Gemini** and **Ollama** are overflow, vision, router, and fallback when Hermes is down or times out. Tools still own mail, files, calendar, and quote numbers — the brain does not invent shop facts.

- **HUD:** [http://127.0.0.1:3000](http://127.0.0.1:3000) (Next.js + Tailwind)
- **API:** [http://127.0.0.1:8000](http://127.0.0.1:8000) (FastAPI + SQLite). Prefer `--host 127.0.0.1` — binding `0.0.0.0:8000` can leave a second ghost listener alongside an existing process.
- **Brain:** Hermes gateway first (`hermes_enabled` defaults on). Gemini when `GEMINI_API_KEY` is set (`LLM_PROVIDER=auto`), otherwise Ollama (`OLLAMA_MODEL`). “Task for Gemini” mail is a separate tool, not the desk brain.

As-built snapshot: [docs/CURRENT.md](docs/CURRENT.md). Cursor agents, skills, and rules: [AGENTS.md](AGENTS.md).

## Requirements

- Python 3.11+, Node 20+, [Ollama](https://ollama.com) for fallback chat
- **Hermes** gateway on `:8642` (primary brain)
- **Voicebox** on `:17493` for Mark TTS (`POST /generate`)
- Chrome for mic / wake word (browser SpeechRecognition)

## Setup

```powershell
cd D:\Cursor\Jarvis
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend
npm install
```

```powershell
ollama pull llama3.2:1b
```

Secrets stay in `.env`. Never commit it.

### Connect Gmail (optional, live mail + Drive + Calendar + Gemini handoff)

1. In Google Cloud, create OAuth credentials for `pgeneration.mech@gmail.com` (or your account). Enable **Gmail**, **Drive**, and **Google Calendar** APIs. Scopes: `gmail.send`, `gmail.readonly`, `drive.file`, `calendar.events`, `calendar.readonly`.
2. Register redirect URI: `http://127.0.0.1:8000/api/google/callback`
3. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` (or `GOOGLE_CLIENT_JSON`).
4. Run API + HUD. Open preferences → **Connect Gmail** (links to `GET /api/google/auth`). After consent, callback lands at `/?gmail=1`. Token: `data/google_token.json` (repo root — `DATA_DIR` resolves against the repo, not `backend/`).
5. If Gmail was connected before Calendar existed, open preferences → **Add Calendar** and consent again. Until then, briefing will not mix in the demo standup.

Without OAuth, mail and calendar stay on the local demo store.

## Run

Start **Hermes gateway** and **Voicebox** on the desk, then two terminals for Jarvis.

```powershell
# API  (prefer 127.0.0.1 to avoid duplicate listeners)
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
# HUD
cd frontend
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Click the orb, hold Space, type, or say **Jarvis** / **Hey Jarvis**.

Quick health: Hermes `http://127.0.0.1:8642`, Voicebox `http://127.0.0.1:17493`, API `GET /api/health`.

### Use from another machine

Bind the API to all interfaces (`--host 0.0.0.0`) only when you need LAN access. On the other device open `http://<this-pc-ip>:3000`. Connect Gmail still on this PC — the OAuth redirect is `http://127.0.0.1:8000/api/google/callback`.

If Hermes and the fallback model are offline, work tools still run where configured. Ordinary chat will not improvise shop numbers.

## Try

- “Brief me.”
- “What's on the calendar?”
- “What's in Priya's mail?”
- “Please reply to her.”
- “Make a spreadsheet.” then “Open the spreadsheet.”
- “Start quote workflow.” (Hermes + shop-quote playbook; drawing path first)
- “Ask Gemini to summarize the pricing sheet.” (needs Connect Gmail; confirms **Authorize**)
- Wake: “Jarvis, brief me.”
- After **Authorize / Reject** — speak yes/no or use the desk buttons (calendar and send paths restore on reload via pending actions)

## Safety and connectors

- Drafts are free. **Send**, **Task for Gemini**, **calendar writes**, and **quote send** need **Authorize / Reject** on the desk.
- Files write only under `exports/` (repo root — `EXPORTS_DIR` resolves against the repo, not `backend/`).
- **Mail:** local demo by default. Live Gmail when OAuth connected (send as `GOOGLE_ACCOUNT`). Failed live send speaks “Gmail did not take it.” Optional IMAP read if `EMAIL_BACKEND=imap` and `IMAP_*` set (read only, no SMTP).
- **Calendar:** local demo when Google is not connected. Live primary calendar when the grant includes `calendar.events` (prefs → **Add Calendar** if Gmail is already connected). Create event still needs Authorize. Failed write speaks “Calendar did not take it.”
- **Drive / Gemini:** need Connect Gmail. A file ask finds the Drive copy or uploads the local one, then Authorize sends **Task for Gemini**. Gemini tasks email `GEMINI_TASK_TO` (defaults to same account).
- `TAVILY_API_KEY` or `BRAVE_API_KEY` for cloud research; otherwise DuckDuckGo.

See [docs/CURRENT.md](docs/CURRENT.md) for what works today. **New machine or migration:** [docs/INSTALL.md](docs/INSTALL.md). Capability tests: [work/CAPABILITY_TEST_MATRIX.md](work/CAPABILITY_TEST_MATRIX.md). Cursor agents/skills/rules: [AGENTS.md](AGENTS.md).
