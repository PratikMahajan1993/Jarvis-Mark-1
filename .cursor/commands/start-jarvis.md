---
description: Start the Jarvis HUD, API, Hermes gateway, and Ollama
---

Run this from the repository root of the checkout you are in:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-jarvis.ps1`

If that script points at a different checkout, start the API and the HUD for this checkout instead. See `docs/INSTALL.md`. Do not start a second listener on a port that is already serving this app.

When the app is up, tell the user to open http://localhost:3000. If startup fails, read the error and check the ports.
