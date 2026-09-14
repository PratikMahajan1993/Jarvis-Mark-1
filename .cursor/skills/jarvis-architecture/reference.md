# Jarvis architecture reference

## Ports

| Service | URL |
| ------- | --- |
| HUD | http://127.0.0.1:3000 |
| API | http://127.0.0.1:8000 |
| Hermes gateway | http://127.0.0.1:8642 |
| Voicebox | http://127.0.0.1:17493 |

Bind API with `--host 127.0.0.1` when possible. A second process on `0.0.0.0:8000` causes confusing dual listeners.

## TTS bridge (frontend)

File: `frontend/src/lib/voice.ts`

1. `speak(text)` starts `/api/tts` fetch and a 160ms browser-TTS bridge.
2. If Voicebox blob arrives before ~1.4s after bridge start → cancel browser, play Mark.
3. If later → **do not play** Voicebox; browser already owns the line (cache still warms).
4. Never play inside fetch before the late-cutover check (causes ~15s double speak).

Backend: `prefetch_tts` on chat/confirm; disk cache under `backend/data/tts_cache/`.

## Mail / snapshot fast path

Kinds in `SNAPSHOT_KINDS` (briefing, mail_search, mail_read, calendar_list) use local DB/tools when ready instead of waiting on Hermes. Empty attachment-only mail must still speak a useful line (not “Mail is on the board.” alone).

## Desk model

- Ambient session = everyday desk
- Discussions / jobs = named conversations in Open notes
- Suggested RFQ “engineering” opens/resumes a job workflow note
- Weather is **outside** the scrollable tasks list (`WeatherCard` + `shrink-0`)

## React Bits inventory

See skill `jarvis-react-bits` / `catalog.md`.

## Capability tests

`work/CAPABILITY_TEST_MATRIX.md` — run order and log template. Parent chat dispatches specialists on observations.
