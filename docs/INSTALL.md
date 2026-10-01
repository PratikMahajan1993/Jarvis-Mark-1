# Local setup

Run commands from this checkout. Python and Node.js must be installed; use backend/requirements.txt and frontend/package.json for dependencies.

## Install

Create .env from .env.example if absent. Preserve an existing environment file.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
cd frontend
npm install
```

On Linux/macOS, use .venv/bin/python instead of .venv\Scripts\python.exe. Run the same pip installation and frontend npm installation; there is no separate environment bootstrap requirement.

## Start this checkout

API, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend, in another terminal:

```powershell
cd frontend
npm run dev
```

Frontend: http://127.0.0.1:3000. API: http://127.0.0.1:8000/api/health.

Do not start duplicate listeners. scripts/start-jarvis.ps1 contains a different checkout path and restarts services; it is not the startup command for this worktree.

## Integrations

Hermes is configured by HERMES_ENABLED, HERMES_GATEWAY_URL, and HERMES_API_KEY in local configuration. Its usual gateway port is 8642. Install and configure Hermes separately; API startup installs the application's shop playbooks.

Ollama normally serves on port 11434; OLLAMA_HOST and OLLAMA_MODEL configure it. Gemini uses GEMINI_API_KEY. backend/app/config.py contains current model and speech defaults. Speech is served through POST /api/tts and played by the browser. Exhausted speech quota leaves the reply available as text.

Google integrations use GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, or GOOGLE_CLIENT_JSON. Enable the APIs needed for Gmail, Drive, Calendar, and Sheets in your Google project. The local redirect is http://127.0.0.1:8000/api/google/callback. Connect the account from the app's preferences. A second staff account has a separate connection and token.

A disconnected Google account uses the configured demo paths where supported; do not mistake demo content for a connected account.

## Data and moving machines

backend/app/config.py resolves relative DATA_DIR and EXPORTS_DIR against this repository. Defaults are data/ and exports/. Preserve the database, local memory, Hermes session map, local drawings, and required OAuth tokens when moving an installation. Transfer secrets and customer data securely, outside Git.

Virtual environments and node_modules are machine-specific: recreate them on the destination rather than copying them. Never overwrite another installation's data during setup.

## Verification

Check /api/health and the frontend in a browser. Select checks appropriate to the task:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live_service"
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

Live-service checks require their actual services. Physical microphone, speaker, and GPU checks require the desk machine. See [behavioral verification](../work/CAPABILITY_TEST_MATRIX.md).

For connection failures, check service listeners, configured URLs, account connection status, and provider quota. Do not print configuration secrets into logs.
