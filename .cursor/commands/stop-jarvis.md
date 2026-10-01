---
description: Stop the Jarvis HUD, API, Hermes gateway, and Ollama
---

Stop the Jarvis desk for this checkout. Do not stop unrelated Node, Python, or Cursor processes.

Stop a listener only when its command line belongs to this app:

| Port | Typical process |
| --- | --- |
| 3000 | Next.js dev server for this checkout |
| 8000 | `uvicorn app.main:app` for this checkout |
| 8642 | Hermes gateway |
| 11434 | Ollama, if this checkout started it |

Report which processes you stopped and any of those ports that are still listening.
