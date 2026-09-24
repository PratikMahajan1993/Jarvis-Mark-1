---
description: Stop the Jarvis HUD, API, Hermes gateway, Voicebox, and Ollama
---

Stop the Jarvis desk on this machine. Do not edit product code.

Stop only these listeners, and only when the process command line matches:

| Port | Stop when the command line is |
| --- | --- |
| 3000 | Next.js dev server under `d:\Cursor\Jarvis\frontend` |
| 8000 | `uvicorn app.main:app` from the Jarvis repo |
| 8642 | `hermes_cli.main gateway run` |
| 17493 | `D:\voicebox\voicebox-server.exe` |
| 11434 | `ollama.exe serve` or the Ollama tray app that owns it |

Kill the process tree for each match. Do not kill unrelated Node, Python, or Cursor processes.

Wait a moment, then check those five ports. Report which processes you stopped and any port that is still listening.
