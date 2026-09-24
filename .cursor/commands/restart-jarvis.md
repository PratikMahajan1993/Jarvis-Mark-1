---
description: Restart the Jarvis HUD, API, Hermes gateway, Voicebox, and Ollama
---

Restart the Jarvis desk. Do not edit product code.

Follow `.cursor/commands/stop-jarvis.md`, then `.cursor/commands/start-jarvis.md`.

Do not start a second copy of a service that is still listening. After the restart, report what was stopped, what came back, and the check results for `http://localhost:3000` and `http://127.0.0.1:8000/api/health`.
