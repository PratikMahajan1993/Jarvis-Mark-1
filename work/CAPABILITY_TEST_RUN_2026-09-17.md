# Jarvis capability-test run log — 2026-09-17

**Purpose:** Hand-written **verdict** log — fill this when a case is done and the owner is satisfied (or we record a fail). Do not auto-append HUD noise here.  
**Live auto recorder (separate file):** `work/LIVE_TEST.md` + `data/live_test.jsonl` — written by the app while you test. Coordinator reads that for “what just happened,” then copies a verdict into this file.  
**Matrix:** [`CAPABILITY_TEST_MATRIX.md`](CAPABILITY_TEST_MATRIX.md) (IDs and targets).  
**Also pull:** `work/LAST_TURNS.md`, `GET /api/turns/recent`, `GET /api/health`, `GET /api/metrics`.  
**Do not mark pass** if Authorize was skipped on an external write.

How to fill: copy **Blank case template** → paste under **Case writeups** → fill every field. Use `n/a` when a field does not apply; use `unknown` when it applies but was not observed. Never leave a relevant field blank.

---

## 1. Run identity

| Field | Value |
| --- | --- |
| Run id | `2026-09-17-workspace-pass` |
| Local date | 2026-09-17 |
| Timezone | Asia/Kolkata (UTC+5:30) |
| Started (local) | 2026-09-17 ~00:48 IST |
| Started (UTC) | 2026-09-16 ~19:18 UTC |
| Tester | desk owner (live HUD) |
| Coordinator | this Cursor chat (capability-test coordinator) |
| Git branch | `main` |
| HEAD | `6967891` — Add bulk mail sync, Google connect UI, and full 2-day hot snapshot |
| Working tree | dirty (workspace HUD overhaul uncommitted: OrchestratorShell, MonitorDesk, EngineeringDesk, hudMorph, etc.) |
| Matrix revision | 2026-09-17 three-workspace + staged morph |
| Pass theme | Casual \| Monitor \| Engineering in one `OrchestratorShell`; staged morph; Monitor Evil Eye (no shards, still suns); Engineering bench; Authorize/Reject |
| Retired this pass | P16 (Aero Shards on Monitor), P17 (revolving orbs), M1 (`/canvas` as primary desk) |

### Runtime endpoints

| Service | URL | I3 snapshot |
| --- | --- | --- |
| HUD | http://127.0.0.1:3000 | HTTP 200 |
| API | http://127.0.0.1:8000 | `/api/health` HTTP 200, `ok: true` |
| Hermes gateway | http://127.0.0.1:8642 | API `hermes.gateway: true` (bare `/` → 404, expected) |
| Voicebox | http://127.0.0.1:17493 | HTTP 200; API `available: true`, profile `Mark` |
| Turns | http://127.0.0.1:8000/api/turns/recent | last write 2026-09-16 11:10:02 +0000 (6 turns; **stale vs this pass**) |
| Metrics | http://127.0.0.1:8000/api/metrics | hermes casual n=3, p50 9618ms (prior evening, not this pass) |

### Latency targets (lock)

| Class | Target | Fail if |
| --- | --- | --- |
| HUD idle / bootstrap | < ~2s | Long blank/black before usable chrome |
| Casual chat (warm) | ≤ ~5s | Warm greeting much slower without tool work |
| Simple tools | ≤ ~15s | Mail/calendar/snapshot path hangs |
| Voicebox cutover | ≤ ~1.4s then Mark | Late clip replay after bridge owns the line |
| Morph presence | ~1.2s same-center crossfade | Black gap; hard cut (unless reduced-motion) |
| Morph theme | after presence (~1.3s) | Warm tokens before eye/orb/bench is in |
| Morph chrome | last (~2.4s) | Rails/weather/findings/suns arrive with presence |

---

## 2. Environment snapshot (I3, 2026-09-17 ~00:53 IST)

Pulled live. Re-snapshot if a case fails in a way that could be env (Hermes down, Google disconnected, Voicebox cold).

