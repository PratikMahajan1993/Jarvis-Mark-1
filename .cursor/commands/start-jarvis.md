---
description: Start the Jarvis HUD, API, Hermes gateway, and Ollama
---

Start the Jarvis desk on this machine. Do not edit product code.

Check listeners first. If a service below is already listening, leave it running and say so. Never start a second copy.

From `d:\Cursor\Jarvis`, start anything that is down:

1. API on `127.0.0.1:8000`
   `D:\Cursor\Jarvis\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`
2. HUD on port `3000`, working directory `d:\Cursor\Jarvis\frontend`
   `npm run dev`
3. Hermes gateway on `127.0.0.1:8642`
   `hermes gateway run`
   If `hermes` is not on PATH, use the Hermes runtime:
   `C:\Users\asus\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe -m hermes_cli.main gateway run`
4. Ollama on port `11434`
   `ollama serve`

Do not start Voicebox. Speech is Gemini TTS (Charon) through the API.

Run each missing server in the background. Then confirm:

- `http://127.0.0.1:3000` returns HTML
- `http://127.0.0.1:8000/api/health` returns 200
- `http://127.0.0.1:8642/health` returns 200
- `/api/health` includes a `tts` block naming Charon

Report which processes you started, which were already up, and any that failed to come up. The app the user opens is `http://localhost:3000`. Port 8000 is the API only.
