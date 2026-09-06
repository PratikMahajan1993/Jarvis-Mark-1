# Jarvis

Local work assistant. You speak or type; the app owns voice, tools, HUD, and confirmations. Ollama is the brain for ordinary chat only. Work paths (mail, files, briefing) use heuristics + tools so `llama3.2:1b` cannot hang them.

- **HUD:** [http://localhost:3000](http://localhost:3000) (Next.js + Tailwind)
- **API:** [http://localhost:8000](http://localhost:8000) (FastAPI + SQLite). Bind `0.0.0.0:8000` to match `.env.example`; the HUD still calls `http://localhost:8000`
- **Brain:** Ollama, default `OLLAMA_MODEL=llama3.2:1b`

## Requirements

- Python 3.11+, Node 20+, [Ollama](https://ollama.com) running locally
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

### Connect Gmail (optional, live mail + Drive + Gemini handoff)

1. In Google Cloud, create OAuth credentials for `pgeneration.mech@gmail.com` (or your account). Scopes: `gmail.send`, `gmail.readonly`, `drive.file`.
2. Register redirect URI: `http://127.0.0.1:8000/api/google/callback`
3. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` (or `GOOGLE_CLIENT_JSON`).
4. Run API + HUD. Open preferences → **Connect Gmail** (links to `GET /api/google/auth`). After consent, callback lands at `/?gmail=1`. Token: `backend/data/google_token.json`.

Without OAuth, mail send/read stay on the local demo mailbox.

## Run

Two terminals.

```powershell
# API  (host 0.0.0.0 matches JARVIS_HOST; 127.0.0.1 also works)
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000
```

```powershell
# HUD
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Click the orb, hold Space, type, or say **Jarvis** / **Hey Jarvis**.

If the model is offline, work tools still run. Ordinary chat will not improvise.

## Try

- “Brief me.”
- “What’s in Priya’s mail?”
- “Please reply to her.”
- “Make a spreadsheet.” then “Open the spreadsheet.”
- “Ask Gemini to summarize the pricing sheet.” (needs Connect Gmail; confirms **Shall I send**)
- Wake: “Jarvis, brief me.”
- After **Shall I?** — speak yes/no or press **Y** / **N**

## Safety and connectors

- Drafts are free. **Send**, **Task for Gemini**, and **calendar writes** need Shall I (Yes/No).
- Files write only under `backend/exports`.
- **Mail:** local demo by default. Live Gmail when OAuth connected (send as `GOOGLE_ACCOUNT`). Failed live send speaks “Gmail did not take it.” Optional IMAP read if `EMAIL_BACKEND=imap` and `IMAP_*` set (read only, no SMTP).
- **Drive / Gemini:** need Connect Gmail. Gemini tasks email `GEMINI_TASK_TO` (defaults to same account).
- `TAVILY_API_KEY` or `BRAVE_API_KEY` for cloud research; otherwise DuckDuckGo.

See [docs/AS_BUILT.md](docs/AS_BUILT.md) for what is real versus demo.