### `/api/health` (verbatim)

```json
{
  "ok": true,
  "gemini": true,
  "model": "gemini-3.6-flash",
  "models": [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-image",
    "gemini-3-flash-preview"
  ],
  "model_ready": true,
  "provider": "gemini",
  "ollama": false,
  "google": {
    "configured": true,
    "connected": true,
    "calendar": true,
    "calendar_list": true,
    "sheets": true,
    "account": "pgeneration.mech@gmail.com",
    "task_to": "pgeneration.mech@gmail.com"
  },
  "hermes": {
    "enabled": true,
    "available": true,
    "bin": "hermes",
    "gateway_url": "http://127.0.0.1:8642",
    "gateway": true,
    "cli": true,
    "prefer_gateway": true,
    "transport": "gateway"
  },
  "voicebox": {
    "enabled": true,
    "available": true,
    "url": "http://127.0.0.1:17493",
    "profile": "Mark",
    "cached_clips": 0
  }
}
```

### Derived env flags

| Flag | Value | Implication |
| --- | --- | --- |
| Brain provider | gemini (`gemini-3.6-flash`) | Overflow/vision/delegate path live |
| Ollama | false | No local GPU Ollama this run |
| Hermes transport | gateway | A8+ should not fall to CLI unless gateway dies |
| Hermes CLI also | true | Fallback possible |
| Google OAuth | connected | Mail/calendar/sheets cases are in play |
| Sheets API | true | F-section not blocked by “API disabled” |
| Voicebox clips cached | 0 | First speaks may pay cold TTS; K2/K4 relevant |
| LAST_TURNS freshness | 2026-09-16 11:10Z | **No turns yet this pass** until first chat/confirm |

### `/api/metrics` (pre-pass, leftover from 2026-09-16)

| Field | Value |
| --- | --- |
| hermes.casual.count | 3 |
| hermes.casual.p50_ms | 9618 |
| hermes.casual.p95_ms | 9618 |
| hermes.casual.mean_ms | 9670 |
| Recent samples | 9618 ok, 9029 ok, 11757 **ok:false**, 10364 ok — all `session_id=default`, `transport=gateway`, `casual=true` |
| Note | These are **not** this pass. After A1, compare new samples to the ≤~5s warm target (prior p50 already over target). |

### Desk machine

| Field | Value |
| --- | --- |
| OS | Windows 10 (build 26200) |
| Shell | PowerShell |
| Browser | unknown until tester says (expect Chrome/Edge on `:3000`) |
| Viewport | unknown |
| `prefers-reduced-motion` | unknown (assume off until P9) |
| GPU | unknown (P10 eye smoothness is the probe) |

---

## 3. Field dictionary (fill these on every case)

### 3.1 Identity

| Field | What to record |
| --- | --- |
| `id` | Matrix ID (`E1`, `P7`, `A1`, …) |
| `title` | Capability name from matrix |
| `attempt` | 1 = first try; 2+ = retest after fix |
| `result` | `pass` \| `fail` \| `flaky` \| `skipped` \| `retired` \| `blocked` \| `awaiting` |
| `started_local` / `ended_local` | IST timestamps |
| `duration_s` | Wall time of the attempt |
| `tags` | desk / cloud / offline / retired |
| `depends_on` | IDs that must already be green (e.g. P5 needs I3 + P1) |

### 3.2 Setup (HUD before the action)

| Field | What to record |
| --- | --- |
| `workspace_before` | `casual` \| `monitor` \| `engineering` |
| `workspace_after` | same enum |
| `pinned` | true/false |
| `fsm_before` / `fsm_after` | IDLE \| LISTENING \| THINKING \| SPEAKING \| AWAITING_HITL \| EXECUTING |
| `hitl_listening` / `hitl_resolving` | only if AWAITING_HITL |
| `session_id` | usually `default` ambient |
| `conversation_id` | or null ambient |
| `conversation_category` | discussion / drawing / workflow / none |
| `focus_title` | e.g. Everyday desk |
| `open_notes_count` | 0–3 (cap is 3) |
| `dock_hidden` | true/false |
| `prefs_voice` / `prefs_email` | if known |
| `reduced_motion` | true/false |
| `hard_refresh` | true if Ctrl+F5 / cold tab |

