---
name: "source-command-start-jarvis"
description: "Start the Jarvis HUD, API, Hermes gateway, and Ollama"
---

# source-command-start-jarvis

Use this skill when the user asks to run the migrated source command `start-jarvis`.

## Command Template

Do not inspect what is already running. Do not read other files. Do not edit product code.

Immediately run this one command from `d:\Codex\Jarvis`:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-jarvis.ps1`

The script restarts the API, the HUD, the Hermes gateway, and Ollama. If one of them is already up, the script stops that listener and starts it again. Do not start Voicebox.

When the script prints its line, tell the user to open http://localhost:3000. Do not probe ports or health unless the script exits with an error.
