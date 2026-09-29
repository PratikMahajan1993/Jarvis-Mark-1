# Scroll-substrate overhaul — review findings

**Archived 2026-09-30.** Point-in-time review of merge `7742e79` only. Later the same day, several bugs in this note were fixed and more of the platform landed. Do not use this file as the current HUD. As-built status is `docs/CURRENT.md`.

**Date:** 2026-09-30  
**Commit reviewed and merged:** `7742e79` on `overhaul` (PR #24, head was `cursor/scroll-substrate-overhaul-401c`)  
**Contracts:** `docs/overhaul/PLATFORM_DECISIONS.md` (P1–P13), `docs/overhaul/EXPERIENCE_DECISIONS.md` (X1–X13).

Read the code, not this review. Line numbers are from `7742e79`.

---

## Checks

| Check | Result | vs previous `overhaul` (`a72690f`) |
|---|---|---|
| `npx tsc --noEmit` (frontend) | Pass | — |
| `npx eslint src` | Pass, 0 errors, 7 warnings | New warning: unused `getSection` in `frontend/src/sdk/index.ts` |
| `npx vitest run` | 5 files, 56 tests passed | — |
| `pytest -m "not live_service"` | 14 failed, 553 passed, 8 errors | 13 failed, 547 passed, 8 errors |

The only **new** pytest failure is `tests/test_rule_budget.py::test_word_budgets`: `.cursor/rules/frontend/22-scroll-substrate.mdc` is 1491 words (cap 400). That test passed before the merge.

Already failing on `a72690f`, still failing here:

- `test_rule_budget.py` tree / T0 word count / alwaysApply / globs (core rule path and length; this merge makes the core rule longer, 314 words vs 254, and adds the scroll rule to the extra set)
- `test_rag_eval.py` (missing `work/RAG_EVAL.md`)
- `test_vision_bench.py::test_bench_analyse_uses_provider_stub`
- `test_vision_gate.py` four tests (`needs_vision` / `ok is False`)
- `test_phase1_rest.py::test_operations_price_only_when_given_and_outsource_blocks` (`UNIQUE constraint failed: customers.name` in a full run)
- `test_drawing_identity.py` eight setup errors (`FOREIGN KEY constraint failed`) in a full run; those tests pass when run alone

Frontend CI on the PR was green. Backend CI was red for the reasons above. The merge went in anyway.

---

## What landed (P13 steps)

| Step | Status | Notes |
|---|---|---|
| 1 Tooling | Done | Lenis, TanStack Query, Vitest, `openapi-typescript`, ESLint import boundaries, z-tokens |
| 2 Substrate v2 | Done | Eye / glow / rays removed. Swarm, three formulas, canvas once in `JarvisRoot` |
| 3 Stores | Done | turn, desk, taskQueue, section. `HITL_PARK`, `HITL_RESUME`, `ROUTE_HINT`, `effectsFor`. Vitest on the FSM |
| 4 Sections | Done | Lenis, registry, stack, nav, backdrop, decor, three sections. Snap type is `"lock"`, not `"mandatory"` |
| 5 Landing | Partial | Gates and timing exist. Not server-rendered. No Hermes status line. Chrome is one 500 ms fade |
| 6 Director + hints | Partial | `decideAuto` works. `ui` on chat stamp and Hermes run start. Turn-event stream does not emit `ui`. Director does not wait for autosave |
| 7 Task queue | Partial | Dock, Later, resume-to-modal. No shared-layout morph. Expiry bookkeeping is wrong |
| 8 Deck + autosave | Partial | Stack, chips, badge when focus already has the fields. Server draft body is only `{ focusMode }`. Scroll-away does not save |
| 9 Feature platform | Partial | Thin SDK, `features.py`, SSE, weather card, `new:feature` stub. No scheduler, no `GET /api/features`, no committed OpenAPI types |
| 10 Wrap-up | Partial | `docs/CURRENT.md` scroll section added, but its main HUD section still describes `OrchestratorShell`. Capability matrix not updated. Perf gate still clicks lenses |

### Contract score (short)

| IDs | Status |
|---|---|
| P5 stores/FSM, P6 swarm, X3 section/workspace, X6 layers, X7 baton dim, X11 lazy, X12 other routes | Done, with the caveats in the bug list |
| P1–P4, P7–P11, X1, X2, X4, X5, X8–X10, X13 | Partial |
| P9 scaffold, P12 "a day's work" checklist | Missing. `frontend/scripts/new-feature.mjs` writes a card and a backend module and does not register either |

Locked rules that held: mail send, calendar write, quote send, and broad memory wipe still queue HITL (those modules were not in the diff). `MAX_EXPANDED = 3`. No secrets in the diff. Files are not written outside the existing export rules; drafts go to SQLite. Voicebox and the Gemini TTS path were not swapped; `voice.ts` only added an analyser level loop. New events client uses `127.0.0.1:8000`. `lib/api.ts` and `voice.ts` still fall back to `localhost:8000` (already true before the PR).

No remaining `useSyncExternalStore` selector was found that returns a fresh object. `TaskDock.tsx` 17–19 selects `items` and `parkedIds` separately. Substrate cleanup removes the worker, listeners, and canvas (`SubstrateCanvas.tsx` 97–105). `/api/events` drops its queue in a `finally` (`features.py` 105–106).

Migration `backend/migrations/0029_drafts.sql` is safe on an existing `jarvis.db`: `CREATE TABLE IF NOT EXISTS`, no alter of older tables, applied once via `schema_migrations` (`db.py` `run_migrations`).

---

## Fix first

These are the gaps the implementation plan should schedule before more feature-platform work. Each one loses owner data or hides an approval.

### 1. Space does nothing in the baton — high

`frontend/src/core/scroll/engine.ts` 43–52 treats `input[type=text]` as not a field, so PageUp/PageDown still work while the baton is focused. Lines 206–211 then `preventDefault` Space for that same case. The baton is `<input type="text">` (`CommandBaton.tsx` 70–72). `handleDeskKey` (`controller.ts` 1065) will not start the mic while an input is focused. Space neither types nor listens.

**Fix:** `preventDefault` Space only when the event target is not a field. Keep PageUp/PageDown behavior if section keys should still work from the baton.

### 2. Baton text is lost or saved on the wrong section — high

`BatonDock.tsx` 37–45. The 2 s timer is cleared on cleanup and not flushed. On section change, saved text loads only when `compose` is empty. Typed text stays on screen, then the new timer writes it under the new section key. Closing the tab inside 2 s loses it. There is no `pagehide` flush for baton text.

**Fix:** on section change and on `pagehide`, `saveBatonText(previousSection, compose)` immediately, then load the next section.

### 3. Leaving Engineering does not autosave, and saves that do run are not awaited — high

X10 / P5: leave Engineering, wait up to 300 ms. `goToSection` (`controller.ts` 129–130) fires `runAutosave` and scrolls immediately. `effectsFor` (`orchestratorFsm.ts` 392–398) emits `autosave` then `scroll`; the runner discards the promise (`controller.ts` 961). `registerServerDraft` (`drafts.ts` 42–45) does not return the fetch promise, so the 300 ms race in `autosave.ts` 15–18 ends before the request. Wheel and snap never call autosave. `EngineeringSection.tsx` 56–61 drops the `pagehide` listener on cleanup without flushing. The body saved is only `{ focusMode }`, not other owner fields.

**Fix:** when the active section leaves Engineering, flush and wait up to 300 ms before the jump. Return the save promise from the handler. Flush on unmount. Decide which owner fields belong in this draft versus `/api/quote/*`.

### 4. `pagehide` beacon can fail silently — high

`drafts.ts` 29–31 posts `Content-Type: application/json` via `sendBeacon` and ignores `false`. The page is `:3000` and the API is `:8000`, so that type needs a CORS preflight, which a beacon does not complete.

**Fix:** if `sendBeacon` returns false, fall back to `fetch` with `keepalive`. Prefer a CORS-simple content type and parse that body on the server.

### 5. Parked approvals vanish or false-expire — high

`setPendingItems` (`taskQueueStore.ts` 109–122) treats every parked id missing from the new list as server-expired and toasts it. `GET /api/pending` is one session (`main.py` 1376–1378). Switching notes drops other sessions' chips. X8 asked for every pending row across sessions.

Client TTL uses `created_at + 30 min`, not time parked (`parkedExpiry.ts` 30–34), so parking an older approval expires on the next check. After TTL, `unmarkParked` removes the chip (`taskQueueStore.ts` 146–158) while the server row stays `pending`. The toast says to reopen it from the dock.

**Fix:** do not prune parked ids the latest response simply omitted. Start the 30 min clock at `parkedAt`. On a real expiry, keep a chip or open the modal.

### 6. Draft key is not validated — medium

Size is checked after JSON parse (`drafts.py` 21–24, 64 KB). `PUT`/`POST /api/drafts/{key}` (43–55) accept any key.

**Fix:** reject keys that are not a short token (for example `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`) before the write. Reject oversized payloads before building a huge object.

### 7. `publish()` is not safe off the event loop — medium

`features.py` 61–67 iterates `_subscribers` and calls `asyncio.Queue.put_nowait`. Sync FastAPI routes run on a threadpool; `asyncio.Queue` is not thread-safe. Nothing in the app calls `publish` yet. `run_jobs` (70–82) swallows every exception and is never started from lifespan.

**Fix:** hop onto the loop with `call_soon_threadsafe`. Start one job loop from lifespan and log failures. Do this before any feature publishes from a sync route.

### 8. Same-session approval badges every engineering card — medium

`deckCardMeta.ts` 118–121: `pendingMatchesConversation` returns true when `action.session_id` equals the conversation session, so a mail approval parked on that session badges every task in it.

**Fix:** match `conversation_id` (and an explicit session match only when the payload has no conversation id and the action is an engineering kind).

### 9. New rule-budget failure — low

`frontend/22-scroll-substrate.mdc` fails `test_word_budgets`. The rule's own templates (`useFeatureQuery`, `defineApprovalView`, `backend/app/features/__init__.py`) are ahead of the code. Cutting the file also stops agents from copying APIs that do not exist.

**Fix:** shorten the rule to the budget, or change the test on purpose. Point templates at hooks that exist, or mark them as not shipped.

---

## Known product gaps (not data-loss)

Owner-deferred or already called out as unfinished. Do not "fix" snap wording until the owner chooses.

| Gap | Where |
|---|---|
| Snap `"lock"` vs contract "mandatory" | `engine.ts` 90–95. Owner decision still open |
| HITL modal → dock chip shared-layout morph | Later only parks state (`controller.ts` 580–588) |
| Card → drawing stage morph | Deck calls `selectConversation`; no shared `layoutId` |
| pdf.js thumbnails + IndexedDB by sha256 | `deckCardMeta.ts` 97–99 reads a URL already on focus |
| Sim budget 6 ms | Degrade watches frame p95 20 ms (`engine.ts` 8–14, 395–400), then bloom, then `simEvery: 2`. Not measured on this GPU |
| `lib/pane/` helpers not migrated | `springs`, `perf`, `quoteContract`, `knowledge` |
| Landing not in first HTML; chrome not staggered; no Hermes line | `page.tsx` 4–8 `ssr: false`; `Desk.tsx` 37–40; `Landing.tsx` labels |
| Deck: no `deltaX` cycle, no empty drop target | `EngineeringDeck.tsx` |
| Turn stream does not emit `ui` at routing time | P8. Hints exist on the chat response and `POST /api/hermes/runs` |
| Feature platform remainder | No `GET /api/features`, no `load_features`, intents not added to the ONNX bank, tools not auto-registered, jobs not started, `schema.gen.ts` not committed, flags not in Preferences |
| `docs/CURRENT.md` main HUD section and the capability matrix | Still describe lenses / `OrchestratorShell` / ambient → Monitor |
| Perf gate | `frontend/scripts/perf-gate.mjs` still clicks lenses. No landing time, scroll round-trips, or listener count |

---

## Not verified on the desk

Needs Hermes (`:8642`), the Gemini speech key and a speaker, Google OAuth, or a microphone:

- Live `ui` hint under the director (pin, modal, 1.2 s quiet)
- TTS playback, analyser level, quota silence
- Voicebox (code path unchanged; not run)
- Real Authorize / Reject of mail, calendar, or quote send
- Space-to-listen, and whether a space character appears in the baton
- 20k-particle `simMs` while blending, bloom degrade, context loss, one WebGL context
- Landing gather, Lenis snap, and chrome fade in a browser
- `sendBeacon` against the live API on `pagehide`

---

## Suggested plan order

1. Data-loss and input bugs: 1–5 above (Space, baton, Engineering autosave, beacon, parked approvals).
2. Draft key validation and the session-wide badge (6, 8).
3. `publish()` thread safety before any new feature uses SSE (7).
4. Rule-budget file, so CI's new failure is gone and agents stop copying missing APIs (9).
5. Product gaps that do not need an owner decision: landing Hermes line and chrome stagger, deck `deltaX` and drop target, turn-stream `ui`, CURRENT.md / matrix / perf gate.
6. Leave snap lock-vs-mandatory, pdf thumbnails, HITL morph, and the 6 ms sim budget as explicit follow-ups. The sim budget needs a desk measurement first.
7. Feature-platform completion (P4 hooks, loader, scheduler, OpenAPI, `new:feature` registration) after 1–4, not before.