### 3.3 Input

| Field | What to record |
| --- | --- |
| `input_channel` | mouse \| keyboard \| Space-mic \| confirm-mic \| HTTP |
| `exact_input` | verbatim utterance, or click path (`Switcher → Monitor`) |
| `talk_jump_expected` | null \| casual \| engineering (from Monitor only) |
| `authorize_required` | true if external write |

### 3.4 Timing (ms; `unknown` if not timed)

| Field | Target / note |
| --- | --- |
| `t_idle_visible_ms` | < ~2000 (E1) |
| `t_thinking_ui_ms` | immediate on send (E10) |
| `t_first_token_or_speak_ms` | casual ≤~5000 warm |
| `t_board_ms` | when SpotlightCard/board appears |
| `t_presence_ms` | ~1200 morph |
| `t_theme_ms` | ~1300 after switch start |
| `t_chrome_ms` | ~2400 |
| `t_hermes_ms` | from `/api/metrics` recent sample |
| `t_tts_cutover_ms` | ≤~1400 then Mark |
| `black_gap` | true/false during morph |
| `hard_cut` | true/false (fail unless reduced-motion) |

### 3.5 Routing / brain (chat & tool cases)

| Field | What to record |
| --- | --- |
| `intent` | casual_chat \| tool_ops \| ui_command \| vision_task \| unknown |
| `target_agent` | RES.01 \| SEC.02 \| DAT.03 \| OPS.04 \| SYS |
| `brain_path` | hermes-gateway \| hermes-cli \| snapshot-local \| gemini \| ollama \| none |
| `tools_called` | names if known |
| `invented_facts` | true if prices/mail/calendar invented |

### 3.6 Visual / workspace (P + E chrome)

| Field | What to record |
| --- | --- |
| `presence` | mint orb \| evil eye \| engineering bench \| none/black |
| `presence_centered` | true/false (same center as previous) |
| `eye_lag` / `eye_paused_off_monitor` | P10 |
| `aero_shards` | **must be false on Monitor** |
| `suns` | still-below \| revolving \| absent |
| `suns_when` | with chrome (last) \| too early \| never |
| `weather_visible` | Casual yes; Monitor **no** |
| `left_rail_visible` | Casual yes; Monitor **no** |
| `orchestra_dots` | Casual yes; Monitor **no** (suns instead) |
| `findings_rail` | Monitor heading “Findings”; Casual “Suggested” |
| `giant_awaiting_instruction` | Monitor **must be false** |
| `command_baton` | visible/quieter/hidden |
| `accent` | mint `#7dffe0` vs Monitor amber/gold |
| `data-workspace` | casual \| monitor \| engineering (theme layer) |
| `engineering_webgl_conflict` | eye/orb/shards under drawings? must be false |
| `drawing_hero` | ~55% viewer present? |
| `quote_stack` | ~40% present? |
| `open_notes_capped` | 4th parked? |
| `hud_error` | overlay / red line / Next crash |
| `console_errors` | if tester pastes |

### 3.7 Voice / HITL

| Field | What to record |
| --- | --- |
| `audio_streams` | 1 expected; 2 = fail K1 |
| `tts_source` | browser-bridge \| voicebox-Mark \| none |
| `late_clip_played` | true = fail K3 |
| `hitl_copy` | Authorize/Reject vs Shall I |
| `blast_radius` | 1–5 + consequence text present? |
| `authorize_used` | button \| voice-yes \| keyboard-Y \| **skipped** |
| `reject_used` | button \| voice-no \| keyboard-N |
| `sent_without_authorize` | true = automatic fail |
| `edited_fields_honored` | B4 |

