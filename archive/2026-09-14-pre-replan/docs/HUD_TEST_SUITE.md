# HUD test suite

Use this on the live HUD at `http://localhost:3000` with the API on port 8000. Type in the command line at the bottom (or wake with **Jarvis** / orb / Space). After each ask, check the **board**, the **whisper** line, and whether **Shall I** appears.

**Safety:** Anything that sends mail, Tasks Gemini, or writes a calendar event asks **Shall I**. Say **no** / **N** unless you actually want it on Gmail or Google Calendar. Drafts and file creates do not send.

Gmail is live (`pgeneration.mech@gmail.com`). Named-mail tests need real people in that inbox (e.g. Muskaan).

---

## How to score a turn

| Check | Pass |
| --- | --- |
| Board | Title and widgets match the ask (mail, schedule, file, briefing) |
| Speak | Short, certain, no Northline/Q3/MSA demo filler |
| Shall I | Only for send / Gemini task / calendar create / unclear “did you want X” |
| Command line | Stays visible; Enter submits what you typed |
| Transcript | Tiny `You : … · Jarvis : …` strip under the whisper |

If Jarvis asks Shall I from a leftover turn, say **no** before the next test.

---

## 1. Morning loop

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 1.1 | `catch me up` | Evening/morning **briefing**: unread, today, next event | No |
| 1.2 | `brief me` | Same briefing board | No |
| 1.3 | `what's on` | Briefing, not a calendar-only board | No |
| 1.4 | `what do I have on the calendar` | **Schedule**, next event spoken (`Next is …, 19:00.`) | No |
| 1.5 | `what is on the calendar` | Schedule only | No |

---

## 2. Mail

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 2.1 | `check mail` or `unread` | Inbox list / recent mail | No |
| 2.2 | `what did Muskaan say` | Her note on the board, spoken summary from **this** mail (not Q3/MSA) | No |
| 2.3 | `Muskaan's quotation` | Same thread / her quote | No |
| 2.4 | `reply` (right after 2.2) | Draft to Muskaan; body thanks/reviews the quote — **no** “trailing mail” paste | **Yes** (send) → say **no** unless you mean it |
| 2.5 | `reply` on a **fresh** session / after reload with no name | `Who is that? Give me a name.` | No |
| 2.6 | `reply to that` after a mail is on the board | Draft to that sender | **Yes** → **no** |
| 2.7 | `what's in that email` after a mail is on the board | Reads that mail | No |

---

## 3. Calendar create (always cancel unless you want it)

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 3.1 | `meeting with Rahul at 4pm` | Event draft titled around **Rahul**, ~16:00, 30 min | **Yes** → **no** |
| 3.2 | `lunch with Rahul tomorrow` | Draft tomorrow ~09:00, title lunch/Rahul | **Yes** → **no** |
| 3.3 | `block 7 for a call with Rahul for an hour` | ~19:00 today (or next day if already past), **1 hour**, title call/Rahul | **Yes** → **no** |
| 3.4 | `put a call with Rahul at 7 on the calendar` | Same idea as 3.3, 30 min default if you omit duration | **Yes** → **no** |
| 3.5 | `what is on the calendar` after cancelling | Still **list**, not another create | No |

Spoken confirmations that **do** mean Yes: `yes`, `yeah`, `go ahead`, `go for it`, `do it`, `send it`, `ship it`.

Spoken that **must not** mean Yes: `please`, `ok`, `okay`, `sure`, `that's fine`.

Spoken No: `no`, `nope`, `cancel`, `not now`, `hold off`, `leave it`, `N`.

---

## 4. Sheets, docs, Drive

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 4.1 | `make me an excel of blockers` | **Blockers** workbook, empty rows, whisper `Blockers is on the board.` | No |
| 4.2 | `make a pricing sheet` | **Pricing** columns Item/Amount/Notes, empty rows — not MSA demo rows | No |
| 4.3 | `open the other spreadsheet` | Previous sheet from this session (stack of last 3) | No |
| 4.4 | `write meeting notes` | Word doc, no MSA bullet list | No |
| 4.5 | `find the pricing sheet on drive` | Existing Drive file on the board (URL). Must **not** upload a duplicate | No |
| 4.6 | `put it on drive` after a local sheet exists | Uploads or reuses the Drive copy | No |
| 4.7 | `share it with Rahul` | Must **not** upload to Drive | No |

---

## 5. Gemini (cancel Shall I)

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 5.1 | `tell Gemini to extract the totals from the pricing sheet` | Task for Gemini, File line is a `https://docs.google.com/…` (or Drive) link, steps keep **extract** and **and** | **Yes** → **no** |
| 5.2 | `ask Gemini to take the pricing sheet and extract the totals` | Same: not a new blank spreadsheet | **Yes** → **no** |
| 5.3 | `please` while Shall I is up | Must **not** send. Jarvis should keep waiting or treat it as chat | — |

---

## 6. Multi-step and presence

| # | Say / type | Expect |
| --- | --- | --- |
| 6.1 | `brief me and make a spreadsheet of blockers` | Briefing first, then ~a beat later Blockers on the board |
| 6.2 | Type `catch me up` and press **Enter** | Command line stays; board updates; transcript shows `You : catch me up` |
| 6.3 | Click the orb, stay silent ~12s | Whisper: **I didn't catch that.** |
| 6.4 | Reload the HUD | Last board comes back **without** re-narrating the last email |

---

## 7. Misses and confidence

| # | Say / type | Expect |
| --- | --- | --- |
| 7.1 | `what's in` (nothing else) | `Mail, the calendar, or a file — which one?` — not silence |
| 7.2 | `open in excel` with no sheet this session | Asks to make one, or says he does not have it yet |
| 7.3 | Random work-ish ask he cannot do | `I don't handle that yet. Mail, calendar, a file, or Gemini.` |

Speech should stay short: `Draft for Muskaan is ready — shall I send it?` / `Blockers is on the board.` / `Next is talk with rahul sir, 19:00.` No “The blockers is…”.

---

## 8. Yes / No while Shall I is showing

Set up with `meeting with Rahul at 4pm`, then:

| Say | Expect |
| --- | --- |
| `yes` / `Y` | Would write the live calendar — use only if you want that |
| `no` / `N` | `Cancelled.` Event not created |
| `ok` / `sure` / `please` | Must **not** create the event |

---

## Suggested 10-minute pass

Do these in order, **no** on every Shall I:

1. `catch me up`
2. `what did Muskaan say`
3. `reply` → **no**
4. `meeting with Rahul at 4pm` → **no**
5. `make me an excel of blockers`
6. `find the pricing sheet on drive`
7. `tell Gemini to extract the totals from the pricing sheet` → **no**
8. `brief me and make a spreadsheet of blockers`
9. Stay silent on the orb for 12s
10. Reload the page — board restores, no replay of mail

If any step dumps Northline/Q3/MSA, treats `please` as Yes, creates a sheet instead of a Gemini task, or uploads a second Pricing file, that step failed.

---

## 9. Research

| # | Say / type | Expect | Shall I? |
| --- | --- | --- | --- |
| 9.1 | `look up aluminium prices in India` or `search the current aluminium prices in India` | Board titled around the topic. Jarvis **speaks a briefing in his own words** (no domain dumps, no Engine/DDG). **What I gathered** comments per outlet. **Pages** are just names + links. | No |
