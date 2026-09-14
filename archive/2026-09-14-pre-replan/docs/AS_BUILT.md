# As built

Hybrid: Ollama chats; the app owns voice, tools, HUD, and Shall I. Work asks skip the model (heuristics + tools) so `llama3.2:1b` cannot hang mail or files. Larger Ollama model still parked.

## Surfaces

- HUD: Next.js `http://localhost:3000` → API `http://localhost:8000` (FastAPI + SQLite at `backend/data/jarvis.db`).
- Brain: Gemini (`GEMINI_API_KEY`) when set, else Ollama (`OLLAMA_MODEL=llama3.2:1b`). `LLM_PROVIDER=ollama` forces local. Email “Task for Gemini” is unchanged.
- Prefs: `assistant_name`, `display_name`, timezone; **Connect Gmail** / **Add Calendar** when Google client keys are in `.env`.

## A spoken turn

1. Wake: `Jarvis` / `Hey Jarvis` / prefs name (also “Jarvish”). Name only → “Yes?” then listen. Orb / Space / type also send.
2. `POST /api/chat` → `run_agent`. Pending Shall I + yes/no (or **Y**/**N**) → `POST /api/confirm`.
3. Work phrase → `_heuristic_tools`; model skipped. Tools queue thoughts; HUD drains via `GET /api/thought`.
4. Non-work → Ollama (1–3 sentences). Ollama down + no tool: “The model is still coming online…”

## Familiarity

Per-session `working_set`: person, thread, artifact, **drive** (link + title), client, aliases.

- Pointers: last / that / him / her / the sheet / this morning.
- Named mail: search demo, IMAP, or Gmail inbox.
- Speak layer: first name + facts; full body on the board.

## Presence

- Glance (`GET /api/glance`, 30s): next event line; whisper only after the HUD has restored and been quiet ~20s. Gemini replies are not glance speech.
- Watch (`GET /api/watch`): waiting vs ready vs **seen**. Opening the HUD restores the board silently, then `POST /api/watch/ack` so the last mail is not narrated again. A reply that arrives while the HUD is already open is spoken once, then acked.
- Session (`GET /api/session`): last scene and reply text for the board. `speak` is empty on restore — reopen is not a replay.
- Shall I: on-screen, spoken yes/no, or **Y**/**N** (`classifyDecision`).

## Safety

| Action | Gate |
| --- | --- |
| Read/draft mail, briefing, calendar list, create file, research, Drive upload/find | Free |
| Send mail, Task for Gemini, handoff unreadable file to Gemini, calendar create, clarify | Shall I |

Files only under `backend/exports`. Secrets in `.env`.

## Gmail (OAuth)

Keys: `GOOGLE_CLIENT_ID`/`SECRET` or `GOOGLE_CLIENT_JSON`. Token: `backend/data/google_token.json`. Scopes: `gmail.send`, `gmail.readonly`, `drive.file`, `calendar.events`, `calendar.readonly`. Send as `GOOGLE_ACCOUNT` (default `pgeneration.mech@gmail.com`).

- Connect: prefs → `GET /api/google/auth` → callback `http://127.0.0.1:8000/api/google/callback` → `HUD_URL/?gmail=1`. Register that redirect on the Google OAuth client. Enable Gmail, Drive, and Calendar APIs on the Cloud project.
- Live: `email.py` prefers Gmail when connected; upserts to SQLite. No token → demo mailbox; send = local SENT row.
- Failed live send → “Gmail did not take it.” Status: `GET /api/google/status` (`connected`, `calendar`).
- Existing Gmail tokens keep mail/Drive. Calendar needs a second consent (**Add Calendar**) so the grant includes `calendar.events`.

## Drive

Same OAuth. Upload artifact/inbox/last file; find by title (contains). Link + title on working set. Not connected → “Connect Gmail in preferences first.”

## Calendar

Same OAuth, extra scope `calendar.events`. List/briefing/glance read the primary calendar. Create still Shall I, then Google insert. Gmail connected without Calendar → empty board (no demo mix) plus prefs **Add Calendar**. Failed write → “Calendar did not take it.” Enable the Calendar API on the Cloud project. No token → local seed events.

## Gemini (email handoff)

No Gemini API. Email to `GEMINI_TASK_TO` (defaults to same account). Subject exactly **Task for Gemini**. Body: **File** / **Do this** / **Reply like this**.

- Triggers: “ask Gemini”, “task for Gemini”, “send to Gemini”, “analyze this”, etc.
- `task_for_gemini`: find on Drive or upload the local file, then envelope + Shall I → send + `start_gemini_watch`. File steps without a Drive URL → ask once.
- Unreadable drop (`review_inbox`, under 40 chars): “I cannot read that here. Shall I send it to Gemini?” → `handoff_gemini` (upload + send + watch).
- Watch ready → speak summary + board. Timeout → “Gemini has not replied yet. I stopped watching.”

## Demo data

Seeded if empty; used without Gmail. Priya/Ashutosh/Amit/Billing threads + local calendar events. `EMAIL_BACKEND=local`; optional IMAP read (`EMAIL_BACKEND=imap`). Calendar uses Google primary when `calendar.events` is granted; otherwise the local seed (or an empty board if Gmail is connected but Calendar is not).

Research: Google Custom Search when `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX` are set; else Tavily / Brave / DuckDuckGo. The board is a takeaway plus a note on each site (page text, not a raw link dump).

## Tools

`get_briefing`, mail tools, calendar, `create_spreadsheet`, `show_artifact`/`open_artifact`, documents, `review_inbox`, `drive_upload`, `drive_find`, `task_for_gemini`, `research`. Model-only: `remember`, `update_preferences`.

Local xlsx under exports. “Open the spreadsheet” → `show_artifact` + `os.startfile` (Windows).

## Canvas

Second surface at `http://localhost:3000/canvas`. Manual only: no voice, no agent, no HUD link yet — open the URL directly.

- Board: one CSS transform (`translate` + `scale`). Scroll zooms at the cursor, shift-scroll pans sideways, drag empty space or middle-mouse pans. **0** resets zoom, **1** fits, **N** adds a note, **Delete** removes the selection, **Esc** deselects.
- Items: sticky notes (double-click to write), dropped images, dropped PDFs. A drop lands under the cursor at true aspect ratio; images and PDFs keep their ratio while resizing (hold Alt to override).
- PDFs show a placeholder card — name, page count, page size from `pypdf` — and open in a tab. Page rasterization is not built.
- Storage: `canvas_boards` / `canvas_items` / `canvas_files` in SQLite, uploads under `backend/data/canvas`. Edits save on a 600ms debounce; the board reopens where you left it, camera included.
- API: `GET`/`POST /api/canvas/boards`, `GET`/`PUT /api/canvas/boards/{id}`, `POST /api/canvas/files`, `GET /api/canvas/files/{id}`. Item geometry is columns; kind-specific fields are JSON, so a new item kind needs no migration.
- Seams: `CanvasItem` union in `lib/canvas/types.ts` plus the `ITEM_RENDERERS` registry on the HUD side, `db.add_canvas_item(...)` on the API side.

## Not built

Larger Ollama model, Electron/Tauri, RAG, in-app vision (unreadable → Gemini email), IMAP send, direct Gemini API.

Canvas: PDF page rendering (`pdfjs-dist`), freehand ink and shapes, multi-select, undo/redo, multiple boards, and any voice or agent control of the board.

## Limits

Heuristic draft replies; short gender name list; “same as this morning” disambiguates sheet vs mail; Chrome mic + network STT; Gemini quality/latency via Gmail thread only.