### 3.8 API evidence (pull after the case)

| Field | Source |
| --- | --- |
| `turns_at` | LAST_TURNS header stamp |
| `turn_source` | chat \| confirm |
| `turn_session` | session_id |
| `turn_user` | verbatim |
| `turn_speak` | speak line |
| `turn_reply` | reply if different from speak |
| `turn_scene` | board title |
| `turn_pending` | pending summary |
| `turn_mail_id` | if any |
| `metrics_sample` | latest hermes latency row |
| `mission_id` | from `/api/missions` if tool turn |

### 3.9 Verdict & dispatch

| Field | What to record |
| --- | --- |
| `vs_target` | met / missed / n/a |
| `owner_words` | **verbatim** observation |
| `coordinator_read` | interpretation (do not contradict owner_words) |
| `screenshots` | paths under `work/screenshots/` |
| `fix` | none \| dispatched |
| `agent` | jarvis-uiux \| jarvis-voice \| jarvis-workflows \| jarvis-builder |
| `model` | composer-2.5-fast (required) |
| `placement` | cloud \| desk |
| `task_id` | subagent id for DONE follow-up |
| `retest` | not-yet \| requested \| pass \| fail |

---

## 4. Scoreboard (this pass)

Update the Result column as cases close. Order = suggested matrix order.

| Seq | ID | Result | Latency | One-line | Worker |
| --- | --- | --- | --- | --- | --- |
| 1 | I3 | **pass** | health <4s | HUD/API/Hermes-gw/Voicebox up | — |
| 2 | E1 | **pass** | owner: idle OK | Owner: successful | — |
| 3 | P1 | **pass** | n/a | Switcher Casual/Monitor/Engineering, one shell | agent |
| 4 | P7 | **pass** | presence ~1.26s overlap | No black gap; orb/eye/bench overlap | agent |
| 5 | P8 | **pass** | theme ~1.36s chrome ~2.50s | Amber after presence; chrome last | agent |
| 6 | P9 | **manual** | | needs OS reduced-motion | |
| 7 | P10 | **pass** (pause/GPU **manual**) | eye canvas 352/640 = 0.55 | Stock size; fps/pause off-screen not fully verified | |
| 8 | P11 | **pass** | n/a | No shards, weather card, left rail, giant awaiting; Findings yes | agent |
| 9 | P12 | **pass** | n/a | Still suns below eye, transform none | agent |
| 10 | P13 | **pass** | n/a | Mint, notes, weather, suggested, baton, [RES] dots | agent |
| 11 | E2 | **pass** | n/a | Owner + agent: Pune weather Casual only | — |
| 12 | E16 | **partial** | n/a | HUD shows 1/3; 4th-note park not exercised | manual |
| 13 | E17 | **pass** | n/a | Casual orb canvases present | agent |
| 14 | P14 | **pass** | n/a | Bench + empty drawing/quote; eye keepMounted hidden | agent |
| 15 | P2 | **manual** | | + New blocked while THINKING | |
| 16 | P3 | **pass** | n/a | Pin toggles; explicit switcher still moves | agent |
| 17 | P4 | **pass** | ~status speak | Monitor send, no talk-jump; stayed until explicit Casual | agent |
| 18 | P5 | **manual** | | mail talk-jump; A14 hung | |
| 19 | P6 | **manual** | | drawing talk-jump | |
| 20 | P15 | **manual** | | need live HITL overlay | |
| 21 | E11 | **manual** | | no pending queued this pass | |
| 22 | B2 | **manual** | | do not Authorize real send | |
| 23 | B3 | **blocked** | | C3 never produced pending | |
| — | P16 | retired | | Aero Shards on Monitor — skip | |
| — | P17 | retired | | Revolving orbs — skip | |
| — | M1 | retired | leftover `/canvas` 200 | Not primary desk | |

**Agent pass 2026-09-17 15:40 IST (API + HUD DOM). Owner already: E1–E4 pass; E5 expected mail-on-bench.**

