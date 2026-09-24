# UI/UX audit

**Method.** This audit ran the actual application, not just its source. `.venv/bin/uvicorn` and `npm run dev` were started fresh in this sandbox (`GET /api/health` confirmed a real, cold-booted backend reporting Hermes/Voicebox/Gemini as correctly unavailable in this environment). The live HUD was then captured directly with headless Chrome (`--enable-unsafe-swiftshader`, per `.cursor/skills/jarvis-react-bits/SKILL.md`'s own documented method — confirmed to work exactly as that skill describes) across all three workspaces and at a 420px mobile width; a second, independent interactive walkthrough was additionally dispatched via a computer-use agent for click/keyboard/typed-input verification beyond what static screenshots can show. Every finding below is anchored to either a captured screenshot, source code read directly during this audit, or both — not general UX platitudes.

<img src="/opt/cursor/artifacts/hud-monitor.png" alt="Monitor workspace on cold load, Google-not-configured modal open" />
<img src="/opt/cursor/artifacts/hud-casual.png" alt="Casual workspace on cold load, same modal open, conversation rail visible behind it" />
<img src="/opt/cursor/artifacts/hud-engineering.png" alt="Engineering workspace on cold load, quote/variance widgets visible behind the modal" />
<img src="/opt/cursor/artifacts/hud-mobile-420.png" alt="Monitor workspace at 420px mobile width" />
<img src="/opt/cursor/artifacts/hud-mobile-casual.png" alt="Casual workspace at 420px mobile width, conversation rail stacked above the modal" />

A follow-up interactive walkthrough (typed input, mic click, keyboard tab order, and a live click on the Engineering workspace's Reject control) was performed by [a computer-use walkthrough agent](bc-4eda711e-e658-572a-8ca0-9f7a069285fc) after the above was written. Its raw findings were **not** taken at face value — every claim below was independently re-verified against source and, where the agent's own screenshots were available, against the pixels themselves, before being written up. Two of its claims did not hold up (noted explicitly below); several others uncovered a genuinely serious, previously-undiscovered issue (`UX-8`).

<img src="/opt/cursor/artifacts/hud-engineering-dead-reject-button.webp" alt="Engineering workspace bench sheet showing a real-looking Authorize/Reject pair on a demo RFQ-FAKE-9001 quote" />
<img src="/opt/cursor/artifacts/hud-casual-idle-voice-vs-board.webp" alt="Casual workspace after a mail search: center voice line reads Awaiting instruction while a real Inbox board with results renders directly below it; devtools console shows the expected /api/tts 503 from an unreachable Voicebox" />

---

## Finding UX-8 — The Engineering bench's "Authorize"/"Reject" buttons are permanently non-functional, and look indistinguishable from the real HITL control

**Priority: CRITICAL**

**User problem.** A shop owner reviewing a quote in the Engineering workspace's sheet panel sees a fully-styled, seemingly state-aware "Authorize"/"Reject" button pair at the bottom of the quote total — the same visual language (filled primary vs. outlined secondary) as the real, backend-wired `HitlModal` used everywhere else in the product for the exact same kind of decision. Clicking "Reject" here does **nothing at all**: no request, no state change, no visible feedback of any kind.

**Relevant workflow.** Reviewing/deciding on a quote from the Engineering bench (`BenchQuotePanel` → `QuoteSheet`), as distinct from the ledger-driven `HitlModal` Authorize/Reject flow analyzed in `UX-2` and `02-logic-audit.md` Flow 2/3.

**Evidence — this is not a UI-testing artifact, it is the shipped code.** `frontend/src/components/bench/QuoteSheet.tsx`:
```tsx
<button type="button" className="orch-btn orch-btn-primary flex-1" disabled={authOff}
  onClick={() => { /* Bench fixture Authorize — no mail / quote_send / jarvis_quote_build */ }}>
  Authorize
</button>
<button type="button" className="orch-btn orch-btn-ghost flex-1"
  onClick={() => { /* Bench fixture Reject — local UI only */ }}>
  Reject
</button>
```
Both handlers are empty — the comments are the *only* content, and they are explicit that this is deliberate scaffolding ("no mail / quote_send / jarvis_quote_build"), not an oversight in the sense of a forgotten `TODO`. This component is mounted unconditionally at the `sheet` panel slot in every Engineering-workspace session (`OrchestratorShell.tsx`: `sheet: <BenchQuotePanel scene={scene} />`), regardless of whether the sheet is showing real quote data or the bundled `frontend/src/lib/pane/fixtures/quote-fixture.json` demo document (confirmed via `grep`: this fixture file is the source of the `RFQ-FAKE-9001` / "Round Numbers Machining Co." / "Widget Bracket MK-II" content visible in the screenshot above, which reproduces the walkthrough agent's exact observation once the correct source string is traced).

**The one detail that makes this worse, not better.** The "Authorize" button *does* correctly reflect state — it is disabled (`disabled={authOff}`, greyed out in the screenshot) exactly when the mirrored `ProofStrip`'s `verify.stop` is true, which is correct, real, state-driven behavior. This means a user has every reason to believe the whole control pair is live and functioning — they can visibly see Authorize respond to the quote's proof state — which makes the silently-inert Reject button (always enabled, never gated, never wired, regardless of `authOff`) far more deceptive than if both buttons were obviously fake. A user who clicks Reject here, on a real quote, with no feedback, cannot tell whether they just rejected a ₹31,675 order, whether the click registered at all, or whether they need to look elsewhere (the real `HitlModal`) to actually act.

**Underlying cause.** This reads as bench-panel scaffolding built ahead of its backend wiring — a reasonable, common way to build a UI panel against a fixture before the real `quote_send`/`resolve_pending` flow is threaded through it — that was never finished or gated behind a visible "preview" affordance before shipping to the branch this audit is running against.

**Why it creates real risk, not just confusion.** This is a case where the audit brief's "confirmation of destructive actions" and "affordances that lie about what they do" concerns converge with an actual safety property this product is otherwise careful about (every real Authorize/Reject decision elsewhere in the codebase is provably wired to `resolve_pending`, per `LOGIC-1`). A control that looks like the real safety gate but isn't is arguably worse for user trust than having no control there at all.

**Recommended direction.** Either wire these two buttons to the real flow (`api.confirm`/`decide()`, the same call the `HitlModal` already uses, scoped to whatever pending action the bench sheet is currently showing — likely requiring the sheet to know the current pending action's id, which it may not today) or, until that's done, visually and functionally disable both buttons whenever the sheet is showing fixture/non-actionable data, and add an explicit label (e.g. "Preview — not connected") so the control cannot be mistaken for the real gate. Given the stakes, the second option is the safer immediate step even if the first is the eventual goal.

**Tradeoffs.** Wiring the buttons fully requires the bench sheet to resolve which real `pending_actions` row (if any) corresponds to the currently-displayed quote — not necessarily a small change, since the sheet's `scene`/document resolution today (`resolveDocument(scene)`) is presentation-focused, not pending-action-aware. Disabling/labeling the fixture state is a small, low-risk, high-value interim fix.

**Migration complexity: LOW** for the safe interim fix (disable + label); **MEDIUM** for full wiring (needs the sheet to resolve a real pending-action id).

---

## Finding UX-9 — A successful result can display "Awaiting instruction" (the idle placeholder) directly above the actual answer, reading as if the system is still stuck

**Priority: MEDIUM — root cause independently identified and confirmed via source, correcting the walkthrough agent's own diagnosis**

**User problem.** After submitting "check my mail" in the Casual workspace, the walkthrough agent observed the center voice line stuck on **"Awaiting instruction."** for several seconds with a real "Inbox" board (showing genuine seeded results — "Ashutosh on Re: Q3 proposal — your note") rendered directly below it, and concluded the backend had hung or failed silently. **This diagnosis does not hold up**: the devtools console captured in the same screenshot shows only expected, correctly-handled `POST http://localhost:8000/api/tts 503 (Service Unavailable)` responses (Voicebox is not running in this sandbox — a 503 here is the server's own documented signal telling the browser to fall back to built-in TTS, per `main.py:api_tts`'s own comment: *"503 (not 502): Voicebox unreachable or synthesis failed — HUD falls back to browser TTS"* — this is correct, designed-for behavior, not a bug, and is unrelated to the chat request itself). The mail search itself plainly succeeded — real inbox content is visible on screen.

**What actually happened, traced to source.** `OrchestratorShell.tsx:applyResponse()`: when a response's `scene` has real board content (`sceneHasBoardContent(nextScene)` — true here, since the Inbox table rendered), the code does `if (boardOwnsHud && workspaceRef.current !== "engineering") clearVoice();` — i.e. it **deliberately** clears the center voice line so it doesn't duplicate text already shown in the board (a reasonable design intent, per the code's own comment: *"Mail board / compose modal owns the center — hide VoiceLine so text is not duplicated."*). But `clearVoice()` doesn't leave the center blank — `VoiceDockPanel`'s converse-lens branch falls back to `const line = (showCenterVoice && voice ? voice : IDLE_VOICE)...` and `showCenterVoice` is now false, so `line = IDLE_VOICE = "Awaiting instruction."` — the **same string used for the true idle state before any request is made** is redisplayed as if nothing happened, at the exact moment a request has *just succeeded*.

**Why it matters.** This is a real, verifiable UX defect, just not the one the walkthrough agent diagnosed: the design intent (don't duplicate text) is sound, but the specific fallback string chosen for "board owns the center, nothing to say up here" is identical to the string used for "nothing has happened yet, waiting for you to speak" — the one case where the two states most need to look different is exactly the case that currently makes a fresh success look like a stall.

**Recommended direction.** Give the "board owns the center" case its own distinct, brief acknowledgement text (even something as simple as a short "✓" glyph or "On the board" instead of reusing `IDLE_VOICE`), so a completed, successful turn is never visually identical to the pre-request idle state.

**Tradeoffs.** None meaningful — this is a small, targeted copy/logic change (a new fallback string for this one branch), not a redesign.

**Migration complexity: LOW.**

---

## Finding UX-10 — The same underlying concept ("a persistent thing you can leave and return to") is named at least three different ways in adjacent UI

**Priority: LOW-MEDIUM**

**Finding.** In the same screenshot (Casual workspace), the left rail's section header reads **"Open notes"** (component: `ConversationRail.tsx`), the one item inside it is labeled **"Everyday desk"** (a hardcoded string in `OrchestratorShell.tsx`'s `focusAmbient()`/bootstrap path), and creating a new one produces a header labeled **"Discussion HH:MM"** (from `conversations.py:kind_label()`, which returns "Discussion," "Job," or "Drawing" depending on category) — so the same left-rail list is introduced as "notes," contains a "desk," and its entries are called "discussions" once opened. `db.py`'s own `MAX_EXPANDED`/`MAX_CONVERSATIONS` constants and the API's `/api/conversations` naming add a fourth term ("conversations") for the same underlying object at the code layer, which is fine internally but is exactly the kind of internal-model-leaking-into-UI-labels pattern the audit brief flags.

**Why it matters.** None of these terms is wrong in isolation, but a first-time user assembling a mental model of "where do my open things live" has to reconcile four different words for what is, underneath, one list of `conversations` rows. This is a small but real information-architecture inconsistency, not a functional bug.

**Recommended direction.** Pick one user-facing term (the code's own `kind_label()` function already shows the product is willing to have a human-facing label distinct from the internal category — "Open notes" is a reasonable candidate) and use it consistently across the rail header, the ambient-desk entry, and any copy describing the feature, reserving "conversation" for internal/API naming only.

**Migration complexity: LOW** — this is copy-only, no logic change.

---

## Two walkthrough claims that did not hold up on independent verification

In the interest of not repeating unverified claims: the walkthrough agent additionally reported (a) the "Open notes" counter changing from "0/3" to "1/6" after creating a discussion, and (b) `POST /api/tti 503` console errors. Both were checked directly: `ConversationRail.tsx` hardcodes `maxOpen={MAX_OPEN_CONVERSATIONS}` (=3) with no code path that could produce a denominator of 6, and the walkthrough's own later screenshot (above) shows the console error is `POST http://localhost:8000/api/tts 503` (the real, existing, expected-in-this-sandbox endpoint) — there is no `/api/tti` route anywhere in the codebase. Both are most likely transcription artifacts from the agent reading its own screenshots, not real product behavior, and are not carried forward as findings.

---

## Finding UX-1 — First-use cold load is dominated by a setup modal that exposes raw environment-variable names

**Priority: HIGH**

**User problem.** The very first thing any new user sees, in **every one of the three workspaces**, on a cold load with Google not yet configured, is a large, sharply-lit modal titled "Google is not configured," reading: *"Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to the API .env file, restart the server, then connect from here."* — captured directly in `hud-monitor.png`, `hud-casual.png`, and `hud-engineering.png`.

**Relevant workflow.** First-use / onboarding.

**Evidence.** Screenshots above; source: `frontend/src/components/orchestrator/ConnectGoogleModal.tsx:googleConnectPrompt()`, the `!status.configured` branch. `OrchestratorShell.tsx` opens this modal unconditionally on mount whenever `googleServicesIncomplete(google)` is true, which is true by definition until Gmail/Calendar/Sheets are all connected — i.e., **every single fresh install of this product**, before any owner has had a chance to do anything else, sees raw backend environment-variable names as its first substantive sentence.

**Why it creates friction/confusion.** `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are backend configuration keys, meaningful to whoever ran `.cursor/install.sh` or edited `.env`, not to the "Sir"-addressed shop owner this product's voice and persona are otherwise built around (see `agent.py`'s system prompts, which consistently avoid technical language). This is a direct, verified instance of the exact "technical/internal terminology exposed to a non-technical user" pattern called out in the audit's own checklist — and it happens at the single highest-leverage moment (first impression), not buried in a settings screen.

**Underlying cause.** `googleConnectPrompt()`'s copy was written from the operator/installer's point of view ("what do I need to add"), not the end-user's; there is no intermediate, friendlier "Google isn't connected yet" state that defers the *how* (env vars) to the Preferences panel's own Google section, which already has a **second, near-identical copy of the same message** (`PreferencesPanel.tsx:GoogleConnect()`: *"Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env on the API machine."*) — the technical instruction is duplicated in two places, once as an unavoidable first-load interstitial and once as the place a user would actually go to act on it.

**Recommended direction.** Split the two audiences: the modal (unavoidable, first thing seen) should say something like *"Jarvis isn't connected to your Google account yet — open Preferences to finish setup,"* with the `.env` mechanics living only in Preferences, where the person actually doing the technical setup will find them. This is a copy-only change, no logic change.

**Tradeoffs.** None meaningful — this loses no information (the detailed instruction still exists, just in one place instead of two, and in the place suited to acting on it).

---

## Finding UX-2 — The HITL Authorize/Reject modal — the single most consequential dialog in the product — has weaker accessibility semantics than the least consequential one

**Priority: HIGH**

**User problem.** A screen-reader or keyboard-only user gets meaningfully worse support for the dialog that approves real external actions (sending mail, calendar writes, quote sends) than for the dialog that merely nudges them to connect Google.

**Relevant workflow.** HITL Authorize/Reject (Flow 2 in `02-logic-audit.md`) — the highest-stakes interaction in the entire product by the project's own framing (every external/destructive effect routes through this one modal).

**Evidence — direct source comparison.**
- `frontend/src/components/orchestrator/ConnectGoogleModal.tsx` (lines ~111–113): `role="dialog" aria-modal="true" aria-labelledby="google-connect-title"` — correct, complete dialog semantics.
- `frontend/src/components/orchestrator/HitlModal.tsx`: **no `role`, no `aria-modal`, no `aria-labelledby` anywhere in the file** (grep-confirmed: zero matches for `role=`/`aria-modal` in this file).
- `frontend/src/components/orchestrator/PreferencesPanel.tsx`: same gap — no dialog role, no `aria-modal`.
- **None of the three modals** implements a focus trap or sets initial focus on open (no `autoFocus`, no `ref.current.focus()`, no focus-trap library import in any of the three files) — confirmed by direct source read, not inferred.
- **None of the three modals** closes on `Escape`. `OrchestratorShell.tsx`'s single global `keydown` handler only handles `Escape` for `LISTENING` (stop listening) and `AWAITING_HITL` + `listening` (stop the confirm-mic) — it has no case for closing `PreferencesPanel` or `ConnectGoogleModal`, so a keyboard-only user must `Tab` all the way to each modal's own "Close"/"Not now" button.

**Why it creates friction/confusion.** A screen reader encountering `HitlModal`'s markup has no signal that focus has entered a dialog context, or what the dialog's accessible name is — it would announce the heading and button text as if they were ordinary page content, not a modal requiring a decision before the rest of the page is relevant again. For a voice-first product whose stated design principle is that Authorize/Reject is *the* safety-critical decision point (per `.cursor/rules/backend/11-hitl-safety.mdc`), this is the one place accessibility quality should be highest, and it is verifiably the opposite.

**Underlying cause.** `ConnectGoogleModal` appears to have been the one component someone deliberately added ARIA to (perhaps because Google's own products have set that expectation); the pattern was not then propagated back to `HitlModal`, which — based on file structure — looks like it may predate `ConnectGoogleModal` in the codebase.

**Recommended direction.** Add `role="dialog" aria-modal="true" aria-labelledby={...}` (pointing at the existing `<h2>{copy.title}</h2>`) to `HitlModal` and `PreferencesPanel`, matching `ConnectGoogleModal`'s already-correct pattern exactly (it does not need to be reinvented, only copied). Add an `Escape` case to the shared keydown handler for these two modals (Reject-equivalent for HitlModal would need product input — see below — but for `PreferencesPanel`, `Escape → onClose` is unambiguous and safe). Add a one-line `useEffect` that focuses the primary action button on open for each modal.

**Tradeoffs.** For `HitlModal` specifically, binding `Escape` to an action needs a product decision: should `Escape` **Reject** the pending action (consistent with typical modal-dismiss semantics) or merely **do nothing** (since silently rejecting a real external action via an easily-mis-pressed key is a materially different risk than dismissing a settings panel)? This audit does not recommend a default — **PRODUCT DECISION REQUIRED** specifically for `HitlModal`'s `Escape` behavior, given it is the one modal where "dismiss" has a real-world consequence (Reject, not just Close).

---

## Finding UX-3 — "Blast radius · N/5" is internal risk-scoring jargon shown directly to the shop owner

**Priority: MEDIUM**

**User problem.** `HitlModal` renders `Blast radius · {copy.irreversibility}/5` directly above the consequence text on every single Authorize/Reject decision — verified in `HitlModal.tsx` (`<span>Blast radius · {copy.irreversibility}/5</span>`), sourced from `backend/app/hitl_meta.py`'s `blast_radius_for()` scoring, which is an internal engineering concept (site-reliability-style "blast radius" terminology) surfaced verbatim to a machine-shop owner with no explanation of what the number means or why it matters.

**Relevant workflow.** Every single HITL decision — this is not a rare edge case, it is the copy shown on every Authorize/Reject card.

**Why it creates friction/confusion.** The instinct behind this (communicate how consequential an action is, beyond just "Authorize/Reject") is genuinely good UX thinking, and the accompanying `copy.consequence` plain-English sentence does the actual explanatory work — but the jargon label sits directly above it, forcing the user to either ignore an unexplained number/5 score or wonder what it means, for a persona ("Sir," per the system prompts) that the rest of the product's copy is otherwise carefully written to avoid confusing.

**Recommended direction.** Either drop the "Blast radius · N/5" label entirely and let `copy.consequence`'s plain sentence carry the weight alone, or relabel it in plain language tied to the same 1–5 scale it already computes (e.g. a short word like "Impact" with a simple visual indicator rather than a raw fraction, if the product wants to keep the at-a-glance signal).

**Tradeoffs.** Removing the label loses a compact "how serious is this" signal for users who've learned to read it; relabeling keeps the signal with different words, at the cost of a small copy change everywhere `shallICopy()` is used.

---

## Finding UX-4 — Engineering workspace's first view is dense with numbers before any interaction, with no visible "why am I seeing this" framing

**Priority: MEDIUM**

**User problem.** `hud-engineering.png` (dimmed behind the Google modal, but legible) shows a populated right-hand rail with what appears to be a job title ("Bridget Bracket MK-2"), several line-item rows with currency-like values, colored status dots, and a bottom-right total (visible as "₹61,475"-shaped text) — all present on a cold load, before the user has typed or spoken anything in this session.

**Relevant workflow.** First-use / returning-user disambiguation in the Engineering workspace.

**Why it creates friction/confusion.** For a brand-new user, this workspace shows financial-looking data immediately with no on-screen indication of *whose* job this is, *when* it was created, or *why* it's showing right now — is this a real quote in progress, demo/seed data (`jobs.py:seed_demo_job()` seeds a demo job at `init_db()` time, per the codebase map), or a restored session from a previous visit? The audit brief specifically asks about "first-use" vs. "returning-user" states being distinguishable; on this evidence, they are not visually distinguished at all — a first-time owner and a returning owner mid-quote would see structurally the same kind of dense panel with no differentiating chrome.

**Underlying cause.** Bench panels are deliberately "always mounted, never destroyed on switch" per `docs/CURRENT.md`'s stated design and confirmed in `frontend/22-frontend-uiux.mdc` ("visibility is depth 0-3... never mount/unmount") — a reasonable architectural choice for continuity, but it means the Engineering lens's default content is whatever the last-touched job/quote state happens to be (including seed data on a truly fresh install), with no separate "nothing in focus yet" empty state distinguishable from "here is your actual last quote."

**Recommended direction.** Add a lightweight, non-intrusive indicator distinguishing seed/demo data from a real in-progress job (e.g. a small "Demo data" tag), and/or an explicit empty state for "no job is currently in focus" that is visually distinct from "a job is in focus and here are its numbers" — this is a targeted addition to the existing bench panels, not a redesign.

**Tradeoffs.** Adds a small amount of new UI state to track (is the currently-shown job "real" vs. seed) that doesn't cleanly exist as a concept in the backend today — `jobs.seed_demo_job()` and a real quote conversation both just end up as normal rows; distinguishing them for display purposes would need a small backend flag, not just a frontend change.

---

## Finding UX-5 — Responsive layout at 420px genuinely works, with one real content-overlap risk

**Priority: LOW-MEDIUM**

**Finding.** `hud-mobile-420.png` and `hud-mobile-casual.png` confirm the pane layout **does** reflow sensibly at a 420px phone width: the modal resizes to fit with correct text wrapping, the top bar's workspace switcher and controls remain reachable, and the command input strip at the bottom remains visible and not clipped. This is a genuine, verified positive — no horizontal scroll, no obviously cut-off critical controls were found in either capture.

**One real risk, not fully verified live.** In `hud-mobile-casual.png`, the dimmed conversation-rail content (two note rows) visually sits close to/behind the top status chip row before the modal's backdrop takes over — with the modal open this is moot (backdrop covers it), but it raises the question of whether the conversation rail's own scroll region and the top bar can visually collide at this width once the modal is dismissed and real content is scrolled. **REQUIRES FURTHER INVESTIGATION**: this was not verified with the modal closed, since Google is unconfigured in this environment and the modal cannot be dismissed permanently without either configuring Google or clicking through it interactively (the "Not now" path) — a deeper, interactive mobile-width pass (post-dismissal) is the natural next step, ideally via the same computer-use approach used for desktop interaction in this audit.

---

## Finding UX-6 — Keyboard shortcuts for Authorize/Reject exist but are entirely undiscoverable

**Priority: LOW-MEDIUM**

**Finding.** `OrchestratorShell.tsx`'s global keydown handler supports `y`/`Y` → Authorize and `n`/`N` → Reject whenever a HITL panel is open and focus isn't in a text field — a genuinely nice power-user affordance for a desk operator who wants to avoid reaching for the mouse. `HitlModal.tsx` itself, however, only ever displays *"or say yes / no"* (a voice-input hint) — there is no on-screen text anywhere indicating the `y`/`n` keyboard shortcuts exist.

**Why it matters.** This is a discoverability gap, not a functional bug — the feature works when found by accident or by reading the source (as this audit did), but a sighted, keyboard-preferring user has no in-product way to learn it exists.

**Recommended direction.** Add a small, low-emphasis hint alongside the existing "or say yes / no" line, e.g. "or press Y / N," consistent with the product's existing terse, mono-font micro-copy style already used elsewhere in the same component.

**Tradeoffs.** None meaningful — this is a small, additive copy change.

---

## Finding UX-7 — Positive: the HITL card's visual design is otherwise strong and appropriately weighted for a consequential decision

**Priority: N/A (positive)**

`HitlModal`'s use of `ElectricBorder` (reserved, per `.cursor/rules/frontend/21-react-bits.mdc`, exclusively for this one modal — confirmed: no other component in the read source uses `ElectricBorder` outside `HitlModal`/`ConnectGoogleModal`), a clear title/summary/consequence hierarchy, and a visually distinct "Authorize" primary button (filled, high-contrast) vs. "Reject" secondary button (outlined, low-emphasis) together correctly signal "this is a decision, and here is the safe default direction of least surprise" without needing extra copy to say so. This is good, disciplined interaction design and should be the template for the accessibility fixes in `UX-2`, not replaced by them.

---

## Application states — coverage check

| State | Found? | Evidence |
| --- | --- | --- |
| First-use | Yes — dominated by the Google setup modal (`UX-1`) | Screenshots |
| Loading | Partial — `THINKING` mode shows "Orchestrating…" text immediately (`OrchestratorShell.tsx:send()`), confirmed in source; not independently screenshotted mid-request in this pass | Source-confirmed |
| Empty | Partial — `_review_inbox`/`show_artifact`/etc. handlers all have explicit "nothing yet" scene text (verified in `tools/registry.py`, e.g. `_show_artifact`'s "I do not have a spreadsheet from this session yet"); no distinct empty state for Engineering's bench panels (`UX-4`) | Mixed |
| Error | Yes, but inconsistent specificity (see `02-logic-audit.md` Flow 2 — generic "Gmail did not take it" vs. specific `str(exc)` for calendar) | Source-confirmed |
| Success | Yes — "Sent"/"On the calendar" scenes only render after execution actually completes (confirmed correct, `02-logic-audit.md` Flow 2) | Source-confirmed |
| Partial success | Present in the quote-verify WARN-vs-BLOCKER model (`02-logic-audit.md`, Flow 3) — a genuinely good partial-success UI pattern (proof checklist with per-item pass/fail) | Source-confirmed |
| Offline/failure | Yes — `api_health()`'s `ok` field correctly reflects real brain/Hermes availability (verified live in this sandbox: `curl /api/health` returned `"ok": false` with Hermes/Voicebox/Ollama all correctly reported unavailable); HUD shows "Connection fault. Awaiting instruction." on a failed chat call | Live-verified + source |
| Permission denied | Not independently exercised (would require a real non-local origin request against the auth middleware, `Cross-6` in the cross-domain doc) | Source-only, `Cross-6` |
| Returning-user | Not visually distinguished from first-use in Engineering (`UX-4`); *is* distinguished correctly for the conversation rail (restores focus by `localStorage` id, per `OrchestratorShell.tsx`'s bootstrap effect) | Mixed |

---

## Summary table

| ID | Priority | One-line |
| --- | --- | --- |
| UX-1 | HIGH | First-load setup modal exposes raw `.env` variable names to every new user, in every workspace |
| UX-2 | HIGH | The highest-stakes modal (HITL) has weaker accessibility semantics than the lowest-stakes one (Google connect) |
| UX-3 | MEDIUM | "Blast radius · N/5" is unexplained internal jargon shown on every single Authorize/Reject decision |
| UX-4 | MEDIUM | Engineering workspace's default view doesn't distinguish demo/seed data or first-use from a real in-progress job |
| UX-5 | LOW-MEDIUM | 420px responsive layout genuinely works; one post-dismissal overlap risk not fully verified live |
| UX-6 | LOW-MEDIUM | `y`/`n` Authorize/Reject keyboard shortcuts exist but are never shown on screen |
| UX-7 | N/A (positive) | HITL modal's visual hierarchy and button-weight design is a genuinely strong, disciplined pattern |
| UX-8 | CRITICAL | Engineering bench's Authorize/Reject buttons are permanently non-functional and visually indistinguishable from the real, backend-wired HITL control |
| UX-9 | MEDIUM | A successful result's board can render alongside the literal idle-state placeholder text, reading as a stall when it isn't one |
| UX-10 | LOW-MEDIUM | The same "open thing you can return to" concept is labeled "notes," "desk," "discussion," and "conversation" across adjacent UI |