---

## 5. Case writeups

### I3 — Health Hermes transport

```
id: I3
title: Health Hermes transport
attempt: 1
result: pass
started_local: 2026-09-17 ~00:53 IST
ended_local: 2026-09-17 ~00:53 IST
duration_s: ~4
tags: desk · cloud
depends_on: none
tester: coordinator (HTTP), not HUD clicks

workspace_before: n/a
workspace_after: n/a
pinned: n/a
fsm_before: n/a
fsm_after: n/a
session_id: n/a
conversation_id: n/a
hard_refresh: n/a

input_channel: HTTP
exact_input: GET :3000 ; GET :8000/api/health ; GET :8642/ ; GET :17493/ ; GET /api/voicebox/status ; GET /api/google/status ; GET /api/metrics
talk_jump_expected: n/a
authorize_required: false

t_idle_visible_ms: n/a (API probe)
t_hermes_ms: n/a this pass (stale metrics only)
black_gap: n/a

intent: n/a
brain_path: n/a
invented_facts: n/a

presence: n/a
hud_error: none on probes
console_errors: unknown

audio_streams: n/a
hitl_copy: n/a
sent_without_authorize: n/a

turns_at: 2026-09-16 11:10:02 +0000 (stale; no new turn)
turn_user: (none this pass)
metrics_sample: leftover 2026-09-16 casual p50 9618ms

vs_target: met
owner_words: (coordinator-run; user had not yet opened E1)
coordinator_read: HUD 200; API ok true; Hermes gateway true (root 404 expected); Voicebox 200 Mark; Google connected; Ollama false. Safe to start visual IDs. Casual Hermes p50 from yesterday is already over the 5s warm target — flag for A1, do not fail I3 on it.
screenshots: none
fix: none
agent: none
retest: n/a
```

**Raw probe notes**

- HUD `:3000` → 200
- API health → 200, body in §2
- Hermes `:8642/` → 404 (gateway up per health; not a failure)
- Voicebox `:17493` → 200; `cached_clips: 0`
- Google account `pgeneration.mech@gmail.com` configured+connected, calendar+sheets true

---

### E1 — Fast HUD bootstrap  ← CURRENT

```
id: E1
title: Fast HUD bootstrap
attempt: 1
result: awaiting
started_local: 2026-09-17 ~00:54 IST (instructions given)
ended_local:
duration_s:
tags: cloud
depends_on: I3

workspace_before: unknown (cold open)
workspace_after:
pinned:
fsm_before: expected IDLE
fsm_after:
session_id: likely default
conversation_id: likely null (ambient)
conversation_category: none
focus_title:
open_notes_count:
dock_hidden:
prefs_voice:
prefs_email:
reduced_motion: assume false
hard_refresh: requested (open or hard-refresh :3000)

input_channel: mouse / browser
exact_input: Open or hard-refresh http://127.0.0.1:3000
talk_jump_expected: n/a
authorize_required: false

t_idle_visible_ms:          ← NEED (target < ~2000)
t_thinking_ui_ms: n/a
t_first_token_or_speak_ms: n/a
t_presence_ms: n/a (no switch yet)
t_theme_ms: n/a
t_chrome_ms: n/a
black_gap:                  ← NEED if any blank/black before idle
hard_cut: n/a

intent: n/a
brain_path: none expected
invented_facts: n/a

presence:                   ← NEED (often Monitor eye if ambient)
presence_centered:
eye_lag:
aero_shards:
suns:
weather_visible:
left_rail_visible:
orchestra_dots:
findings_rail:
giant_awaiting_instruction:
command_baton:
accent:
data-workspace:
engineering_webgl_conflict: n/a
hud_error:                  ← NEED
console_errors:

audio_streams:
tts_source:
late_clip_played: n/a
hitl_copy: n/a
sent_without_authorize: n/a

turns_at: expect unchanged unless HUD auto-chats (should not)
turn_user:
turn_speak:
turn_pending:

vs_target:
owner_words:
coordinator_read:
screenshots:
fix:
agent:
retest:
```

**How to test (from matrix):** Cold open `:3000`. Idle UI <~2s; no long blank; lands in a workspace (often Monitor if ambient).

**Need from tester:** time-to-idle, which workspace, any blank flash or error overlay.

---

## 6. Worker dispatch log

| When (IST) | Case | Agent | Model | Place | Task id | DONE summary | Retest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-17 ~01:01 | (infra) live recorder | jarvis-builder | composer-2.5-fast | desk | e506d177-c8e0-4e05-aa69-50d6f1864b0f | JSONL + LIVE_TEST.md; chat/confirm/TTS/Hermes/HUD beacons; API restarted; 2 offline tests | n/a — refresh HUD |

Rules: one specialist per concern; cloud-default for HUD layout; desk only for Hermes / Voicebox / real Google OAuth / GPU Ollama / physical mic-speaker. Coordinator does not patch code.

---

## 7. Cross-cutting anomalies (running)

Add a bullet the moment something shows up outside a single ID (layout always broken, TTS always double, Hermes always slow).

| Seen | First ID | Notes | Status |
| --- | --- | --- | --- |
| Hermes casual p50 ~9.6s on 2026-09-16 leftover metrics | (pre-pass) | Over ≤~5s warm target historically; confirm on A1 this pass | watch |
| LAST_TURNS not updated since 2026-09-16 11:10Z | I3 | Expected until first chat/confirm this pass | watch |

---

## 8. Blank case template (copy for the next ID)

```
id:
title:
attempt: 1
result: awaiting | pass | fail | flaky | skipped | retired | blocked
started_local:
ended_local:
duration_s:
tags:
depends_on:

workspace_before:
workspace_after:
pinned:
fsm_before:
fsm_after:
hitl_listening:
hitl_resolving:
session_id:
conversation_id:
conversation_category:
focus_title:
open_notes_count:
dock_hidden:
prefs_voice:
prefs_email:
reduced_motion:
hard_refresh:

input_channel:
exact_input:
talk_jump_expected:
authorize_required:

t_idle_visible_ms:
t_thinking_ui_ms:
t_first_token_or_speak_ms:
t_board_ms:
t_presence_ms:
t_theme_ms:
t_chrome_ms:
t_hermes_ms:
t_tts_cutover_ms:
black_gap:
hard_cut:

intent:
target_agent:
brain_path:
tools_called:
invented_facts:

presence:
presence_centered:
eye_lag:
eye_paused_off_monitor:
aero_shards:
suns:
suns_when:
weather_visible:
left_rail_visible:
orchestra_dots:
findings_rail:
giant_awaiting_instruction:
command_baton:
accent:
data-workspace:
engineering_webgl_conflict:
drawing_hero:
quote_stack:
open_notes_capped:
hud_error:
console_errors:

audio_streams:
tts_source:
late_clip_played:
hitl_copy:
blast_radius:
authorize_used:
reject_used:
sent_without_authorize:
edited_fields_honored:

turns_at:
turn_source:
turn_session:
turn_user:
turn_speak:
turn_reply:
turn_scene:
turn_pending:
turn_mail_id:
metrics_sample:
mission_id:

vs_target:
owner_words:
coordinator_read:
screenshots:
fix:
agent:
model:
placement:
task_id:
retest:
```

---

## 9. Coordinator checklist after every observation

1. Paste owner words into `owner_words` **verbatim**.
2. Read `work/LAST_TURNS.md` + `/api/turns/recent` if the case could have created a turn; copy speak/pending/scene.
3. For latency/routing cases, read `/api/metrics` latest hermes row.
4. Fill every field in §3 (`n/a` / `unknown` allowed; blank not allowed on relevant fields).
5. Set scoreboard Result.
6. If fail/flaky: dispatch roster worker (`composer-2.5-fast`), log in §6, continue next ID.
7. Never pass HITL if Authorize was skipped.
8. Offer retest only when the tester wants it.

---

## 10. Agent-run pass — 2026-09-17 ~15:40 IST

Tester: coordinator (HTTP + Cursor browser). Session `cap-agent-20260917` for API chats; HUD used `default`. Hermes casual p50 **12178ms** (over ≤~5s). No Authorize of outbound mail.

### Ops / CI

| ID | Result | Notes |
| --- | --- | --- |
| I3 | pass | Reconfirmed after restart |
| I5 | pass | Voicebox available, profile Mark, cached_clips 0 |
| I6 | pass | `pytest -m "not live_service"` → **210 passed**, 11 deselected |
| I7 | **pass** | `tsc` clean; eslint **0 errors**, 6 warnings (allowed). Retest after uiux prefer-const |
| I8 | pass | `data/jarvis.db` + `data/tts_cache` under repo |
| I9 | pass | `pytest -m api_service` → **9 passed** |
| I1 | pass | metrics p50/p95 visible; all Hermes samples ~8–16s |
| I4 | pass | `/api/turns/recent` updated this pass |
| I2 | flaky | `/api/missions` timed out while a chat was in flight |
| N1 | pass | Google configured+connected, calendar+sheets |
| N2 | pass | PATCH voice_enabled flip then restore |
| D5 | pass | `/api/glance` 200, empty line, no crash |
| O5 | pass | `/lab/diarize` 200 |
| M2 | pass | POST/GET canvas board `cap-agent-tmp` |
| G7 | pass | `GET /api/rfqs` 4 intake rows (list, not new intake POST) |

### Brain / tools (no outbound Authorize)

| ID | Result | Latency | Notes |
| --- | --- | --- | --- |
| A1 | **fail latency** | 13616ms | Behavior OK; `casual_chat` RES.01; over ≤~5s warm |
| A2 | pass | 11374ms | RFQ shop summary; no prices; routed `tool_ops` DAT.03 |
| A10 | **pass** (retest) | 38849ms | `casual_chat` RES.01 definition — routing fixed. Still over ≤~5s (Hermes). Router Gemini 2.5-flash 404 is leftover |
| A12 | pass (API) | 1601ms | `ui_command` SYS “Hiding open notes.” HUD not on that session |
| A14 | **pass** (retest) | 3443ms | After snapshot-first gate + clean `:8000`: `tool_ops` SEC.02, Inbox scene, real unread speak |
| D2 | flaky | 15169ms | `casual_chat` “Nothing on the calendar this week.” Calendar connected — owner should confirm empty vs skipped snapshot |
| F1 | **pass** (retest) | 4068ms | After shop-intent skip-Hermes: `"No shop sheet yet..."` — no textbook OEE. HUD card still says shop log bound — owner can confirm bind |
| H2 | pass | 19156ms | Recalls Pratik / shop / short bullets (slow vs 5s) |
| C3 | **fail** | 70626ms | Draft-to-example.com → “I do not have that mail open.” **No pending** → B3 not run. Did not Authorize |
| E10 | pass | immediate | HUD “Orchestrating…”; FSM SEND→THINKING in live log |
| E14 | pass | n/a | Casual `[RES.01]`… dots; Monitor still suns |
| E15 | pass | n/a | Activity control present |

### Left for owner (manual / HITL / ears / GPU)

A3 (kill Hermes), A4 mic, A5/A7/A8/A11/A15/A16, B1–B15 except where noted, C1–C13 live mail UX, D1/D3/D4, E5–E9, E11–E13, E18–E19, F2–F8, G1–G6/G8, H1/H3–H6, J1–J8 HUD voice, K1–K7, L1–L5, M3–M5, N3–N5, O1–O4/O6, P5/P6/P9/P15, E16 fourth note.

---

*Owner next: HITL/voice/talk-jump mail (P5) when ready. Agent fails dispatched below.*
